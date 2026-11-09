import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_the_scan_kept_only_the_maduro_touch_that_grew():
    scan = json.loads((ROOT / "paper" / "2026-11-08-scan.json").read_text())
    assert scan["trades"] == ["paper/2026-11-08-maduro-add.json"]
    for test in scan["tests"]:
        assert test["cleared"] == 0

    add = json.loads((ROOT / "paper" / "2026-11-08-maduro-add.json").read_text())
    size = Decimal(add["size"])
    cost = sum(size * Decimal(leg["price"]) + Decimal(leg["fee"]) for leg in add["legs"])
    assert cost == Decimal(add["spent"])
    assert size - cost == Decimal(add["locked_profit"])
    assert (size - cost) / size >= Decimal("0.01")
    assert Decimal(add["starting_cash"]) - cost == Decimal(add["cash"])
    held = json.loads((ROOT / "paper" / "2026-11-08-edge.json").read_text())
    prior = next(b for b in held["baskets"] if b["event_slug"] == add["event_slug"])
    assert size + Decimal(prior["size"]) == Decimal("15.9")
