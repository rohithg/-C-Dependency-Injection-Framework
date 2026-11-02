from __future__ import annotations

from pathlib import Path

import polars as pl


SOURCE_FILES = {
    "customers": "customers.csv",
    "products": "products.csv",
    "orders": "orders.csv",
    "order_lines": "order_lines.csv",
}


SCHEMAS: dict[str, dict[str, pl.DataType]] = {
    "customers": {
        "customer_id": pl.Utf8,
        "customer_name": pl.Utf8,
        "region_name": pl.Utf8,
        "country_code": pl.Utf8,
        "segment": pl.Utf8,
        "is_active": pl.Utf8,
    },
    "products": {
        "product_id": pl.Utf8,
        "product_name": pl.Utf8,
        "product_category": pl.Utf8,
        "brand": pl.Utf8,
        "unit_cost": pl.Float64,
    },
    "orders": {
        "order_id": pl.Utf8,
        "customer_id": pl.Utf8,
        "order_date": pl.Utf8,
        "order_status": pl.Utf8,
        "order_channel": pl.Utf8,
        "currency_code": pl.Utf8,
    },
    "order_lines": {
        "order_line_id": pl.Utf8,
        "order_id": pl.Utf8,
        "product_id": pl.Utf8,
        "quantity": pl.Int64,
        "unit_price": pl.Float64,
        "discount_pct": pl.Float64,
        "tax_amount": pl.Float64,
    },
}


def extract_all(raw_dir: Path) -> dict[str, pl.LazyFrame]:
    """Read raw CSVs as lazy frames with declared schemas."""
    frames: dict[str, pl.LazyFrame] = {}
    for name, filename in SOURCE_FILES.items():
        path = raw_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Missing source {path}. Run: python3 -m retail_etl run --seed"
            )
        frames[name] = pl.scan_csv(
            path,
            schema_overrides=SCHEMAS[name],
            infer_schema_length=0,
        )
    return frames
