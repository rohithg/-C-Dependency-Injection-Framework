"""Backtest engine for TVM vs. a buy-and-hold benchmark.

Execution model
---------------
* Signals on day t use closes through t; the resulting position earns the
  return from close(t) to close(t+1). This matches running the live trader in
  the last minutes of the session (or at the next open, with a small gap).
* Exposure above 1x comes from the real 2x ETF (SSO/QLD) when it has data.
  Before their 2006 inception a synthetic 2x is used:
      2*r_asset - (t_bill + borrow_spread + expense) / 252
  which is a slightly pessimistic model of how daily-reset leveraged ETFs are
  financed.
* Transaction cost = cost_bps on fund dollars traded (sum of |weight change|).
  An asset switch therefore costs a full round trip.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from .config import TVMConfig, DEFAULT
from .strategy import compute_signals, run_states, target_weights, State

TRADING_DAYS = 252


@dataclass
class BacktestResult:
    returns: pd.Series            # daily strategy returns (net of costs)
    benchmark: pd.Series          # daily benchmark returns
    positions: pd.DataFrame       # asset / exposure / risk_on / traded per day
    weights: pd.DataFrame         # ETF weights actually held each day
    trades: int

    def equity(self) -> pd.DataFrame:
        return pd.DataFrame({
            "strategy": (1 + self.returns).cumprod(),
            "benchmark": (1 + self.benchmark).cumprod(),
        })


def run_backtest(closes: pd.DataFrame, cash_returns: pd.Series, cfg: TVMConfig = DEFAULT,
                 start: str | None = None, end: str | None = None,
                 benchmark: str | None = None, synthetic_leverage_only: bool = False) -> BacktestResult:
    benchmark = benchmark or cfg.benchmark_symbol
    if benchmark not in closes:
        raise ValueError(f"benchmark {benchmark} not in closes")

    signals = compute_signals(closes, cfg)
    states = run_states(signals, cfg)
    # Position decided at close t is held over t -> t+1
    held = states.shift(1)

    rets = closes.pct_change()
    cash = cash_returns.reindex(closes.index).fillna(0.0)

    strat = pd.Series(np.nan, index=closes.index)
    weight_rows = []
    trades = 0
    prev_weights: dict[str, float] = {}

    for i, ts in enumerate(closes.index):
        row = held.iloc[i]
        if i == 0 or pd.isna(row["exposure"]):
            weight_rows.append({})
            continue
        state = State(row["asset"], float(row["exposure"]), 0, bool(row["risk_on"]))
        w = target_weights(state, cfg)

        day_ret = 0.0
        for sym, wt in w.items():
            if sym == cfg.cash_symbol:
                r = cash.iloc[i]
            elif sym in cfg.leveraged_2x.values():
                r = _leveraged_return(sym, i, rets, cash, cfg, synthetic_leverage_only)
            else:
                r = rets[sym].iloc[i]
            if pd.isna(r):
                r = 0.0
            day_ret += wt * r

        cost = 0.0
        if row["traded"]:
            trades += 1
            # costs accrue on fund dollars traded (spread + commission), not on
            # the underlying notional a 2x fund represents
            turnover = sum(abs(w.get(s, 0.0) - prev_weights.get(s, 0.0)) for s in set(w) | set(prev_weights))
            cost = turnover * cfg.cost_bps / 1e4
        prev_weights = w
        strat.iloc[i] = day_ret - cost
        weight_rows.append(w)

    weights = pd.DataFrame(weight_rows, index=closes.index).fillna(0.0)
    bench = rets[benchmark]

    sl = slice(start, end)
    strat, bench, states, weights = strat.loc[sl], bench.loc[sl], states.loc[sl], weights.loc[sl]
    valid = strat.notna() & bench.notna()
    first = valid.idxmax() if valid.any() else strat.index[0]
    strat, bench = strat.loc[first:].fillna(0.0), bench.loc[first:].fillna(0.0)
    trade_count = int(states.loc[first:, "traded"].sum())
    return BacktestResult(strat, bench, states.loc[first:], weights.loc[first:], trade_count)


def _leveraged_return(sym: str, i: int, rets: pd.DataFrame, cash: pd.Series, cfg: TVMConfig,
                      synthetic_only: bool) -> float:
    base = next(k for k, v in cfg.leveraged_2x.items() if v == sym)
    if not synthetic_only and sym in rets and not pd.isna(rets[sym].iloc[i]):
        return float(rets[sym].iloc[i])
    r = rets[base].iloc[i]
    if pd.isna(r):
        return 0.0
    financing = (cash.iloc[i] + (cfg.borrow_spread + cfg.lev_etf_expense) / TRADING_DAYS)
    return 2.0 * float(r) - financing


# --------------------------------------------------------------------------- metrics

def summarize(returns: pd.Series, rf: pd.Series | None = None) -> dict[str, float]:
    r = returns.dropna()
    if r.empty:
        return {}
    eq = (1 + r).cumprod()
    years = len(r) / TRADING_DAYS
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = r.std() * math.sqrt(TRADING_DAYS)
    excess = r - (rf.reindex(r.index).fillna(0.0) if rf is not None else 0.0)
    sharpe = excess.mean() / excess.std() * math.sqrt(TRADING_DAYS) if excess.std() > 0 else np.nan
    downside = r[r < 0].std() * math.sqrt(TRADING_DAYS)
    sortino = r.mean() * TRADING_DAYS / downside if downside > 0 else np.nan
    dd = eq / eq.cummax() - 1
    return {
        "CAGR": cagr, "Vol": vol, "Sharpe": sharpe, "Sortino": sortino,
        "MaxDD": dd.min(), "Calmar": cagr / abs(dd.min()) if dd.min() < 0 else np.nan,
        "Final multiple": eq.iloc[-1], "Years": years,
    }


def yearly_table(result: BacktestResult) -> pd.DataFrame:
    df = pd.DataFrame({"strategy": result.returns, "benchmark": result.benchmark})
    yearly = df.resample("YE").apply(lambda x: (1 + x).prod() - 1)
    yearly.index = yearly.index.year
    yearly["excess"] = yearly["strategy"] - yearly["benchmark"]
    return yearly


def rolling_win_rate(result: BacktestResult, years: int) -> float:
    eq = result.equity()
    n = years * TRADING_DAYS
    if len(eq) <= n:
        return float("nan")
    roll = eq.pct_change(n).dropna()
    return float((roll["strategy"] > roll["benchmark"]).mean())


def format_summary(name: str, s: dict[str, float]) -> str:
    return (f"{name:<28s} CAGR {s['CAGR']:7.2%}  Vol {s['Vol']:6.2%}  Sharpe {s['Sharpe']:5.2f}  "
            f"MaxDD {s['MaxDD']:7.2%}  Calmar {s['Calmar']:5.2f}  x{s['Final multiple']:6.2f}")
