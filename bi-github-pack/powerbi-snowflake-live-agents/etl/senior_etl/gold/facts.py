from __future__ import annotations

import polars as pl


def build_transactional_fact(lines: pl.DataFrame, orders: pl.DataFrame) -> pl.DataFrame:
    return (
        lines.join(orders, on="order_id", how="inner")
        .with_columns(
            (
                pl.col("quantity") * pl.col("unit_price") * (1.0 - pl.col("discount_pct").fill_null(0.0))
            ).alias("line_net_amount"),
            pl.col("order_date").alias("event_date"),
        )
    )


def build_accumulating_snapshot(orders: pl.DataFrame) -> pl.DataFrame:
    """
    Accumulating snapshot fact: one row per order, milestones fill in over time.
    Measures pipeline latency between promise → ship → deliver.
    """
    if orders.is_empty():
        return orders
    return orders.with_columns(
        pl.when(pl.col("actual_ship_date").is_not_null() & pl.col("promised_ship_date").is_not_null())
        .then(
            (pl.col("actual_ship_date") - pl.col("promised_ship_date"))
            .dt.total_days()
        )
        .otherwise(None)
        .alias("ship_delay_days"),
        pl.when(pl.col("delivered_date").is_not_null() & pl.col("actual_ship_date").is_not_null())
        .then((pl.col("delivered_date") - pl.col("actual_ship_date")).dt.total_days())
        .otherwise(None)
        .alias("transit_days"),
        pl.when(pl.col("delivered_date").is_not_null())
        .then(pl.lit("DELIVERED"))
        .when(pl.col("actual_ship_date").is_not_null())
        .then(pl.lit("SHIPPED"))
        .otherwise(pl.col("order_status"))
        .alias("pipeline_status"),
    )


def build_periodic_snapshot(fact: pl.DataFrame, as_of) -> pl.DataFrame:
    """Periodic snapshot: balances/KPI as of a date grain (daily region)."""
    if fact.is_empty():
        return pl.DataFrame()
    return (
        fact.group_by(["event_date", "region_name", "currency_code"])
        .agg(
            pl.col("line_net_amount_usd").sum().alias("net_revenue_usd"),
            pl.col("order_id").n_unique().alias("orders"),
            pl.col("order_line_id").count().alias("lines"),
        )
        .with_columns(pl.lit(as_of).alias("snapshot_as_of"))
        .sort(["event_date", "region_name"])
    )
