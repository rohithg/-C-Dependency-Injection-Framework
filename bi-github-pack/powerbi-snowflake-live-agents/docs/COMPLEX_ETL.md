# Complex ETL walkthrough

This pack’s **complex** pipeline is a miniature data platform: medallion layers, a DAG orchestrator, CDC, SCD Type 2, data-quality gates, quarantine, watermarks, and lineage — all in **Python + Polars**.

## Architecture

```text
Sources
  ├─ CSV snapshots (customers day1/day2, products, orders, lines)
  ├─ JSON (order↔promo bridge)
  ├─ Paginated FX API mock (multi-currency → USD)
  └─ CDC JSONL (I/U/D on orders)
        │
        ▼
BRONZE  append-only land with _ingest_run_id / _source_system / partitions
        │
        ▼
SILVER  clean + quarantine bad rows
        apply CDC to orders
        SCD2 dimensions (history + is_current)
        │
        ▼
GOLD    fct_orders (FX to USD) · bridges · daily/monthly rollups
        │
        ▼
DQ GATES  not_null · unique · positive · accepted_values · referential · row_count
        orphans → quarantine, clean fact republished
        │
        ▼
REPORT  run JSON · DQ JSON · lineage graph · watermarks
```

## DAG tasks (in order)

1. `extract_land_bronze` — multi-source extract + bronze land + watermark bump  
2. `silver_clean_cdc` — validate/clean + CDC merge + quarantine  
3. `silver_scd2` — customer day1→day2 history, product current versions  
4. `gold_marts` — fact, bridges, aggregates  
5. `dq_gates` — enforce rules; fail run on error severity  
6. `emit_report` — lineage + run summary  

## Why it’s “complex”

| Capability | What it does here |
|--|--|
| Medallion | Separate bronze/silver/gold lakes |
| Multi-source | CSV + JSON + API pages + CDC log |
| CDC | Incremental I/U/D into orders |
| SCD2 | Close/open dimension versions on attribute change |
| Quarantine | Bad/orphan rows isolated, not silently dropped |
| DQ gates | Configurable rules with error vs warn |
| Watermarks | Persist CDC/API high-water marks across runs |
| Lineage | Edge list source→target transforms |
| Orchestration | Dependency DAG + retries |
| FX enrichment | Convert EUR/GBP lines to USD for gold KPIs |

## Run

```bash
cd bi-github-pack/powerbi-snowflake-live-agents/etl
python3 -m complex_etl seed
python3 -m complex_etl run
python3 -m pytest complex_etl/tests -q
```

Outputs:
- `complex_etl/data/lake/{bronze,silver,gold,quarantine}/`
- `complex_etl/data/reports/latest_run.json`
- `complex_etl/data/state/watermarks.json`
