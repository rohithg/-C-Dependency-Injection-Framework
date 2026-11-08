"""Text status for a scan or a paper cycle."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .money import ZERO, money

PT = ZoneInfo("America/Los_Angeles")


def render(result, account, now: datetime | None = None) -> str:
    now = now or datetime.now(PT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=PT)
    local = now.astimezone(PT)
    locked_cost = sum((pkg.cost for pkg in account.packages), ZERO)
    locked_floor = sum((pkg.floor for pkg in account.packages), ZERO)
    lines = [
        f"prediction-edge  {local.strftime('%Y-%m-%d %H:%M')} PT",
        f"equity ${money(account.last_equity)}   cash ${money(account.cash)}   "
        f"daily ${money(account.daily_pnl())}   fees ${money(account.fees_paid)}",
        f"locked packages ${money(locked_floor)} floor on ${money(locked_cost)} cost   "
        f"open ${money(account.open_notional())}   resting {len(account.resting)}",
    ]
    if account.halted:
        lines.append("HALTED. No new risk until the halt is cleared.")
    lines.append("")
    if result.taken:
        lines.append("Acted:")
        for opp in result.taken:
            flag = "locked $" + money(opp.net_profit) if opp.risk_free else "not risk-free"
            if opp.kind == "maker":
                flag = f"quote, {money(opp.net_profit)} if both fill"
            lines.append(f"  {opp.kind:18} {opp.title}  {opp.size} sh  {flag}")
            lines.append(f"    {opp.note}")
    else:
        lines.append("Nothing cleared the edge bar this pass.")
    if result.matched:
        lines.append("")
        lines.append("Maker fills:")
        for note in result.matched:
            lines.append(f"  {note}")
    if result.repairs:
        lines.append("")
        lines.append("Inventory:")
        for note in result.repairs:
            lines.append(f"  {note}")
    if result.skipped:
        lines.append("")
        lines.append("Skipped:")
        for opp, reason in result.skipped[:8]:
            lines.append(f"  {opp.kind} {opp.title}: {reason}")
    watches = sorted(result.watches, key=lambda w: w.edge_per_share, reverse=True)[:8]
    if watches:
        lines.append("")
        lines.append("Closest to the bar (negative means the book is not paying):")
        for watch in watches:
            lines.append(f"  {watch.edge_per_share:+.4f}/sh  {watch.venue:10} {watch.kind:18} {watch.title}")
            lines.append(f"    {watch.detail}")
    return "\n".join(lines)
