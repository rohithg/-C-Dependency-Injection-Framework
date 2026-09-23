# Publish these BI projects to GitHub

Cursor currently only has write access to `-C-Dependency-Injection-Framework`.
To publish each project as its own repo:

## Option A — Grant Cursor access (recommended)

1. GitHub → Settings → Applications → Cursor → Repository access → **All repositories**
   (or select: `rohith-portfolio`, `Snowflake-Retail-Data-Warehouse`, `IMP`, plus any new repos below)
2. Create these public repos (empty, no README) if they do not exist:
   - `linkedin-executive-dashboard` ← **LinkedIn showcase (pin this)**
   - `powerbi-semantic-layer`
   - `healthcare-dimensional-model`
   - `dbt-analytics-engineering`
3. Reply **access granted** in the Cursor agent chat so it can push and enable GitHub Pages.

## Option B — Publish yourself

```bash
# From this bi-github-pack directory
./scripts/publish-all.sh
```

Requires `gh auth login` with repo scope.

## Target mapping

| Folder | GitHub repo |
|--------|-------------|
| `rohith-portfolio/` | `rohithg/rohith-portfolio` → enable Pages (main / root) |
| `linkedin-executive-dashboard/` | `rohithg/linkedin-executive-dashboard` → enable Pages + pin on profile |
| `Snowflake-Retail-Data-Warehouse/` | `rohithg/Snowflake-Retail-Data-Warehouse` |
| `powerbi-semantic-layer/` | `rohithg/powerbi-semantic-layer` (or `IMP`) |
| `healthcare-dimensional-model/` | `rohithg/healthcare-dimensional-model` |
| `dbt-analytics-engineering/` | `rohithg/dbt-analytics-engineering` |
