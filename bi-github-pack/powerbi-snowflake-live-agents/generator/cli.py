from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .manifest import load_manifest
from .pbip_project import generate_pbip
from .snowflake_ddl import render_grants_sql, render_view_ddl


def _pack_root() -> Path:
    return Path(__file__).resolve().parents[1]


def cmd_generate(args: argparse.Namespace) -> int:
    pack = _pack_root()
    manifest = load_manifest(args.manifest)
    out = Path(args.output) if args.output else pack / "generated" / manifest.name
    if out.exists() and args.clean:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    views_dir = Path(args.views_dir) if args.views_dir else pack / "snowflake" / "views"
    ddl = render_view_ddl(manifest, views_dir)
    grants = render_grants_sql(manifest)
    sql_dir = out / "snowflake"
    sql_dir.mkdir(parents=True, exist_ok=True)
    (sql_dir / "01_create_views.sql").write_text(ddl, encoding="utf-8")
    (sql_dir / "02_grants.sql").write_text(grants, encoding="utf-8")

    pbip = generate_pbip(manifest, out / "pbip")
    print(f"Dashboard: {manifest.name}")
    print(f"Snowflake DDL: {sql_dir / '01_create_views.sql'}")
    print(f"Grants:        {sql_dir / '02_grants.sql'}")
    print(f"PBIP:          {pbip}")
    print("Open the .pbip in Power BI Desktop, sign in to Snowflake, then publish.")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    assert manifest.tables, "manifest must define tables"
    assert any(p.role == "overview" for p in manifest.pages), "need an overview page"
    fact_views = [t.snowflake_view for t in manifest.tables]
    assert fact_views, "tables need snowflake_view"
    print(f"OK: {manifest.name} ({len(manifest.tables)} tables, {len(manifest.pages)} pages)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generator",
        description="Generate live Power BI DirectQuery PBIP projects from Snowflake view manifests",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Emit Snowflake DDL + PBIP project")
    g.add_argument("--manifest", required=True, help="Path to dashboard manifest YAML")
    g.add_argument("--output", help="Output directory (default: generated/<name>)")
    g.add_argument("--views-dir", help="Directory containing view SQL files")
    g.add_argument("--clean", action="store_true", help="Delete output directory first")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate", help="Validate a manifest")
    v.add_argument("--manifest", required=True)
    v.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
