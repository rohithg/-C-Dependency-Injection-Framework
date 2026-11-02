from __future__ import annotations

from pathlib import Path

import polars as pl


MART_TABLES = ("dim_customer", "dim_product", "dim_date", "fct_orders")


def write_parquet(marts: dict[str, pl.DataFrame], out_dir: Path) -> dict[str, Path]:
    """Persist marts (and cleaned raw) as Snappy Parquet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, df in marts.items():
        path = out_dir / f"{name}.parquet"
        df.write_parquet(path, compression="snappy")
        written[name] = path
    return written


def write_manifest(written: dict[str, Path], out_dir: Path, stats: dict) -> Path:
    import json
    from datetime import datetime, timezone

    path = out_dir / "run_manifest.json"
    payload = {
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "tables": {k: {"path": str(v), "rows": stats.get(k)} for k, v in written.items()},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
