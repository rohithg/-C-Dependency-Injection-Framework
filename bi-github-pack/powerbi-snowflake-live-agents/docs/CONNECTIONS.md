# Connections — Snowflake + Power BI

Agents can generate PBIP + SQL without live credentials. To **apply** views or manage Service workspaces, connect both apps.

## Composio (recommended for agents)

1. [Snowflake auth config](https://dashboard.composio.dev/~/org/connect/apps/snowflake?open=true) — account identifier, user, role, warehouse, key-pair or password.
2. [Power BI auth config](https://dashboard.composio.dev/~/org/connect/apps/microsoft_power_bi?open=true) — Azure AD app / delegated scopes for Dataset + Workspace APIs.
3. Reply in chat after both show **Active**, then ask the orchestrator to deploy.

## Power BI Desktop (required to open `.pbip`)

1. Open the generated `.pbip`.
2. When prompted, sign in to Snowflake (SSO or username/password/key).
3. Confirm tables resolve under Parameters → `SfAccount`, `SfWarehouse`, `SfDatabase`, `SfSchema`.
4. Publish to a workspace. Semantic model stays DirectQuery — configure gateway only if your Snowflake is private-link / on-prem style networking that needs one.

## Environment variables (optional scripts)

| Variable | Purpose |
|--|--|
| `SF_ACCOUNT` | Snowflake account locator / URL host |
| `SF_USER` | User |
| `SF_ROLE` | BI role (e.g. `BI_ANALYST`) |
| `SF_WAREHOUSE` | Warehouse for DDL / test queries |
| `SF_DATABASE` / `SF_SCHEMA` | Target namespace for views |
| `PBI_WORKSPACE_ID` | Optional publish target |

Never commit secrets. Prefer key-pair + secret store.
