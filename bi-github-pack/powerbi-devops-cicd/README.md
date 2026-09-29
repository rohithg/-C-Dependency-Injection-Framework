# Power BI / Fabric DevOps (CI/CD)

[![Stack](https://img.shields.io/badge/stack-Power%20BI%20REST%20API%20%7C%20GitHub%20Actions%20%7C%20Fabric-6264A7)](docs/architecture.md)

**Rohith Gangapuram** · resume-aligned (Fabric governance · BI CI/CD · REST API automation)

Workspace deployment, dataset refresh automation, and RLS deployment checks — the DevOps layer behind enterprise Power BI / Fabric platforms.

## Scripts

```bash
pip install -r requirements.txt
export PBI_TENANT_ID=... PBI_CLIENT_ID=... PBI_CLIENT_SECRET=...
python scripts/deploy_workspace.py --config workspaces/dev.json --dry-run
python scripts/trigger_refresh.py --workspace-id $WS --dataset-id $DS --dry-run
python scripts/validate_rls.py --config workspaces/dev.json
```

## Resume mapping

| Resume signal | Artifact |
|--|--|
| Power BI REST API automation | `scripts/trigger_refresh.py`, `deploy_workspace.py` |
| CI/CD for BI · 70–75% fewer prod defects | `.github/workflows/pbi-ci.yml` |
| Fabric / workspace governance | `workspaces/*.json`, docs |
| RLS / access management | `scripts/validate_rls.py` |
