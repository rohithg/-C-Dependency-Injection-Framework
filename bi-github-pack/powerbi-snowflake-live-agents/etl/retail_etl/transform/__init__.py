from __future__ import annotations

import polars as pl


def _surrogate(col: str, alias: str) -> pl.Expr:
    """Fast vectorized surrogate key (stable within an engine run)."""
    return pl.col(col).hash(seed=42).cast(pl.Utf8).alias(alias)


def transform(frames: dict[str, pl.LazyFrame]) -> dict[str, pl.DataFrame]:
    """Clean sources and build dim/fact marts with lazy Polars plans."""
    customers = (
        frames["customers"]
        .with_columns(
            pl.col("customer_id").str.strip_chars(),
            pl.col("customer_name").str.strip_chars(),
            pl.col("region_name").str.strip_chars().str.to_titlecase(),
            pl.col("country_code").str.strip_chars().str.to_uppercase(),
            pl.col("segment").str.strip_chars().str.to_uppercase(),
            (pl.col("is_active").str.to_lowercase().is_in(["1", "true", "y", "yes"])).alias(
                "is_active"
            ),
        )
        .filter(pl.col("customer_id").is_not_null() & (pl.col("customer_id") != ""))
        .unique(subset=["customer_id"], keep="last")
    )

    products = (
        frames["products"]
        .with_columns(
            pl.col("product_id").str.strip_chars(),
            pl.col("product_name").str.strip_chars(),
            pl.col("product_category").str.strip_chars(),
            pl.col("brand").str.strip_chars(),
            pl.col("unit_cost").cast(pl.Float64).fill_null(0.0),
        )
        .filter(pl.col("product_id").is_not_null())
        .unique(subset=["product_id"], keep="last")
    )

    orders = (
        frames["orders"]
        .with_columns(
            pl.col("order_id").str.strip_chars(),
            pl.col("customer_id").str.strip_chars(),
            pl.col("order_date").str.to_datetime(strict=False).dt.date().alias("order_date"),
            pl.col("order_status").str.strip_chars().str.to_uppercase(),
            pl.col("order_channel").str.strip_chars().str.to_titlecase(),
            pl.col("currency_code").str.strip_chars().str.to_uppercase(),
        )
        .filter(pl.col("order_id").is_not_null())
        .unique(subset=["order_id"], keep="last")
    )

    order_lines = (
        frames["order_lines"]
        .with_columns(
            pl.col("order_line_id").str.strip_chars(),
            pl.col("order_id").str.strip_chars(),
            pl.col("product_id").str.strip_chars(),
            pl.col("quantity").cast(pl.Int64),
            pl.col("unit_price").cast(pl.Float64),
            pl.col("discount_pct").cast(pl.Float64).fill_null(0.0),
            pl.col("tax_amount").cast(pl.Float64).fill_null(0.0),
        )
        .filter(
            pl.col("order_line_id").is_not_null()
            & (pl.col("quantity") > 0)
            & (pl.col("unit_price") >= 0)
        )
        .unique(subset=["order_line_id"], keep="last")
    )

    dim_customer = customers.with_columns(_surrogate("customer_id", "customer_sk")).select(
        "customer_sk",
        "customer_id",
        "customer_name",
        "region_name",
        "country_code",
        "segment",
        "is_active",
    )

    dim_product = products.with_columns(_surrogate("product_id", "product_sk")).select(
        "product_sk",
        "product_id",
        "product_name",
        "product_category",
        "brand",
        "unit_cost",
    )

    fct_orders = (
        order_lines.join(orders, on="order_id", how="inner")
        .join(
            dim_customer.select(
                "customer_id", "customer_sk", "region_name", "country_code"
            ),
            on="customer_id",
            how="inner",
        )
        .join(
            dim_product.select(
                "product_id",
                "product_sk",
                "unit_cost",
                "product_category",
                "product_name",
            ),
            on="product_id",
            how="inner",
        )
        .with_columns(
            (
                pl.col("quantity")
                * pl.col("unit_price")
                * (1.0 - pl.col("discount_pct"))
            ).alias("line_net_amount"),
            (pl.col("quantity") * pl.col("unit_cost")).alias("line_cogs"),
            _surrogate("order_line_id", "order_line_sk"),
        )
        .with_columns(
            (pl.col("line_net_amount") - pl.col("line_cogs")).alias("line_gross_margin"),
        )
        .filter(~pl.col("order_status").is_in(["CANCELLED", "VOID"]))
        .select(
            "order_line_sk",
            "order_line_id",
            "order_id",
            "customer_sk",
            "customer_id",
            "product_sk",
            "product_id",
            "order_date",
            "order_status",
            "order_channel",
            "currency_code",
            "region_name",
            "country_code",
            "product_category",
            "product_name",
            "quantity",
            "unit_price",
            "discount_pct",
            "tax_amount",
            "line_net_amount",
            "line_cogs",
            "line_gross_margin",
        )
    )

    dim_date = (
        fct_orders.select(pl.col("order_date").alias("date_day"))
        .unique()
        .drop_nulls()
        .with_columns(
            pl.col("date_day").dt.strftime("%Y%m%d").alias("date_sk"),
            pl.col("date_day").dt.year().alias("year"),
            pl.col("date_day").dt.month().alias("month"),
            pl.col("date_day").dt.quarter().alias("quarter"),
        )
        .sort("date_day")
    )

    # Single collect boundary for the whole mart graph
    collected = pl.collect_all(
        [dim_customer, dim_product, dim_date, fct_orders, customers, products, orders, order_lines]
    )
    return {
        "dim_customer": collected[0],
        "dim_product": collected[1],
        "dim_date": collected[2],
        "fct_orders": collected[3],
        "raw_customers_clean": collected[4],
        "raw_products_clean": collected[5],
        "raw_orders_clean": collected[6],
        "raw_order_lines_clean": collected[7],
    }
