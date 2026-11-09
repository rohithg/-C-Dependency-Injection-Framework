"""Did the full-outcome basket pay on markets that have already resolved?

The entry is fixed before the result is known. One share of every YES is
bought at the last trade print, plus the taker fee. The trade is taken only
when that cost is under $1. A negative-risk event is supposed to pay $1 in
total. The backtest counts whatever actually resolved, so a second winner or
a void is not assumed away.
"""

from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal

from edge.fees import polymarket_taker_fee

_GAMMA = "https://gamma-api.polymarket.com/events"
_HISTORY = "https://clob.polymarket.com/prices-history"


def leg_fee(price: float, rate: float) -> float:
    if not 0.0 < price < 1.0 or rate <= 0:
        return 0.0
    return float(polymarket_taker_fee(Decimal("1"), Decimal(str(price)), Decimal(str(rate))))


def basket_quote(prices: list[float], rates: list[float], haircut: float = 0.0) -> dict | None:
    """Cost of one share of every outcome. None when a leg has no usable price."""
    if len(prices) < 2 or len(prices) != len(rates):
        return None
    cost = 0.0
    for price, rate in zip(prices, rates):
        lifted = price + haircut
        if not 0.0 < lifted < 1.0:
            return None
        cost += lifted + leg_fee(lifted, rate)
    return {"cost": round(cost, 5), "edge": round(1.0 - cost, 5), "take": cost < 1.0}


def settle(cost: float, winners: int) -> float:
    """Each resolved YES pays $1. The basket pays `winners` dollars."""
    return round(winners - cost, 5)


def _get_json(url: str, attempts: int = 4):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    last = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.3 * (attempt + 1))
    raise RuntimeError(str(last))


def _winner(market: dict) -> bool | None:
    raw = market.get("outcomePrices")
    try:
        prices = json.loads(raw) if isinstance(raw, str) else raw
        yes = float(prices[0])
    except (TypeError, ValueError, IndexError, json.JSONDecodeError):
        return None
    if yes >= 0.99:
        return True
    if yes <= 0.01:
        return False
    return None


def _print_at(history: list[dict], decision: int, max_age: int) -> float | None:
    prior = [row for row in history if int(row["t"]) <= decision]
    if not prior:
        return None
    last = max(prior, key=lambda row: int(row["t"]))
    if decision - int(last["t"]) > max_age:
        return None
    price = float(last["p"])
    if not 0.0 < price < 1.0:
        return None
    return price


def quote_event(event: dict, decision: int, max_age: int, haircut: float = 0.0) -> dict:
    """Price every YES at `decision`. Skip the event when any leg is stale."""
    markets = [m for m in (event.get("markets") or []) if not m.get("archived")]
    winners = []
    prices = []
    rates = []
    for market in markets:
        won = _winner(market)
        if won is None:
            return {"status": "unresolved", "slug": event.get("slug")}
        winners.append(won)
        rate = float((market.get("feeSchedule") or {}).get("rate") or 0)
        try:
            tokens = json.loads(market.get("clobTokenIds") or "[]")
            outcomes = json.loads(market.get("outcomes") or "[]")
        except json.JSONDecodeError:
            return {"status": "book_error", "slug": event.get("slug")}
        if "Yes" not in outcomes:
            return {"status": "book_error", "slug": event.get("slug")}
        yes = tokens[outcomes.index("Yes")]
        try:
            payload = _get_json(
                f"{_HISTORY}?market={yes}&startTs={decision - max_age}&endTs={decision}&fidelity=1"
            )
        except Exception as exc:  # noqa: BLE001
            return {"status": "book_error", "slug": event.get("slug"), "error": type(exc).__name__}
        price = _print_at(payload.get("history") or [], decision, max_age)
        if price is None:
            return {"status": "no_print", "slug": event.get("slug")}
        prices.append(price)
        rates.append(rate)
    quote = basket_quote(prices, rates, haircut)
    if quote is None:
        return {"status": "no_quote", "slug": event.get("slug")}
    won_n = sum(winners)
    worse = basket_quote(prices, rates, 0.01)
    quote.update({
        "status": "quoted",
        "slug": event.get("slug"),
        "title": event.get("title"),
        "n": len(markets),
        "winners": won_n,
        "pnl": settle(quote["cost"], won_n) if quote["take"] else None,
        "prices": [round(price, 4) for price in prices],
        "haircut_1c": None if worse is None else {
            "cost": worse["cost"],
            "take": worse["take"],
            "pnl": settle(worse["cost"], won_n) if worse["take"] else None,
        },
    })
    return quote


