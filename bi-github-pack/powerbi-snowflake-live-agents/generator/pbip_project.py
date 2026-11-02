from __future__ import annotations

import json
import uuid
from pathlib import Path

from .manifest import ColumnSpec, DashboardManifest, MeasureSpec, TableSpec


def _guid() -> str:
    return str(uuid.uuid4())


def _tmdl_escape(name: str) -> str:
    if any(c in name for c in " '.-"):
        return f"'{name}'"
    return name


def _column_block(col: ColumnSpec) -> str:
    lines = [f"\tcolumn {_tmdl_escape(col.name)}"]
    lines.append(f"\t\tdataType: {col.data_type}")
    if col.is_key:
        lines.append("\t\tisKey")
    if col.format_string:
        lines.append(f"\t\tformatString: {col.format_string}")
    if col.summarize_by:
        lines.append(f"\t\tsummarizeBy: {col.summarize_by}")
    src = col.source_column or col.name
    lines.append(f"\t\tsourceColumn: {src}")
    if col.summarize_by == "none" or col.data_type in {"string", "dateTime"}:
        lines.append('\t\tannotation Summarization = "None"')
    return "\n".join(lines)


def _measure_block(m: MeasureSpec) -> str:
    lines = [f"\tmeasure {_tmdl_escape(m.name)} = {m.expression}"]
    if m.format_string:
        lines.append(f"\t\tformatString: {m.format_string}")
    if m.display_folder:
        lines.append(f"\t\tdisplayFolder: {m.display_folder}")
    return "\n".join(lines)


def _partition_m(table: TableSpec, manifest: DashboardManifest) -> str:
    sf = manifest.snowflake
    view = table.snowflake_view
    return f"""\tpartition {_tmdl_escape(table.name)} = m
\t\tmode: directQuery
\t\tsource =
\t\t\tlet
\t\t\t    Source = Snowflake.Databases({sf.account_param}, {sf.warehouse_param}),
\t\t\t    Db = Source{{[Name={sf.database_param}, Kind="Database"]}}[Data],
\t\t\t    Sch = Db{{[Name={sf.schema_param}, Kind="Schema"]}}[Data],
\t\t\t    View = Sch{{[Name="{view}", Kind="View"]}}[Data]
\t\t\tin
\t\t\t    View"""


def render_table_tmdl(table: TableSpec, manifest: DashboardManifest) -> str:
    parts = [f"table {_tmdl_escape(table.name)}", f"\tlineageTag: {_guid()}"]
    for col in table.columns:
        parts.append(_column_block(col))
        parts.append("")
    for m in table.measures:
        parts.append(_measure_block(m))
        parts.append("")
    parts.append(_partition_m(table, manifest))
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def render_model_tmdl(manifest: DashboardManifest) -> str:
    order = json.dumps([t.name for t in manifest.tables])
    lines = [
        f"model {_tmdl_escape(manifest.name)}",
        "\tculture: en-US",
        "\tdefaultMode: directQuery",
        "\tdiscourageImplicitMeasures",
        f"\tannotation PBI_QueryOrder = {order}",
        '\tannotation StorageMode = "DirectQuery"',
        f'\tannotation Description = "{manifest.description}"',
        "",
    ]
    return "\n".join(lines)


def render_expressions_tmdl(manifest: DashboardManifest) -> str:
    sf = manifest.snowflake
    return f"""expression {sf.account_param} =
\t"{sf.default_account}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]

expression {sf.warehouse_param} =
\t"{sf.default_warehouse}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]

expression {sf.database_param} =
\t"{sf.database}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]

expression {sf.schema_param} =
\t"{sf.schema}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
"""


def render_relationships_tmdl(manifest: DashboardManifest) -> str:
    chunks: list[str] = []
    for r in manifest.relationships:
        chunks.append(
            f"""relationship {_tmdl_escape(r.name)}
\tfromColumn: {_tmdl_escape(r.from_table)}.{_tmdl_escape(r.from_column)}
\ttoColumn: {_tmdl_escape(r.to_table)}.{_tmdl_escape(r.to_column)}
\tjoinOnDateBehavior: datePartOnly
\tcardinality: {r.cardinality}
\tcrossFilteringBehavior: {r.cross_filtering}
"""
        )
    return "\n".join(chunks)


