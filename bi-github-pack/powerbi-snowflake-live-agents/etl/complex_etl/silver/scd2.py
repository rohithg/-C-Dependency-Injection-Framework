from __future__ import annotations

from datetime import date

import polars as pl


FAR_FUTURE = date(9999, 12, 31)


def apply_scd2(
    existing: pl.DataFrame,
    incoming: pl.DataFrame,
    natural_key: str,
    track_columns: list[str],
    as_of: date,
) -> pl.DataFrame:
    """SCD Type 2: version rows on tracked attribute changes."""
    incoming = incoming.unique(subset=[natural_key], keep="last")
    if incoming.is_empty() and (existing is None or existing.is_empty()):
        return pl.DataFrame()

    def _stamp_new(df: pl.DataFrame, version_expr: pl.Expr) -> pl.DataFrame:
        return (
            df.with_columns(
                pl.lit(as_of).alias("effective_from"),
                pl.lit(FAR_FUTURE).alias("effective_to"),
                pl.lit(True).alias("is_current"),
                version_expr.alias("version"),
            )
            .with_columns(
                (
                    pl.col(natural_key).hash(seed=7).cast(pl.Utf8)
                    + "_v"
                    + pl.col("version").cast(pl.Utf8)
                ).alias("surrogate_key")
            )
        )

    if existing is None or existing.is_empty():
        return _stamp_new(incoming, pl.lit(1))

    current = existing.filter(pl.col("is_current"))
    history = existing.filter(~pl.col("is_current"))

    # Compare on natural key
    cmp = current.join(incoming, on=natural_key, how="inner", suffix="_new")
    change_preds = []
    for c in track_columns:
        change_preds.append(pl.col(c).ne_missing(pl.col(f"{c}_new")))
    changed = cmp.filter(pl.any_horizontal(change_preds)) if change_preds else cmp.head(0)

    unchanged_keys = (
        current.select(natural_key)
        .join(changed.select(natural_key), on=natural_key, how="anti")
    )
    unchanged = current.join(unchanged_keys, on=natural_key, how="inner")

    closed = changed.select(current.columns).with_columns(
        pl.lit(as_of).alias("effective_to"),
        pl.lit(False).alias("is_current"),
    )

    max_ver = existing.group_by(natural_key).agg(pl.col("version").max().alias("_max_v"))
    new_from_change = (
        incoming.join(changed.select(natural_key), on=natural_key, how="inner")
        .join(max_ver, on=natural_key, how="left")
        .with_columns((pl.col("_max_v").fill_null(0) + 1).alias("_next_v"))
    )
    new_from_change = _stamp_new(new_from_change.drop("_max_v"), pl.col("_next_v")).drop("_next_v")

    brand_new = incoming.join(current.select(natural_key), on=natural_key, how="anti")
    brand_new = _stamp_new(brand_new, pl.lit(1))

    parts = [p for p in [history, closed, unchanged, new_from_change, brand_new] if not p.is_empty()]
    if not parts:
        return existing

    # Harmonize columns
    cols = list(dict.fromkeys(c for p in parts for c in p.columns))
    norm = []
    for p in parts:
        for c in cols:
            if c not in p.columns:
                p = p.with_columns(pl.lit(None).alias(c))
        norm.append(p.select(cols))
    return pl.concat(norm, how="vertical_relaxed")
