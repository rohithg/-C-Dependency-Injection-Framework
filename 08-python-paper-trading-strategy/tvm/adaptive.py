"""Adaptive layer: learn which TVM variant to trust from realised mistakes.

Instead of betting on one parameter set, a pool of *experts* (TVM variants
with different trend windows, momentum horizons and risk budgets, plus plain
buy-and-hold as a safety net) is run as virtual portfolios every day. A
multiplicative-weights learner (Hedge / exponentiated gradient with
forgetting) moves capital toward experts that have been earning and away from
those that have recently lost. The real portfolio holds the weight-averaged
target of all experts.

Why this and not "an ML model that predicts returns":
* Hedge has a regret bound: over time the blend does nearly as well as the
  best single expert in hindsight, whatever the market did. A return
  forecaster has no such guarantee and is notoriously easy to overfit.
* Everything is recomputed from price history on every run, so there is no
  learned state that can drift, corrupt, or need retraining.
* With buy-and-hold in the pool, the worst case is "converge to VOO", not
  "converge to something broken".

Timing: learner weights for day t use expert returns through close t; the
combined target decided at close t is held over t -> t+1.
"""
from __future__ import annotations

from dataclasses import dataclass, replace, field
import math

import numpy as np
import pandas as pd

from .config import TVMConfig, DEFAULT
from .strategy import compute_signals, run_states, target_weights, State

TRADING_DAYS = 252


@dataclass(frozen=True)
class Expert:
    name: str
    cfg: TVMConfig
    kind: str = "tvm"            # "tvm" | "hold"


@dataclass(frozen=True)
class AdaptiveConfig:
    eta: float = 10.0            # learning rate: exp(eta * score) weighting
    halflife_days: int = 126     # forgetting: how fast old mistakes are forgiven
    portfolio_band: float = 0.10 # L1 distance between held and target weights that triggers a trade
    max_leverage: float = 2.0    # hard cap on combined notional exposure
    experts: tuple[str, ...] = ()  # subset of default experts to use; empty = all


def default_experts(base: TVMConfig = DEFAULT) -> list[Expert]:
    experts: list[Expert] = []
    for sma in (150, 200, 250):
        for mom in (63, 126, 252):
            experts.append(Expert(f"sma{sma}/mom{mom}/tv20", replace(base, sma_window=sma, momentum_window=mom, target_vol=0.20)))
    experts.append(Expert("sma200/mom126/tv15", replace(base, target_vol=0.15)))
    experts.append(Expert("sma200/mom126/tv25", replace(base, target_vol=0.25)))
    experts.append(Expert("sma200/mom126/no-leverage", replace(base, max_leverage=1.0)))
    experts.append(Expert("sma200/spy-only/tv20", replace(base, risk_assets=(base.trend_symbol,))))
    # mistake-aware variants
    experts.append(Expert("whipsaw-aware/mom126/tv20", replace(base, whipsaw_penalty=0.005, whipsaw_max=0.03)))
    experts.append(Expert("sma-vote100-300/mom126/tv20", replace(base, trend_vote_windows=(100, 150, 200, 250, 300))))
    experts.append(Expert("buy-and-hold", base, kind="hold"))
    return experts


# --------------------------------------------------------------------------- building blocks

def tradable_symbols(cfg: TVMConfig) -> list[str]:
    return sorted({cfg.cash_symbol, *cfg.risk_assets, *cfg.leveraged_2x.values()})


def etf_returns(closes: pd.DataFrame, cash: pd.Series, cfg: TVMConfig = DEFAULT) -> pd.DataFrame:
    """Daily returns for every tradable ETF. 2x funds fall back to a synthetic
    2*r - financing before their inception; cash ETF falls back to T-bill."""
    rets = closes.pct_change()
    out = pd.DataFrame(index=closes.index)
    cash = cash.reindex(closes.index).fillna(0.0)
    out[cfg.cash_symbol] = rets[cfg.cash_symbol].fillna(cash) if cfg.cash_symbol in rets else cash
    for sym in cfg.risk_assets:
        out[sym] = rets[sym]
        lev = cfg.leveraged_2x[sym]
        synthetic = 2.0 * rets[sym] - (cash + (cfg.borrow_spread + cfg.lev_etf_expense) / TRADING_DAYS)
        out[lev] = rets[lev].fillna(synthetic) if lev in rets else synthetic
    return out.fillna(0.0)


