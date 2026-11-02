from __future__ import annotations

from pathlib import Path

from .manifest import DashboardManifest


def render_view_ddl(manifest: DashboardManifest, views_dir: Path) -> str:
    """Concatenate referenced view SQL files and wrap with USE DATABASE/SCHEMA."""
    chunks: list[str] = [
        f"-- Generated for dashboard: {manifest.name}",
        f"USE DATABASE {manifest.snowflake.database};",
        f"USE SCHEMA {manifest.snowflake.schema};",
        "",
    ]
    for rel in manifest.views_sql:
        path = views_dir / rel
        if not path.exists():
            raise FileNotFoundError(f"View SQL not found: {path}")
        chunks.append(f"-- === {rel} ===")
        chunks.append(path.read_text(encoding="utf-8").rstrip())
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def render_grants_sql(manifest: DashboardManifest) -> str:
    role = manifest.snowflake.bi_role
    db = manifest.snowflake.database
    sch = manifest.snowflake.schema
    lines = [
        f"-- Grants for live Power BI DirectQuery role {role}",
        f"GRANT USAGE ON DATABASE {db} TO ROLE {role};",
        f"GRANT USAGE ON SCHEMA {db}.{sch} TO ROLE {role};",
        f"GRANT USAGE ON WAREHOUSE {manifest.snowflake.default_warehouse} TO ROLE {role};",
    ]
    views = sorted({t.snowflake_view for t in manifest.tables})
    for view in views:
        lines.append(f"GRANT SELECT ON VIEW {db}.{sch}.{view} TO ROLE {role};")
    return "\n".join(lines) + "\n"
