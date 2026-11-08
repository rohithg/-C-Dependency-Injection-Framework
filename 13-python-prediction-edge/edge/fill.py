"""Turn one package into a paper position.

The fill pays the touch on every leg. A basket, a complete-set buy, and a
ladder each pay at least $1 a share when every leg is held, so the cash
left over plus that floor is the position.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Opportunity
from .money import ONE, ZERO, D


PACKAGES = ("yes_basket", "complete_set_buy", "ladder")


@dataclass(frozen=True)
class PaperPosition:
    kind: str
    title: str
    cash: object
    spent: object
    fees: object
    size: object
    payout_floor: object
    locked_profit: object

    def __post_init__(self) -> None:
        for name in ("cash", "spent", "fees", "size", "payout_floor", "locked_profit"):
            object.__setattr__(self, name, D(getattr(self, name)))


def paper_fill(cash, opportunity: Opportunity) -> PaperPosition:
    """Buy every leg. Cash falls by the asks and the fees."""
    if opportunity.kind not in PACKAGES:
        raise ValueError(f"{opportunity.kind} is not a package that pays at least $1")
    if not opportunity.legs:
        raise ValueError("opportunity has no legs")
    cash = D(cash)
    spent = sum((leg.price * leg.size + leg.fee for leg in opportunity.legs), ZERO)
    fees = sum((leg.fee for leg in opportunity.legs), ZERO)
    if spent > cash:
        raise ValueError("not enough cash")
    payout = opportunity.size * ONE
    return PaperPosition(
        kind=opportunity.kind,
        title=opportunity.title,
        cash=cash - spent,
        spent=spent,
        fees=fees,
        size=opportunity.size,
        payout_floor=payout,
        locked_profit=payout - spent,
    )
