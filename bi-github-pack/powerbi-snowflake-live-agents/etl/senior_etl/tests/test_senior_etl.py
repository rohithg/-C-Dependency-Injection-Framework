from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import polars as pl

from senior_etl.contracts.registry import SchemaRegistry, load_contract
from senior_etl.load.merge import delete_insert_by_batch, idempotent_merge_by_hash
from senior_etl.pipeline import SeniorPlatform
from senior_etl.seed import seed_senior_landing
from senior_etl.silver.temporal import point_in_time_join, scd2_merge


def test_contract_breaking_change_detected(tmp_path: Path):
    reg = SchemaRegistry(tmp_path / "reg")
    c = load_contract(Path(__file__).resolve().parents[1] / "contracts" / "customers.yaml")
    reg.publish(c)
    broken = load_contract(Path(__file__).resolve().parents[1] / "contracts" / "customers.yaml")
    broken.primary_key = ["email"]
    try:
        reg.publish(broken)
        assert False, "expected breaking change"
    except ValueError as e:
        assert "primary_key" in str(e)


def test_pit_join_picks_correct_version():
    facts = pl.DataFrame(
        {
            "order_line_id": ["L1", "L2"],
            "customer_nk": ["C1", "C1"],
            "order_date": [date(2026, 1, 15), date(2026, 2, 20)],
        }
    )
    dim = pl.DataFrame(
        {
            "customer_nk": ["C1", "C1"],
            "dim_sk": ["C1_v1", "C1_v2"],
            "effective_from": [date(2026, 1, 1), date(2026, 2, 1)],
            "effective_to": [date(2026, 2, 1), date(9999, 12, 31)],
            "version": [1, 2],
            "is_current": [False, True],
        }
    )
    out = point_in_time_join(facts, dim, "customer_nk", "customer_nk", "order_date", "customer_sk")
    m = {r["order_line_id"]: r["customer_sk"] for r in out.select(["order_line_id", "customer_sk"]).to_dicts()}
    assert m["L1"] == "C1_v1"
    assert m["L2"] == "C1_v2"


def test_idempotent_delete_insert():
    existing = pl.DataFrame({"id": [1, 2], "v": [10, 20], "_batch_id": ["b1", "b1"]})
    incoming = pl.DataFrame({"id": [2, 3], "v": [99, 30], "_batch_id": ["b1", "b1"]})
    out = delete_insert_by_batch(existing, incoming, batch_id="b1")
    assert sorted(out["id"].to_list()) == [2, 3]
    assert out.filter(pl.col("id") == 2)["v"][0] == 99


def test_hash_merge_noop_and_update():
    existing = pl.DataFrame({"bk": ["a", "b"], "val": [1, 2], "_row_hash": ["h1", "h2"]})
    incoming = pl.DataFrame({"bk": ["b", "c"], "val": [3, 4], "_row_hash": ["h2x", "h3"]})
    out = idempotent_merge_by_hash(existing, incoming, ["bk"])
    assert set(out["bk"].to_list()) == {"a", "b", "c"}
    assert out.filter(pl.col("bk") == "b")["val"][0] == 3


def test_full_senior_platform(tmp_path: Path):
    # isolate under tmp by copying contracts/config and seeding landing
    src = Path(__file__).resolve().parents[1]
    root = tmp_path / "senior_etl"
    # minimal copy
    import shutil

    shutil.copytree(src / "contracts", root / "contracts")
    shutil.copytree(src / "config", root / "config")
    seed_senior_landing(root)
    platform = SeniorPlatform(root=root, batch_id="batch_test_001")
    report = platform.run()
    assert report["status"] == "SUCCESS"
    assert report["metrics"]["fct_orders_rows"] >= 8
    # replay is idempotent success
    report2 = platform.run(force_replay=True)
    assert report2["status"] == "REPLAYED"
    # third call without force skips
    skipped = SeniorPlatform(root=root, batch_id="batch_test_001").run(force_replay=False)
    assert skipped.get("skipped") is True
    # PII masked
    cust = pl.read_parquet(
        root / "data" / "lake" / "bronze" / "customers" / "batch_id=batch_test_001" / "data.parquet"
    )
    assert str(cust["email"][0]).startswith("***")
    # inferred late product exists
    prod = pl.read_parquet(root / "data" / "lake" / "silver" / "dim_product_current.parquet")
    assert prod.filter(pl.col("product_nk") == "P999").height == 1