def _field_ref(table: str, column: str) -> dict:
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": column,
        }
    }


def _overview_visuals(page_id: str, manifest: DashboardManifest) -> dict[str, dict]:
    """Minimal overview: KPI card + clustered bar for first hierarchy field."""
    fact = next((t for t in manifest.tables if t.kind == "fact"), manifest.tables[0])
    measure = fact.measures[0].name if fact.measures else fact.columns[0].name
    # Prefer a string dimension from a dim or fact for category
    category_table = fact.name
    category_col = None
    for t in manifest.tables:
        for c in t.columns:
            if c.data_type == "string" and not c.is_key:
                category_table, category_col = t.name, c.name
                break
        if category_col:
            break
    if not category_col:
        category_col = next(c.name for c in fact.columns if not c.is_key)

    card_id = "visual_kpi_card"
    bar_id = "visual_region_bar"
    visuals = {
        card_id: {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
            "name": card_id,
            "position": {"x": 40, "y": 40, "z": 1000, "width": 360, "height": 160, "tabOrder": 0},
            "visual": {
                "visualType": "card",
                "query": {
                    "queryState": {
                        "Values": {
                            "projections": [
                                {
                                    "field": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": fact.name}},
                                            "Property": measure,
                                        }
                                    },
                                    "queryRef": f"{fact.name}.{measure}",
                                    "nativeQueryRef": measure,
                                }
                            ]
                        }
                    }
                },
            },
        },
        bar_id: {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
            "name": bar_id,
            "position": {"x": 40, "y": 240, "z": 2000, "width": 1200, "height": 640, "tabOrder": 1},
            "visual": {
                "visualType": "clusteredBarChart",
                "query": {
                    "queryState": {
                        "Category": {
                            "projections": [
                                {
                                    "field": _field_ref(category_table, category_col),
                                    "queryRef": f"{category_table}.{category_col}",
                                    "nativeQueryRef": category_col,
                                    "active": True,
                                }
                            ]
                        },
                        "Y": {
                            "projections": [
                                {
                                    "field": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Entity": fact.name}},
                                            "Property": measure,
                                        }
                                    },
                                    "queryRef": f"{fact.name}.{measure}",
                                    "nativeQueryRef": measure,
                                }
                            ]
                        },
                    }
                },
            },
        },
    }
    return visuals


def _drill_visuals(manifest: DashboardManifest) -> dict[str, dict]:
    fact = next((t for t in manifest.tables if t.kind == "fact"), manifest.tables[0])
    measure = fact.measures[0].name if fact.measures else fact.columns[0].name
    string_cols = [c for c in fact.columns if c.data_type == "string"][:3]
    if not string_cols:
        string_cols = [c for c in fact.columns if not c.is_key][:2]
    table_id = "visual_detail_table"
    projections = []
    for c in string_cols:
        projections.append(
            {
                "field": _field_ref(fact.name, c.name),
                "queryRef": f"{fact.name}.{c.name}",
                "nativeQueryRef": c.name,
            }
        )
    projections.append(
        {
            "field": {
                "Measure": {
                    "Expression": {"SourceRef": {"Entity": fact.name}},
                    "Property": measure,
                }
            },
            "queryRef": f"{fact.name}.{measure}",
            "nativeQueryRef": measure,
        }
    )
    return {
        table_id: {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
            "name": table_id,
            "position": {"x": 40, "y": 40, "z": 1000, "width": 1840, "height": 1000, "tabOrder": 0},
            "visual": {
                "visualType": "tableEx",
                "query": {"queryState": {"Values": {"projections": projections}}},
            },
        }
    }


def _page_json(page_id: str, display_name: str, role: str, drill_fields: list[dict]) -> dict:
    page: dict = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": page_id,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": 1080,
        "width": 1920,
    }
    if role == "drillthrough" and drill_fields:
        page["filterConfig"] = {
            "filters": [
                {
                    "name": f"drill_{i}",
                    "field": _field_ref(f["table"], f["column"]),
                    "type": "Categorical",
                    "howCreated": "User",
                }
                for i, f in enumerate(drill_fields)
            ]
        }
    if role == "tooltip":
        page["type"] = "Tooltip"
        page["visibility"] = "HiddenInViewMode"
        page["displayOption"] = "ActualSize"
        page["width"] = 320
        page["height"] = 240
    return page


