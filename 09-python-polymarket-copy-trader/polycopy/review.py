"""Per-trade review before a leader's BUY is copied live.

Every candidate goes through the same checklist and the result (each check,
its value, pass/fail) is kept in the run report, so the daily summary shows
*why* something was or was not copied, not just that it was skipped.

The static checks are the ones the backtest also applies (`copy.copyable`).
The live-only checks need the current order book and market stats that do
not exist historically: liquidity, 24h volume, spread, and how far the price
has already moved since the leader's fill.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from .analysis import category
from .copy import CopyConfig, Portfolio


@dataclass
class Check:
    name: str
    value: str
    ok: bool
    note: str = ""


def review_buy(trade: dict, market: dict | None, book: dict | None, cfg: CopyConfig, portfolio: Portfolio,
               now: int, max_age_h: float) -> tuple[bool, list[Check]]:
    """Return (approved, checks) for a leader BUY."""
    checks: list[Check] = []
    usd = float(trade.get("usdcSize", 0) or 0)
    leader_px = float(trade["price"])
    slug = (trade.get("slug") or (market or {}).get("slug") or "").lower()
    age_h = (now - int(trade["timestamp"])) / 3600

    checks.append(Check("leader size", f"${usd:,.0f}", usd >= cfg.min_usdc, f"min ${cfg.min_usdc:,.0f}"))
    short = any(p in slug for p in cfg.skip_slug_parts)
    checks.append(Check("market type", category(slug), not short, "no 5m/15m/1h up-down markets"))
    checks.append(Check("leader price", f"{leader_px:.2f}", cfg.min_price <= leader_px <= cfg.max_price,
                        f"{cfg.min_price:.2f}-{cfg.max_price:.2f}"))
    checks.append(Check("seen after", f"{age_h:.1f}h", age_h <= max_age_h, f"max {max_age_h:.0f}h"))

    if market is None:
        checks.append(Check("market", "unknown", False, "not found on Gamma"))
        return False, checks
    end_ts = market.get("end_ts")
    if end_ts is None:
        checks.append(Check("time to end", "none", False, "no end date"))
    else:
        hours = (end_ts - int(trade["timestamp"])) / 3600
        checks.append(Check("time to end", f"{hours:.0f}h", hours >= cfg.min_hours_to_end, f"min {cfg.min_hours_to_end:.0f}h"))
    if market.get("closed"):
        checks.append(Check("status", "closed", False, ""))

    liq = market.get("liquidity")
    if cfg.min_liquidity_usd > 0:
        checks.append(Check("liquidity", _usd(liq), liq is not None and liq >= cfg.min_liquidity_usd, f"min ${cfg.min_liquidity_usd:,.0f}"))
    vol = market.get("volume_24h")
    if cfg.min_volume_24h_usd > 0:
        checks.append(Check("24h volume", _usd(vol), vol is not None and vol >= cfg.min_volume_24h_usd, f"min ${cfg.min_volume_24h_usd:,.0f}"))

    best_ask = book["asks"][0][0] if book and book.get("asks") else None
    best_bid = book["bids"][0][0] if book and book.get("bids") else None
    if best_ask is None:
        checks.append(Check("order book", "no asks", False, "nothing to buy"))
    else:
        spread = best_ask - best_bid if best_bid is not None else None
        checks.append(Check("spread", f"{spread:.3f}" if spread is not None else "no bids",
                            spread is not None and spread <= cfg.max_spread, f"max {cfg.max_spread:.2f}"))
        move = best_ask - leader_px
        checks.append(Check("price since leader", f"{move:+.3f}", move <= cfg.max_chase, f"max +{cfg.max_chase:.2f}"))
        checks.append(Check("current price", f"{best_ask:.3f}", best_ask <= cfg.max_price, f"max {cfg.max_price:.2f}"))

    equity = portfolio.last_equity
    room = cfg.max_market_fraction * equity - portfolio.market_cost(market["condition_id"])
    budget = min(cfg.trade_fraction * equity, room, portfolio.cash)
    if cfg.max_leader_multiple > 0:
        budget = min(budget, cfg.max_leader_multiple * usd)
    checks.append(Check("position size", f"${max(budget, 0):,.0f}", budget >= 1.0,
                        "market cap reached" if room < 1.0 else ("no cash" if portfolio.cash < 1.0 else f"{cfg.trade_fraction:.0%} of equity, <= leader")))
    return all(c.ok for c in checks), checks


def review_to_dict(trade: dict, market: dict | None, approved: bool, checks: list[Check], result: str) -> dict:
    return {"ts": int(trade["timestamp"]), "wallet": trade["proxyWallet"], "name": trade.get("name") or trade["proxyWallet"][:8],
            "title": trade.get("title") or (market or {}).get("question") or "", "outcome": trade.get("outcome", ""),
            "side": trade["side"], "usdc": float(trade.get("usdcSize", 0) or 0), "price": float(trade["price"]),
            "approved": approved, "result": result, "checks": [asdict(c) for c in checks]}


def _usd(v: float | None) -> str:
    return "unknown" if v is None else f"${v:,.0f}"
