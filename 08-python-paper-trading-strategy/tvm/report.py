"""Human-readable summaries for the daily run.

Written to $GITHUB_STEP_SUMMARY so the whole run can be read from the GitHub
mobile app / mobile browser without opening logs.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .broker import Broker
from .config import TVMConfig, DEFAULT


def performance_vs_benchmark(broker: Broker, bench_closes: pd.Series) -> dict | None:
    """Compare paper-account equity to the benchmark since the account's first day."""
    try:
        eq = broker.equity_history()
    except Exception:
        return None
    if eq is None or len(eq) < 2:
        return None
    bench = bench_closes.dropna()
    bench = bench.loc[eq.index[0]:eq.index[-1]]
    if len(bench) < 2:
        return None
    strat_ret = eq.iloc[-1] / eq.iloc[0] - 1
    bench_ret = bench.iloc[-1] / bench.iloc[0] - 1
    dd = (eq / eq.cummax() - 1).min()
    bdd = (bench / bench.cummax() - 1).min()
    return {
        "since": str(eq.index[0].date()), "days": len(eq),
        "start_equity": float(eq.iloc[0]), "equity": float(eq.iloc[-1]),
        "strategy_return": float(strat_ret), "benchmark_return": float(bench_ret),
        "strategy_maxdd": float(dd), "benchmark_maxdd": float(bdd),
    }


def to_markdown(report: dict, perf: dict | None, cfg: TVMConfig = DEFAULT, mode: str = "") -> str:
    sig, after = report["signal"], report["state_after"]
    regime = "RISK-ON" if sig["risk_on"] else "RISK-OFF (cash)"
    lines = [
        f"## TVM daily run - {report['as_of']}  {('(' + mode + ')') if mode else ''}".rstrip(),
        "",
        f"**Regime:** {regime}  |  **Asset:** {after['asset']}  |  **Target exposure:** {after['exposure']:.2f}x  "
        f"|  **Realized vol:** {sig['realized_vol']:.1%}  |  **Equity:** ${report['equity']:,.0f}",
        "",
        "| Momentum (6m) | " + " | ".join(cfg.risk_assets) + " |",
        "|---|" + "---|" * len(cfg.risk_assets),
        "| return | " + " | ".join(f"{sig.get(f'mom_{s}', float('nan')):+.1%}" for s in cfg.risk_assets) + " |",
        "",
        "### Target portfolio",
        "| ETF | Target weight | Current weight |",
        "|---|---|---|",
    ]
    syms = sorted(set(report["target_weights"]) | set(report["current_weights"]))
    for s in syms:
        lines.append(f"| {s} | {report['target_weights'].get(s, 0):.1%} | {report['current_weights'].get(s, 0):.1%} |")
    lines.append("")
    if report["orders"]:
        verb = "Orders (NOT sent, dry run)" if report["dry_run"] else "Orders sent"
        lines += [f"### {verb}", "| ETF | Action |", "|---|---|"]
        results = report.get("order_results", [])
        for i, o in enumerate(report["orders"]):
            action = "Sell all" if o["liquidate"] else (f"Buy ${o['notional']:,.0f}" if o["notional"] > 0 else f"Sell ${-o['notional']:,.0f}")
            if i < len(results):
                action += f" ({results[i]})"
            lines.append(f"| {o['symbol']} | {action} |")
    else:
        lines.append("### No trades needed today (inside rebalance band)")
    lines.append("")
    if report.get("learner"):
        lines += [f"### Learner (adaptive ensemble, drift from target {report.get('drift_from_target', 0):.2f})",
                  "| Expert | Weight | Trailing 1y |", "|---|---|---|"]
        for e in report["learner"][:6]:
            lines.append(f"| {e['expert']} | {e['weight']:.1%} | {e['trailing_1y']:+.1%} |")
        if len(report["learner"]) > 6:
            lines.append(f"| ... {len(report['learner']) - 6} more | | |")
        lines.append("")
    if report.get("postmortem"):
        lines += ["### Recent regime exits (lessons)", "| Exit | Re-entry | Days out | Market moved | Verdict |", "|---|---|---|---|---|"]
        for r in report["postmortem"]:
            lines.append(f"| {r['exit']} | {r['reentry'] or '-'} | {r['days_out']} | {r['missed']:+.1%} | {r['verdict']} |")
        lines.append("")
    if perf:
        lines += [
            f"### Paper account vs {cfg.benchmark_symbol} since {perf['since']} ({perf['days']} trading days)",
            "| | TVM paper account | " + cfg.benchmark_symbol + " buy & hold |",
            "|---|---|---|",
            f"| Return | {perf['strategy_return']:+.2%} | {perf['benchmark_return']:+.2%} |",
            f"| Max drawdown | {perf['strategy_maxdd']:.2%} | {perf['benchmark_maxdd']:.2%} |",
            f"| Equity | ${perf['equity']:,.0f} (from ${perf['start_equity']:,.0f}) | |",
            "",
        ]
    lines.append(f"<sub>live prices used: {report['live_prices_used']} - state before: {report['state_before']['asset']} "
                 f"{report['state_before']['exposure']:.2f}x</sub>")
    return "\n".join(lines) + "\n"


def write_step_summary(markdown: str) -> Path | None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return None
    with open(path, "a") as f:
        f.write(markdown)
    return Path(path)
