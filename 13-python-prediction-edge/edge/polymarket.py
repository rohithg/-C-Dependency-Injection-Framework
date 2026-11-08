"""Public Polymarket reads. No key, no orders.

Gamma describes the market. The CLOB book is the only price used for a decision.
"""

from __future__ import annotations

import json
import time

import requests

from .models import BinaryMarket, Book, Level
from .money import ZERO, D

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


class PolymarketPublic:
    def __init__(self, timeout: float = 20.0, pause: float = 0.05):
        self.timeout = timeout
        self.pause = pause
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "prediction-edge/0.1"

    def active_binaries(self, limit: int) -> list[BinaryMarket]:
        events = self._get(f"{GAMMA}/events", {
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
            "limit": str(limit),
        }) or []
        if isinstance(events, dict):
            events = events.get("events") or events.get("data") or []
        specs = []
        for event in events:
            if event.get("closed"):
                continue
            for raw in event.get("markets") or []:
                spec = parse_market_spec(raw)
                if spec is not None:
                    spec["event_id"] = str(event.get("id") or "")
                    specs.append(spec)
        books = self.books([token for spec in specs for token in (spec["yes_token"], spec["no_token"])])
        now_ms = int(time.time() * 1000)
        markets = []
        for spec in specs:
            yes = books.get(spec["yes_token"])
            no = books.get(spec["no_token"])
            if not yes or not no:
                continue
            markets.append(spec_to_market(spec, yes, no, now_ms))
        return markets

    def by_condition(self, condition_id: str) -> BinaryMarket | None:
        rows = self._get(f"{GAMMA}/markets", {"condition_ids": condition_id, "limit": "5"}) or []
        if isinstance(rows, dict):
            rows = rows.get("markets") or rows.get("data") or []
        for raw in rows:
            spec = parse_market_spec(raw)
            if spec is None or spec["market_id"] != condition_id:
                continue
            books = self.books([spec["yes_token"], spec["no_token"]])
            yes, no = books.get(spec["yes_token"]), books.get(spec["no_token"])
            if not yes or not no:
                return None
            return spec_to_market(spec, yes, no, int(time.time() * 1000))
        return None

    def books(self, token_ids: list[str]) -> dict[str, dict]:
        found: dict[str, dict] = {}
        ids = list(dict.fromkeys(token_ids))
        for start in range(0, len(ids), 40):
            chunk = ids[start:start + 40]
            rows = self._post(f"{CLOB}/books", [{"token_id": token} for token in chunk]) or []
            for row in rows:
                asset = str(row.get("asset_id") or "")
                if asset:
                    found[asset] = row
        return found

    def _get(self, url: str, params: dict):
        time.sleep(self.pause)
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, url: str, body):
        time.sleep(self.pause)
        response = self.session.post(url, json=body, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


def parse_market_spec(raw: dict) -> dict | None:
    if raw.get("closed") or raw.get("acceptingOrders") is False or raw.get("enableOrderBook") is False:
        return None
    outcomes = _json_list(raw.get("outcomes"))
    if [str(x).lower() for x in outcomes] != ["yes", "no"]:
        return None
    version = str(raw.get("version") or "v1")
    if version == "v2" and _json_list(raw.get("positionIds")):
        tokens = [str(x) for x in _json_list(raw.get("positionIds"))]
    else:
        tokens = [str(x) for x in _json_list(raw.get("clobTokenIds"))]
    if len(tokens) != 2:
        return None
    schedule = raw.get("feeSchedule") or {}
    rate = D(schedule.get("rate") or 0) if raw.get("feesEnabled") else ZERO
    return {
        "market_id": str(raw.get("conditionId") or raw.get("id")),
        "title": raw.get("question") or raw.get("slug") or "polymarket",
        "yes_token": tokens[0],
        "no_token": tokens[1],
        "tick": D(raw.get("orderPriceMinTickSize") or "0.01"),
        "min_size": D(raw.get("orderMinSize") or "1"),
        "fee_rate": rate,
        "fee_exponent": D(schedule.get("exponent") or 1),
        "taker_only": bool(schedule.get("takerOnly", True)),
        "event_id": "",
    }


def spec_to_market(spec: dict, yes_book: dict, no_book: dict, now_ms: int) -> BinaryMarket:
    return BinaryMarket(
        "polymarket",
        spec["market_id"],
        spec["title"],
        _book(spec, "yes", spec["yes_token"], yes_book, now_ms),
        _book(spec, "no", spec["no_token"], no_book, now_ms),
        spec.get("event_id", ""),
    )


def _book(spec: dict, outcome: str, token: str, payload: dict, now_ms: int) -> Book:
    ts = int(payload.get("timestamp") or now_ms)
    return Book(
        venue="polymarket",
        market_id=spec["market_id"],
        token_id=token,
        outcome=outcome,
        bids=_levels(payload.get("bids")),
        asks=_levels(payload.get("asks")),
        tick=spec["tick"],
        min_size=spec["min_size"],
        fee_model="polymarket",
        fee_rate=spec["fee_rate"],
        fee_exponent=spec["fee_exponent"],
        taker_only=spec["taker_only"],
        ts_ms=ts,
        title=spec["title"],
    )


def _levels(rows) -> list[Level]:
    levels = []
    for row in rows or []:
        price = D(row.get("price"))
        size = D(row.get("size"))
        if size > 0 and ZERO < price < 1:
            levels.append(Level(price, size))
    return levels


def _json_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []
