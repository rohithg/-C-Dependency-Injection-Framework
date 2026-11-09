"""One week of Polymarket 15-minute crypto, scored at the last minute.

The sample stops at seven days. A longer history is not used. At the start of
the final minute the latest trade print is the price, the settlement model
prices the side, and the crypto taker fee comes off. A cycle is a trade only
when that net edge is from 2 to 3 cents. One contract, held to the result.
"""

from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from edge.crypto15m import EDGE_HIGH_CENTS, EDGE_LOW_CENTS, settlement_up_prob, sigma_1m
from edge.fees import polymarket_taker_fee

ASSETS = (("BTC", "btc", "BTC-USD"), ("ETH", "eth", "ETH-USD"), ("SOL", "sol", "SOL-USD"))
WEEK_S = 7 * 24 * 60 * 60
WINDOW_S = 900
DECISION_OFFSET = 14 * 60
MAX_PRINT_AGE = 60
FEE_RATE = Decimal("0.07")
_GAMMA = "https://gamma-api.polymarket.com/events"
_HISTORY = "https://clob.polymarket.com/prices-history"
_COINBASE = "https://api.exchange.coinbase.com/products"


def poly_fee(price: float, rate: Decimal = FEE_RATE) -> float:
    return float(polymarket_taker_fee(Decimal("1"), Decimal(str(price)), rate))


def print_at(history: list[dict], decision_ts: int, max_age: int = MAX_PRINT_AGE) -> float | None:
    """Latest trade at or before the decision, if it is fresh enough to use."""
    prior = [row for row in history if int(row["t"]) <= decision_ts]
    if not prior:
        return None
    last = max(prior, key=lambda row: int(row["t"]))
    if decision_ts - int(last["t"]) > max_age:
        return None
    price = float(last["p"])
    if not 0.0 < price < 1.0:
        return None
    return price


def score_side(chance: float, price: float, rate: Decimal = FEE_RATE) -> tuple[float, float] | None:
    """Fee-adjusted edge in cents, and the fee in dollars. None when the price is unusable."""
    if not 0.01 < price < 0.99:
        return None
    fee = poly_fee(price, rate)
    return chance * 100.0 - price * 100.0 - fee * 100.0, fee


def score_window(
    *,
    spot: float,
    strike: float,
    closes: list[float],
    up_px: float | None,
    down_px: float | None,
    up_won: bool,
    rate: Decimal = FEE_RATE,
) -> dict | None:
    """One window. The taken side is the larger edge, and only inside 2 to 3 cents."""
    sigma = sigma_1m(closes)
    prob = settlement_up_prob(spot, strike, sigma, 1.0) if sigma else None
    if prob is None or sigma is None:
        return None
    scored: list[tuple[float, str, float, float]] = []
    up = score_side(prob, up_px, rate) if up_px is not None else None
    down = score_side(1.0 - prob, down_px, rate) if down_px is not None else None
    if up is not None and up_px is not None:
        scored.append((up[0], "up", up_px, up[1]))
    if down is not None and down_px is not None:
        scored.append((down[0], "down", down_px, down[1]))
    if not scored:
        return None
    edge, side, price, fee = max(scored, key=lambda row: row[0])
    won = up_won if side == "up" else not up_won
    pnl = (1.0 if won else 0.0) - price - fee
    return {
        "side": side,
        "price": round(price, 4),
        "edge_cents": round(edge, 2),
        "fee": round(fee, 5),
        "up_prob": round(prob, 4),
        "sigma": sigma,
        "take": EDGE_LOW_CENTS <= edge <= EDGE_HIGH_CENTS,
        "won": won,
        "pnl": round(pnl, 5),
    }


def _get_json(url: str, attempts: int = 4):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    last = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except Exception as exc:  # noqa: BLE001 — retry the public feeds, then give up
            last = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(str(last))


def load_candles(product: str, start: int, end: int) -> dict[int, tuple[float, float]]:
    """Coinbase 1-minute open and close, including a half hour before the week."""
    candles: dict[int, tuple[float, float]] = {}
    cursor = start - 40 * 60
    while cursor < end:
        chunk = min(end + 60, cursor + 300 * 60)
        url = f"{_COINBASE}/{product}/candles?granularity=60&start={cursor}&end={chunk}"
        rows = _get_json(url)
        for row in rows:
            candles[int(row[0])] = (float(row[3]), float(row[4]))
        cursor = chunk
        time.sleep(0.05)
    return candles


def _resolved_up(market: dict) -> bool | None:
    raw = market.get("outcomePrices")
    try:
        prices = json.loads(raw) if isinstance(raw, str) else raw
        up = float(prices[0])
        down = float(prices[1])
    except (TypeError, ValueError, IndexError, json.JSONDecodeError):
        return None
    if up >= 0.99 and down <= 0.01:
        return True
    if down >= 0.99 and up <= 0.01:
        return False
    return None


def _history(token_id: str, start: int) -> list[dict]:
    url = f"{_HISTORY}?market={token_id}&startTs={start}&endTs={start + WINDOW_S}&fidelity=1"
    payload = _get_json(url)
    return payload.get("history") or []


