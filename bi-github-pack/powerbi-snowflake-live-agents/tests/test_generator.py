from __future__ import annotations

from pathlib import Path

import pytest

from generator.cli import main
from generator.manifest import load_manifest
from generator.pbip_project import generate_pbip, render_table_tmdl
from generator.snowflake_ddl import render_grants_sql, render_view_ddl

PACK = Path(__file__).resolve().parents[1]
MANIFEST = PACK / "examples" / "revenue-drilldown" / "manifest.yaml"
VIEWS = PACK / "snowflake" / "views"


def test_load_manifest():
    m = load_manifest(MANIFEST)
    assert m.name == "RevenueLiveDrilldown"
    assert any(t.kind == "fact" for t in m.tables)
    assert any(p.role == "drillthrough" for p in m.pages)


def test_view_ddl_includes_secure_views():
    m = load_manifest(MANIFEST)
    ddl = render_view_ddl(m, VIEWS)
    assert "VW_REVENUE_ORDER_LINE" in ddl
    assert "CREATE OR REPLACE SECURE VIEW" in ddl
    assert "USE DATABASE ANALYTICS" in ddl


def test_grants_cover_all_views():
    m = load_manifest(MANIFEST)
    grants = render_grants_sql(m)
    for t in m.tables:
        assert t.snowflake_view in grants


def test_tmdl_is_direct_query():
    m = load_manifest(MANIFEST)
    fact = next(t for t in m.tables if t.kind == "fact")
    tmdl = render_table_tmdl(fact, m)
    assert "mode: directQuery" in tmdl
    assert "Snowflake.Databases" in tmdl
    assert 'Kind="View"' in tmdl


def test_generate_pbip(tmp_path: Path):
    m = load_manifest(MANIFEST)
    pbip = generate_pbip(m, tmp_path / "pbip")
    assert pbip.exists()
    model = tmp_path / "pbip" / f"{m.name}.SemanticModel" / "definition" / "model.tmdl"
    assert "defaultMode: directQuery" in model.read_text(encoding="utf-8")
    pages = tmp_path / "pbip" / f"{m.name}.Report" / "definition" / "pages" / "pages.json"
    assert pages.exists()
    drill = (
        tmp_path
        / "pbip"
        / f"{m.name}.Report"
        / "definition"
        / "pages"
        / "drill_region_product_customer"
        / "page.json"
    )
    text = drill.read_text(encoding="utf-8")
    assert "filterConfig" in text
    assert "REGION_NAME" in text


def test_cli_generate_and_validate(tmp_path: Path):
    assert main(["validate", "--manifest", str(MANIFEST)]) == 0
    out = tmp_path / "out"
    assert (
        main(
            [
                "generate",
                "--manifest",
                str(MANIFEST),
                "--output",
                str(out),
                "--views-dir",
                str(VIEWS),
                "--clean",
            ]
        )
        == 0
    )
    assert (out / "snowflake" / "01_create_views.sql").exists()
    assert (out / "pbip" / "RevenueLiveDrilldown.pbip").exists()
