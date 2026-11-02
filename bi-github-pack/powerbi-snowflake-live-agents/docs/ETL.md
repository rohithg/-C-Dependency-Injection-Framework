# ETL workflow (start → finish)

Language: **Python + Polars** (fast columnar ETL; Snowflake connector optional for load).

## Stages

1. **Seed / Extract** — `data/raw/*.csv` (customers, products, orders, order_lines)
2. **Transform** — type cast, strip, dedupe, filter bad rows, surrogate keys, fact enrichment (net / COGS / margin)
3. **Load (local)** — Snappy Parquet marts under `data/out/parquet/` + `quality_summary.json`
4. **Load (Snowflake)** — DDL + PUT/COPY into `ANALYTICS.MARTS.*` when `--load-snowflake` + `SF_*` env
5. **Serve** — secure views `VW_*` → Power BI DirectQuery PBIP

## Commands

```bash
cd etl
pip install -r requirements.txt
python3 -m retail_etl run --seed
python3 -m retail_etl run --seed --load-snowflake   # needs SF_ACCOUNT, SF_USER, SF_PASSWORD or key
python3 -m retail_etl apply-views                   # after load
python3 -m pytest tests/ -q
```

## Outputs

| Artifact | Purpose |
|--|--|
| `dim_customer.parquet` | Customer dimension |
| `dim_product.parquet` | Product dimension |
| `dim_date.parquet` | Date dimension |
| `fct_orders.parquet` | Order-line fact for revenue |
| `sql/01_etl_ddl.sql` | Snowflake DDL mirror |
| `quality_summary.json` | Row counts + net revenue check |
