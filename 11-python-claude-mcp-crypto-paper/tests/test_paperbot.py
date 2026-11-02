"""Offline tests: risk gate, ledger math, strategy rules, MCP server over stdio, dashboard."""
import asyncio
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from paperbot.ledger import Ledger, RiskGate           # noqa: E402
from paperbot import strategy                           # noqa: E402

T0 = 1_700_000_000.0
PX = {"BTC": 50_000.0, "ETH": 2_000.0, "SOL": 100.0}


def test_gate_one_position_cap_fee_leverage_shorting(tmp_path):
    led = Ledger(tmp_path)
    assert led.buy("BTC", 25.0, "ok", PX["BTC"], T0)["status"] == "filled"
    assert led.cash == pytest.approx(100 - 25 - 0.10)                     # 0.4% fee charged
    r = led.buy("ETH", 10.0, "second", PX["ETH"], T0)
    assert r["status"] == "refused" and "one position" in r["refused_because"]
    led.sell_all("flat", PX, T0 + 60)
    assert led.cash == pytest.approx(100 - 0.10 - 0.10) and led.position is None
    r = led.buy("BTC", 26.0, "too big", PX["BTC"], T0 + 120)
    assert r["status"] == "refused" and "25%" in r["refused_because"]
    r = led.buy("BTC", -5.0, "short", PX["BTC"], T0 + 120)
    assert r["status"] == "refused" and "shorting" in r["refused_because"]
    r = led.buy("DOGE", 5.0, "unknown", 0.1, T0 + 120)
    assert r["status"] == "refused"
    assert led.stats()["refused"] == 4


def test_gate_six_fills_per_day_and_halt_below_half(tmp_path):
    led = Ledger(tmp_path)
    for k in range(3):                                                        # 3 round trips = 6 fills
        assert led.buy("SOL", 20.0, "in", PX["SOL"], T0 + k * 100)["status"] == "filled"
        assert led.sell_all("out", PX, T0 + k * 100 + 50)["status"] == "filled"
    r = led.buy("SOL", 20.0, "seventh", PX["SOL"], T0 + 1000)
    assert r["status"] == "refused" and "daily fill limit" in r["refused_because"]
    # three days of buying 25% and watching it go to ~zero: equity ends under $50
    crash = {**PX, "SOL": 1.0}
    for day in range(1, 4):
        t = T0 + day * 86_400
        usd = int(led.equity(PX) * 0.25 * 100) / 100
        assert led.buy("SOL", usd, "in", PX["SOL"], t)["status"] == "filled"
        assert led.sell_all("crash", crash, t + 10)["status"] == "filled"      # selling is always allowed
    assert led.equity(PX) < 50
    r = led.buy("BTC", 5.0, "after crash", PX["BTC"], T0 + 5 * 86_400)
    assert r["status"] == "refused" and "halted" in r["refused_because"]


def test_ledger_round_trip_pnl_and_log(tmp_path):
    led = Ledger(tmp_path)
    led.buy("BTC", 25.0, "entry", 50_000.0, T0)
    led.mark({"BTC": 55_000.0}, T0 + 3600)
    assert led.equity({"BTC": 55_000.0}) == pytest.approx(100 - 25 - 0.10 + 27.5)
    r = led.sell_all("take profit", {"BTC": 55_000.0}, T0 + 7200)
    assert r["pnl_pct"] == pytest.approx(0.10) and r["pnl_usd"] == pytest.approx(27.5 - 0.11 - 25.10)
    led.hold("nothing to do", PX, T0 + 9000)
    kinds = [d["action"] for d in led.decisions()]
    assert kinds == ["buy", "sell_all", "hold"]
    assert all({"time", "symbol", "price", "size_usd", "fee", "reason"} <= set(d) for d in led.decisions())
    s = led.stats()
    assert s["round_trips"] == 1 and s["wins"] == 1 and s["holds"] == 1 and s["fees_paid"] == pytest.approx(0.21)


def walk(p0: float, n: int, drift: float = 0.002, vol: float = 0.01) -> list[float]:
    """Deterministic random walk whose last window qualifies for an entry (first seed that does)."""
    import random
    for seed in range(200):
        rng, xs = random.Random(seed), [p0]
        for _ in range(n - 1):
            xs.append(xs[-1] * (1 + rng.gauss(drift, vol)))
        f = strategy.features(xs)
        if f and f["close"] > f["sma"] and 50 <= f["rsi"] <= 70 and f["mom"] > 0.01:
            return xs
    raise AssertionError("no qualifying walk")


def test_strategy_rules():
    up = [100 + i for i in range(30)]                     # steady uptrend: above SMA, RSI 100, 24h > 1%
    f = strategy.features(up)
    assert f["close"] > f["sma"] and f["mom"] > 0.01 and f["rsi"] == 100
    assert strategy.entry_candidate({"BTC": f}) is None   # RSI 100 is outside 50-70: no chase
    g = strategy.features(walk(100.0, 31))
    assert strategy.entry_candidate({"BTC": g, "ETH": None}) == ("BTC", g)
    assert strategy.exit_reason(g, entry_price=120.0, last_price=111.0).startswith("stop")
    assert strategy.exit_reason(g, entry_price=100.0, last_price=111.0).startswith("take-profit")
    assert strategy.exit_reason(g, entry_price=110.0, last_price=111.0) is None


def _fixture(tmp_path: Path) -> Path:
    def series(p0, n=60):
        return [{"time": int(T0 + i * 14400), "open": c, "high": c, "low": c, "close": c, "volume": 1.0}
                for i, c in enumerate(walk(p0, n))]
    closes = {s: series(p) for s, p in PX.items()}
    last = {s: closes[s][-1]["close"] for s in PX}
    fx = {"candles": {s: {"4h": closes[s]} for s in PX}, "prices": last}
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fx))
    return path


def test_mcp_server_round_over_stdio_buys_then_holds(tmp_path, monkeypatch):
    from paperbot.agent import run_round
    monkeypatch.setenv("PAPERBOT_FIXTURE", str(_fixture(tmp_path)))
    monkeypatch.chdir(ROOT)
    state = tmp_path / "state"
    out = asyncio.run(run_round(str(state), log=lambda *_: None))
    assert out["decision"]["action"] == "buy" and out["decision"]["status"] == "filled"
    assert out["decision"]["size_usd"] == pytest.approx(25.0)
    assert out["account"]["position"]["symbol"] in PX and out["account"]["paper_money_only"] is True
    out2 = asyncio.run(run_round(str(state), log=lambda *_: None))
    assert out2["decision"]["action"] == "hold"           # already in; no exit signal
    decisions = Ledger(state).decisions()
    assert [d["action"] for d in decisions] == ["buy", "hold"]


def test_dashboard_has_banner_and_every_decision(tmp_path):
    from build_dashboard import build
    led = Ledger(tmp_path)
    led.buy("ETH", 25.0, "entry reason", PX["ETH"], T0); led.mark(PX, T0)
    led.buy("BTC", 5.0, "second", PX["BTC"], T0 + 1); led.mark(PX, T0 + 1)
    page = build(tmp_path, tmp_path / "dashboard.html").read_text()
    assert page.startswith("<!doctype html>") and "Paper money only. Not financial advice." in page
    assert "entry reason" in page and "refused" in page and "<svg" in page
