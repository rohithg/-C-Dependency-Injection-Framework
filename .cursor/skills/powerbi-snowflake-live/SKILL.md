---
name: powerbi-snowflake-live
description: Build live DirectQuery Power BI drill-down dashboards from Snowflake views using manifests, TMDL, and PBIR. Use when creating Power BI + Snowflake live BI agents or PBIP projects.
---

# Power BI + Snowflake live drill-down

## Workflow

1. Write or edit a dashboard `manifest.yaml` (tables → Snowflake views, pages with overview + drillthrough).
2. Author/update SQL under `snowflake/views/` as secure views with hierarchy columns.
3. Run:

```bash
cd bi-github-pack/powerbi-snowflake-live-agents
python3 -m generator.cli generate --manifest examples/revenue-drilldown/manifest.yaml --clean
python3 -m pytest tests/ -q
```

4. Open generated `.pbip` in Power BI Desktop → Snowflake auth → Publish.

## DirectQuery rules

- Semantic model `defaultMode: directQuery`
- Partitions use `Snowflake.Databases` → Database → Schema → **View**
- Prefer aggregate views for overview visuals
- Drillthrough pages use `filterConfig` on hierarchy fields

## Agents

Use `/live-dashboard-orchestrator` or specialists `snowflake-view-designer`, `powerbi-semantic-model`, `powerbi-drilldown-report`.
