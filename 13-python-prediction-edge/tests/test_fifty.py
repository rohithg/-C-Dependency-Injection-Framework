import json
from decimal import Decimal
from pathlib import Path

from edge.fees import polymarket_taker_fee

TICKET = Path(__file__).parents[1] / "paper" / "2026-11-08-50-to-500.json"


def test_fifty_dollars_pays_more_than_five_hundred_if_liverpool_wins():
    doc = json.loads(TICKET.read_text())
    size = Decimal(doc["size"])
    ask = Decimal(doc["ask"])
    fee = polymarket_taker_fee(size, ask, Decimal(doc["fee_rate"]))
    spent = size * ask + fee
    assert fee == Decimal(doc["fee"])
    assert spent == Decimal(doc["spent"])
    assert spent <= Decimal("50")
    assert size == Decimal(doc["payout_if_yes"])
    assert size > Decimal("500")
    assert Decimal(doc["starting_cash"]) - spent == Decimal(doc["cash"])
