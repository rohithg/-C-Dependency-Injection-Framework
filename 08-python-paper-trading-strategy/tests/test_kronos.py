"""Kronos signal plumbing - no torch, no model download. A stub predictor
returns deterministic candle paths so the forecast -> calibration -> weights
-> trader chain can be exercised offline."""
import json

import numpy as np
import pandas as pd
import pytest

from tvm.broker import FakeBroker
from tvm.config import TVMConfig
from tvm import kronos_signal as ks
from tvm.kronos_signal import KronosConfig, calibrate, kronos_weights, rule_targets, future_timestamps, forecast
from tvm.trader import run_once

CFG = TVMConfig()


class StubPredictor:
    """Each sampled path drifts by `drift[symbol]` per day with alternating noise."""

    def __init__(self, drift):
        self.drift = drift

    def predict_batch(self, dfs, xts, yts, pred_len, **kw):
        out = []
        for i, (df, yt) in enumerate(zip(dfs, yts)):
            last = float(df["close"].iloc[-1])
            sym = "QQQ" if abs(last - 200.0) < 50 else "SPY"
            noise = 0.0005 * (1 if i % 2 else -1)
            closes = last * np.cumprod([1 + self.drift[sym] + noise] * pred_len)
            out.append(pd.DataFrame({"open": closes, "high": closes * 1.01, "low": closes * 0.99,
                                     "close": closes, "volume": 1.0, "amount": 1.0}, index=yt))
        return out


def bars(n=450, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=n)
    out = {}
    for sym, level in (("SPY", 100.0), ("QQQ", 200.0)):
        c = level * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n)))
        c = c / c[-1] * level
        out[sym] = pd.DataFrame({"open": c, "high": c * 1.005, "low": c * 0.995, "close": c, "volume": 1e6}, index=idx)
    return out


def test_future_timestamps_skips_weekends():
    ts = future_timestamps(pd.Timestamp("2024-05-03"), 3)      # a Friday
    assert list(ts.dt.day_of_week) == [0, 1, 2]


def test_forecast_summarises_sampled_paths():
    cfg = KronosConfig(samples=4, horizon=5)
    fc = forecast(StubPredictor({"SPY": 0.002, "QQQ": -0.003}), bars(), cfg)
    assert list(fc.index) == ["SPY", "QQQ"]
    assert fc.loc["SPY", "exp_ret"] > 0 > fc.loc["QQQ", "exp_ret"]
    assert fc.loc["SPY", "p_up"] == 1.0 and fc.loc["QQQ", "p_up"] == 0.0
    assert fc.loc["SPY", "std_ret"] > 0
    assert fc.loc["QQQ", "exp_min_low"] < fc.loc["QQQ", "exp_ret"]


def test_forecast_requires_enough_history():
    short = {k: v.iloc[-100:] for k, v in bars().items()}
    with pytest.raises(ValueError):
        forecast(StubPredictor({"SPY": 0, "QQQ": 0}), short, KronosConfig(context=400))


def _long(n=60, bias=-0.01):
    dates = pd.bdate_range("2024-01-01", periods=n)
    rows = []
    for i, d in enumerate(dates):
        for sym in ("SPY", "QQQ"):
            rows.append({"date": d, "symbol": sym, "exp_ret": bias + 0.001 * np.sin(i), "std_ret": 0.01,
                         "p_up": 0.4, "exp_ret_1d": bias / 5, "exp_min_low": bias - 0.01})
    return pd.DataFrame(rows)


def test_calibrate_uses_only_prior_forecasts():
    long = _long(n=60)
    # a single very bullish forecast on the last day must get a large positive z
    long.loc[(long["date"] == long["date"].max()) & (long["symbol"] == "SPY"), "exp_ret"] = 0.05
    cal = calibrate(long, window=30, min_periods=10)
    last = cal[cal["date"] == cal["date"].max()].set_index("symbol")
    assert last.loc["SPY", "z_ret"] > 3
    assert abs(last.loc["QQQ", "z_ret"]) < 3
    assert cal["z_ret"].iloc[:18].isna().all()          # warm-up (first 9 days x 2 symbols)


def _fc(spy, qqq, z_spy=None, z_qqq=None):
    df = pd.DataFrame({"exp_ret": [spy, qqq], "std_ret": [0.01, 0.02], "p_up": [0.6 if spy > 0 else 0.2, 0.6 if qqq > 0 else 0.2],
                       "exp_ret_1d": [0, 0], "exp_min_low": [-0.02, -0.03]}, index=["SPY", "QQQ"])
    if z_spy is not None:
        df["z_ret"] = [z_spy, z_qqq]
    return df


