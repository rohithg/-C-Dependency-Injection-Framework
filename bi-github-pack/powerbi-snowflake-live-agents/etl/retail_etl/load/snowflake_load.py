from __future__ import annotations

import os
from pathlib import Path

import polars as pl

from retail_etl.config import EtlConfig
from retail_etl.load.local import MART_TABLES


DDL = """
CREATE DATABASE IF NOT EXISTS {database};
CREATE SCHEMA IF NOT EXISTS {database}.{raw_schema};
CREATE SCHEMA IF NOT EXISTS {database}.{marts_schema};

CREATE OR REPLACE TABLE {database}.{raw_schema}.CUSTOMERS (
  customer_id STRING, customer_name STRING, region_name STRING,
  country_code STRING, segment STRING, is_active STRING
);
CREATE OR REPLACE TABLE {database}.{raw_schema}.PRODUCTS (
  product_id STRING, product_name STRING, product_category STRING,
  brand STRING, unit_cost FLOAT
);
CREATE OR REPLACE TABLE {database}.{raw_schema}.ORDERS (
  order_id STRING, customer_id STRING, order_date STRING,
  order_status STRING, order_channel STRING, currency_code STRING
);
CREATE OR REPLACE TABLE {database}.{raw_schema}.ORDER_LINES (
  order_line_id STRING, order_id STRING, product_id STRING,
  quantity NUMBER, unit_price FLOAT, discount_pct FLOAT, tax_amount FLOAT
);

CREATE OR REPLACE TABLE {database}.{marts_schema}.DIM_CUSTOMER (
  customer_sk STRING, customer_id STRING, customer_name STRING,
  region_name STRING, country_code STRING, segment STRING, is_active BOOLEAN
);
CREATE OR REPLACE TABLE {database}.{marts_schema}.DIM_PRODUCT (
  product_sk STRING, product_id STRING, product_name STRING,
  product_category STRING, brand STRING, unit_cost FLOAT
);
CREATE OR REPLACE TABLE {database}.{marts_schema}.DIM_DATE (
  date_sk STRING, date_day DATE, year NUMBER, month NUMBER, quarter NUMBER
);
CREATE OR REPLACE TABLE {database}.{marts_schema}.FCT_ORDERS (
  order_line_sk STRING, order_line_id STRING, order_id STRING,
  customer_sk STRING, customer_id STRING, product_sk STRING, product_id STRING,
  order_date DATE, order_status STRING, order_channel STRING, currency_code STRING,
  region_name STRING, country_code STRING, product_category STRING, product_name STRING,
  quantity NUMBER, unit_price FLOAT, discount_pct FLOAT, tax_amount FLOAT,
  line_net_amount FLOAT, line_cogs FLOAT, line_gross_margin FLOAT
);
"""


def _connect(cfg: EtlConfig):
    import snowflake.connector

    kwargs = {
        "account": os.environ["SF_ACCOUNT"],
        "user": os.environ["SF_USER"],
        "warehouse": cfg.warehouse,
        "database": cfg.database,
        "role": cfg.role,
    }
    if os.getenv("SF_PASSWORD"):
        kwargs["password"] = os.environ["SF_PASSWORD"]
    elif os.getenv("SF_PRIVATE_KEY_PATH"):
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization

        with open(os.environ["SF_PRIVATE_KEY_PATH"], "rb") as f:
            p_key = serialization.load_pem_private_key(
                f.read(),
                password=os.getenv("SF_PRIVATE_KEY_PASSPHRASE", "").encode() or None,
                backend=default_backend(),
            )
        kwargs["private_key"] = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    else:
        raise RuntimeError("Set SF_PASSWORD or SF_PRIVATE_KEY_PATH")
    return snowflake.connector.connect(**kwargs)


def apply_ddl(cfg: EtlConfig) -> None:
    ddl = DDL.format(
        database=cfg.database,
        raw_schema=cfg.raw_schema,
        marts_schema=cfg.marts_schema,
    )
    with _connect(cfg) as conn:
        cur = conn.cursor()
        for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
            cur.execute(stmt)


def load_marts_to_snowflake(
    cfg: EtlConfig, marts: dict[str, pl.DataFrame], stage_dir: Path
) -> None:
    """Load mart DataFrames into Snowflake MARTS tables via temp CSV + PUT/COPY."""
    apply_ddl(cfg)
    stage_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "dim_customer": f"{cfg.database}.{cfg.marts_schema}.DIM_CUSTOMER",
        "dim_product": f"{cfg.database}.{cfg.marts_schema}.DIM_PRODUCT",
        "dim_date": f"{cfg.database}.{cfg.marts_schema}.DIM_DATE",
        "fct_orders": f"{cfg.database}.{cfg.marts_schema}.FCT_ORDERS",
    }
    with _connect(cfg) as conn:
        cur = conn.cursor()
        cur.execute(f"USE WAREHOUSE {cfg.warehouse}")
        for name in MART_TABLES:
            table = mapping[name]
            csv_path = stage_dir / f"{name}.csv"
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            marts[name].write_csv(csv_path)
            cur.execute(f"TRUNCATE TABLE IF EXISTS {table}")
            cur.execute(f"PUT file://{csv_path.resolve()} @~/etl_stage/{name} OVERWRITE=TRUE")
            cur.execute(
                f"""
                COPY INTO {table}
                FROM @~/etl_stage/{name}
                FILE_FORMAT=(TYPE=CSV SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"')
                FORCE=TRUE
                """
            )


def write_snowflake_sql_bundle(cfg: EtlConfig, sql_dir: Path) -> Path:
    sql_dir.mkdir(parents=True, exist_ok=True)
    path = sql_dir / "01_etl_ddl.sql"
    path.write_text(
        DDL.format(
            database=cfg.database,
            raw_schema=cfg.raw_schema,
            marts_schema=cfg.marts_schema,
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def apply_powerbi_views(cfg: EtlConfig, views_sql_dir: Path) -> None:
    """Execute secure view DDL used by the live Power BI pack."""
    files = sorted(views_sql_dir.glob("*.sql"))
    if not files:
        raise FileNotFoundError(f"No view SQL in {views_sql_dir}")
    with _connect(cfg) as conn:
        cur = conn.cursor()
        cur.execute(f"USE DATABASE {cfg.database}")
        cur.execute(f"USE SCHEMA {cfg.marts_schema}")
        cur.execute(f"USE WAREHOUSE {cfg.warehouse}")
        for path in files:
            sql = path.read_text(encoding="utf-8")
            cur.execute(sql)