def generate_pbip(manifest: DashboardManifest, output_dir: Path) -> Path:
    """Write a PBIP project folder. Returns path to .pbip file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_dir = output_dir / f"{manifest.name}.SemanticModel"
    report_dir = output_dir / f"{manifest.name}.Report"
    tables_dir = model_dir / "definition" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    pages_root = report_dir / "definition" / "pages"
    pages_root.mkdir(parents=True, exist_ok=True)

    # Semantic model
    (model_dir / "definition.pbism").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                "version": "1.0",
                "settings": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (model_dir / ".platform").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                "metadata": {"type": "SemanticModel", "displayName": manifest.name},
                "config": {"version": "2.0", "logicalId": _guid()},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    defn = model_dir / "definition"
    (defn / "model.tmdl").write_text(render_model_tmdl(manifest), encoding="utf-8")
    (defn / "expressions.tmdl").write_text(render_expressions_tmdl(manifest), encoding="utf-8")
    if manifest.relationships:
        (defn / "relationships.tmdl").write_text(
            render_relationships_tmdl(manifest), encoding="utf-8"
        )
    for table in manifest.tables:
        (tables_dir / f"{table.name}.tmdl").write_text(
            render_table_tmdl(table, manifest), encoding="utf-8"
        )
    (defn / "database.tmdl").write_text(
        f"database\n\tcompatibilityLevel: 1567\n", encoding="utf-8"
    )

    # Report
    (report_dir / "definition.pbir").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                "version": "4.0",
                "datasetReference": {
                    "byPath": {"path": f"../{manifest.name}.SemanticModel"}
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / ".platform").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                "metadata": {"type": "Report", "displayName": manifest.name},
                "config": {"version": "2.0", "logicalId": _guid()},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "definition" / "report.json").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
                "themeCollection": {
                    "baseTheme": {"name": "CY24SU10", "type": "SharedResources", "version": "3.49"}
                },
                "objects": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (report_dir / "definition" / "version.json").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/version/1.0.0/schema.json",
                "version": "2.0.0",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    page_order: list[str] = []
    for page in manifest.pages:
        page_id = page.name if "-" in page.name else _guid()
        # keep stable ids from manifest when they look like guids; else create folder from name
        folder = pages_root / page.name
        folder.mkdir(parents=True, exist_ok=True)
        visuals_dir = folder / "visuals"
        visuals_dir.mkdir(exist_ok=True)
        page_doc = _page_json(page.name, page.display_name, page.role, page.drill_fields)
        (folder / "page.json").write_text(json.dumps(page_doc, indent=2) + "\n", encoding="utf-8")
        visuals = (
            _overview_visuals(page.name, manifest)
            if page.role == "overview"
            else _drill_visuals(manifest)
        )
        for vid, vdoc in visuals.items():
            vfolder = visuals_dir / vid
            vfolder.mkdir(exist_ok=True)
            (vfolder / "visual.json").write_text(
                json.dumps(vdoc, indent=2) + "\n", encoding="utf-8"
            )
        page_order.append(page.name)

    (pages_root / "pages.json").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
                "pageOrder": page_order,
                "activePageName": page_order[0] if page_order else "",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    pbip_path = output_dir / f"{manifest.name}.pbip"
    pbip_path.write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/projectProperties/1.0.0/schema.json",
                "version": "1.0",
                "artifacts": [
                    {
                        "report": {
                            "path": f"{manifest.name}.Report",
                            "byPath": None,
                        }
                    }
                ],
                "settings": {"enableAutoRecovery": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Fix artifacts structure to common PBIP shape
    pbip_path.write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/projectProperties/1.0.0/schema.json",
                "version": "1.0",
                "artifacts": [{"report": {"path": f"{manifest.name}.Report"}}],
                "settings": {"enableAutoRecovery": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return pbip_path
