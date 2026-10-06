# Architecture — live drill-down

```text
┌─────────────────┐     CREATE VIEW      ┌──────────────────────┐
│ Cursor agents   │ ───────────────────► │ Snowflake            │
│ + generator CLI │                      │  VW_* presentation   │
└────────┬────────┘                      └──────────┬───────────┘
         │ PBIP TMDL + PBIR                          │ DirectQuery SQL
         ▼                                           ▼
┌─────────────────┐                      ┌──────────────────────┐
│ Power BI Desktop│ ── publish ────────► │ Power BI Service     │
│ / Fabric        │                      │ Report + Sem. model  │
└─────────────────┘                      └──────────────────────┘
```

## Drill path

Overview page uses an aggregate view (cheap). Right-click → drillthrough page filters a grain view (order line / customer).

## Why views

- Stable contract for BI while dbt/ELT tables evolve
- Secure views + grants for least privilege
- Same SQL callable from agents, dbt exposures, and Power BI
