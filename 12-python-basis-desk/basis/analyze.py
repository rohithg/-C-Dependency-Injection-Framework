"""Turn a live market into a reading: stance, payoff, risks, and an exit.

The price is the forecast. This does not add news the crowd has not already
priced, and it does not claim an edge. A reading is Pass or Watch.
"""
from __future__ import annotations

import datetime as dt


STAKE = 100.0
MIN_LIQUIDITY = 2_000.0
MIN_VOLUME_24H = 1_000.0
MAX_SPREAD = 0.04
MIN_HOURS = 6.0
DECIDED = 0.08          # below this, or above 1-this, the crowd has already called it


def analyze(market: dict, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    outcomes = list(market.get("outcomes") or [])
    priced = [o for o in outcomes if o.get("price") is not None]
    priced.sort(key=lambda o: -float(o["price"]))
    lead = priced[0] if priced else None
    hours = _hours_left(market.get("end"), now)
    liquidity = float(market.get("liquidity") or 0)
    volume_24h = float(market.get("volume_24h") or 0)
    spread = market.get("spread")
    spread_f = float(spread) if spread is not None else None

    checks = [
        _check("open", "Open", not market.get("closed") and market.get("accepting", True),
               "closed" if market.get("closed") else "taking orders",
               "a closed market is a result, not a bet"),
        _check("clock", "Time left", hours is not None and hours >= MIN_HOURS,
               "no end date" if hours is None else _hours_label(hours),
               "a market with no end date, or one inside "
               f"{MIN_HOURS:.0f} hours of the end, is not a new position"),
        _check("liquidity", "Liquidity", liquidity >= MIN_LIQUIDITY,
               _usd(liquidity), f"under ${_usd_num(MIN_LIQUIDITY)} the printed price is a poor fill"),
        _check("volume", "24h volume", volume_24h >= MIN_VOLUME_24H,
               _usd(volume_24h), "a quiet book moves when you show up"),
        _check("spread", "Spread", spread_f is None or spread_f <= MAX_SPREAD,
               "not published" if spread_f is None else f"{spread_f:.1%}",
               f"wider than {MAX_SPREAD:.0%} means the quote and the fill differ"),
        _check("called", "Still contested", lead is None or DECIDED <= float(lead["price"]) <= 1 - DECIDED,
               _cents(lead) if lead else "no price",
               f"outside {DECIDED:.0%}–{1-DECIDED:.0%} the crowd has already called it"),
    ]
    failed = [c for c in checks if not c["ok"]]
    stance = "PASS" if failed else "WATCH"
    payoff = [_payoff(o) for o in priced]
    return {
        "stance": stance,
        "headline": _headline(stance, failed, lead, payoff),
        "checks": checks,
        "payoff": payoff,
        "risks": _risks(market, hours, failed),
        "exit": (
            "If you buy, use a fixed dollar amount. Exit when the price moves 10¢ against you, "
            f"or when {MIN_HOURS:.0f} hours remain, whichever comes first. Do not add to a loser."
        ),
        "rules": (market.get("description") or "").strip()[:700],
    }


def _headline(stance: str, failed: list[dict], lead: dict | None, payoff: list[dict]) -> str:
    if stance == "PASS":
        reason = failed[0]["note"] if failed else "there is nothing here to price"
        return f"Pass. {reason[0].upper() + reason[1:]}."
    buy = next((p for p in payoff if lead and p["name"] == lead["name"]), None)
    if buy is None:
        return "Watch. The market is open, and we have no separate forecast."
    return (
        f"Watch. {lead['name']} is {_cents(lead)}. "
        f"A ${STAKE:.0f} buy loses ${STAKE:.0f} if it is wrong and pays ${buy['profit_if_wins']:.0f} if it is right. "
        "That price is the forecast."
    )


def _payoff(outcome: dict) -> dict:
    price = float(outcome["price"])
    price = min(0.999, max(0.001, price))
    shares = STAKE / price
    payout = shares  # $1 a share if this outcome wins
    return {
        "name": outcome["name"],
        "price": price,
        "stake": STAKE,
        "shares": round(shares, 2),
        "payout_if_wins": round(payout, 2),
        "profit_if_wins": round(payout - STAKE, 2),
        "loss_if_loses": STAKE,
    }


def _risks(market: dict, hours: float | None, failed: list[dict]) -> list[str]:
    risks = [c["note"] for c in failed]
    if hours is not None and hours < 48:
        risks.append(f"It ends in {_hours_label(hours)}, so there is little time to be early.")
    source = (market.get("resolution_source") or "").strip()
    if source:
        risks.append(f"It resolves from {source}. Read that source, not the headline.")
    else:
        risks.append("Read the resolution rules below. The headline is not the contract.")
    risks.append("A reading is not a fill. The live book can be worse than the price shown here.")
    return risks[:5]


def _check(name: str, label: str, ok: bool, value: str, note: str) -> dict:
    return {"name": name, "label": label, "ok": bool(ok), "value": value, "note": note}


def _hours_left(end: str | None, now: dt.datetime) -> float | None:
    if not end:
        return None
    try:
        parsed = dt.datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return (parsed - now).total_seconds() / 3600


def _hours_label(hours: float) -> str:
    if hours < 0:
        return "already ended"
    if hours < 48:
        return f"{hours:.0f}h left"
    return f"{hours / 24:.0f}d left"


def _cents(outcome: dict | None) -> str:
    if not outcome:
        return "no price"
    return f"{float(outcome['price']) * 100:.1f}¢"


def _usd(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}m"
    if amount >= 1_000:
        return f"${amount / 1_000:.0f}k"
    return f"${amount:.0f}"


def _usd_num(amount: float) -> str:
    return f"{amount:,.0f}"
