"""Position, cash, staleness, and daily-loss gates.

Repair orders are not passed through here. Completing a broken pair reduces
risk, so the daily-loss halt does not block it. Everything that adds a new
package or a new quote does.
"""

from __future__ import annotations

from .models import Opportunity
from .money import POLY_QUANTUM, ZERO


def allow(account, opp: Opportunity, config, now_ms: int) -> tuple[bool, str]:
    if account.halted:
        return False, "kill switch"
    if account.daily_pnl() <= -config.max_daily_loss:
        return False, "daily loss limit"
    if opp.book_ts_ms and now_ms and now_ms - opp.book_ts_ms > config.max_book_age_ms:
        return False, "stale book"
    if opp.net_profit < config.min_profit:
        return False, "below minimum profit"
    if opp.kind == "basis" and opp.edge_per_share < config.min_basis_edge:
        return False, "basis edge too small"
    if opp.kind != "basis" and opp.edge_per_share < config.min_edge:
        return False, "edge too small"
    notional = sum((leg.notional for leg in opp.orders), ZERO)
    if notional > config.max_order_notional + POLY_QUANTUM:
        return False, "order notional cap"
    freeing = account.reserved_for(opp.market_ids) if opp.kind == "maker" else ZERO
    if account.open_notional() - freeing + notional > config.max_open_notional:
        return False, "open notional cap"
    if account.market_notional(opp.market_ids) - freeing + notional > config.max_market_notional:
        return False, "market notional cap"
    if opp.event_id and account.event_notional(opp.event_id) - freeing + notional > config.max_event_notional:
        return False, "event notional cap"
    if account.available() + freeing < opp.cash_needed:
        return False, "not enough cash"
    if opp.kind == "maker" and account.unpaired_notional(opp.market_ids[0]) > ZERO:
        return False, "waiting for the other side"
    return True, "ok"