def test_direction_rule_picks_best_or_cash():
    assert kronos_weights(_fc(0.01, 0.02), KronosConfig(rule="direction"), CFG) == {"QQQ": 1.0}
    assert kronos_weights(_fc(-0.01, -0.02), KronosConfig(rule="direction"), CFG) == {"BIL": 1.0}
    assert kronos_weights(_fc(0.001, 0.0), KronosConfig(rule="direction", min_edge=0.005), CFG) == {"BIL": 1.0}


def test_calibrated_rule_ignores_raw_sign_and_handles_warmup():
    cfg = KronosConfig(rule="calibrated")
    assert kronos_weights(_fc(-0.01, -0.02, z_spy=0.8, z_qqq=0.2), cfg, CFG) == {"SPY": 1.0}
    assert kronos_weights(_fc(0.01, 0.02, z_spy=-0.5, z_qqq=-0.1), cfg, CFG) == {"BIL": 1.0}
    assert kronos_weights(_fc(0.01, 0.02), cfg, CFG) == {"BIL": 1.0}           # no z column yet


def test_relative_rule_is_always_invested():
    assert kronos_weights(_fc(-0.03, -0.01), KronosConfig(rule="relative"), CFG) == {"QQQ": 1.0}


def test_confidence_rule_uses_leverage_via_2x_etf():
    cfg = KronosConfig(rule="confidence", confidence_scale=1.0, max_leverage=2.0)
    w = kronos_weights(_fc(0.01, 0.0, z_spy=1.5, z_qqq=0.0), cfg, CFG)
    assert w == {"SSO": 0.5, "SPY": 0.5}
    w = kronos_weights(_fc(0.01, 0.0, z_spy=0.4, z_qqq=0.0), cfg, CFG)
    assert w == {"SPY": 0.4, "BIL": 0.6}


def test_tvm_veto_rule():
    cfg = KronosConfig(rule="tvm-veto", veto_p_up=0.35)
    tvm = {"QLD": 0.3, "QQQ": 0.7}
    assert kronos_weights(_fc(0.01, 0.01), cfg, CFG, tvm) == tvm                 # p_up 0.6 -> keep
    assert kronos_weights(_fc(0.01, -0.01), cfg, CFG, tvm) == {"BIL": 1.0}       # QQQ p_up 0.2 -> cash
    assert kronos_weights(_fc(0.01, -0.01), cfg, CFG, {"BIL": 1.0}) == {"BIL": 1.0}
    assert kronos_weights(_fc(0.01, -0.01), cfg, CFG, None) == {"BIL": 1.0}


def test_rule_targets_covers_every_forecast_day():
    long = _long(n=80)
    tgt = rule_targets(long, KronosConfig(rule="relative"), CFG)
    assert len(tgt) == 80 and set(tgt.columns) == {"BIL", "QQQ", "QLD", "SPY", "SSO"}
    assert np.allclose(tgt.sum(axis=1), 1.0)


def test_run_once_kronos_path_trades_and_persists_history(tmp_path, monkeypatch):
    monkeypatch.setattr(ks, "load_predictor", lambda variant: StubPredictor({"SPY": 0.004, "QQQ": -0.002}))
    b = bars()
    closes = pd.DataFrame({s: b[s]["close"] for s in b})
    closes["BIL"] = 100.0; closes["SSO"] = closes["SPY"]; closes["QLD"] = closes["QQQ"]
    broker = FakeBroker(equity=100_000, is_open=False)
    cfg = KronosConfig(rule="direction", samples=4)
    report = run_once(broker, closes, CFG, state_dir=tmp_path, kronos=cfg, bars=b, log=lambda *_: None)
    assert report["mode_detail"].startswith("Kronos-small")
    assert report["target_weights"] == {"SPY": 1.0}
    assert broker.positions == {"SPY": 100_000.0}
    assert report["kronos"]["SPY"]["exp_ret"] > 0 and report["kronos"]["SPY"]["z_ret"] is None   # first day: no baseline
    hist = pd.read_csv(tmp_path / "kronos_forecasts.csv")
    assert len(hist) == 2 and report["kronos_history_days"] == 1
    # same day again: history is not duplicated, nothing more to trade
    report2 = run_once(broker, closes, CFG, state_dir=tmp_path, kronos=cfg, bars=b, log=lambda *_: None)
    assert len(pd.read_csv(tmp_path / "kronos_forecasts.csv")) == 2
    assert report2["orders"] == []
    assert json.loads((tmp_path / "tvm_state.json").read_text())["asset"] == "SPY"
