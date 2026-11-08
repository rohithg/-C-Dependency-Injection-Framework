"""Live order submission.

Live mode lifts two taker packages only: a Polymarket YES+NO set, and a
Kalshi strike ladder. It does not rest maker quotes. A quote that sits for
the whole polling interval can be picked off on one side, and this process
has no fill websocket to pull it. Maker quotes stay on the paper account.

A live run does nothing unless three gates are all open: the command flag,
`live_enabled` in the config, and the environment phrase. Basis hedges stay
off unless `live_basis` is also set, because the two rulebooks can disagree.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal

from .kalshi import ORDER_PATH, kalshi_order, sign_request
from .models import Leg
from .money import ONE, ZERO, D

LIVE_PHRASE = "I_UNDERSTAND_THIS_CAN_LOSE_MONEY"
_LIVE_KINDS = {"complete_set_buy", "ladder"}


@dataclass
class Fill:
    size: Decimal
    price: Decimal
    fee: Decimal


def gate(config, flagged: bool) -> str | None:
    """None when live trading is allowed. Otherwise the reason it is not."""
    if not flagged:
        return "live trading stays off without --live"
    if not config.live_enabled:
        return "live_enabled is false in the config"
    if os.environ.get("EDGE_LIVE_OK") != LIVE_PHRASE:
        return f"set EDGE_LIVE_OK to {LIVE_PHRASE}"
    return None


def execute(opportunities, broker, account, binaries, books, config) -> list[str]:
    notes = []
    for opp in opportunities:
        if opp.kind not in _LIVE_KINDS and not (opp.kind == "basis" and config.live_basis):
            continue
        if opp.kind == "basis" and not config.live_basis:
            continue
        if any(not broker.supports(leg) for leg in opp.legs):
            notes.append(f"skip {opp.title}: that venue is not configured")
            continue
        fills: list[Fill] = []
        broken = False
        for leg in opp.legs:
            try:
                fill = broker.submit(leg)
            except Exception as exc:
                broken = True
                notes.append(f"{opp.title}: order failed ({exc})")
                break
            if fill.size <= 0:
                broken = True
                notes.append(f"{opp.title}: {leg.outcome} was not filled")
                break
            account._buy(leg.venue, leg.market_id, leg.token_id, leg.outcome, leg.title, fill.size, fill.price, fill.fee)
            fills.append(fill)
            if fill.size + Decimal("0.01") < leg.size:
                broken = True
                notes.append(f"{opp.title}: partial fill {fill.size} of {leg.size}")
                break
        if broken:
            notes.extend(account.repair(binaries, books, config, force=True))
            if _leftover(account, opp):
                account.halted = True
                notes.append(f"HALTED on {opp.title}: a leg is still open")
                break
            notes.append(f"{opp.title}: broken leg was completed inside the loss cap")
            continue
        _close(account, opp, fills, config)
        notes.append(f"live {opp.kind} {opp.title} {opp.size}")
    account._refresh()
    return notes


class VenueBroker:
    """Routes a leg to whichever venue client is actually configured."""

    def __init__(self, polymarket=None, kalshi=None):
        self.polymarket = polymarket
        self.kalshi = kalshi

    def supports(self, leg: Leg) -> bool:
        return self._client(leg) is not None

    def submit(self, leg: Leg) -> Fill:
        client = self._client(leg)
        if client is None:
            raise RuntimeError(f"{leg.venue} is not configured")
        return client.submit(leg)

    def _client(self, leg: Leg):
        if leg.venue == "polymarket":
            return self.polymarket
        if leg.venue == "kalshi":
            return self.kalshi
        return None


class KalshiBroker:
    def __init__(self, key_id: str, private_key, session, base: str):
        self.key_id = key_id
        self.private_key = private_key
        self.session = session
        self.base = base.rstrip("/")

    def submit(self, leg: Leg) -> Fill:
        payload = kalshi_order(leg, str(uuid.uuid4()))
        headers = _kalshi_headers(self.private_key, self.key_id, "POST", ORDER_PATH)
        response = self.session.post(self.base + "/portfolio/events/orders", json=payload, headers=headers, timeout=15)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"kalshi {response.status_code}: {response.text[:180]}")
        return _kalshi_fill(response.json(), leg)


class PolymarketBroker:
    """Taker buys through py-clob-client. Imported only when a live order is sent."""

    def __init__(self, private_key: str, host: str = "https://clob.polymarket.com"):
        self.private_key = private_key
        self.host = host
        self._client = None

    def submit(self, leg: Leg) -> Fill:
        if leg.side != "buy":
            raise RuntimeError("live Polymarket mode does not mint, so it cannot sell a complete set")
        client = self.client()
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY

        signed = client.create_order(OrderArgs(
            price=float(leg.price), size=float(leg.size), side=BUY, token_id=leg.token_id,
        ))
        order_type = getattr(OrderType, "FAK", None) or OrderType.IOC
        response = client.post_order(signed, order_type)
        return _polymarket_fill(response, leg)

    def client(self):
        if self._client is None:
            from py_clob_client.client import ClobClient

            client = ClobClient(self.host, key=self.private_key, chain_id=137)
            client.set_api_creds(client.create_or_derive_api_creds())
            self._client = client
        return self._client


def broker_from_env(session=None):
    import requests as http

    session = session or http.Session()
    kalshi = None
    key_id = os.environ.get("KALSHI_API_KEY_ID", "")
    key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if key_id and key_path:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        private = load_pem_private_key(open(key_path, "rb").read(), password=None)
        base = os.environ.get("KALSHI_BASE_URL", "https://external-api.kalshi.com/trade-api/v2")
        kalshi = KalshiBroker(key_id, private, session, base)
    polymarket = None
    poly_key = os.environ.get("POLY_PRIVATE_KEY", "")
    if poly_key:
        polymarket = PolymarketBroker(poly_key)
    return VenueBroker(polymarket, kalshi)


def _kalshi_headers(private_key, key_id: str, method: str, path: str) -> dict:
    timestamp = str(int(time.time() * 1000))
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": sign_request(private_key, timestamp, method, path),
        "Content-Type": "application/json",
    }


def _kalshi_fill(body: dict, leg: Leg) -> Fill:
    size = D(body.get("fill_count") or 0)
    raw_price = body.get("average_fill_price")
    price = D(raw_price) if raw_price not in (None, "") else D(leg.price)
    if leg.outcome == "no" and raw_price not in (None, ""):
        price = ONE - price
    avg_fee = body.get("average_fee_paid")
    fee = D(avg_fee) * size if avg_fee not in (None, "") else _scaled_fee(leg, size)
    return Fill(size, price, fee)


def _polymarket_fill(response, leg: Leg) -> Fill:
    if not isinstance(response, dict):
        raise RuntimeError(f"unexpected polymarket response: {response!r}"[:200])
    taking = response.get("takingAmount") or response.get("size") or response.get("filled")
    if taking in (None, ""):
        raise RuntimeError(f"polymarket response has no fill size: {response!r}"[:200])
    size = D(taking)
    price = D(response.get("price") or leg.price)
    return Fill(size, price, _scaled_fee(leg, size))


def _scaled_fee(leg: Leg, size) -> Decimal:
    if leg.size <= 0:
        return ZERO
    return (D(leg.fee) * D(size) / D(leg.size)).quantize(D("0.0001"))


def _close(account, opp, fills: list[Fill], config) -> None:
    size = min(fill.size for fill in fills)
    if opp.kind == "complete_set_buy":
        account._merge(opp.legs[0].token_id, opp.legs[1].token_id, size, config.merge_gas_usd)
        return
    if size != opp.size:
        raise RuntimeError("refusing to lock a ladder at a size other than the planned size")
    account._lock(opp)


def _leftover(account, opp) -> bool:
    return any(getattr(account.lots.get(leg.token_id), "qty", ZERO) > 0 for leg in opp.legs)
