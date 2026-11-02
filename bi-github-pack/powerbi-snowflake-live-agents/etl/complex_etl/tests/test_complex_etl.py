from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import polars as pl

from complex_etl.config_loader import PipelineConfig
from complex_etl.pipeline import run_complex_pipeline
from complex_etl.seed import seed_complex_sources
from complex_etl.silver.scd2 import apply_scd2
from complex_etl.quality.gates import evaluate_gates
from complex_etl.orchestrator.dag import DagRunner, Task


def test_scd2_versions_on_attribute_change():
    day1 = pl.DataFrame(
        {
            "customer_nk": ["C1", "C2"],
            "customer_name": ["A", "B"],
            "region_name": ["West", "East"],
            "country_code": ["US", "US"],
            "segment": ["SMB", "SMB"],
            "credit_tier": ["B", "B"],
        }
    )
    day2 = pl.DataFrame(
        {
            "customer_nk": ["C1", "C2", "C3"],
            "customer_name": ["A International", "B", "C New"],
            "region_name": ["West", "East", "West"],
            "country_code": ["US", "US", "US"],
            "segment": ["SMB", "SMB", "ENTERPRISE"],
            "credit_tier": ["A", "B", "A"],
        }
    )
    v1 = apply_scd2(pl.DataFrame(), day1, "customer_nk", ["customer_name", "credit_tier"], date(2026, 1, 1))
    v2 = apply_scd2(v1, day2, "customer_nk", ["customer_name", "credit_tier"], date(2026, 2, 1))
    assert v2.filter(pl.col("is_current")).height == 3
    assert v2.filter(~pl.col("is_current")).height == 1  # C1 closed
    assert v2.filter((pl.col("customer_nk") == "C1") & pl.col("is_current"))["credit_tier"][0] == "A"


def test_dag_respects_dependencies():
    order: list[str] = []

    def a():
        order.append("a")
        return {}

    def b():
        order.append("b")
        return {}

    def c():
        order.append("c")
        return {}

    DagRunner(
        [
            Task("c", c, depends_on=["a", "b"]),
            Task("b", b, depends_on=["a"]),
            Task("a", a),
        ]
    ).run()
    assert order == ["a", "b", "c"]


def test_full_complex_pipeline(tmp_path: Path, monkeypatch):
    # Run inside temp copy of package data paths via config override
    etl_root = Path(__file__).resolve().parents[2]  # .../etl
    # seed into real complex_etl data (idempotent) then run
    seed_complex_sources(etl_root / "complex_etl")
    cfg = PipelineConfig.create(root=etl_root, run_id="test_run_complex")
    # isolate lake outputs under tmp
    cfg.bronze_dir = tmp_path / "bronze"
    cfg.silver_dir = tmp_path / "silver"
    cfg.gold_dir = tmp_path / "gold"
    cfg.quarantine_dir = tmp_path / "quarantine"
    cfg.state_dir = tmp_path / "state"
    cfg.report_dir = tmp_path / "reports"

    result = run_complex_pipeline(cfg, apply_day2_customers=True)
    assert result["task_results"]["dq_gates"]["ok"] is True
    fact = pl.read_parquet(cfg.gold_dir / "fct_orders.parquet")
    assert fact.height >= 8
    assert "line_net_amount_usd" in fact.columns
    scd = pl.read_parquet(cfg.silver_dir / "scd2" / "dim_customer_scd2.parquet")
    assert scd.filter(~pl.col("is_current")).height >= 1
    latest = json.loads((cfg.report_dir / "latest_run.json").read_text())
    assert latest["run_id"] == "test_run_complex"
    # orphan P999 quarantined / removed from gold
    assert fact.filter(pl.col("product_nk") == "P999").height == 0


def test_dq_referential_detects_orphans():
    tables = {
        "fct_orders": pl.DataFrame(
            {
                "order_line_id": ["L1", "L2"],
                "order_id": ["O1", "O1"],
                "customer_nk": ["C1", "CX"],
                "product_nk": ["P1", "P1"],
                "quantity": [1, 1],
                "unit_price": [10.0, 10.0],
                "order_status": ["SHIPPED", "SHIPPED"],
            }
        ),
        "dim_customer_current": pl.DataFrame({"customer_nk": ["C1"]}),
        "dim_product_current": pl.DataFrame({"product_nk": ["P1"]}),
    }
    dq = {
        "fct_orders": [
            {
                "rule": "referential",
                "column": "customer_nk",
                "ref_table": "dim_customer_current",
                "ref_column": "customer_nk",
                "severity": "error",
            }
        ]
    }
    report = evaluate_gates(tables, dq)
    assert report.errors
    assert report.errors[0].bad_rows == 1
