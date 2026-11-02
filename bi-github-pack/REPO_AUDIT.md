# GitHub repository audit — rohithg

Audit date: 2026-09-29 · agent can **only write** to `rohithg/-C-Dependency-Injection-Framework`.

## Verdict

| Status | Count | Notes |
|--|--|--|
| Substantive career / BI content | Pack under this repo’s `bi-github-pack/` + `gh-pages/projects/` | Source of truth |
| Thin “template” public repos (Jan 2026) | ~20 | Tiny README + one sample file — not career-grade |
| Partially filled BI siblings | 2–3 | `Snowflake-Retail-Data-Warehouse`, `rohith-portfolio`, `IMP` have some code but agent cannot push updates |
| Missing separate repos for new pack projects | Several | Content lives in pack until App access is widened |

## Dead / thin public repos (size ≤ ~9; often one nested folder)

These look like auto-generated language demos, **not** resume showcases:

- Rust-CLI-Tool, Go-Concurrent-Web-Scraper, Kotlin-Coroutines-Flow, Swift-Combine-Framework
- Java-Spring-Boot-Microservice, JavaScript-Event-Driven-Architecture, C-High-Performance-Data-Structures
- TypeScript-Full-Stack-Application, E-Commerce-Backend-API, GraphQL-API-with-Apollo-Server
- -CI-CD-Pipeline-Configuration, AI-Powered-Task-Manager, Blockchain-Transaction-Tracker
- Data-Visualization-Dashboard, Distributed-Task-Queue-System-, Machine-Learning-Image-Classifier
- Real-Time-Chat-Application, Real-Time-Collaborative-Whiteboard, Video-Streaming-Platform

**Recommendation:** archive or make private so recruiters don’t see them ahead of BI work. Agent cannot change visibility without write access.

## BI / career repos

| Repo | Remote state | Pack / Pages |
|--|--|--|
| `-C-Dependency-Injection-Framework` | Live showcase + full pack | ★ Source of truth |
| `Snowflake-Retail-Data-Warehouse` | Partial (27 files) | Richer pack copy (49+ files) |
| `rohith-portfolio` | Thin (5 files) | Full pack site |
| `IMP` | Small dbt metrics sketch | Prefer pack `dbt-analytics-engineering` |
| `powerbi-semantic-layer` etc. | Often missing as separate repos | Under `gh-pages/projects/` |

## New resume-aligned projects (this update)

Added under `bi-github-pack/` (and synced to `gh-pages/projects/`):

1. **energy-utility-analytics** — Nexant / Amplytico energy programs (kWh, peak, compliance)
2. **databricks-azure-lakehouse** — ADLS → ADF → Databricks → Synapse + Iceberg eval
3. **supply-chain-control-tower** — GSC OTIF / yard / freight
4. **data-quality-observability** — ELT DQ scorecard (~80% defect story)
5. **powerbi-devops-cicd** — REST API + Fabric/workspace CI/CD + RLS gates

## How to get true separate non-empty repos

1. GitHub → Settings → Applications → Cursor → **Repository access: All repositories** (or add each repo)
2. Or provide a PAT with `repo` scope to a new agent
3. Re-run publish: `bi-github-pack/scripts/publish-all.sh`
