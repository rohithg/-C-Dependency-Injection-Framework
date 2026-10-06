# Complex Retail ETL Platform

A production-style **medallion** pipeline (Bronze → Silver → Gold) with DAG orchestration, CDC, SCD2, DQ gates, watermarks, quarantine, and lineage — implemented in **Python + Polars**.

```text
┌──────────── sources ────────────┐
│ CSV · JSON · paginated API mock │
│ CDC change log (insert/update)  │
└──────────────┬──────────────────┘
               ▼
        ┌─ BRONZE ─┐  land as-is + ingest metadata + partitions
               ▼
        ┌─ SILVER ─┐  clean · quarantine · SCD2 dims · late facts
               ▼
     ┌── DQ GATES ──┐  block / warn / quarantine by rule severity
               ▼
        ┌─ GOLD ───┐  star facts · bridges · rollups · KPI marts
               ▼
     Parquet lake (+ optional Snowflake) → Power BI views
```

```bash
cd bi-github-pack/powerbi-snowflake-live-agents/etl
pip install -r requirements.txt
python3 -m complex_etl seed
python3 -m complex_etl run
python3 -m pytest complex_etl/tests -q
```

See [COMPLEX_ETL.md](../docs/COMPLEX_ETL.md) for a full walkthrough.
