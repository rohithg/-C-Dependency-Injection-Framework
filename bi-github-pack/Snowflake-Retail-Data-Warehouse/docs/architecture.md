# Architecture — Snowflake Retail Data Warehouse

## Overview

This project implements an **ELT** pattern for retail and supply-chain analytics:

1. **Extract / Load** operational data from ERP (NetSuite), CRM, TMS, and YMS into Snowflake `RAW` tables.
2. **Transform** with **dbt** through staging → intermediate → marts (star schema).
3. **Orchestrate** the daily cycle with **Airflow**.

## ELT flow

```mermaid
flowchart TB
    subgraph sources [Operational Sources]
        NS[NetSuite ERP / Finance]
        CRM[CRM Customer Master]
        TMS[TMS Shipments]
        YMS[YMS Locations / Yard]
    end

    subgraph snowflake [Snowflake]
        RAW[(RAW Landing<br/>raw_customers, raw_orders,<br/>raw_products, raw_invoices,<br/>raw_shipments, raw_locations)]
        STG[Staging Views<br/>stg_*]
        INT[Intermediate Views<br/>int_*]
        MARTS[(Marts / Star Schema<br/>dim_* + fct_*)]
    end

    subgraph orch [Orchestration]
        AF[Airflow DAG<br/>retail_elt_daily]
        DBT[dbt run / test / docs]
    end

    NS --> RAW
    CRM --> RAW
    TMS --> RAW
    YMS --> RAW

    AF -->|extract stub / COPY INTO| RAW
    AF --> DBT
    DBT --> STG
    STG --> INT
    INT --> MARTS
    DBT -->|dbt test| MARTS
```

## Layering

| Layer | Schema | Materialization | Responsibility |
|-------|--------|-----------------|----------------|
| Raw | `raw` | Tables (load / seed) | Immutable landing; 1:1 with source extracts |
| Staging | `staging` | Views | Rename, type cast, dedupe, light enrichment |
| Intermediate | `intermediate` | Views | Business joins, margin / dwell / AR logic |
| Marts | `marts` | Tables | Conformed dimensions + facts for BI |

## Star schema

```mermaid
erDiagram
    dim_customer ||--o{ fct_orders : customer_sk
    dim_product ||--o{ fct_orders : product_sk
    dim_date ||--o{ fct_orders : order_date_sk
    dim_location ||--o{ fct_orders : ship_from_to

    dim_customer ||--o{ fct_shipments : customer_sk
    dim_date ||--o{ fct_shipments : ship_delivery_dates
    dim_location ||--o{ fct_shipments : origin_dest

    dim_customer ||--o{ fct_finance : customer_sk
    dim_date ||--o{ fct_finance : invoice_due_paid

    fct_orders ||--o| fct_shipments : order_id
    fct_orders ||--o| fct_finance : order_id
```

### Fact grains

- **fct_orders** — one row per sales order line
- **fct_shipments** — one row per TMS shipment (with YMS dwell)
- **fct_finance** — one row per AR invoice

### Dimensions

- **dim_customer**, **dim_product**, **dim_location** — conformed entities
- **dim_date** — calendar + fiscal attributes (fiscal year starts in February)

## Data quality

dbt tests (unique, not_null, relationships, accepted_values) gate every DAG run after `dbt run`. Failed tests fail the Airflow task and block docs refresh.

## Local vs Snowflake

| Mode | Profile target | Notes |
|------|----------------|-------|
| Production | `snowflake` | Use `sql/ddl/raw_landing_tables.sql`, real extract, Airflow |
| Local demo | `duckdb` | `dbt seed && dbt run --target duckdb` (see README) |

Models intentionally avoid Snowflake-only syntax where practical so the same project can smoke-test on DuckDB.
