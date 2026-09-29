# Architecture

```
ADLS Gen2 (bronze CSV/Parquet)
    │  ADF Copy + trigger Databricks job
    ▼
Databricks (silver Delta / optional Iceberg)
    │  optimize, ZORDER, AQE
    ▼
Gold marts → Synapse serverless / Power BI DirectQuery
```

**Optimization levers demonstrated in code:** partition pruning, broadcast joins for accounts dim, AQE, coalesce for small-file control, predicate pushdown on event_ts.
