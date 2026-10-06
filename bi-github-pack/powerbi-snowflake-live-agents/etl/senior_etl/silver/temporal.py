from __future__ import annotations

from datetime import date

import polars as pl


def scd2_merge(
    existing: pl.DataFrame,
    incoming: pl.DataFrame,
    nk: str,
    track: list[str],
    as_of: date,
) -> pl.DataFrame:
    incoming = incoming.unique(subset=[nk], keep="last")
    if incoming.is_empty() and (existing is None or existing.is_empty()):
        return pl.DataFrame()

    def stamp(df: pl.DataFrame, ver: pl.Expr) -> pl.DataFrame:
        return (
            df.with_columns(
                pl.lit(as_of).alias("effective_from"),
                pl.lit(date(9999, 12, 31)).alias("effective_to"),
                pl.lit(True).alias("is_current"),
                ver.alias("version"),
            ).with_columns(
                (
                    pl.col(nk).hash(seed=3).cast(pl.Utf8)
                    + "_v"
                    + pl.col("version").cast(pl.Utf8)
                ).alias("dim_sk")
            )
        )

    if existing is None or existing.is_empty():
        return stamp(incoming, pl.lit(1))

    current = existing.filter(pl.col("is_current"))
    history = existing.filter(~pl.col("is_current"))
    cmp = current.join(incoming, on=nk, how="inner", suffix="_new")
    changed = cmp.filter(
        pl.any_horizontal([pl.col(c).ne_missing(pl.col(f"{c}_new")) for c in track])
    )
    unchanged = current.join(changed.select(nk), on=nk, how="anti")
    closed = changed.select(current.columns).with_columns(
        pl.lit(as_of).alias("effective_to"),
        pl.lit(False).alias("is_current"),
    )
    max_v = existing.group_by(nk).agg(pl.col("version").max().alias("_mv"))
    new_chg = (
        incoming.join(changed.select(nk), on=nk, how="inner")
        .join(max_v, on=nk, how="left")
        .with_columns((pl.col("_mv").fill_null(0) + 1).alias("_nv"))
    )
    new_chg = stamp(new_chg.drop("_mv"), pl.col("_nv")).drop("_nv")
    brand = stamp(incoming.join(current.select(nk), on=nk, how="anti"), pl.lit(1))
    parts = [p for p in [history, closed, unchanged, new_chg, brand] if not p.is_empty()]
    cols = list(dict.fromkeys(c for p in parts for c in p.columns))
    norm = []
    for p in parts:
        for c in cols:
            if c not in p.columns:
                p = p.with_columns(pl.lit(None).alias(c))
        norm.append(p.select(cols))
    return pl.concat(norm, how="vertical_relaxed")


def point_in_time_join(
    facts: pl.DataFrame,
    dim_scd2: pl.DataFrame,
    fact_nk: str,
    dim_nk: str,
    fact_date_col: str,
    dim_sk_alias: str,
) -> pl.DataFrame:
    """Attach dimension version where effective_from <= fact_date < effective_to."""
    if facts.is_empty():
        return facts
    if dim_scd2.is_empty():
        return facts.with_columns(pl.lit(None).cast(pl.Utf8).alias(dim_sk_alias))

    d = dim_scd2.rename({dim_nk: fact_nk}).select(
        fact_nk,
        pl.col("dim_sk").alias(dim_sk_alias),
        "effective_from",
        "effective_to",
        "version",
    )
    joined = facts.join(d, on=fact_nk, how="left")
    pit = joined.filter(
        pl.col("effective_from").is_not_null()
        & (pl.col(fact_date_col) >= pl.col("effective_from"))
        & (pl.col(fact_date_col) < pl.col("effective_to"))
    )
    grain = "order_line_id" if "order_line_id" in facts.columns else fact_nk
    pit = pit.sort("version", descending=True).unique(subset=[grain], keep="first")
    miss = facts.join(pit.select(grain), on=grain, how="anti").with_columns(
        pl.lit(None).cast(pl.Utf8).alias(dim_sk_alias),
        pl.lit(None).alias("effective_from"),
        pl.lit(None).alias("effective_to"),
        pl.lit(None).alias("version"),
    )
    cols = list(dict.fromkeys(list(pit.columns) + list(miss.columns)))
    parts = []
    for p in [pit, miss]:
        for c in cols:
            if c not in p.columns:
                p = p.with_columns(pl.lit(None).alias(c))
        parts.append(p.select(cols))
    return pl.concat(parts, how="vertical_relaxed")


def ensure_inferred_dimension(
    facts: pl.DataFrame,
    dim: pl.DataFrame,
    fact_nk: str,
    dim_nk: str,
    defaults: dict,
) -> pl.DataFrame:
    """Create inferred dim members for late-arriving keys seen in facts."""
    if facts.is_empty():
        return dim if dim is not None else pl.DataFrame()
    if dim is None or dim.is_empty():
        dim = pl.DataFrame({dim_nk: []}).cast({dim_nk: pl.Utf8})

    missing = (
        facts.select(pl.col(fact_nk).alias(dim_nk))
        .unique()
        .filter(pl.col(dim_nk).is_not_null())
        .join(dim.select(dim_nk), on=dim_nk, how="anti")
    )
    if missing.is_empty():
        if "_inferred" not in dim.columns:
            dim = dim.with_columns(pl.lit(False).alias("_inferred"))
        return dim

    inferred = missing.with_columns([pl.lit(v).alias(k) for k, v in defaults.items()])
    inferred = inferred.with_columns(
        pl.lit(True).alias("_inferred"),
        pl.lit(True).alias("is_current"),
        pl.lit(1).alias("version"),
        (pl.col(dim_nk).hash(seed=3).cast(pl.Utf8) + "_inferred").alias("dim_sk"),
        pl.lit(date(1970, 1, 1)).alias("effective_from"),
        pl.lit(date(9999, 12, 31)).alias("effective_to"),
    )
    if "_inferred" not in dim.columns:
        dim = dim.with_columns(pl.lit(False).alias("_inferred"))
    all_cols = list(dict.fromkeys(list(dim.columns) + list(inferred.columns)))
    parts = []
    for p in [dim, inferred]:
        for c in all_cols:
            if c not in p.columns:
                p = p.with_columns(pl.lit(None).alias(c))
        parts.append(p.select(all_cols))
    return pl.concat(parts, how="vertical_relaxed")
