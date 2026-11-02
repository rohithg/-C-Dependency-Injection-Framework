from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from retail_etl.config import EtlConfig
from retail_etl.extract import extract_all
from retail_etl.load.local import write_manifest, write_parquet
from retail_etl.load.snowflake_load import write_snowflake_sql_bundle
from retail_etl.transform import transform


@dataclass
class PipelineResult:
    rows: dict[str, int]
    parquet: dict[str, Path]
    manifest: Path
    snowflake_loaded: bool


def run_pipeline(cfg: EtlConfig) -> PipelineResult:
    frames = extract_all(cfg.raw_dir)
    marts = transform(frames)
    row_stats = {k: v.height for k, v in marts.items()}
    written = write_parquet(marts, cfg.out_dir)
    manifest = write_manifest(written, cfg.out_dir, row_stats)
    write_snowflake_sql_bundle(cfg, cfg.sql_dir)

    snowflake_loaded = False
    if cfg.load_snowflake:
        if not cfg.snowflake_ready():
            raise RuntimeError(
                "Snowflake load requested but SF_ACCOUNT/SF_USER and password or key are missing"
            )
        from retail_etl.load.snowflake_load import load_marts_to_snowflake

        load_marts_to_snowflake(cfg, marts, cfg.root / "data" / "out" / "stage_csv")
        snowflake_loaded = True

    # Quality summary beside parquet
    summary = {
        "fct_orders_rows": row_stats.get("fct_orders", 0),
        "dim_customer_rows": row_stats.get("dim_customer", 0),
        "dim_product_rows": row_stats.get("dim_product", 0),
        "net_revenue": float(marts["fct_orders"]["line_net_amount"].sum())
        if row_stats.get("fct_orders")
        else 0.0,
        "snowflake_loaded": snowflake_loaded,
    }
    (cfg.out_dir / "quality_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return PipelineResult(
        rows=row_stats,
        parquet=written,
        manifest=manifest,
        snowflake_loaded=snowflake_loaded,
    )
