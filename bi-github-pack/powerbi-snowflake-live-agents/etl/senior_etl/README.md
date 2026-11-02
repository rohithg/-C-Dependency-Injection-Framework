# Senior Data Engineer ETL Platform

Enterprise-grade pipeline a senior DE would own in production:

- **Data contracts** + schema registry (breaking-change detection)
- **Idempotent micro-batches** with batch control table
- **Checksums / row hashes** for exactly-once style merges
- **SCD2 + point-in-time (PIT)** temporal joins
- **Late-arriving dimensions** (inferred members)
- **Multiple fact styles**: transactional, accumulating snapshot, periodic snapshot
- **PII masking** + audit events
- **Volume anomaly gates** + SLA/circuit-breaker
- **Replay / backfill** by `batch_id`
- Fan-out DAG with retries

```bash
cd bi-github-pack/powerbi-snowflake-live-agents/etl
pip install -r requirements.txt
python3 -m senior_etl seed
python3 -m senior_etl run
python3 -m senior_etl replay --batch-id <id>   # reprocess one batch idempotently
python3 -m pytest senior_etl/tests -q
```

Full step-by-step: [../../docs/SENIOR_ETL_WALKTHROUGH.md](../../docs/SENIOR_ETL_WALKTHROUGH.md)
