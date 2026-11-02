from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from retail_etl.config import EtlConfig
from retail_etl.pipeline import run_pipeline
from retail_etl.seed import write_seed_data
from retail_etl.transform import transform
from retail_etl.extract import extract_all


def test_seed_and_full_pipeline(tmp_path: Path):
    root = tmp_path / "etl"
    raw = root / "data" / "raw"
    write_seed_data(raw)
    cfg = EtlConfig(
        root=root,
        raw_dir=raw,
        out_dir=root / "data" / "out" / "parquet",
        sql_dir=root / "sql",
        load_snowflake=False,
    )
    result = run_pipeline(cfg)
    assert result.rows["dim_customer"] == 6  # C001..C006 unique (C001 kept last)
    assert result.rows["dim_product"] == 5
    assert result.rows["fct_orders"] >= 8  # cancelled + qty=0 filtered
    assert (cfg.out_dir / "fct_orders.parquet").exists()
    assert (cfg.out_dir / "quality_summary.json").exists()
    summary = json.loads((cfg.out_dir / "quality_summary.json").read_text())
    assert summary["net_revenue"] > 0
    assert (cfg.sql_dir / "01_etl_ddl.sql").exists()


def test_transform_filters_cancelled_and_zero_qty(tmp_path: Path):
    raw = tmp_path / "raw"
    write_seed_data(raw)
    frames = extract_all(raw)
    marts = transform(frames)
    statuses = set(marts["fct_orders"]["order_status"].to_list())
    assert "CANCELLED" not in statuses
    assert marts["fct_orders"].filter(pl.col("quantity") <= 0).height == 0
    # Margin math
    row = marts["fct_orders"].filter(pl.col("order_line_id") == "L1").row(0, named=True)
    expected_net = 4 * 349.0 * (1 - 0.05)
    assert abs(row["line_net_amount"] - expected_net) < 1e-6