def expert_targets(closes: pd.DataFrame, expert: Expert) -> pd.DataFrame:
    """Target ETF weights decided at each close (NaN rows during warm-up)."""
    cfg = expert.cfg
    cols = tradable_symbols(cfg)
    if expert.kind == "hold":
        w = pd.DataFrame(0.0, index=closes.index, columns=cols)
        w[cfg.trend_symbol] = 1.0
        return w
    sig = compute_signals(closes, cfg)
    states = run_states(sig, cfg)
    # run_states reports "flat" during warm-up; for scoring purposes the
    # expert simply has no opinion yet, so mark those rows undefined
    warm = (sig["risk_on"].isna() | sig["exposure_target"].isna()).to_numpy()
    rows = []
    for i, row in enumerate(states.itertuples()):
        if warm[i] or pd.isna(row.exposure):
            rows.append(None)
            continue
        rows.append(target_weights(State(row.asset, float(row.exposure), 0, bool(row.risk_on)), cfg))
    w = pd.DataFrame([r if r is not None else {} for r in rows], index=closes.index).reindex(columns=cols).fillna(0.0)
    w.loc[[r is None for r in rows]] = np.nan
    return w


def portfolio_returns(targets: pd.DataFrame, etf_rets: pd.DataFrame, cost_bps: float) -> pd.Series:
    """Returns of holding `targets` (decided at t) over t -> t+1, net of costs.
    Trades every day the target changes (no band) - fine for scoring experts."""
    held = targets.shift(1)
    gross = (held * etf_rets.reindex(columns=held.columns).fillna(0.0)).sum(axis=1)
    turnover = held.diff().abs().sum(axis=1)
    out = gross - turnover * cost_bps / 1e4
    out[held.isna().all(axis=1)] = np.nan
    return out


def hedge_weights(expert_rets: pd.DataFrame, eta: float, halflife_days: int) -> pd.DataFrame:
    """Multiplicative weights with exponential forgetting.

    score_i(t) = lambda * score_i(t-1) + log(1 + r_i(t)), lambda = 0.5^(1/halflife)
    w_i(t)    = exp(eta * score_i(t)) / sum_j exp(eta * score_j(t))
    """
    lam = 0.5 ** (1.0 / halflife_days)
    log_r = np.log1p(expert_rets.fillna(0.0))
    # ewm with adjust=False gives y_t = lam*y_{t-1} + (1-lam)*x_t ; divide by (1-lam) for the discounted sum
    score = log_r.ewm(alpha=1 - lam, adjust=False).mean() / (1 - lam)
    # experts still warming up get the worst live score so they carry ~no weight
    score = score.where(expert_rets.notna(), score.min(axis=1), axis=0)
    z = eta * score.sub(score.max(axis=1), axis=0)
    w = np.exp(z)
    return w.div(w.sum(axis=1), axis=0)


def cap_exposure(weights: pd.Series | dict, cfg: TVMConfig, max_leverage: float) -> dict[str, float]:
    """Scale risk weights down (into cash) if combined notional exceeds the cap."""
    w = dict(weights)
    lev_syms = set(cfg.leveraged_2x.values())
    exposure = sum(v * (2.0 if s in lev_syms else 1.0) for s, v in w.items() if s != cfg.cash_symbol)
    if exposure > max_leverage and exposure > 0:
        k = max_leverage / exposure
        for s in list(w):
            if s != cfg.cash_symbol:
                w[s] *= k
        w[cfg.cash_symbol] = max(0.0, 1.0 - sum(v for s, v in w.items() if s != cfg.cash_symbol))
    return {s: round(float(v), 6) for s, v in w.items() if v > 1e-9}


# --------------------------------------------------------------------------- the ensemble

@dataclass
class AdaptiveResult:
    returns: pd.Series                 # net daily returns of the blended portfolio
    held: pd.DataFrame                 # ETF weights actually held each day (after band)
    targets: pd.DataFrame              # blended target weights decided each close
    learner_weights: pd.DataFrame      # expert weights per day
    expert_returns: pd.DataFrame       # virtual portfolio returns per expert
    trades: int


