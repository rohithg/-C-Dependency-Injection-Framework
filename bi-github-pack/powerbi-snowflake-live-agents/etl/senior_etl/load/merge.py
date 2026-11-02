from __future__ import annotations

from pathlib import Path

import polars as pl


def mask_pii(df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
    exprs = []
    for c in columns:
        if c in df.columns:
            exprs.append(
                pl.when(pl.col(c).is_null())
                .then(None)
                .otherwise(
                    pl.concat_str(
                        [
                            pl.lit("***"),
                            pl.col(c).cast(pl.Utf8).str.slice(-4, 4).fill_null(""),
                        ]
                    )
                )
                .alias(c)
            )
    return df.with_columns(exprs) if exprs else df


def write_parquet(df: pl.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if df.is_empty():
        pl.DataFrame({"_empty": [True]}).write_parquet(path)
    else:
        df.write_parquet(path, compression="zstd")
    return path


def read_parquet(path: Path) -> pl.DataFrame:
    if not path.exists():
        return pl.DataFrame()
    df = pl.read_parquet(path)
    if df.columns == ["_empty"]:
        return pl.DataFrame()
    return df


def idempotent_merge_by_hash(
    existing: pl.DataFrame,
    incoming: pl.DataFrame,
    business_key: list[str],
    hash_col: str = "_row_hash",
) -> pl.DataFrame:
    """
    Idempotent upsert:
    - same business key + same hash → keep existing (no-op)
    - same business key + new hash → replace with incoming
    - new business key → insert
    """
    if incoming.is_empty():
        return existing
    if existing.is_empty():
        return incoming

    # drop existing rows whose keys are being replaced (changed hash or force refresh)
    incoming_keys = incoming.select(business_key + [hash_col])
    # unchanged keys (same hash)
    same = existing.join(incoming_keys, on=business_key + [hash_col], how="inner")
    # existing rows not in incoming keys at all
    not_touched = existing.join(incoming.select(business_key), on=business_key, how="anti")
    # incoming always wins for its keys
    parts = [p for p in [not_touched, same, incoming] if not p.is_empty()]
    # Prefer incoming over same for key — unique keep last after concat order
    cols = list(dict.fromkeys(c for p in parts for c in p.columns))
    norm = []
    for p in parts:
        for c in cols:
            if c not in p.columns:
                p = p.with_columns(pl.lit(None).alias(c))
        norm.append(p.select(cols))
    return pl.concat(norm, how="vertical_relaxed").unique(subset=business_key, keep="last")


def delete_insert_by_batch(
    existing: pl.DataFrame,
    incoming: pl.DataFrame,
    batch_col: str = "_batch_id",
    batch_id: str = "",
) -> pl.DataFrame:
    """Classic idempotent pattern: delete prior rows for batch_id, then insert."""
    if existing.is_empty():
        return incoming
    if batch_col in existing.columns and batch_id:
        kept = existing.filter(pl.col(batch_col) != batch_id)
    else:
        kept = existing
    if incoming.is_empty():
        return kept
    cols = list(dict.fromkeys(list(kept.columns) + list(incoming.columns)))
    parts = []
    for p in [kept, incoming]:
        for c in cols:
            if c not in p.columns:
                p = p.with_columns(pl.lit(None).alias(c))
        parts.append(p.select(cols))
    return pl.concat(parts, how="vertical_relaxed")
