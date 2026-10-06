# Live Power BI drill-down agents (Snowflake DirectQuery)

Agents + generator that produce **live** Power BI dashboards: Snowflake **views** → PBIP **DirectQuery** semantic model → PBIR **drillthrough** report pages.

## What you get

| Piece | Role |
|--|--|
| `.cursor/agents/*` | Cursor subagents: orchestrator, Snowflake views, TMDL model, PBIR drilldown |
| `generator/` | Manifest → Snowflake DDL + PBIP project |
| `snowflake/views/` | Reference drill-ready views |
| `examples/revenue-drilldown/` | End-to-end sample (Region → Product → Customer) |
| `docs/CONNECTIONS.md` | Composio / Desktop / Service auth |

## Quick start

```bash
cd bi-github-pack/powerbi-snowflake-live-agents
pip install -r requirements.txt
python3 -m generator.cli generate --manifest examples/revenue-drilldown/manifest.yaml
python3 -m pytest tests/ -q
```

### End-to-end ETL (Python + Polars)

Simple retail ETL:

```bash
cd etl
pip install -r requirements.txt
python3 -m retail_etl run --seed
```

**Complex medallion platform** (CDC · SCD2 · DQ gates · lineage):

```bash
cd etl
python3 -m complex_etl seed
python3 -m complex_etl run
python3 -m pytest complex_etl/tests -q
```

**Senior / enterprise platform** (contracts · PIT · idempotent batches · anomaly/SLA · replay):

```bash
cd etl
python3 -m senior_etl seed
python3 -m senior_etl run --batch-id batch_demo_001
python3 -m senior_etl replay --batch-id batch_demo_001
python3 -m pytest senior_etl/tests -q
```

Details: [docs/SENIOR_ETL_WALKTHROUGH.md](docs/SENIOR_ETL_WALKTHROUGH.md) · [docs/COMPLEX_ETL.md](docs/COMPLEX_ETL.md) · [docs/ETL.md](docs/ETL.md)

Open the generated `.pbip` in Power BI Desktop, sign in to Snowflake, then publish. Queries run live on every visual interaction (DirectQuery).

## Agent usage in Cursor

Ask:

> Use the live-dashboard-orchestrator to build a live drill-down Power BI dashboard on Snowflake views for revenue by Region → Product → Customer.

Or invoke specialists directly: `/snowflake-view-designer`, `/powerbi-semantic-model`, `/powerbi-drilldown-report`.

## Live vs Import

This pack **defaults to DirectQuery**. Power BI sends SQL to Snowflake when users open a page, change slicers, cross-filter, or drill through — no scheduled refresh for fact data.

## Connections

Composio apps need custom auth configs (not one-click OAuth):

- [Set up Snowflake](https://dashboard.composio.dev/~/org/connect/apps/snowflake?open=true)
- [Set up Power BI](https://dashboard.composio.dev/~/org/connect/apps/microsoft_power_bi?open=true)

Details: [docs/CONNECTIONS.md](docs/CONNECTIONS.md).

## Resume / portfolio signal

BI Architect · Analytics Engineer — agentic PBIP generation, Snowflake presentation views, live DirectQuery drill-down.
