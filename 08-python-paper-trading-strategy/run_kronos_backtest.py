#!/usr/bin/env python3
"""Walk-forward evaluation of the Kronos candlestick forecaster as a trading signal.

    python run_kronos_backtest.py                      # extend the forecast cache, print report
    python run_kronos_backtest.py --no-extend          # reuse results/kronos_forecasts_*.csv only
    python run_kronos_backtest.py --variant mini --start 2023-01-01

Each day the model sees only bars up to that close and samples `samples`
5-day candle paths for SPY and QQQ (~3s/day on a 4-core CPU for Kronos-small).
Forecasts are cached in results/ so the report can be regenerated instantly.

The public Kronos checkpoints were pre-trained on data through June 2024, so
results are split into the overlapping window and the truly out-of-sample
window from July 2024 onward.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from tvm.config import TVMConfig, DEFAULT
from tvm.data import load_closes, load_ohlcv, tbill_daily_return
from tvm.backtest import summarize, format_summary
from tvm.adaptive import run_adaptive, AdaptiveConfig, etf_returns, portfolio_returns, cap_exposure, tradable_symbols
from tvm.kronos_signal import KronosConfig, walk_forward, load_forecasts, calibrate, rule_targets, FORECAST_COLS

warnings.filterwarnings("ignore", category=FutureWarning)

RESULTS = Path(__file__).resolve().parent / "results"
TRAIN_CUTOFF = "2024-06-30"      # end of Kronos pre-training data

RULE_VARIANTS = {
    "Kronos direction (raw sign)": KronosConfig(rule="direction"),
    "Kronos calibrated (z>0)": KronosConfig(rule="calibrated"),
    "Kronos calibrated (z>0.5)": KronosConfig(rule="calibrated", min_edge=0.5),
    "Kronos relative (SPY vs QQQ)": KronosConfig(rule="relative"),
    "Kronos confidence (<=2x)": KronosConfig(rule="confidence", confidence_scale=1.0, max_leverage=2.0),
    "TVM ensemble + Kronos veto": KronosConfig(rule="tvm-veto"),
}


def _rank_ic(a: pd.Series, b: pd.Series) -> float:
    """Spearman correlation without scipy."""
    m = a.notna() & b.notna()
    return float(a[m].rank().corr(b[m].rank())) if m.sum() > 2 else float("nan")


def information_content(long: pd.DataFrame, closes: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """How much does the forecast know? Per symbol and window: rank
    correlation with the realised forward return, sign hit-rate, mean bias."""
    rows = []
    for sym, g in long.groupby("symbol"):
        g = g.set_index("date").sort_index()
        fwd = closes[sym].shift(-horizon) / closes[sym] - 1
        fwd1 = closes[sym].shift(-1) / closes[sym] - 1
        g = g.join(fwd.rename("fwd")).join(fwd1.rename("fwd1")).dropna(subset=["fwd"])
        for win, part in (("<= 2024-06 (in training data)", g.loc[:TRAIN_CUTOFF]), ("2024-07 -> (out of sample)", g.loc[TRAIN_CUTOFF:].iloc[1:])):
            if len(part) < 30:
                continue
            rows.append({
                "symbol": sym, "window": win, "days": len(part),
                "IC exp_ret vs fwd": _rank_ic(part["exp_ret"], part["fwd"]),
                "IC z_ret vs fwd": _rank_ic(part["z_ret"], part["fwd"]),
                "IC 1d": _rank_ic(part["exp_ret_1d"], part["fwd1"]),
                "sign hit-rate": (np.sign(part["exp_ret"]) == np.sign(part["fwd"])).mean(),
                "mean exp_ret": part["exp_ret"].mean(), "mean realised": part["fwd"].mean(),
                "days exp_ret>0": (part["exp_ret"] > 0).mean(),
            })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="small", choices=["mini", "small", "base"])
    ap.add_argument("--start", default="2022-01-01", help="first forecast date")
    ap.add_argument("--no-extend", action="store_true", help="do not run the model; use cached forecasts only")
    ap.add_argument("--refresh", action="store_true", help="ignore the price cache")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    tvm_cfg = DEFAULT
    kcfg = KronosConfig(variant=args.variant)
    symbols = sorted({*tradable_symbols(tvm_cfg), tvm_cfg.trend_symbol, tvm_cfg.benchmark_symbol, "^IRX", *kcfg.symbols})
    closes = load_closes(symbols, start="2007-01-01", refresh=args.refresh)
    cash = tbill_daily_return(closes)
    bars = {s: load_ohlcv(s, start="2000-01-01", refresh=args.refresh) for s in kcfg.symbols}

    cache = kcfg.forecast_cache()
    if args.no_extend:
        long = load_forecasts(cache)
    else:
        dates = closes.loc[args.start:].index
        dates = dates[dates.isin(bars[kcfg.symbols[0]].index)]
        long = walk_forward(bars, dates, kcfg, cache_path=cache)
    if long.empty:
        raise SystemExit(f"no forecasts in {cache}; run without --no-extend")
    long = calibrate(long)
    first, last = long["date"].min(), long["date"].max()
    print(f"Kronos-{args.variant}: {long['date'].nunique()} forecast days {first.date()} -> {last.date()} "
          f"(context {kcfg.context}, horizon {kcfg.horizon}, {kcfg.samples} paths)\n")

    ic = information_content(long, closes, kcfg.horizon)
    print("Information content of the raw forecasts:")
    print(ic.to_string(index=False, float_format=lambda v: f"{v:7.3f}"))
    print()

    # --- strategies ------------------------------------------------------
    rets = etf_returns(closes, cash, tvm_cfg)
    ares = run_adaptive(closes, cash, tvm_cfg, AdaptiveConfig(max_leverage=tvm_cfg.max_leverage))
    tvm_targets = ares.targets.apply(
        lambda r: pd.Series(cap_exposure(r.fillna(0.0), tvm_cfg, tvm_cfg.max_leverage)) if not r.isna().any() else r, axis=1
    ).reindex(columns=ares.targets.columns).fillna(0.0)
    tvm_targets[ares.targets.isna().any(axis=1)] = np.nan

    curves: dict[str, pd.Series] = {}
    dates = pd.DatetimeIndex(sorted(long["date"].unique()))
    curves["VOO buy & hold"] = closes[tvm_cfg.benchmark_symbol].pct_change().reindex(dates)
    curves["TVM adaptive ensemble"] = ares.returns.reindex(dates)
    turnover: dict[str, float] = {}
    for name, cfg in RULE_VARIANTS.items():
        tgt = rule_targets(long, cfg, tvm_cfg, tvm_targets if cfg.rule == "tvm-veto" else None)
        # align with the ETF return calendar; a day without a forecast keeps yesterday's target
        tgt = tgt.reindex(rets.loc[tgt.index[0]:tgt.index[-1]].index).ffill()
        pr = portfolio_returns(tgt, rets.loc[tgt.index], tvm_cfg.cost_bps)
        curves[name] = pr.reindex(dates)
        turnover[name] = float(tgt.diff().abs().sum(axis=1).mean() * 252 / 2)   # one-way turnover per year
    curves["TVM adaptive ensemble"] = curves["TVM adaptive ensemble"]

    windows = [
        ("Whole forecast window", None, None),
        ("Overlaps Kronos training data (-> 2024-06)", None, TRAIN_CUTOFF),
        ("Out of sample for Kronos (2024-07 ->)", "2024-07-01", None),
    ]
    report_lines = []
    for title, s, e in windows:
        sl = slice(s, e)
        print(f"=== {title} ===")
        report_lines.append(f"\n**{title}**\n\n| strategy | CAGR | Vol | Sharpe | MaxDD | turnover/yr |\n|---|---|---|---|---|---|")
        for name, r in curves.items():
            rr = r.loc[sl].dropna()
            if rr.empty:
                continue
            smry = summarize(rr, cash)
            print("  " + format_summary(name, smry))
            to = f"{turnover[name]:.1f}" if name in turnover else "-"
            report_lines.append(f"| {name} | {smry['CAGR']:.1%} | {smry['Vol']:.1%} | {smry['Sharpe']:.2f} | {smry['MaxDD']:.1%} | {to} |")
        print()

    RESULTS.mkdir(exist_ok=True)
    md = (f"# Kronos-{args.variant} walk-forward results\n\nForecast days {first.date()} -> {last.date()}; "
          f"context {kcfg.context} bars, horizon {kcfg.horizon} days, {kcfg.samples} sampled paths/day. "
          f"Costs {tvm_cfg.cost_bps:.0f} bps per dollar traded.\n\n## Information content\n\n"
          + _md_table(ic) + "\n\n## Strategies\n" + "\n".join(report_lines) + "\n")
    (RESULTS / f"kronos_backtest_{args.variant}.md").write_text(md)
    print(f"report written to {RESULTS / f'kronos_backtest_{args.variant}.md'}")

    if not args.no_plot:
        _plot(curves, args.variant)


def _md_table(df: pd.DataFrame) -> str:
    fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns)
    body = "\n".join("| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False))
    return head + "\n" + body


def _plot(curves: dict[str, pd.Series], variant: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 6))
    for name, r in curves.items():
        eq = (1 + r.fillna(0.0)).cumprod()
        ax.plot(eq.index, eq, lw=1.6 if name.startswith(("VOO", "TVM adaptive")) else 1.0, label=name,
                alpha=1.0 if name.startswith(("VOO", "TVM adaptive")) else 0.8)
    ax.axvline(pd.Timestamp(TRAIN_CUTOFF), color="k", ls="--", lw=0.8)
    ax.text(pd.Timestamp(TRAIN_CUTOFF), ax.get_ylim()[1], " end of Kronos training data", va="top", fontsize=8)
    ax.set_yscale("log"); ax.set_ylabel("Growth of $1 (log)"); ax.legend(loc="upper left", fontsize=8)
    ax.set_title(f"Kronos-{variant} forecast rules vs TVM ensemble vs VOO")
    fig.tight_layout()
    out = RESULTS / f"kronos_equity_{variant}.png"
    fig.savefig(out, dpi=130)
    print(f"chart written to {out}")


if __name__ == "__main__":
    main()
