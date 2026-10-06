# Retail ETL — Python + Polars → Snowflake → Power BI

End-to-end **Extract → Transform → Load** pipeline that feeds the live DirectQuery Power BI views in this pack.

## Why Python + Polars

| Choice | Why |
|--|--|
| **Python** | Best fit for Snowflake connectors, agent tooling, CI, and this repo’s generator |
| **Polars** | Columnar, lazy plans, much faster/leaner than pandas for multi-million-row transforms |
| **Parquet staging** | Cheap local lake + Snowflake `COPY INTO` without reinventing Spark |

## Pipeline

```text
data/raw/*.csv  ──extract──►  LazyFrames
                              │
                         transform (types, DQ, keys, marts)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
     data/out/parquet/                 Snowflake RAW → MARTS
     (always, dry-run OK)              (when SF_* env set)
              │                               │
              └──────────► VW_* views ───────► Power BI DirectQuery
```

## Quick start (no Snowflake required)

```bash
cd bi-github-pack/powerbi-snowflake-live-agents/etl
pip install -r requirements.txt
python3 -m retail_etl run --seed   # writes sample raw if missing
python3 -m retail_etl run          # full ETL → parquet marts
python3 -m pytest tests/ -q
```

Outputs land in `data/out/parquet/` (`dim_customer`, `dim_product`, `fct_orders`, …).

## With Snowflake

```bash
export SF_ACCOUNT=... SF_USER=... SF_PASSWORD=...   # or key-pair
export SF_WAREHOUSE=BI_WH SF_DATABASE=ANALYTICS SF_SCHEMA=RAW SF_ROLE=SYSADMIN
python3 -m retail_etl run --load-snowflake
python3 -m retail_etl apply-views   # create MARTS + Power BI secure views
```

## Stages

1. **Extract** — CSV (and optional HTTP) sources with schema contracts  
2. **Transform** — cast, null policy, duplicate drop, surrogate keys, order-line facts + dims  
3. **Load** — Parquet always; Snowflake PUT/COPY + MERGE when configured  

See `docs` in the parent pack for Power BI connection steps.
