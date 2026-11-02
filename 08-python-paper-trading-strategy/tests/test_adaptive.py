"""Adaptive ensemble tests on synthetic data (no network)."""
import numpy as np
import pandas as pd

from tvm.config import TVMConfig
from tvm.adaptive import (Expert, AdaptiveConfig, default_experts, etf_returns, expert_targets, portfolio_returns,
                          hedge_weights, cap_exposure, run_adaptive, latest_allocation, regime_postmortem,
                          tradable_symbols)
from tvm.broker import FakeBroker
from tvm.trader import run_once
from tvm.strategy import compute_signals

CFG = TVMConfig()


def make_closes(n=900, seed=3, drift=0.0005, vol=0.01):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n)
    spy = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    qqq = 100 * np.exp(np.cumsum(rng.normal(drift * 1.3, vol * 1.2, n)))
    df = pd.DataFrame({"SPY": spy, "QQQ": qqq}, index=idx)
    df["SSO"] = 50 * np.exp(np.cumsum(2 * np.diff(np.log(spy), prepend=np.log(spy[0])) - 0.01 / 252))
    df["QLD"] = 50 * np.exp(np.cumsum(2 * np.diff(np.log(qqq), prepend=np.log(qqq[0])) - 0.01 / 252))
    df["BIL"] = 100 * np.exp(np.arange(n) * 0.02 / 252)
    return df


def zero_cash(closes):
    return pd.Series(0.0, index=closes.index)


def test_default_pool_contains_safety_net_and_mistake_aware_experts():
    names = [e.name for e in default_experts(CFG)]
    assert "buy-and-hold" in names and any("whipsaw" in n for n in names) and any("vote" in n for n in names)
    assert len(names) == len(set(names))


def test_etf_returns_uses_real_columns_and_synthesises_missing():
    closes = make_closes()
    r = etf_returns(closes, zero_cash(closes), CFG)
    assert set(r.columns) == set(tradable_symbols(CFG))
    pd.testing.assert_series_equal(r["SSO"].iloc[1:], closes["SSO"].pct_change().iloc[1:], check_names=False)
    r2 = etf_returns(closes.drop(columns=["SSO", "QLD", "BIL"]), zero_cash(closes), CFG)
    spy = closes["SPY"].pct_change()
    assert np.allclose(r2["SSO"].iloc[1:], (2 * spy - (CFG.borrow_spread + CFG.lev_etf_expense) / 252).iloc[1:])
    assert (r2["BIL"] == 0).all()


def test_hold_expert_is_always_fully_in_trend_symbol():
    closes = make_closes()
    t = expert_targets(closes, Expert("hold", CFG, kind="hold"))
    assert (t["SPY"] == 1.0).all() and (t.drop(columns="SPY") == 0).all().all()


def test_tvm_expert_targets_sum_to_one_after_warmup():
    closes = make_closes()
    t = expert_targets(closes, Expert("x", CFG))
    assert t.iloc[: CFG.sma_window - 1].isna().all().all()
    live = t.dropna()
    assert np.allclose(live.sum(axis=1), 1.0)


def test_portfolio_returns_match_manual_computation():
    closes = make_closes()
    rets = etf_returns(closes, zero_cash(closes), CFG)
    t = pd.DataFrame(0.0, index=closes.index, columns=rets.columns)
    t["SPY"] = 1.0
    t.iloc[500:, t.columns.get_loc("SPY")] = 0.0
    t.iloc[500:, t.columns.get_loc("BIL")] = 1.0
    pr = portfolio_returns(t, rets, cost_bps=10.0)
    assert np.isclose(pr.iloc[10], rets["SPY"].iloc[10])
    # the switch is held from day 501; its turnover (2.0) is charged that day
    assert np.isclose(pr.iloc[501], rets["BIL"].iloc[501] - 2.0 * 10 / 1e4)


def test_hedge_weights_sum_to_one_and_favor_the_winner():
    idx = pd.bdate_range("2020-01-01", periods=300)
    good = pd.Series(0.001, index=idx); bad = pd.Series(-0.001, index=idx)
    w = hedge_weights(pd.DataFrame({"good": good, "bad": bad}), eta=10.0, halflife_days=126)
    assert np.allclose(w.sum(axis=1), 1.0)
    assert w["good"].iloc[-1] > 0.6 > w["bad"].iloc[-1]
    assert w["good"].is_monotonic_increasing
    flat = hedge_weights(pd.DataFrame({"a": good, "b": good}), eta=10.0, halflife_days=126)
    assert np.allclose(flat.iloc[-1], 0.5)


