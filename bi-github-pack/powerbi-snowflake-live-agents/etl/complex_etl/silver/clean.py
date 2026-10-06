from __future__ import annotations

from pathlib import Path

import polars as pl


def clean_customers(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    if df.is_empty():
        return df, pl.DataFrame()
    base = df.with_columns(
        pl.col("customer_id").str.strip_chars().alias("customer_nk"),
        pl.col("customer_name").str.strip_chars(),
        pl.col("region_name").str.strip_chars().str.to_titlecase(),
        pl.col("country_code").str.strip_chars().str.to_uppercase(),
        pl.col("segment").str.strip_chars().str.to_uppercase(),
        pl.col("credit_tier").str.strip_chars().str.to_uppercase(),
    )
    bad = base.filter(pl.col("customer_nk").is_null() | (pl.col("customer_nk") == ""))
    good = base.filter(pl.col("customer_nk").is_not_null() & (pl.col("customer_nk") != "")).unique(
        subset=["customer_nk"], keep="last"
    )
    return good, bad


def clean_products(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    if df.is_empty():
        return df, pl.DataFrame()
    base = df.with_columns(
        pl.col("product_id").str.strip_chars().alias("product_nk"),
        pl.col("product_name").str.strip_chars(),
        pl.col("product_category").str.strip_chars(),
        pl.col("brand").str.strip_chars(),
        pl.col("unit_cost").cast(pl.Float64),
        pl.col("is_active").cast(pl.Boolean),
    )
    bad = base.filter(pl.col("product_nk").is_null() | pl.col("unit_cost").is_null())
    good = base.filter(pl.col("product_nk").is_not_null() & pl.col("unit_cost").is_not_null()).unique(
        subset=["product_nk"], keep="last"
    )
    return good, bad


def clean_orders(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    if df.is_empty():
        return df, pl.DataFrame()
    base = df.with_columns(
        pl.col("order_id").str.strip_chars(),
        pl.col("customer_id").str.strip_chars().alias("customer_nk"),
        pl.col("order_date").str.to_datetime(strict=False).dt.date().alias("order_date"),
        pl.col("order_status").str.strip_chars().str.to_uppercase(),
        pl.col("order_channel").str.strip_chars().str.to_titlecase(),
        pl.col("currency_code").str.strip_chars().str.to_uppercase(),
    )
    bad = base.filter(pl.col("order_id").is_null() | pl.col("order_date").is_null())
    good = base.filter(pl.col("order_id").is_not_null() & pl.col("order_date").is_not_null()).unique(
        subset=["order_id"], keep="last"
    )
    return good, bad


def clean_order_lines(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    if df.is_empty():
        return df, pl.DataFrame()
    base = df.with_columns(
        pl.col("order_line_id").str.strip_chars(),
        pl.col("order_id").str.strip_chars(),
        pl.col("product_id").str.strip_chars().alias("product_nk"),
        pl.col("quantity").cast(pl.Int64),
        pl.col("unit_price").cast(pl.Float64),
        pl.col("discount_pct").cast(pl.Float64).fill_null(0.0),
        pl.col("tax_amount").cast(pl.Float64).fill_null(0.0),
    )
    bad = base.filter(
        pl.col("order_line_id").is_null()
        | (pl.col("quantity") <= 0)
        | (pl.col("unit_price") < 0)
    )
    good = base.filter(
        pl.col("order_line_id").is_not_null()
        & (pl.col("quantity") > 0)
        & (pl.col("unit_price") >= 0)
    ).unique(subset=["order_line_id"], keep="last")
    return good, bad


def apply_cdc_to_orders(orders: pl.DataFrame, cdc: pl.DataFrame) -> pl.DataFrame:
    """Apply insert/update/delete CDC ops onto a silver orders snapshot."""
    if cdc.is_empty():
        return orders
    # Expand payload-style CDC into order rows
    needed = [
        "order_id",
        "customer_id",
        "order_date",
        "order_status",
        "order_channel",
        "currency_code",
    ]
    for c in needed:
        if c not in cdc.columns:
            cdc = cdc.with_columns(pl.lit(None).alias(c))

    deletes = cdc.filter(pl.col("op") == "D").select("order_id")
    upserts = cdc.filter(pl.col("op").is_in(["I", "U"])).select(needed).unique(
        subset=["order_id"], keep="last"
    )

    base = orders
    if not deletes.is_empty() and not base.is_empty():
        base = base.join(deletes, on="order_id", how="anti")
    if upserts.is_empty():
        return base
    if base.is_empty():
        return upserts
    return (
        pl.concat([base, upserts], how="vertical_relaxed")
        .unique(subset=["order_id"], keep="last")
    )


def write_quarantine(df: pl.DataFrame, path: Path, reason: str) -> Path | None:
    if df.is_empty():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.with_columns(pl.lit(reason).alias("_quarantine_reason"))
    out.write_parquet(path)
    return path