def scan_window(asset: str, slug: str, start: int, candles: dict[int, tuple[float, float]]) -> dict:
    decision_ts = start + DECISION_OFFSET
    opened = candles.get(start)
    spot_candle = candles.get(decision_ts - 60)
    if opened is None or spot_candle is None:
        return {"asset": asset, "start": start, "status": "no_spot"}
    strike, _ = opened
    _, spot = spot_candle
    times = sorted(t for t in candles if t <= decision_ts - 60)
    closes = [candles[t][1] for t in times[-31:]]
    try:
        events = _get_json(f"{_GAMMA}?slug={slug}-updown-15m-{start}")
    except Exception as exc:  # noqa: BLE001
        return {"asset": asset, "start": start, "status": "book_error", "error": type(exc).__name__}
    if not events:
        return {"asset": asset, "start": start, "status": "no_market"}
    market = (events[0].get("markets") or [None])[0]
    if not market:
        return {"asset": asset, "start": start, "status": "no_market"}
    up_won = _resolved_up(market)
    if up_won is None:
        return {"asset": asset, "start": start, "status": "unresolved"}
    try:
        tokens = json.loads(market.get("clobTokenIds") or "[]")
        outcomes = json.loads(market.get("outcomes") or "[]")
    except json.JSONDecodeError:
        return {"asset": asset, "start": start, "status": "book_error"}
    if len(tokens) != 2 or [str(name).lower() for name in outcomes] != ["up", "down"]:
        return {"asset": asset, "start": start, "status": "book_error"}
    try:
        up_px = print_at(_history(tokens[0], start), decision_ts)
        down_px = print_at(_history(tokens[1], start), decision_ts)
    except Exception as exc:  # noqa: BLE001
        return {"asset": asset, "start": start, "status": "book_error", "error": type(exc).__name__}
    if up_px is None and down_px is None:
        return {"asset": asset, "start": start, "status": "no_print"}
    schedule = market.get("feeSchedule") or {}
    rate = Decimal(str(schedule.get("rate") or FEE_RATE))
    scored = score_window(
        spot=spot, strike=strike, closes=closes, up_px=up_px, down_px=down_px, up_won=up_won, rate=rate,
    )
    if scored is None:
        return {"asset": asset, "start": start, "status": "no_score"}
    scored.update({
        "asset": asset,
        "start": start,
        "status": "scored",
        "spot": round(spot, 4),
        "strike": round(strike, 4),
        "up_px": None if up_px is None else round(up_px, 4),
        "down_px": None if down_px is None else round(down_px, 4),
        "up_won": up_won,
    })
    return scored


def summarize(rows: list[dict], start: int, end: int) -> dict:
    scored = [row for row in rows if row.get("status") == "scored"]
    taken = [row for row in scored if row.get("take")]
    skips: dict[str, int] = {}
    for row in rows:
        if row.get("status") != "scored":
            skips[row["status"]] = skips.get(row["status"], 0) + 1

    def pack(trades: list[dict]) -> dict:
        by_asset = {}
        for asset, _, _ in ASSETS:
            group = [row for row in trades if row["asset"] == asset]
            by_asset[asset] = {
                "trades": len(group),
                "wins": sum(1 for row in group if row["won"]),
                "pnl": round(sum(row["pnl"] for row in group), 5),
            }
        return {
            "trades": len(trades),
            "wins": sum(1 for row in trades if row["won"]),
            "losses": sum(1 for row in trades if not row["won"]),
            "pnl_1_contract": round(sum(row["pnl"] for row in trades), 5),
            "by_asset": by_asset,
        }

    return {
        "sampled_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week_start_utc": datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week_end_utc": datetime.fromtimestamp(end, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "windows": len(rows),
        "scored": len(scored),
        "skips": skips,
        "books": "Polymarket 15-minute Up/Down. Entry is the last trade print at or before the final minute, within 60 seconds.",
        "spot": "Coinbase 1-minute open at the window start, and the close at the start of the final minute.",
        "rule": "Buy one contract when the settlement model's fee-adjusted edge on that print is from 2 to 3 cents. Hold to the window result.",
        "fee": "Polymarket crypto taker fee, 0.07 times price times one minus price, half-up to 0.00001.",
        "rule_2_to_3c": pack(taken),
        "trades": [
            {
                "asset": row["asset"],
                "start": row["start"],
                "side": row["side"],
                "price": row["price"],
                "edge_cents": row["edge_cents"],
                "fee": row["fee"],
                "won": row["won"],
                "pnl": row["pnl"],
            }
            for row in taken
        ],
    }


def collect(start: int, end: int, workers: int = 8) -> dict:
    candles = {product: load_candles(product, start, end) for _, _, product in ASSETS}
    jobs = []
    for asset, slug, product in ASSETS:
        window = start
        while window < end:
            jobs.append((asset, slug, window, candles[product]))
            window += WINDOW_S
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(scan_window, *job) for job in jobs]
        for done, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            if done % 100 == 0:
                print(f"scanned {done}/{len(jobs)}", flush=True)
    rows.sort(key=lambda row: (row["start"], row["asset"]))
    return summarize(rows, start, end)


def main() -> None:
    now = int(time.time())
    end = (now // WINDOW_S) * WINDOW_S - WINDOW_S
    start = end - WEEK_S
    report = collect(start, end)
    out = Path(__file__).resolve().parents[1] / "paper" / "15m-week-poly.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    rule = report["rule_2_to_3c"]
    print(json.dumps({"windows": report["windows"], "scored": report["scored"], "skips": report["skips"], "rule": rule}, indent=2))
    print(out)


if __name__ == "__main__":
    main()
