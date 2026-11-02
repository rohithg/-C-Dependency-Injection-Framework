#!/usr/bin/env python3
"""Run YAML expectation suites against sample_data; emit scorecard."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sample_data"
SUITES = ROOT / "great_expectations" / "expectations"
OUT = ROOT / "reports"
OUT.mkdir(exist_ok=True)


def run_expectation(df: pd.DataFrame, exp: dict) -> dict:
    t = exp["type"]
    k = exp.get("kwargs", {})
    col = k.get("column")
    try:
        if t == "expect_column_values_to_not_be_null":
            bad = int(df[col].isna().sum() + (df[col].astype(str).str.strip() == "").sum())
            return {"type": t, "column": col, "success": bad == 0, "unexpected": bad}
        if t == "expect_column_values_to_be_unique":
            bad = int(df[col].duplicated(keep=False).sum())
            return {"type": t, "column": col, "success": bad == 0, "unexpected": bad}
        if t == "expect_column_values_to_be_in_set":
            allowed = set(k["value_set"])
            series = df[col].fillna("__NULL__")
            bad = int((~series.isin(allowed)).sum())
            return {"type": t, "column": col, "success": bad == 0, "unexpected": bad}
        if t == "expect_column_values_to_be_between":
            s = pd.to_numeric(df[col], errors="coerce")
            bad = int(((s < k["min_value"]) | (s > k["max_value"]) | s.isna()).sum())
            return {"type": t, "column": col, "success": bad == 0, "unexpected": bad}
        if t == "expect_column_pair_values_a_to_be_greater_than_b":
            a, b = k["column_A"], k["column_B"]
            sa, sb = pd.to_datetime(df[a], errors="coerce"), pd.to_datetime(df[b], errors="coerce")
            cmp = sa >= sb if k.get("or_equal") else sa > sb
            bad = int((~cmp.fillna(False)).sum())
            return {"type": t, "columns": [a, b], "success": bad == 0, "unexpected": bad}
    except Exception as exc:
        return {"type": t, "success": False, "error": str(exc)}
    return {"type": t, "success": False, "error": "unknown expectation"}


def main():
    results = []
    for suite_path in sorted(SUITES.glob("*.yml")):
        suite = yaml.safe_load(suite_path.read_text())
        table = suite["table"]
        df = pd.read_csv(DATA / f"{table}.csv")
        # normalize empties
        df = df.replace({"": pd.NA})
        checks = [run_expectation(df, e) for e in suite["expectations"]]
        passed = sum(1 for c in checks if c.get("success"))
        results.append({
            "suite": suite["suite_name"],
            "table": table,
            "rows": len(df),
            "passed": passed,
            "total": len(checks),
            "pass_rate": round(passed / max(len(checks), 1), 3),
            "checks": checks,
        })

    overall = {
        "suites": results,
        "overall_pass_rate": round(
            sum(r["passed"] for r in results) / max(sum(r["total"] for r in results), 1), 3
        ),
        "note": "Baseline on dirty synthetic data — expect failures; wire into CI to block regressions.",
    }
    (OUT / "quality_scorecard.json").write_text(json.dumps(overall, indent=2))

    lines = ["# Quality scorecard", "", f"Overall pass rate: **{overall['overall_pass_rate']:.1%}**", ""]
    for r in results:
        lines.append(f"## {r['suite']} ({r['passed']}/{r['total']})")
        for c in r["checks"]:
            mark = "✅" if c.get("success") else "❌"
            lines.append(f"- {mark} `{c.get('type')}` unexpected={c.get('unexpected', c.get('error'))}")
        lines.append("")
    (OUT / "quality_scorecard.md").write_text("\n".join(lines))
    print(json.dumps({"overall_pass_rate": overall["overall_pass_rate"], "report": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
