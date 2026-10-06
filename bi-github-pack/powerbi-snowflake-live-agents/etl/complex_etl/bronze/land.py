from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl


def land_bronze(
    df: pl.DataFrame,
    entity: str,
    bronze_dir: Path,
    run_id: str,
    source_system: str,
) -> Path:
    """Write append-only bronze partition with ingest metadata."""
    if df.is_empty():
        # still record empty marker for lineage/audit
        out_dir = bronze_dir / entity / f"run_id={run_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "part-empty.parquet"
        pl.DataFrame({"_empty": [True]}).write_parquet(path)
        return path

    stamped = df.with_columns(
        pl.lit(run_id).alias("_ingest_run_id"),
        pl.lit(source_system).alias("_source_system"),
        pl.lit(datetime.now(timezone.utc).isoformat()).alias("_ingested_at_utc"),
        pl.lit(entity).alias("_entity"),
    )
    out_dir = bronze_dir / entity / f"run_id={run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "part-000.parquet"
    stamped.write_parquet(path, compression="zstd")
    return path


def read_bronze_entity(bronze_dir: Path, entity: str, run_id: str | None = None) -> pl.DataFrame:
    root = bronze_dir / entity
    if not root.exists():
        return pl.DataFrame()
    if run_id:
        files = sorted((root / f"run_id={run_id}").glob("*.parquet"))
    else:
        # latest partition by name
        parts = sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("run_id=")])
        if not parts:
            return pl.DataFrame()
        files = sorted(parts[-1].glob("*.parquet"))
    files = [f for f in files if f.name != "part-empty.parquet"]
    if not files:
        return pl.DataFrame()
    return pl.concat([pl.read_parquet(f) for f in files], how="vertical_relaxed")