def list_events(tag: str, pages: int = 8) -> list[dict]:
    events = []
    for page in range(pages):
        url = (
            f"{_GAMMA}?closed=true&limit=100&offset={page * 100}"
            f"&tag_slug={tag}&order=closedTime&ascending=false"
        )
        try:
            batch = _get_json(url)
        except Exception:
            break
        if not batch:
            break
        events.extend(batch)
        if len(batch) < 100:
            break
    return events


def run_tag(tag: str, *, hours_before: int, max_age: int, pages: int, market_count: tuple[int, int]) -> dict:
    low, high = market_count
    events = [
        event for event in list_events(tag, pages)
        if event.get("negRisk") and low <= len(event.get("markets") or []) <= high
        and " - " not in (event.get("title") or "")
    ]
    rows = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = []
        for event in events:
            end = event.get("endDate")
            if not end:
                continue
            decision = int(datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp()) - hours_before * 3600
            futures.append(pool.submit(quote_event, event, decision, max_age, 0.0))
        for future in as_completed(futures):
            rows.append(future.result())
    taken = [row for row in rows if row.get("take")]
    lifted = [row for row in rows if (row.get("haircut_1c") or {}).get("take")]
    skips: dict[str, int] = {}
    for row in rows:
        if row.get("status") != "quoted":
            skips[row["status"]] = skips.get(row["status"], 0) + 1
    quoted = [row for row in rows if row.get("status") == "quoted"]
    return {
        "tag": tag,
        "hours_before_end": hours_before,
        "max_print_age_s": max_age,
        "events": len(rows),
        "quoted": len(quoted),
        "mean_cost": None if not quoted else round(sum(row["cost"] for row in quoted) / len(quoted), 5),
        "under_1": len(taken),
        "pnl_at_print": round(sum(row["pnl"] for row in taken), 5),
        "under_1_after_1c": len(lifted),
        "pnl_after_1c": round(sum(row["haircut_1c"]["pnl"] for row in lifted), 5),
        "winners_not_one": sum(1 for row in taken if row["winners"] != 1),
        "skips": skips,
        "trades": [
            {
                "slug": row["slug"],
                "title": row.get("title"),
                "n": row["n"],
                "cost": row["cost"],
                "winners": row["winners"],
                "pnl": row["pnl"],
                "pnl_after_1c": None if row.get("haircut_1c") is None else row["haircut_1c"]["pnl"],
            }
            for row in taken
        ],
    }


def main() -> None:
    started = datetime.now(timezone.utc)
    reports = [
        run_tag("soccer", hours_before=0, max_age=3600, pages=4, market_count=(3, 3)),
        run_tag("midterms", hours_before=24, max_age=24 * 3600, pages=6, market_count=(3, 12)),
    ]
    out = {
        "sampled_at_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule": "Buy one share of every YES when the last prints plus taker fees cost less than $1. Hold to resolution.",
        "reports": reports,
    }
    path = Path(__file__).resolve().parents[1] / "paper" / "basket-resolved.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({
        "file": str(path),
        "reports": [
            {k: report[k] for k in ("tag", "events", "quoted", "mean_cost", "under_1", "pnl_at_print", "under_1_after_1c", "pnl_after_1c")}
            for report in reports
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
