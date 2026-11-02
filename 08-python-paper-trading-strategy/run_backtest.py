#!/usr/bin/env python3
"""Backtest TVM against buy-and-hold VOO (SPY as proxy before VOO's 2010 inception).

    python run_backtest.py                 # full report + results/*.png
    python run_backtest.py --start 2015-01-01 --end 2024-12-31
    python run_backtest.py --config my_params.json --no-plot
"""
from __future__ import annotations

import argparse
from pathlib import Path
import warnings

import pandas as pd

from tvm.config import TVMConfig, DEFAULT
from tvm.data import load_closes, tbill_daily_return
from tvm.backtest import run_backtest, summarize, yearly_table, rolling_win_rate, format_summary

warnings.filterwarnings("ignore", category=FutureWarning)

RESULTS = Path(__file__).resolve().parent / "results"

PERIODS = [
    ("Full history (1994->)", "1994-01-01", None),
    ("Out-of-sample: dot-com + GFC (1999-04 -> 2010-09)", "1999-04-01", "2010-09-08"),
    ("VOO era (2010-09 ->)", "2010-09-09", None),
    ("Real 2x ETFs available (2007 ->)", "2007-01-01", None),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="JSON file overriding TVMConfig fields")
    ap.add_argument("--start"); ap.add_argument("--end")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="ignore the data cache")
    args = ap.parse_args()

    cfg = TVMConfig.from_json(args.config) if args.config else DEFAULT
    symbols = sorted({cfg.trend_symbol, *cfg.risk_assets, *cfg.leveraged_2x.values(),
                      cfg.cash_symbol, cfg.benchmark_symbol, "SPY", "^IRX"})
    closes = load_closes(symbols, start="1993-01-01", refresh=args.refresh)
    cash = tbill_daily_return(closes)

    # VOO tracks the same index as SPY; splice SPY in before VOO existed so the
    # benchmark covers the whole sample.
    bench = closes[cfg.benchmark_symbol].pct_change().fillna(closes["SPY"].pct_change())
    closes = closes.copy()
    closes["_BENCH"] = (1 + bench.fillna(0)).cumprod()

    periods = [(f"{args.start or 'start'} -> {args.end or 'now'}", args.start, args.end)] if (args.start or args.end) else PERIODS
    print(f"Config: {cfg}\n")
    last = None
    for name, start, end in periods:
        res = run_backtest(closes, cash, cfg, start=start, end=end, benchmark="_BENCH")
        s, b = summarize(res.returns, cash), summarize(res.benchmark, cash)
        print(f"=== {name}  ({s['Years']:.1f}y, {res.trades} rebalances) ===")
        print("  " + format_summary("TVM strategy", s))
        print("  " + format_summary("VOO buy & hold", b))
        print(f"  rolling 3y win rate vs VOO: {rolling_win_rate(res, 3):.0%}   5y: {rolling_win_rate(res, 5):.0%}   10y: {rolling_win_rate(res, 10):.0%}")
        exp = res.positions["exposure"]
        print(f"  avg exposure {exp.mean():.2f}x   time in cash {(exp == 0).mean():.0%}   "
              f"time in QQQ {((res.positions['asset'] == 'QQQ') & (exp > 0)).mean():.0%}\n")
        last = res

    if last is not None:
        yt = yearly_table(last)
        print("Year-by-year (last period above):")
        print(yt.to_string(float_format=lambda v: f"{v:8.1%}"))
        print(f"\nyears beating VOO: {(yt['excess'] > 0).sum()} / {len(yt)}")

    if not args.no_plot:
        full = run_backtest(closes, cash, cfg, start="1994-01-01", benchmark="_BENCH")
        _plot(full, cfg)


def _plot(res, cfg: TVMConfig) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    RESULTS.mkdir(exist_ok=True)
    eq = res.equity()
    dd = eq / eq.cummax() - 1
    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1.2, 1]})
    axes[0].plot(eq.index, eq["strategy"], label="TVM strategy", lw=1.4)
    axes[0].plot(eq.index, eq["benchmark"], label="VOO buy & hold (SPY pre-2010)", lw=1.2, alpha=0.85)
    axes[0].set_yscale("log"); axes[0].set_ylabel("Growth of $1 (log)"); axes[0].legend(loc="upper left")
    axes[0].set_title(f"TVM: {cfg.sma_window}d trend gate, {cfg.target_vol:.0%} vol target, {cfg.max_leverage:.0f}x cap, "
                      f"{'/'.join(cfg.risk_assets)} momentum")
    axes[1].fill_between(dd.index, dd["strategy"], 0, alpha=0.6, label="TVM drawdown")
    axes[1].fill_between(dd.index, dd["benchmark"], 0, alpha=0.35, label="VOO drawdown")
    axes[1].set_ylabel("Drawdown"); axes[1].legend(loc="lower left")
    axes[2].plot(res.positions.index, res.positions["exposure"], lw=0.8, color="tab:purple")
    axes[2].set_ylabel("Exposure (x)"); axes[2].set_ylim(0, cfg.max_leverage + 0.1)
    fig.tight_layout()
    out = RESULTS / "equity_curve.png"
    fig.savefig(out, dpi=130)
    print(f"\nchart written to {out}")

    yt = yearly_table(res)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(yt.index - 0.2, yt["strategy"], width=0.4, label="TVM")
    ax.bar(yt.index + 0.2, yt["benchmark"], width=0.4, label="VOO / SPY")
    ax.axhline(0, color="k", lw=0.6); ax.legend(); ax.set_title("Calendar-year returns")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(RESULTS / "yearly_returns.png", dpi=130)


if __name__ == "__main__":
    main()
