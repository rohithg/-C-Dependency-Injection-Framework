import json
from decimal import Decimal
from pathlib import Path

TICKET = Path(__file__).parents[1] / "paper" / "2026-11-08-50-to-500.json"


def test_the_liverpool_longshot_is_cancelled_and_the_cash_is_back():
    doc = json.loads(TICKET.read_text())
    assert doc["status"] == "cancelled"
    assert Decimal(doc["spent"]) == 0
    assert Decimal(doc["cash"]) == Decimal(doc["starting_cash"])
    assert Decimal(doc["payout_if_yes"]) == 0
