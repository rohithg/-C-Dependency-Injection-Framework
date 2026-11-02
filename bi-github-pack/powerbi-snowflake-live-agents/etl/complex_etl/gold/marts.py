from __future__ import annotations

import polars as pl


def build_fct_orders(
    order_lines: pl.DataFrame,
    orders: pl.DataFrame,
    customers_current: pl.DataFrame,
    products_current: pl.DataFrame,
    fx: pl.DataFrame,
) -> pl.DataFrame:
    """Gold fact: order lines enriched with SCD2 current dims + FX to USD."""
    if order_lines.is_empty() or orders.is_empty():
        return pl.DataFrame()

    cust = customers_current.select(
        "customer_nk",
        pl.col("surrogate_key").alias("customer_sk"),
        "region_name",
        "country_code",
        "segment",
        "credit_tier",
    )
    prod = products_current.select(
        "product_nk",
        pl.col("surrogate_key").alias("product_sk"),
        "product_name",
        "product_category",
        "brand",
        "unit_cost",
    )

    fact = (
        order_lines.join(orders, on="order_id", how="inner")
        .join(cust, on="customer_nk", how="left")
        .join(prod, on="product_nk", how="left")
        .filter(~pl.col("order_status").is_in(["CANCELLED", "VOID"]))
        .with_columns(
            (
                pl.col("quantity")
                * pl.col("unit_price")
                * (1.0 - pl.col("discount_pct"))
            ).alias("line_net_amount"),
            (pl.col("quantity") * pl.col("unit_cost").fill_null(0.0)).alias("line_cogs"),
            pl.col("order_date").alias("order_day"),
            pl.col("order_date").dt.strftime("%Y-%m").alias("order_month"),
        )
        .with_columns(
            (pl.col("line_net_amount") - pl.col("line_cogs")).alias("line_gross_margin"),
        )
    )

    if not fx.is_empty():
        fx2 = fx.with_columns(
            pl.col("as_of_date").str.to_date(strict=False).alias("fx_date"),
            pl.col("from_currency").alias("currency_code"),
            pl.col("rate").alias("fx_to_usd"),
        ).select("fx_date", "currency_code", "fx_to_usd").sort("fx_date")
        # as-of: latest FX rate on or before order_date per currency
        fact = fact.sort("order_date").join_asof(
            fx2,
            left_on="order_date",
            right_on="fx_date",
            by="currency_code",
            strategy="backward",
        ).with_columns(
            pl.when(pl.col("currency_code") == "USD")
            .then(1.0)
            .otherwise(pl.col("fx_to_usd"))
            .fill_null(1.0)
            .alias("fx_to_usd")
        )
    else:
        fact = fact.with_columns(pl.lit(1.0).alias("fx_to_usd"))

    return fact.with_columns(
        (pl.col("line_net_amount") * pl.col("fx_to_usd")).alias("line_net_amount_usd"),
        (pl.col("line_gross_margin") * pl.col("fx_to_usd")).alias("line_gross_margin_usd"),
        pl.col("order_line_id").hash(seed=11).cast(pl.Utf8).alias("order_line_sk"),
    )


def build_order_product_bridge(fact: pl.DataFrame) -> pl.DataFrame:
    if fact.is_empty():
        return pl.DataFrame()
    return (
        fact.select("order_id", "product_nk", "product_sk", "quantity", "line_net_amount_usd")
        .group_by(["order_id", "product_nk", "product_sk"])
        .agg(
            pl.col("quantity").sum().alias("quantity"),
            pl.col("line_net_amount_usd").sum().alias("net_usd"),
        )
    )


def build_daily_region_agg(fact: pl.DataFrame) -> pl.DataFrame:
    if fact.is_empty():
        return pl.DataFrame()
    return (
        fact.group_by(["order_day", "region_name", "currency_code"])
        .agg(
            pl.col("line_net_amount_usd").sum().alias("net_revenue_usd"),
            pl.col("line_gross_margin_usd").sum().alias("gross_margin_usd"),
            pl.col("order_id").n_unique().alias("order_count"),
            pl.col("order_line_id").count().alias("line_count"),
        )
        .sort(["order_day", "region_name"])
    )


def build_monthly_category_agg(fact: pl.DataFrame) -> pl.DataFrame:
    if fact.is_empty():
        return pl.DataFrame()
    return (
        fact.group_by(["order_month", "product_category"])
        .agg(
            pl.col("line_net_amount_usd").sum().alias("net_revenue_usd"),
            pl.col("quantity").sum().alias("units"),
        )
        .sort(["order_month", "product_category"])
    )
