# Revenue live drill-down example

Region → Product Category → Customer, powered by Snowflake secure views and a DirectQuery PBIP model.

```bash
cd bi-github-pack/powerbi-snowflake-live-agents
python -m generator.cli generate --manifest examples/revenue-drilldown/manifest.yaml --clean
```

Then open `generated/RevenueLiveDrilldown/pbip/RevenueLiveDrilldown.pbip` in Power BI Desktop.
