from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl


@dataclass
class RuleResult:
    table: str
    rule: str
    severity: str
    passed: bool
    detail: str
    bad_rows: int = 0


@dataclass
class GateReport:
    results: list[RuleResult] = field(default_factory=list)

    @property
    def errors(self) -> list[RuleResult]:
        return [r for r in self.results if r.severity == "error" and not r.passed]

    @property
    def warnings(self) -> list[RuleResult]:
        return [r for r in self.results if r.severity == "warn" and not r.passed]

    def ok(self, fail_on_error: bool = True) -> bool:
        return not self.errors if fail_on_error else True


def _run_rule(
    table: str,
    df: pl.DataFrame,
    rule: dict[str, Any],
    refs: dict[str, pl.DataFrame],
) -> RuleResult:
    kind = rule["rule"]
    severity = rule.get("severity", "error")

    if kind == "not_null":
        cols = rule["columns"]
        bad = df.filter(pl.any_horizontal([pl.col(c).is_null() for c in cols]))
        return RuleResult(table, kind, severity, bad.height == 0, f"nulls in {cols}", bad.height)

    if kind == "unique":
        cols = rule["columns"]
        bad = df.filter(pl.struct(cols).is_duplicated())
        return RuleResult(table, kind, severity, bad.height == 0, f"dupes on {cols}", bad.height)

    if kind == "positive":
        cols = rule["columns"]
        bad = df.filter(pl.any_horizontal([pl.col(c) <= 0 for c in cols]))
        return RuleResult(table, kind, severity, bad.height == 0, f"non-positive {cols}", bad.height)

    if kind == "accepted_values":
        col = rule["column"]
        values = rule["values"]
        bad = df.filter(~pl.col(col).is_in(values))
        return RuleResult(
            table, kind, severity, bad.height == 0, f"{col} not in {values}", bad.height
        )

    if kind == "referential":
        col = rule["column"]
        ref = refs.get(rule["ref_table"], pl.DataFrame())
        ref_col = rule["ref_column"]
        if ref.is_empty():
            return RuleResult(table, kind, severity, False, "ref table missing", df.height)
        bad = df.join(ref.select(ref_col).unique(), left_on=col, right_on=ref_col, how="anti")
        return RuleResult(
            table, kind, severity, bad.height == 0, f"orphan {col}→{rule['ref_table']}", bad.height
        )

    if kind == "row_count_min":
        minimum = int(rule["min"])
        passed = df.height >= minimum
        return RuleResult(table, kind, severity, passed, f"rows={df.height} min={minimum}", 0)

    return RuleResult(table, kind, severity, False, f"unknown rule {kind}", 0)


def evaluate_gates(
    tables: dict[str, pl.DataFrame],
    dq_config: dict[str, list[dict[str, Any]]],
) -> GateReport:
    report = GateReport()
    for table, rules in dq_config.items():
        df = tables.get(table, pl.DataFrame())
        for rule in rules:
            report.results.append(_run_rule(table, df, rule, tables))
    return report
