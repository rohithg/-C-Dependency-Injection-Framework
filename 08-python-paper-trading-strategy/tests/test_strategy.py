"""Unit tests for the pure signal logic. Synthetic data only; no network."""
import math

import numpy as np
import pandas as pd
import pytest

from tvm.config import TVMConfig
from tvm.strategy import (State, compute_signals, step, target_weights, exposure_from_weights,
                          initial_state, run_states, best_asset)

CFG = TVMConfig()


def make_closes(n=400, spy_drift=0.0004, qqq_drift=0.0006, vol=0.01, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    spy = 100 * np.exp(np.cumsum(rng.normal(spy_drift, vol, n)))
    qqq = 100 * np.exp(np.cumsum(rng.normal(qqq_drift, vol, n)))
    return pd.DataFrame({"SPY": spy, "QQQ": qqq}, index=idx)


def test_signals_shape_and_warmup():
    closes = make_closes()
    sig = compute_signals(closes, CFG)
    assert set(sig.columns) == {"risk_on", "entry_threshold", "realized_vol", "exposure_target", "mom_SPY", "mom_QQQ"}
    assert sig["risk_on"].iloc[: CFG.sma_window - 1].isna().all()
    assert sig["risk_on"].iloc[CFG.sma_window:].notna().all()
    assert (sig["exposure_target"].dropna() <= CFG.max_leverage).all()


def test_exposure_target_is_target_vol_over_realized_vol_capped():
    closes = make_closes(vol=0.02)   # ~32% annualised -> exposure ~0.63
    sig = compute_signals(closes, CFG).dropna()
    expected = (CFG.target_vol / sig["realized_vol"]).clip(upper=CFG.max_leverage)
    pd.testing.assert_series_equal(sig["exposure_target"], expected, check_names=False)
    assert 0.3 < sig["exposure_target"].mean() < 1.0


def test_low_vol_hits_leverage_cap():
    closes = make_closes(vol=0.003)  # ~5% annualised -> wants 4x, capped at 2x
    sig = compute_signals(closes, CFG).dropna()
    assert (sig["exposure_target"] == CFG.max_leverage).all()


def test_trend_gate_goes_to_cash_in_downtrend():
    closes = make_closes(spy_drift=-0.003, qqq_drift=-0.003, vol=0.005)
    states = run_states(compute_signals(closes, CFG), CFG)
    assert (states["exposure"].iloc[-50:] == 0).all()


def test_target_weights_round_trip():
    for exposure in [0.0, 0.4, 1.0, 1.3, 2.0]:
        for asset in CFG.risk_assets:
            st = State(asset, exposure, 0, exposure > 0)
            w = target_weights(st, CFG)
            assert math.isclose(sum(w.values()), 1.0, abs_tol=1e-6)
            inferred_asset, inferred_exposure = exposure_from_weights(w, CFG)
            assert math.isclose(inferred_exposure, exposure, abs_tol=1e-6)
            if exposure > 0:
                assert inferred_asset == asset


def test_target_weights_uses_2x_etf_above_one():
    w = target_weights(State("QQQ", 1.5, 0, True), CFG)
    assert w == {"QLD": 0.5, "QQQ": 0.5}
    w = target_weights(State("SPY", 0.75, 0, True), CFG)
    assert w == {"SPY": 0.75, "BIL": 0.25}
    assert target_weights(State("SPY", 0.0, 0, False), CFG) == {"BIL": 1.0}


def _row(risk_on=True, exposure_target=1.5, mom_spy=0.05, mom_qqq=0.10):
    return pd.Series({"risk_on": risk_on, "realized_vol": 0.13, "exposure_target": exposure_target,
                      "mom_SPY": mom_spy, "mom_QQQ": mom_qqq})


def test_step_rebalance_band_suppresses_small_changes():
    st = State("QQQ", 1.5, 100, True)
    new, traded = step(st, _row(exposure_target=1.55), CFG)
    assert not traded and new.exposure == 1.5 and new.days_held == 101
    new, traded = step(st, _row(exposure_target=1.75), CFG)
    assert traded and new.exposure == 1.75


def test_step_regime_flip_always_trades():
    st = State("QQQ", 1.5, 100, True)
    new, traded = step(st, _row(risk_on=False), CFG)
    assert traded and new.exposure == 0.0 and not new.risk_on
    # and back in, even for a small target
    new2, traded2 = step(new, _row(risk_on=True, exposure_target=0.05), CFG)
    assert traded2 and new2.exposure == 0.05


def test_step_min_hold_blocks_asset_switch():
    st = State("SPY", 1.5, 5, True)                 # held only 5 days
    new, traded = step(st, _row(mom_spy=0.0, mom_qqq=0.2), CFG)
    assert new.asset == "SPY" and not traded
    st = State("SPY", 1.5, CFG.min_hold_days, True)
    new, traded = step(st, _row(mom_spy=0.0, mom_qqq=0.2), CFG)
    assert new.asset == "QQQ" and traded and new.days_held == 0


def test_step_switching_asset_while_flat_is_not_a_trade():
    st = State("SPY", 0.0, 100, False)
    new, traded = step(st, _row(risk_on=False, mom_qqq=0.5), CFG)
    assert new.asset == "QQQ" and not traded and new.exposure == 0.0


def test_step_warmup_rows_are_noops():
    st = initial_state(CFG)
    new, traded = step(st, _row(risk_on=np.nan), CFG)
    assert not traded and new.exposure == 0.0


def test_best_asset_handles_missing_momentum():
    assert best_asset(pd.Series({"mom_SPY": 0.1, "mom_QQQ": np.nan}), CFG) == "SPY"
    assert best_asset(pd.Series({"mom_SPY": np.nan, "mom_QQQ": np.nan}), CFG) is None


def test_compute_signals_requires_columns():
    with pytest.raises(ValueError):
        compute_signals(make_closes()[["SPY"]], CFG)
