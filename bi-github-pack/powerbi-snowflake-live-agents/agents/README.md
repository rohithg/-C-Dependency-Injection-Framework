# Agent playbooks

Copies of the Cursor subagent contracts for portfolio readers who browse GitHub without `.cursor/`.

Canonical prompts live in repo-root `.cursor/agents/`:

- `live-dashboard-orchestrator.md`
- `snowflake-view-designer.md`
- `powerbi-semantic-model.md`
- `powerbi-drilldown-report.md`

## Typical handoff

1. Orchestrator clarifies KPI + drill path.
2. View designer emits `snowflake/views/*.sql`.
3. Semantic model agent / CLI emits DirectQuery TMDL.
4. Report agent / CLI emits PBIR overview + drillthrough.
5. Human opens `.pbip`, authenticates to Snowflake, publishes.
