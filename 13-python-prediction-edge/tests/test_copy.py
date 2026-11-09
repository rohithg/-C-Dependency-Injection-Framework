import json
from decimal import Decimal
from pathlib import Path

from edge.fees import polymarket_taker_fee

TICKET = Path(__file__).parents[1] / "paper" / "2026-11-08-copy.json"


def test_the_copy_ticket_spends_twenty_five_dollars_at_each_ask():
    doc = json.loads(TICKET.read_text())
    spent = Decimal("0")
    for leg in doc["legs"]:
        size = Decimal(leg["size"])
        ask = Decimal(leg["ask"])
        fee = polymarket_taker_fee(size, ask, Decimal(leg["fee_rate"]))
        assert fee == Decimal(leg["fee"])
        assert size * ask + fee == Decimal(leg["spent"])
        assert Decimal("15") <= size * ask <= Decimal("25")
        assert Decimal("0.15") < ask < Decimal("0.85")
        spent += Decimal(leg["spent"])
    assert spent == Decimal(doc["spent"])
    assert Decimal(doc["starting_cash"]) - spent == Decimal(doc["cash"])
