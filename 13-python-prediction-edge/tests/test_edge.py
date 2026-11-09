import json
from decimal import Decimal
from pathlib import Path

from edge.fees import polymarket_taker_fee

TICKET = Path(__file__).parents[1] / "paper" / "2026-11-08-edge.json"


def test_the_fifty_goes_into_baskets_that_cost_less_than_a_dollar():
    doc = json.loads(TICKET.read_text())
    spent = Decimal("0")
    locked = Decimal("0")
    for basket in doc["baskets"]:
        size = Decimal(basket["size"])
        cost = Decimal("0")
        for leg in basket["legs"]:
            assert Decimal(leg["size"]) == size
            price = Decimal(leg["price"])
            # Rates live on the market; the recorded fee has to match a taker fee at some rate.
            fee = Decimal(leg["fee"])
            assert fee == polymarket_taker_fee(size, price, _rate_for(fee, size, price))
            cost += size * price + fee
        assert cost == Decimal(basket["spent"])
        assert size - cost == Decimal(basket["locked_profit"])
        assert (size - cost) / size >= Decimal("0.01")
        assert size - cost >= Decimal("0.05")
        spent += cost
        locked += size - cost
    assert spent == Decimal(doc["spent"])
    assert locked == Decimal(doc["locked_profit"])
    assert spent <= Decimal(doc["budget"])
    assert Decimal(doc["starting_cash"]) - spent == Decimal(doc["cash"])


def _rate_for(fee: Decimal, size: Decimal, price: Decimal) -> Decimal:
    for rate in (Decimal("0"), Decimal("0.03"), Decimal("0.04"), Decimal("0.05"), Decimal("0.07")):
        if polymarket_taker_fee(size, price, rate) == fee:
            return rate
    raise AssertionError(f"no fee schedule matches {fee}")
