# Snowflake Retail Data Warehouse

[![dbt](https://img.shields.io/badge/dbt-ORM-FF694B?logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?logo=snowflake&logoColor=white)](https://www.snowflake.com/)
[![Airflow](https://img.shields.io/badge/Airflow-017CEE?logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Production-style **ELT** project for retail and supply-chain analytics on **Snowflake**, transformed with **dbt**, and orchestrated with **Airflow**.

Built by **[Rohith Gangapuram](https://github.com/rohithg)** to demonstrate end-to-end dimensional modeling across ERP / CRM / logistics sources (NetSuite-style orders & invoices, TMS shipments, YMS locations).

**Validated locally:** `dbt seed` → `dbt run` → `dbt test` (**105/105 PASS** on DuckDB target).

---

## Overview

Operational systems land in Snowflake `RAW`. dbt cleans and conforms that data into a **star schema** for order, shipment, and finance analytics:

| Layer | What you get |
|-------|----------------|
| Staging | Typed, deduped `stg_*` models from `source()` |
| Intermediate | Margin, on-time delivery, AR bridge logic |
| Marts | `dim_customer`, `dim_product`, `dim_date`, `dim_location`, `fct_orders`, `fct_shipments`, `fct_finance` |

Sample seeds (~75–240 rows per entity) make the project runnable without live connectors.

## Architecture

```text
NetSuite / CRM / TMS / YMS
        │  Airflow stage + COPY INTO RAW
        ▼
   Snowflake RAW
        │  dbt seed (demo) / dbt run
        ▼
 staging → intermediate → marts (star schema)
        │  dbt test → dbt docs
        ▼
     BI / analysts
```

See [docs/architecture.md](docs/architecture.md) for Mermaid diagrams of the ELT flow and star schema.

## Project layout

```text
├── airflow/dags/retail_elt_dag.py   # daily ELT DAG
├── docs/architecture.md
├── macros/                          # surrogate keys, schema naming, finance helpers
├── models/
│   ├── staging/                     # stg_* + sources.yml
│   ├── intermediate/                # business joins
│   └── marts/core/                  # dimensions + facts + tests
├── seeds/                           # raw_* sample CSVs
├── sql/ddl/raw_landing_tables.sql   # Snowflake RAW DDL
├── dbt_project.yml
├── packages.yml
└── profiles.yml.example
```

## How to run

### Prerequisites

- Python 3.9+
- [dbt-core](https://docs.getdbt.com/) **≥ 1.7** with either:
  - **`dbt-snowflake`** (primary), or
  - **`dbt-duckdb`** (local smoke test)
- Optional: Airflow 2.x for orchestration

### 1. Configure profile

```bash
cp profiles.yml.example ~/.dbt/profiles.yml
# set SNOWFLAKE_* env vars, or switch target to duckdb for local runs
```

**Snowflake (preferred)** — create objects first:

```bash
# in a Snowflake worksheet / snowsql
!source sql/ddl/raw_landing_tables.sql
```

**DuckDB (local note)** — no cloud warehouse required:

```bash
pip install dbt-core dbt-duckdb
export DBT_PROFILES_DIR=$PWD   # after copying profiles.yml.example → profiles.yml
```

Edit `profiles.yml` so `target: duckdb` (or pass `--target duckdb`). Custom schemas (`raw`, `staging`, `marts`, …) are preserved via `generate_schema_name` so `source()` resolves to seed tables.

### 2. Install packages, seed, run, test

```bash
dbt deps
dbt seed
dbt run
dbt test
dbt docs generate && dbt docs serve
```

Expected marts after a successful run: four dimensions and three facts under the `marts` schema.

### 3. Optional — Airflow

Point Airflow Variables (or defaults in the DAG) at this repo:

| Variable | Purpose |
|----------|---------|
| `retail_dbt_project_dir` | Path to this project on the worker |
| `retail_dbt_profiles_dir` | Directory containing `profiles.yml` |
| `retail_dbt_target` | `snowflake` or `duckdb` |

Copy `airflow/dags/retail_elt_dag.py` into your `dags/` folder. The DAG runs daily at 06:00 UTC:

`stage+COPY INTO RAW → dbt deps → dbt seed → dbt run → dbt test → dbt snapshot → dbt docs`

The Airflow DAG stages CSVs and runs `sql/load/01_copy_into_raw.sql`. Swap the file source for Snowpipe, Fivetran, or Airbyte in production; keep dbt for transforms, tests, and snapshots.

## Skills demonstrated

- **dbt** — sources, refs, staging/intermediate/marts layering, macros, packages (`dbt_utils`), documentation
- **Snowflake** — RAW landing DDL, warehouse/schema layout, ELT-oriented design
- **Airflow** — scheduled DAG with extract → transform → test → docs task chain
- **Dimensional modeling** — retail/supply-chain star schema (orders, shipments, finance)
- **Data quality** — `unique`, `not_null`, `relationships`, `accepted_values` tests on critical columns

## Author

**Rohith Gangapuram**  
GitHub: [github.com/rohithg](https://github.com/rohithg)

---

Licensed for portfolio and educational use. Adapt freely for your own Snowflake + dbt environments.


## Custom tests, analyses & snapshots

| Path | Purpose |
|--|--|
| `tests/assert_*.sql` | Singular tests: margin reconcile, shipment dates, AR positivity, customer FK |
| `analyses/otif_by_region.sql` | Ops OTIF by origin region |
| `analyses/margin_by_channel.sql` | Gross margin by order channel |
| `analyses/ar_aging_buckets.sql` | Finance AR aging (matches Command Center buckets) |
| `snapshots/snap_dim_customer.sql` | SCD2 history for customer credit/status |
| `sql/load/01_copy_into_raw.sql` | Production-shaped COPY INTO from stage |
