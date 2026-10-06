from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import yaml


@dataclass(frozen=True)
class FieldContract:
    name: str
    dtype: str
    required: bool = True
    pii: bool = False


@dataclass
class DatasetContract:
    name: str
    version: str
    fields: list[FieldContract]
    primary_key: list[str]

    def field_map(self) -> dict[str, FieldContract]:
        return {f.name: f for f in self.fields}


def load_contract(path: Path) -> DatasetContract:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    fields = [
        FieldContract(
            name=f["name"],
            dtype=f["dtype"],
            required=bool(f.get("required", True)),
            pii=bool(f.get("pii", False)),
        )
        for f in raw["fields"]
    ]
    return DatasetContract(
        name=raw["name"],
        version=str(raw["version"]),
        fields=fields,
        primary_key=list(raw["primary_key"]),
    )


_DTYPE_MAP = {
    "string": pl.Utf8,
    "int": pl.Int64,
    "float": pl.Float64,
    "bool": pl.Boolean,
    "date": pl.Utf8,  # parse later
    "datetime": pl.Utf8,
}


class SchemaRegistry:
    """File-backed schema registry with breaking-change detection."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def publish(self, contract: DatasetContract) -> dict[str, Any]:
        payload = {
            "name": contract.name,
            "version": contract.version,
            "primary_key": contract.primary_key,
            "fields": [
                {
                    "name": f.name,
                    "dtype": f.dtype,
                    "required": f.required,
                    "pii": f.pii,
                }
                for f in contract.fields
            ],
        }
        path = self._path(contract.name)
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            breaking = self._breaking(old, payload)
            if breaking:
                raise ValueError(
                    f"Breaking schema change for {contract.name}: {'; '.join(breaking)}"
                )
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload

    def _breaking(self, old: dict, new: dict) -> list[str]:
        issues = []
        old_fields = {f["name"]: f for f in old["fields"]}
        new_fields = {f["name"]: f for f in new["fields"]}
        for name, f in old_fields.items():
            if f.get("required") and name not in new_fields:
                issues.append(f"removed required field {name}")
            elif name in new_fields and f["dtype"] != new_fields[name]["dtype"]:
                issues.append(f"dtype change {name}: {f['dtype']}→{new_fields[name]['dtype']}")
        if old.get("primary_key") != new.get("primary_key"):
            issues.append("primary_key changed")
        return issues

    def validate_frame(self, contract: DatasetContract, df: pl.DataFrame) -> list[str]:
        errors: list[str] = []
        for f in contract.fields:
            if f.name not in df.columns:
                if f.required:
                    errors.append(f"missing column {f.name}")
                continue
            if f.required:
                nulls = df.filter(pl.col(f.name).is_null()).height
                if nulls:
                    errors.append(f"{nulls} nulls in required {f.name}")
        for pk in contract.primary_key:
            if pk not in df.columns:
                errors.append(f"missing pk {pk}")
        if all(pk in df.columns for pk in contract.primary_key) and df.height:
            dupes = df.filter(pl.struct(contract.primary_key).is_duplicated()).height
            if dupes:
                errors.append(f"duplicate primary key rows={dupes}")
        return errors


def row_hash(df: pl.DataFrame, cols: list[str]) -> pl.Expr:
    """Stable content hash for idempotent merges."""
    return (
        pl.concat_str([pl.col(c).cast(pl.Utf8).fill_null("__NULL__") for c in cols], separator="|")
        .hash(seed=99)
        .cast(pl.Utf8)
        .alias("_row_hash")
    )


def file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()
