from __future__ import annotations

from pathlib import Path

import polars as pl


def write_layer_table(df: pl.DataFrame, root: Path, name: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}.parquet"
    if df.is_empty():
        # keep schema marker
        pl.DataFrame({"_empty": [True]}).write_parquet(path)
    else:
        df.write_parquet(path, compression="zstd")
    return path


def read_table(path: Path) -> pl.DataFrame:
    if not path.exists():
        return pl.DataFrame()
    df = pl.read_parquet(path)
    if df.columns == ["_empty"]:
        return pl.DataFrame()
    return df
