"""Load a recorded snapshot and play it through the paper account."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import Config
from .models import BasisLink, BinaryMarket, Book, Ladder, Level, StrikeMarket
from .money import ONE
from .paper import Account, run_cycle


def load_document(path: Path) -> tuple[Config, list[dict]]:
    raw = json.loads(path.read_text())
    return Config(**raw.get("config", {})), list(raw["steps"])


def run_document(path: Path, account: Account | None = None):
    config, steps = load_document(path)
    account = account or Account(config.bankroll)
    results = []
    for i, step in enumerate(steps):
        binaries, ladders, links = snapshot_from_step(step)
        now = datetime.fromisoformat(step["time"]) if step.get("time") else datetime(2026, 11, 8, 12, 0, i)
        results.append(run_cycle(account, binaries, ladders, links, config, now, int(step.get("now_ms") or 0)))
    return account, results, config


def snapshot_from_step(step: dict):
    binaries = [binary_from_dict(raw) for raw in step.get("markets") or []]
    ladders = [ladder_from_dict(raw) for raw in step.get("ladders") or []]
    links = []
    for raw in step.get("links") or []:
        links.append(BasisLink(
            raw["name"], binary_from_dict(raw["left"]), binary_from_dict(raw["right"]), bool(raw.get("same_yes", True)),
        ))
    return binaries, ladders, links


def binary_from_dict(raw: dict) -> BinaryMarket:
    fee = raw.get("fee_model", "polymarket")
    rate = raw.get("fee_rate", "0")
    exponent = raw.get("fee_exponent", "1")
    multiplier = raw.get("fee_multiplier", "1")
    maker = raw.get("maker_rate", "0")
    taker_only = bool(raw.get("taker_only", True))
    tick = raw.get("tick", "0.01")
    min_size = raw.get("min_size", "1")
    title = raw.get("title", raw["market_id"])
    ts = int(raw.get("ts_ms") or 0)
    return BinaryMarket(
        raw.get("venue", "polymarket"),
        raw["market_id"],
        title,
        _book(raw, "yes", fee, rate, exponent, multiplier, maker, taker_only, tick, min_size, title, ts),
        _book(raw, "no", fee, rate, exponent, multiplier, maker, taker_only, tick, min_size, title, ts),
        raw.get("event_id", ""),
    )


def ladder_from_dict(raw: dict) -> Ladder:
    strikes = []
    for row in raw["strikes"]:
        market = binary_from_dict(row["market"])
        strikes.append(StrikeMarket(market, row["strike"], raw["kind"]))
    return Ladder(raw.get("venue", "kalshi"), raw["event_id"], raw.get("title", raw["event_id"]), raw["kind"], strikes)


def _book(raw, outcome, fee, rate, exponent, multiplier, maker, taker_only, tick, min_size, title, ts) -> Book:
    side = raw[outcome]
    return Book(
        venue=raw.get("venue", "polymarket"),
        market_id=raw["market_id"],
        token_id=side["token_id"],
        outcome=outcome,
        bids=[Level(p, s) for p, s in side.get("bids") or []],
        asks=[Level(p, s) for p, s in side.get("asks") or []],
        tick=tick,
        min_size=min_size,
        fee_model=fee,
        fee_rate=rate,
        fee_exponent=exponent,
        fee_multiplier=multiplier,
        maker_rate=maker,
        taker_only=taker_only,
        ts_ms=ts,
        title=title,
    )


def complement_no(yes_bid, yes_bid_size, yes_ask, yes_ask_size):
    """Kalshi NO top of book implied by the YES top. Exposed for the live parser and tests."""
    no_bids = []
    no_asks = []
    if yes_ask is not None and yes_ask_size and yes_ask_size > 0 and 0 < yes_ask < 1:
        no_bids.append(Level(ONE - yes_ask, yes_ask_size))
    if yes_bid is not None and yes_bid_size and yes_bid_size > 0 and 0 < yes_bid < 1:
        no_asks.append(Level(ONE - yes_bid, yes_bid_size))
    return no_bids, no_asks
