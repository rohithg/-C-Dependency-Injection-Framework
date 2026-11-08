from decimal import Decimal

import pytest

from edge.fill import paper_fill
from edge.models import Leg, Opportunity


def _opp():
    legs = (
        Leg("polymarket", "a", "a:yes", "yes", "buy", "0.40", "10", "0.10", "A"),
        Leg("polymarket", "b", "b:yes", "yes", "buy", "0.40", "10", "0.10", "B"),
    )
    return Opportunity(
        kind="yes_basket", title="A + B", size="10", edge_per_share="0.18",
        net_profit="1.80", legs=legs, risk_free=True, market_ids=("a", "b"),
        note="exactly one YES pays $1",
    )


def test_paper_fill_locks_the_dollar_payout():
    position = paper_fill("1000", _opp())
    assert position.spent == Decimal("8.20")
    assert position.fees == Decimal("0.20")
    assert position.cash == Decimal("991.80")
    assert position.payout_floor == Decimal("10")
    assert position.locked_profit == Decimal("1.80")


def test_paper_fill_refuses_a_quote_and_an_empty_wallet():
    quote = _opp()
    object.__setattr__(quote, "kind", "maker")
    with pytest.raises(ValueError):
        paper_fill("1000", quote)
    with pytest.raises(ValueError):
        paper_fill("1", _opp())
