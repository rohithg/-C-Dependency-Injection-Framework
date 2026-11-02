"""Pure signal logic for the TVM strategy.

Nothing in this module talks to a broker or the network, so the exact same
code path drives the backtest and the live paper trader. The strategy is
expressed as:

    signals  = compute_signals(close_prices)      # vectorised, one row per day
    state'   = step(state, signals.loc[day])      # stateful decision w/ bands
    weights  = target_weights(state')             # ETF weights that implement it

Decision rules
--------------
1. Regime gate   : risk-on iff trend_symbol close > SMA(sma_window).
                   Risk-off => 100% cash_symbol.
2. Asset pick    : among risk_assets choose the highest momentum_window return,
                   but only re-evaluate once the current pick has been held
                   >= min_hold_days (cuts whipsaw between SPY and QQQ).
3. Sizing        : exposure = clip(target_vol / realized_vol, 0, max_leverage),
                   realized_vol = max over risk_assets of vol_window daily-return
                   std, annualised. A 2x ETF supplies exposure above 1.0.
4. Rebalance band: only trade when the regime flips, the asset changes, or
                   |target_exposure - current_exposure| > rebalance_band.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math

import numpy as np
import pandas as pd

from .config import TVMConfig, DEFAULT

TRADING_DAYS = 252
HOLD_UNKNOWN = 10**6   # sentinel: hold period certainly elapsed


@dataclass(frozen=True)
class State:
    asset: str                 # which risk asset is (or would be) held
    exposure: float            # notional exposure to that asset, 0..max_leverage
    days_held: int             # trading days since the asset pick last changed
    risk_on: bool

    @property
    def in_market(self) -> bool:
        return self.exposure > 0


def initial_state(cfg: TVMConfig = DEFAULT) -> State:
    return State(asset=cfg.risk_assets[0], exposure=0.0, days_held=HOLD_UNKNOWN, risk_on=False)


def compute_signals(close: pd.DataFrame, cfg: TVMConfig = DEFAULT) -> pd.DataFrame:
    """Return one row per trading day with everything `step` needs.

    `close` must contain adjusted closes for cfg.trend_symbol and every symbol
    in cfg.risk_assets. Values on row t use data up to and including t's
    close, so a trade acting on row t can be executed at (or just before) that
    close, or at the next open.
    """
    missing = {cfg.trend_symbol, *cfg.risk_assets} - set(close.columns)
    if missing:
        raise ValueError(f"close is missing columns: {sorted(missing)}")

    trend_px = close[cfg.trend_symbol]
    sma = trend_px.rolling(cfg.sma_window).mean()
    out = pd.DataFrame(index=close.index)
    out["risk_on"] = (trend_px > sma).where(sma.notna())

    rets = close[list(cfg.risk_assets)].pct_change()
    realized = rets.rolling(cfg.vol_window).std().max(axis=1) * math.sqrt(TRADING_DAYS)
    out["realized_vol"] = realized
    out["exposure_target"] = (cfg.target_vol / realized).clip(upper=cfg.max_leverage)

    for sym in cfg.risk_assets:
        out[f"mom_{sym}"] = close[sym].pct_change(cfg.momentum_window)
    return out


def best_asset(row: pd.Series, cfg: TVMConfig = DEFAULT) -> str | None:
    """Highest-momentum risk asset, or None if momentum is not yet defined."""
    moms = {sym: row.get(f"mom_{sym}") for sym in cfg.risk_assets}
    moms = {k: v for k, v in moms.items() if v is not None and not pd.isna(v)}
    if not moms:
        return None
    return max(moms, key=moms.get)


def step(state: State, row: pd.Series, cfg: TVMConfig = DEFAULT) -> tuple[State, bool]:
    """Advance one trading day. Returns (new_state, traded).

    `traded` is True when the target allocation changed enough to warrant
    sending orders; callers use it to count turnover or decide to hit the
    broker.
    """
    if pd.isna(row["risk_on"]) or pd.isna(row["exposure_target"]):
        return replace(state, days_held=_bump(state.days_held)), False

    risk_on = bool(row["risk_on"])
    want_exposure = float(row["exposure_target"]) if risk_on else 0.0

    want_asset = state.asset
    if state.days_held >= cfg.min_hold_days:
        pick = best_asset(row, cfg)
        if pick is not None:
            want_asset = pick

    asset_changed = want_asset != state.asset
    regime_flipped = (want_exposure == 0) != (state.exposure == 0)
    outside_band = abs(want_exposure - state.exposure) > cfg.rebalance_band

    # Switching asset while flat is free bookkeeping, not a trade.
    if asset_changed and want_exposure == 0 and state.exposure == 0:
        return State(want_asset, 0.0, 0, risk_on), False

    if (asset_changed and want_exposure > 0) or regime_flipped or outside_band:
        return State(want_asset, want_exposure, 0 if asset_changed else _bump(state.days_held), risk_on), True

    return replace(state, days_held=_bump(state.days_held), risk_on=risk_on), False


def _bump(days_held: int) -> int:
    """Increment the hold counter without letting the 'unknown' sentinel grow."""
    return min(days_held + 1, HOLD_UNKNOWN)


def target_weights(state: State, cfg: TVMConfig = DEFAULT) -> dict[str, float]:
    """Translate (asset, exposure) into portfolio weights over tradable ETFs.

    exposure <= 1 : exposure in the 1x ETF, remainder in cash ETF
    exposure  > 1 : (exposure - 1) in the 2x ETF, (2 - exposure) in the 1x ETF
                    (weights sum to 1, notional exposure = 2*w2 + w1 = exposure)
    """
    e = min(max(state.exposure, 0.0), cfg.max_leverage)
    weights: dict[str, float] = {}
    if e <= 1.0:
        if e > 0:
            weights[state.asset] = e
        if 1.0 - e > 1e-9:
            weights[cfg.cash_symbol] = 1.0 - e
    else:
        lev_sym = cfg.leveraged_2x[state.asset]
        weights[lev_sym] = e - 1.0
        if 2.0 - e > 1e-9:
            weights[state.asset] = 2.0 - e
    return {k: round(v, 6) for k, v in weights.items() if v > 1e-9}


def exposure_from_weights(weights: dict[str, float], cfg: TVMConfig = DEFAULT) -> tuple[str, float]:
    """Inverse of target_weights: infer (asset, exposure) from live positions.

    Used by the paper trader to reconstruct state from the broker instead of
    trusting a local file that could drift from reality.
    """
    inv_lev = {v: k for k, v in cfg.leveraged_2x.items()}
    exposure_by_asset: dict[str, float] = {a: 0.0 for a in cfg.risk_assets}
    for sym, w in weights.items():
        if sym in exposure_by_asset:
            exposure_by_asset[sym] += w
        elif sym in inv_lev:
            exposure_by_asset[inv_lev[sym]] += 2.0 * w
    asset = max(exposure_by_asset, key=exposure_by_asset.get)
    return asset, exposure_by_asset[asset]


def run_states(signals: pd.DataFrame, cfg: TVMConfig = DEFAULT,
               start_state: State | None = None) -> pd.DataFrame:
    """Replay `step` over every row; returns per-day asset/exposure/traded."""
    state = start_state or initial_state(cfg)
    rows = []
    for ts, row in signals.iterrows():
        state, traded = step(state, row, cfg)
        rows.append((ts, state.asset, state.exposure, state.risk_on, traded))
    return pd.DataFrame(rows, columns=["date", "asset", "exposure", "risk_on", "traded"]).set_index("date")
