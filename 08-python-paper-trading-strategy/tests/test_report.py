import numpy as np
import pandas as pd

from tvm.broker import FakeBroker
from tvm.config import TVMConfig
from tvm.report import performance_vs_benchmark, to_markdown, write_step_summary

CFG = TVMConfig()


def sample_report(orders=True, dry_run=True):
    return {
        "as_of": "2026-10-30", "equity": 100_000.0,
        "signal": {"risk_on": True, "realized_vol": 0.2264, "exposure_target": 0.883, "mom_SPY": 0.054, "mom_QQQ": 0.0264},
        "state_before": {"asset": "SPY", "exposure": 0.0, "days_held": 5, "risk_on": False},
        "state_after": {"asset": "SPY", "exposure": 0.883, "days_held": 6, "risk_on": True},
        "target_weights": {"SPY": 0.883, "BIL": 0.117}, "current_weights": {},
        "orders": [{"symbol": "BIL", "notional": 11_700.0, "liquidate": False},
                   {"symbol": "SPY", "notional": 88_300.0, "liquidate": False}] if orders else [],
        "dry_run": dry_run, "live_prices_used": False,
    }


def test_markdown_contains_key_facts():
    md = to_markdown(sample_report(), None, CFG, mode="preview")
    assert "RISK-ON" in md and "0.88x" in md and "(preview)" in md
    assert "| SPY | 88.3% | 0.0% |" in md
    assert "NOT sent" in md and "Buy $88,300" in md


def test_markdown_no_orders_and_sent_results():
    md = to_markdown(sample_report(orders=False), None, CFG)
    assert "No trades needed" in md
    rep = sample_report(dry_run=False); rep["order_results"] = ["accepted", "accepted"]
    md = to_markdown(rep, None, CFG, mode="live")
    assert "Orders sent" in md and "(accepted)" in md


def test_performance_vs_benchmark_with_fake_broker():
    broker = FakeBroker(equity=105_000.0)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=30)
    bench = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
    perf = performance_vs_benchmark(broker, bench)
    assert perf is not None
    assert perf["strategy_return"] == 0.0 and perf["benchmark_return"] > 0
    md = to_markdown(sample_report(), perf, CFG)
    assert "Paper account vs VOO" in md and "+0.00%" in md


def test_performance_returns_none_without_history():
    class NoHistory(FakeBroker):
        def equity_history(self):
            raise RuntimeError("boom")
    assert performance_vs_benchmark(NoHistory(), pd.Series(dtype=float)) is None


def test_step_summary_written_only_when_env_set(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert write_step_summary("x") is None
    target = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(target))
    write_step_summary("hello\n"); write_step_summary("again\n")
    assert target.read_text() == "hello\nagain\n"
