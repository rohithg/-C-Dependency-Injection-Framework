from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ColumnSpec:
    name: str
    data_type: str
    source_column: str | None = None
    is_key: bool = False
    format_string: str | None = None
    summarize_by: str | None = None  # none | sum | count | ...


@dataclass
class MeasureSpec:
    name: str
    expression: str
    format_string: str | None = None
    display_folder: str | None = None


@dataclass
class TableSpec:
    name: str
    snowflake_view: str
    kind: str  # fact | dim | agg
    columns: list[ColumnSpec]
    measures: list[MeasureSpec] = field(default_factory=list)


@dataclass
class RelationshipSpec:
    name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str = "manyToOne"
    cross_filtering: str = "singleDirection"


@dataclass
class DrillPageSpec:
    name: str
    display_name: str
    role: str  # overview | drillthrough | tooltip
    drill_fields: list[dict[str, str]] = field(default_factory=list)
    # drill_fields: [{table, column}]


@dataclass
class SnowflakeSpec:
    account_param: str = "SfAccount"
    warehouse_param: str = "SfWarehouse"
    database_param: str = "SfDatabase"
    schema_param: str = "SfSchema"
    database: str = "ANALYTICS"
    schema: str = "MARTS"
    bi_role: str = "BI_ANALYST"
    default_account: str = "ORG-ACCOUNT"
    default_warehouse: str = "BI_WH"


@dataclass
class DashboardManifest:
    name: str
    description: str
    snowflake: SnowflakeSpec
    tables: list[TableSpec]
    relationships: list[RelationshipSpec]
    pages: list[DrillPageSpec]
    views_sql: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def _columns(raw: list[dict[str, Any]]) -> list[ColumnSpec]:
    return [
        ColumnSpec(
            name=c["name"],
            data_type=c.get("data_type", "string"),
            source_column=c.get("source_column", c["name"]),
            is_key=bool(c.get("is_key", False)),
            format_string=c.get("format_string"),
            summarize_by=c.get("summarize_by"),
        )
        for c in raw
    ]


def _measures(raw: list[dict[str, Any]] | None) -> list[MeasureSpec]:
    if not raw:
        return []
    return [
        MeasureSpec(
            name=m["name"],
            expression=m["expression"],
            format_string=m.get("format_string"),
            display_folder=m.get("display_folder"),
        )
        for m in raw
    ]


def load_manifest(path: Path | str) -> DashboardManifest:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sf = data.get("snowflake", {})
    snowflake = SnowflakeSpec(
        account_param=sf.get("account_param", "SfAccount"),
        warehouse_param=sf.get("warehouse_param", "SfWarehouse"),
        database_param=sf.get("database_param", "SfDatabase"),
        schema_param=sf.get("schema_param", "SfSchema"),
        database=sf.get("database", "ANALYTICS"),
        schema=sf.get("schema", "MARTS"),
        bi_role=sf.get("bi_role", "BI_ANALYST"),
        default_account=sf.get("default_account", "ORG-ACCOUNT"),
        default_warehouse=sf.get("default_warehouse", "BI_WH"),
    )
    tables = [
        TableSpec(
            name=t["name"],
            snowflake_view=t["snowflake_view"],
            kind=t.get("kind", "fact"),
            columns=_columns(t.get("columns", [])),
            measures=_measures(t.get("measures")),
        )
        for t in data.get("tables", [])
    ]
    relationships = [
        RelationshipSpec(
            name=r["name"],
            from_table=r["from_table"],
            from_column=r["from_column"],
            to_table=r["to_table"],
            to_column=r["to_column"],
            cardinality=r.get("cardinality", "manyToOne"),
            cross_filtering=r.get("cross_filtering", "singleDirection"),
        )
        for r in data.get("relationships", [])
    ]
    pages = [
        DrillPageSpec(
            name=p["name"],
            display_name=p.get("display_name", p["name"]),
            role=p.get("role", "overview"),
            drill_fields=p.get("drill_fields", []),
        )
        for p in data.get("pages", [])
    ]
    return DashboardManifest(
        name=data["name"],
        description=data.get("description", ""),
        snowflake=snowflake,
        tables=tables,
        relationships=relationships,
        pages=pages,
        views_sql=list(data.get("views_sql", [])),
        raw=data,
    )
