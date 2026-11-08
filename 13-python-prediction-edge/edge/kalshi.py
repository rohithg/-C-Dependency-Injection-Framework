"""Public Kalshi reads, plus the request signature used by live orders.

A single Kalshi binary has no complete-set edge: the NO ask is one minus the
YES bid, so the two sides are the same book. The edge is across strikes.
`mutually_exclusive` is not used. On Kalshi it means at most one market
resolves YES, which is not the same as exactly one.
"""

from __future__ import annotations

import time

import requests

from .fees import KALSHI_MAKER, KALSHI_TAKER
from .models import BinaryMarket, Book, Ladder, Level, StrikeMarket
from .money import ONE, ZERO, D
from .replay import complement_no

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ORDER_PATH = "/trade-api/v2/portfolio/events/orders"
_LADDER_KINDS = ("greater", "greater_or_equal", "less", "less_or_equal")


class KalshiPublic:
    def __init__(self, base: str = BASE, timeout: float = 20.0, pause: float = 0.05):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.pause = pause
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "prediction-edge/0.1"

    def ladders(self, series: tuple[str, ...], per_series: int) -> list[Ladder]:
        found = []
        for name in series:
            payload = self._get("/events", {
                "series_ticker": name,
                "status": "open",
                "limit": str(per_series),
                "with_nested_markets": "true",
            })
            now_ms = int(time.time() * 1000)
            for event in payload.get("events") or []:
                ladder = parse_event_ladder(event)
                if ladder is None:
                    continue
                for strike in ladder.strikes:
                    strike.market.yes.ts_ms = now_ms
                    strike.market.no.ts_ms = now_ms
                found.append(ladder)
        return found

    def by_ticker(self, ticker: str) -> BinaryMarket | None:
        payload = self._get(f"/markets/{ticker}", {})
        raw = payload.get("market") or payload
        market = parse_market(raw)
        if market is None:
            return None
        now_ms = int(time.time() * 1000)
        market.yes.ts_ms = now_ms
        market.no.ts_ms = now_ms
        return market

    def _get(self, path: str, params: dict):
        time.sleep(self.pause)
        response = self.session.get(self.base + path, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


def parse_event_ladder(event: dict) -> Ladder | None:
    grouped: dict[str, list[StrikeMarket]] = {}
    for raw in event.get("markets") or []:
        if raw.get("status") not in (None, "active"):
            continue
        kind = raw.get("strike_type")
        if kind not in _LADDER_KINDS:
            continue
        strike = raw.get("floor_strike") if str(kind).startswith("greater") else raw.get("cap_strike")
        if strike is None:
            continue
        market = parse_market(raw)
        if market is None:
            continue
        grouped.setdefault(kind, []).append(StrikeMarket(market, strike, kind))
    if len(grouped) != 1:
        return None
    kind, strikes = next(iter(grouped.items()))
    if len(strikes) < 2:
        return None
    return Ladder(
        "kalshi",
        str(event.get("event_ticker") or ""),
        event.get("title") or str(event.get("event_ticker") or "kalshi"),
        kind,
        strikes,
    )


def parse_market(raw: dict) -> BinaryMarket | None:
    yes_bid = _level(raw.get("yes_bid_dollars"), raw.get("yes_bid_size_fp"))
    yes_ask = _level(raw.get("yes_ask_dollars"), raw.get("yes_ask_size_fp"))
    if yes_bid is not None and raw.get("no_ask_dollars") not in (None, ""):
        reported = D(raw.get("no_ask_dollars"))
        if abs(reported - (ONE - yes_bid.price)) > D("0.00015"):
            return None
    no_bids, no_asks = complement_no(
        yes_bid.price if yes_bid else None,
        yes_bid.size if yes_bid else ZERO,
        yes_ask.price if yes_ask else None,
        yes_ask.size if yes_ask else ZERO,
    )
    ticker = str(raw.get("ticker") or "")
    title = raw.get("yes_sub_title") or raw.get("title") or ticker
    tick = _tick(raw)
    yes = _book(ticker, ticker + ":yes", "yes", [yes_bid] if yes_bid else [], [yes_ask] if yes_ask else [], title, tick)
    no = _book(ticker, ticker + ":no", "no", no_bids, no_asks, title, tick)
    return BinaryMarket("kalshi", ticker, str(title), yes, no, str(raw.get("event_ticker") or ""))


def sign_request(private_key, timestamp: str, method: str, path: str) -> str:
    """Kalshi v2 signature. `path` is the URL path from the root, without the query."""
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    message = f"{timestamp}{method}{path.split('?')[0]}".encode()
    if isinstance(private_key, Ed25519PrivateKey):
        signature = private_key.sign(message)
    else:
        signature = private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
    return base64.b64encode(signature).decode()


def kalshi_order(leg, client_order_id: str) -> dict:
    """Translate a buy of YES or NO into the single-book V2 order."""
    if leg.side != "buy":
        raise ValueError("live Kalshi orders are buys")
    if leg.outcome == "yes":
        side, price = "bid", D(leg.price)
    elif leg.outcome == "no":
        side, price = "ask", ONE - D(leg.price)
    else:
        raise ValueError(f"unknown outcome {leg.outcome}")
    if price <= 0 or price >= 1:
        raise ValueError("order price is off the board")
    return {
        "ticker": leg.market_id,
        "side": side,
        "count": format(D(leg.size).quantize(D("0.01")), "f"),
        "price": format(price.quantize(D("0.0001")), "f"),
        "time_in_force": "immediate_or_cancel",
        "self_trade_prevention_type": "taker_at_cross",
        "post_only": False,
        "client_order_id": client_order_id,
    }


def _book(market_id, token_id, outcome, bids, asks, title, tick) -> Book:
    return Book(
        venue="kalshi",
        market_id=market_id,
        token_id=token_id,
        outcome=outcome,
        bids=[level for level in bids if level is not None],
        asks=[level for level in asks if level is not None],
        tick=tick,
        min_size=D("1"),
        fee_model="kalshi",
        fee_rate=KALSHI_TAKER,
        fee_exponent=1,
        fee_multiplier=1,
        maker_rate=KALSHI_MAKER,
        taker_only=False,
        ts_ms=0,
        title=title,
    )


def _level(price, size) -> Level | None:
    if price in (None, "") or size in (None, ""):
        return None
    level = Level(price, size)
    if level.size <= 0 or level.price <= 0 or level.price >= 1:
        return None
    return level


def _tick(raw: dict):
    for row in raw.get("price_ranges") or []:
        step = row.get("step") or row.get("tick") or row.get("tick_size")
        if step:
            return D(step)
    return D("0.01")