def run_adaptive(closes: pd.DataFrame, cash: pd.Series, base: TVMConfig = DEFAULT,
                 acfg: AdaptiveConfig = AdaptiveConfig(), experts: list[Expert] | None = None) -> AdaptiveResult:
    experts = experts or default_experts(base)
    if acfg.experts:
        experts = [e for e in experts if e.name in acfg.experts]
    cols = tradable_symbols(base)
    rets = etf_returns(closes, cash, base)

    targets = {e.name: expert_targets(closes, e).reindex(columns=cols) for e in experts}
    exp_rets = pd.DataFrame({n: portfolio_returns(t, rets, base.cost_bps) for n, t in targets.items()})
    lw = hedge_weights(exp_rets, acfg.eta, acfg.halflife_days)

    # Experts still warming up have no opinion: renormalise the learner weights
    # over the experts that do, so the blend always sums to 1.
    defined = pd.DataFrame({n: t.notna().all(axis=1) for n, t in targets.items()})
    eff = lw.where(defined, 0.0)
    eff = eff.div(eff.sum(axis=1).replace(0.0, np.nan), axis=0)
    blended = pd.DataFrame(0.0, index=closes.index, columns=cols)
    for n, t in targets.items():
        blended += t.fillna(0.0).mul(eff[n].fillna(0.0), axis=0)
    blended[eff.isna().all(axis=1)] = np.nan   # every expert warming up

    # execute with a band: trade only when target drifts far enough from held
    # `cur` = weights held going into day i (decided at close i-1). Day i's
    # return is cur . rets[i]; afterwards we decide what to hold for i+1 and
    # charge that trade's cost against day i.
    held_rows, ret_vals, trades = [], [], 0
    cur = None
    for i in range(len(closes)):
        tgt = blended.iloc[i]
        if tgt.isna().any():
            held_rows.append(None); ret_vals.append(np.nan)
            continue
        r_i = float((cur * rets.iloc[i]).sum()) if cur is not None else np.nan
        capped = pd.Series(cap_exposure(tgt, base, acfg.max_leverage)).reindex(cols).fillna(0.0)
        dist = float((capped - cur).abs().sum()) if cur is not None else np.inf
        if dist > acfg.portfolio_band:
            if cur is not None:
                r_i -= dist * base.cost_bps / 1e4
            cur = capped
            trades += 1
        held_rows.append(cur); ret_vals.append(r_i)
    held = pd.DataFrame([r if r is not None else {} for r in held_rows], index=closes.index).reindex(columns=cols)
    returns = pd.Series(ret_vals, index=closes.index)
    return AdaptiveResult(returns, held, blended, lw, exp_rets, trades)


def latest_allocation(closes: pd.DataFrame, cash: pd.Series, base: TVMConfig = DEFAULT,
                      acfg: AdaptiveConfig = AdaptiveConfig()) -> tuple[dict[str, float], pd.DataFrame]:
    """For the live trader: today's blended target weights and a leaderboard
    (learner weight, trailing 1y return) per expert, best-weighted first."""
    res = run_adaptive(closes, cash, base, acfg)
    target = cap_exposure(res.targets.iloc[-1].fillna(0.0), base, acfg.max_leverage)
    lw = res.learner_weights.iloc[-1].sort_values(ascending=False)
    trailing = (1 + res.expert_returns.iloc[-TRADING_DAYS:].fillna(0.0)).prod() - 1
    board = pd.DataFrame({"weight": lw, "trailing_1y": trailing.reindex(lw.index)})
    return target, board


# --------------------------------------------------------------------------- post-mortem

def regime_postmortem(closes: pd.DataFrame, cfg: TVMConfig = DEFAULT, last_n: int = 5) -> pd.DataFrame:
    """Score each completed regime exit of the base rules.

    For every exit (risk-on -> risk-off) that was later followed by a re-entry,
    report what the trend asset did in between. A positive `missed` means the
    exit was a whipsaw (price was higher when we got back in: a mistake); a
    negative value means the exit avoided a loss. This is the raw material the
    whipsaw-aware expert learns from, surfaced so a human can see it too.
    """
    sig = compute_signals(closes, cfg)
    on = sig["risk_on"].dropna().astype(bool)
    px = closes[cfg.trend_symbol]
    rows, exit_day, was_on = [], None, False
    for day, flag in on.items():
        if was_on and not flag:
            exit_day = day
        elif not was_on and flag and exit_day is not None:
            missed = float(px.loc[day] / px.loc[exit_day] - 1)
            rows.append({"exit": exit_day, "reentry": day, "days_out": int(on.loc[exit_day:day].shape[0] - 1),
                         "missed": missed, "verdict": "whipsaw (mistake)" if missed > 0 else "avoided loss"})
            exit_day = None
        was_on = flag
    if exit_day is not None:
        rows.append({"exit": exit_day, "reentry": None, "days_out": int(on.loc[exit_day:].shape[0] - 1),
                     "missed": float(px.iloc[-1] / px.loc[exit_day] - 1), "verdict": "still out"})
    df = pd.DataFrame(rows, columns=["exit", "reentry", "days_out", "missed", "verdict"])
    return df.tail(last_n)
