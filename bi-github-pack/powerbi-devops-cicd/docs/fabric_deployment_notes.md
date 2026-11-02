# Microsoft Fabric deployment notes

Resume alignment: Fabric governance, semantic models, CI/CD.

## Environments

| Env | Workspace | Capacity | Gate |
|--|--|--|--|
| Dev | BI-Dev-SupplyChain | PPU | RLS roles present |
| Test | BI-Test-SupplyChain | PPU | Refresh success 24h |
| Prod | BI-Prod-SupplyChain | Premium | Sensitivity label + RLS + refresh |

## Release flow

1. PR updates `workspaces/*.json`
2. GitHub Actions dry-run validate + RLS check
3. Manual approve → `deploy_workspace.py` against Test
4. Refresh smoke test → promote config to Prod
5. `trigger_refresh.py` on Prod datasets after promote

## Copilot / AI

Use Copilot for measure scaffolding only; certified measures remain in source control (`powerbi-semantic-layer/dax`).
