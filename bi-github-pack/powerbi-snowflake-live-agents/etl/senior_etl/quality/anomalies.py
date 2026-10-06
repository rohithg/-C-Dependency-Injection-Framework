from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl


@dataclass
class AnomalyFinding:
    metric: str
    value: float
    ok: bool
    detail: str


def evaluate_anomalies(fact: pl.DataFrame, cfg: dict[str, Any]) -> list[AnomalyFinding]:
    findings: list[AnomalyFinding] = []
    rows = float(fact.height)
    findings.append(
        AnomalyFinding(
            "fct_orders_rows",
            rows,
            cfg.get("fct_orders_min_rows", 0) <= rows <= cfg.get("fct_orders_max_rows", 1e18),
            f"rows={rows}",
        )
    )
    revenue = float(fact["line_net_amount_usd"].sum()) if fact.height and "line_net_amount_usd" in fact.columns else 0.0
    findings.append(
        AnomalyFinding(
            "net_revenue_usd",
            revenue,
            cfg.get("net_revenue_usd_min", 0) <= revenue <= cfg.get("net_revenue_usd_max", 1e18),
            f"revenue={revenue}",
        )
    )
    return findings
