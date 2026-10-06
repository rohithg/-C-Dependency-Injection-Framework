# Agents — live Power BI on Snowflake

This folder is designed for Cursor agents that generate **live DirectQuery** Power BI dashboards from Snowflake views.

## Subagents (repo root `.cursor/agents/`)

| Agent | Job |
|--|--|
| `live-dashboard-orchestrator` | End-to-end pipeline |
| `snowflake-view-designer` | Secure views + grants |
| `powerbi-semantic-model` | TMDL DirectQuery model |
| `powerbi-drilldown-report` | PBIR overview + drillthrough |

## Commands

```bash
pip install -r requirements.txt
python3 -m generator.cli validate --manifest examples/revenue-drilldown/manifest.yaml
python3 -m generator.cli generate --manifest examples/revenue-drilldown/manifest.yaml --clean
python3 -m pytest tests/ -q
```

## Auth

See `docs/CONNECTIONS.md`. Composio Snowflake + Power BI require custom auth configs before agents can execute live DDL / workspace APIs.
