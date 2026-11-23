import json
from decimal import Decimal
from pathlib import Path

from edge.fees import polymarket_taker_fee

TICKET = Path(__file__).parents[1] / "paper" / "2026-11-22-aggressive.json"


def test_each_longshot_is_a_hundred_fifty_dollar_ask_walk():
    doc = json.loads(TICKET.read_text())
    spent = Decimal("0")
    for leg in doc["legs"]:
        size = Decimal("0")
        fees = Decimal("0")
        cost = Decimal("0")
        rate = Decimal(leg["fee_rate"])
        for fill in leg["fills"]:
            px = Decimal(fill["price"])
            sz = Decimal(fill["size"])
            fee = polymarket_taker_fee(sz, px, rate)
            assert fee == Decimal(fill["fee"])
            size += sz
            fees += fee
            cost += sz * px + fee
        assert size == Decimal(leg["size"]) == Decimal(leg["payout_if_yes"])
        assert fees == Decimal(leg["fees"])
        assert cost == Decimal(leg["spent"])
        assert cost <= Decimal(doc["budget_each"])
        assert Decimal(leg["payout_if_yes"]) > Decimal("600")
        spent += cost
    assert spent == Decimal(doc["spent"])
    assert Decimal(doc["starting_cash"]) - spent == Decimal(doc["cash"])
