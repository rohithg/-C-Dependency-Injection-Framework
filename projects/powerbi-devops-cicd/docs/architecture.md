# BI DevOps architecture

```
GitHub (report defs / workspace config)
   → Actions: lint config + dry-run deploy
   → Power BI REST API / Fabric APIs
   → Dev → Test → Prod workspaces
   → Refresh + RLS validation gates
```
