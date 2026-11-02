"""Trader + fake broker integration tests (no network, no credentials)."""
import json

import numpy as np
import pandas as pd

from tvm.broker import FakeBroker, Account
from tvm.config import TVMConfig
from tvm.trader import run_once, plan_orders, reconstruct_state

CFG = TVMConfig()


def uptrend_closes(n=320, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=n)
    spy = 100 * np.exp(np.cumsum(rng.normal(0.0008, 0.006, n)))
    qqq = 100 * np.exp(np.cumsum(rng.normal(0.0012, 0.007, n)))
    return pd.DataFrame({"SPY": spy, "QQQ": qqq}, index=idx)


def test_plan_orders_sells_before_buys_and_liquidates_dropped_symbols():
    acct = Account(equity=100_000, cash=0, positions={"SPY": 60_000, "BIL": 40_000})
    orders = plan_orders(acct, {"QLD": 0.5, "QQQ": 0.5}, {"SPY", "QQQ", "SSO", "QLD", "BIL"})
    by_sym = {o.symbol: o for o in orders}
    assert by_sym["SPY"].liquidate and by_sym["BIL"].liquidate
    assert by_sym["QLD"].notional == 50_000 and by_sym["QQQ"].notional == 50_000
    assert [o.notional < 0 for o in orders] == sorted([o.notional < 0 for o in orders], reverse=True)


def test_plan_orders_ignores_dust():
    acct = Account(equity=100_000, cash=0, positions={"QQQ": 99_900})
    assert plan_orders(acct, {"QQQ": 1.0}, {"QQQ"}) == []


def test_reconstruct_state_from_positions():
    acct = Account(equity=100_000, cash=0, positions={"QLD": 30_000, "QQQ": 70_000})
    st = reconstruct_state(acct, CFG, days_held=7, saved_asset="QQQ")
    assert st.asset == "QQQ" and abs(st.exposure - 1.3) < 1e-6 and st.days_held == 7 and st.risk_on


def test_reconstruct_state_resets_hold_if_positions_disagree_with_saved_asset():
    acct = Account(equity=100_000, cash=0, positions={"SPY": 100_000})
    st = reconstruct_state(acct, CFG, days_held=7, saved_asset="QQQ")
    assert st.asset == "SPY" and st.days_held >= CFG.min_hold_days


def test_run_once_from_flat_account_buys_into_uptrend(tmp_path):
    broker = FakeBroker(equity=100_000, is_open=False)
    report = run_once(broker, uptrend_closes(), CFG, state_dir=tmp_path, log=lambda *_: None)
    assert report["signal"]["risk_on"] is True
    assert report["orders"], "expected orders when moving from cash into the market"
    assert abs(sum(broker.positions.values()) - 100_000) < 1.0
    held = set(broker.positions)
    assert held <= {"SPY", "QQQ", "SSO", "QLD", "BIL"}
    saved = json.loads((tmp_path / "tvm_state.json").read_text())
    assert saved["exposure"] == report["state_after"]["exposure"]
    assert (tmp_path / "trade_log.jsonl").exists()


def test_run_once_is_idempotent_within_band(tmp_path):
    broker = FakeBroker(equity=100_000, is_open=False)
    closes = uptrend_closes()
    run_once(broker, closes, CFG, state_dir=tmp_path, log=lambda *_: None)
    n_orders = len(broker.submitted)
    first_saved = json.loads((tmp_path / "tvm_state.json").read_text())
    second = run_once(broker, closes, CFG, state_dir=tmp_path, log=lambda *_: None)
    assert second["orders"] == [] and len(broker.submitted) == n_orders
    # re-running on the same signal date must not advance the hold counter
    assert second["state_after"]["days_held"] == first_saved["days_held"]


def test_dry_run_sends_nothing(tmp_path):
    broker = FakeBroker(equity=50_000, is_open=False)
    report = run_once(broker, uptrend_closes(), CFG, dry_run=True, state_dir=tmp_path, log=lambda *_: None)
    assert report["orders"] and broker.submitted == [] and not (tmp_path / "tvm_state.json").exists()


def test_live_prices_append_today_bar(tmp_path):
    closes = uptrend_closes()
    last = closes.iloc[-1]
    # a crash in today's live prices should flip the regime to cash
    broker = FakeBroker(equity=100_000, is_open=True, positions={"QQQ": 100_000},
                        prices={"SPY": last["SPY"] * 0.6, "QQQ": last["QQQ"] * 0.6})
    report = run_once(broker, closes, CFG, state_dir=tmp_path, log=lambda *_: None)
    assert report["live_prices_used"] and report["signal"]["risk_on"] is False
    assert broker.positions == {"BIL": 100_000.0}