def test_hedge_weights_handle_warming_experts():
    idx = pd.bdate_range("2020-01-01", periods=100)
    a = pd.Series(0.001, index=idx); b = a.copy(); b.iloc[:50] = np.nan
    w = hedge_weights(pd.DataFrame({"a": a, "b": b}), eta=10.0, halflife_days=126)
    assert w["b"].iloc[10] < w["a"].iloc[10] and np.allclose(w.sum(axis=1), 1.0)


def test_cap_exposure_scales_into_cash():
    w = cap_exposure({"SSO": 0.8, "SPY": 0.2}, CFG, max_leverage=1.5)   # 1.8x -> 1.5x
    lev = 2 * w.get("SSO", 0) + w.get("SPY", 0)
    assert np.isclose(lev, 1.5) and np.isclose(sum(w.values()), 1.0) and w["BIL"] > 0
    assert cap_exposure({"SPY": 0.5, "BIL": 0.5}, CFG, 2.0) == {"SPY": 0.5, "BIL": 0.5}


def test_run_adaptive_end_to_end_in_uptrend():
    closes = make_closes()
    res = run_adaptive(closes, zero_cash(closes), CFG, AdaptiveConfig())
    r = res.returns.dropna()
    assert len(r) > 400 and res.trades > 0
    assert np.allclose(res.learner_weights.sum(axis=1), 1.0)
    held = res.held.dropna()
    assert np.allclose(held.sum(axis=1), 1.0)
    lev = 2 * (held["SSO"] + held["QLD"]) + held["SPY"] + held["QQQ"]
    assert (lev <= CFG.max_leverage + 1e-6).all()
    assert (1 + r).prod() > 1.0        # steady uptrend should make money


def test_latest_allocation_and_postmortem():
    closes = make_closes()
    target, board = latest_allocation(closes, zero_cash(closes), CFG, AdaptiveConfig())
    assert np.isclose(sum(target.values()), 1.0) and set(target) <= set(tradable_symbols(CFG))
    assert np.isclose(board["weight"].sum(), 1.0) and board["weight"].is_monotonic_decreasing
    pm = regime_postmortem(closes, CFG, last_n=5)
    assert set(pm.columns) == {"exit", "reentry", "days_out", "missed", "verdict"}
    assert set(pm["verdict"]) <= {"whipsaw (mistake)", "avoided loss", "still out"}


def test_postmortem_classifies_a_constructed_whipsaw():
    n = 600
    idx = pd.bdate_range("2019-01-01", periods=n)
    px = np.linspace(100, 160, n)
    px[400:410] = px[399] * 0.85            # brief dip below the SMA, then recover above the dip
    closes = pd.DataFrame({"SPY": px, "QQQ": px}, index=idx)
    pm = regime_postmortem(closes, CFG, last_n=5)
    assert len(pm) >= 1 and pm.iloc[-1]["verdict"] == "whipsaw (mistake)" and pm.iloc[-1]["missed"] > 0


def test_whipsaw_memory_raises_entry_threshold():
    n = 600
    idx = pd.bdate_range("2019-01-01", periods=n)
    px = np.linspace(100, 160, n)
    for start in (300, 330, 360):
        px[start:start + 5] = px[start - 1] * 0.85
    closes = pd.DataFrame({"SPY": px, "QQQ": px}, index=idx)
    cfg = TVMConfig(whipsaw_penalty=0.01, whipsaw_max=0.05)
    sig = compute_signals(closes, cfg)
    assert sig["entry_threshold"].max() >= 0.02
    assert sig["entry_threshold"].iloc[250] == 0.0


def test_vote_gate_scales_exposure():
    closes = make_closes()
    cfg = TVMConfig(trend_vote_windows=(100, 150, 200, 250, 300))
    sig = compute_signals(closes, cfg).dropna()
    assert ((sig["trend_vote"] >= 0) & (sig["trend_vote"] <= 1)).all()
    assert (sig["exposure_target"] <= cfg.max_leverage + 1e-9).all()


def test_trader_adaptive_mode_trades_toward_blend(tmp_path):
    closes = make_closes()
    closes.index = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=len(closes))
    broker = FakeBroker(equity=100_000, is_open=False)
    rep = run_once(broker, closes, CFG, adaptive=AdaptiveConfig(), state_dir=tmp_path, log=lambda *_: None)
    assert rep["mode_detail"] == "adaptive ensemble" and rep["learner"] and "postmortem" in rep
    assert rep["orders"] and abs(sum(broker.positions.values()) - 100_000) < 1.0
    assert np.isclose(sum(rep["target_weights"].values()), 1.0)
    again = run_once(broker, closes, CFG, adaptive=AdaptiveConfig(), state_dir=tmp_path, log=lambda *_: None)
    assert again["orders"] == [] and again["drift_from_target"] < AdaptiveConfig().portfolio_band
