"""Simulator, selection and the hourly paper tick against a fake API."""
import datetime as dt

import pytest

from polycopy.backtest import PriceSource, simulate, summarize, month_starts
from polycopy.copy import CopyConfig, Portfolio, LeaderBook
from polycopy.selection import score_wallets, choose
from polycopy import paper
from polycopy.paper import run_once

T0 = 1_700_000_000 - 1_700_000_000 % 86400          # a UTC midnight
CFG = CopyConfig(min_copyable_trades=2, follow_n=2)


class FakeAPI:
    """Two markets. 'good' resolves YES (our token wins), 'bad' resolves NO."""

    def __init__(self, resolved=True, liquidity=50_000.0, volume_24h=20_000.0):
        self.requests_made = 0
        self.resolved = resolved
        self.liquidity, self.volume_24h = liquidity, volume_24h
        self.books = {"good": {"asks": [(0.42, 1000)], "bids": [(0.40, 1000)]},
                      "bad": {"asks": [(0.62, 1000)], "bids": [(0.60, 1000)]}}
        self.activity_rows = {}
        self.positions = {}

    def market(self, cid):
        res = self.resolved and cid in ("good", "bad")
        return {"condition_id": cid, "slug": cid, "closed": res, "resolved": res, "end_ts": T0 + 10 * 86400, "fee_rate": 0.02,
                "liquidity": self.liquidity, "volume_24h": self.volume_24h,
                "tokens": [{"token_id": cid, "outcome": "Yes", "winner": cid == "good"},
                           {"token_id": cid + "-no", "outcome": "No", "winner": cid == "bad"}]}

    def markets_bulk(self, cids):
        return {c: self.market(c) for c in cids}

    def price_history(self, token, fidelity=60, closed=False, start_ts=None, end_ts=None):
        start = 0.40 if token == "good" else 0.60
        end = 1.0 if token == "good" else 0.0
        pts = []
        for h in range(0, 10 * 24 + 1):
            frac = h / (10 * 24)
            pts.append((T0 + h * 3600, start + (end - start) * frac))
        return pts

    def book(self, token):
        return self.books.get(token)

    def midpoints(self, tokens):
        return {t: (self.books[t]["asks"][0][0] + self.books[t]["bids"][0][0]) / 2 for t in tokens if t in self.books}

    def activity(self, wallet, start, end, max_trades=None):
        return [r for r in self.activity_rows.get(wallet, []) if start <= r["timestamp"] < end]

    def position(self, wallet, cid):
        return self.positions.get((wallet, cid), {})


def tr(wallet, cid, side="BUY", ts=T0 + 3600, price=0.40, usdc=500.0, size=None):
    return {"proxyWallet": wallet, "timestamp": ts, "conditionId": cid, "asset": cid, "side": side,
            "size": size or usdc / price, "usdcSize": usdc, "price": price, "outcome": "Yes", "title": cid, "slug": cid}


def test_simulate_fills_with_latency_and_resolves():
    api = FakeAPI()
    markets = {}
    trades = [tr("0xgood", "good"), tr("0xbad", "bad", price=0.60, ts=T0 + 7200)]
    res = simulate(trades, markets, PriceSource(api, markets), CopyConfig(), T0, T0 + 12 * 86400, api=api)
    buys = [f for f in res.fills if f.side == "BUY"]
    assert len(buys) == 2
    # filled one hour after the leader, at the hourly price + slippage
    assert buys[0].price == pytest.approx(0.40 + 0.6 * 2 / 240 + 0.01, abs=1e-6)   # price at T0+2h, +slippage
    resolved = [f for f in res.fills if f.side == "RESOLVE"]
    assert {f.token: f.price for f in resolved} == {"good": 1.0, "bad": 0.0}
    assert len(res.equity) == 12
    # +100 bet to ~1.0 on good (~+140), -100 on bad, minus fees -> small net gain
    assert 10_000 < res.equity.iloc[-1] < 10_200


def test_follow_set_restricts_new_buys_but_not_exits():
    api = FakeAPI()
    markets = {}
    trades = [tr("0xgood", "good"), tr("0xbad", "bad", price=0.60, ts=T0 + 7200)]
    res = simulate(trades, markets, PriceSource(api, markets), CopyConfig(), T0, T0 + 86400, follow={"0xgood"}, api=api)
    assert [f.token for f in res.fills if f.side == "BUY"] == ["good"]


def test_score_and_choose_prefers_copyable_winner():
    api = FakeAPI()
    markets = {}
    hist = {"0xgood": [tr("0xgood", "good", ts=T0 + h * 3600) for h in (1, 2, 3)],
            "0xbad": [tr("0xbad", "bad", price=0.60, ts=T0 + h * 3600) for h in (1, 2, 3)],
            "0xquiet": [tr("0xquiet", "good")]}
    scores = score_wallets(hist, {}, markets, PriceSource(api, markets), CFG, T0, T0 + 12 * 86400, api=api)
    assert [s.wallet for s in scores] == ["0xgood", "0xbad"]            # quiet wallet lacks min trades
    assert [s.wallet for s in choose(scores, CFG)] == ["0xgood"]        # only positive copy return


def test_summary_and_month_starts():
    import pandas as pd
    eq = pd.Series([100, 110, 99, 120.0], index=pd.date_range("2026-01-01", periods=4))
    s = summarize(eq)
    assert s["Total"] == pytest.approx(0.2) and s["MaxDD"] == pytest.approx(-0.1)
    assert len(month_starts(dt.date(2026, 1, 15), dt.date(2026, 3, 1))) == 3


def test_paper_tick_copies_marks_and_persists(tmp_path, monkeypatch):
    api = FakeAPI(resolved=False)
    now = T0 + 2 * 3600
    api.activity_rows = {"0xgood": [tr("0xgood", "good", ts=now - 600)]}
    monkeypatch.setattr(paper, "select_followed", lambda api_, cfg, log: [
        {"wallet": "0xgood", "name": "good", "copy_return": 0.1, "max_dd": -0.02, "copied_buys": 5, "since": now}])
    rep = run_once(api, CopyConfig(), tmp_path, now=now, log=lambda *_: None)
    assert rep["reselected"] and [f["side"] for f in rep["fills"]] == ["BUY"]
    fill = rep["fills"][0]
    assert fill["price"] == pytest.approx(0.42)                        # walked the live ask
    assert rep["activity"][0]["kind"] == "new position" and rep["activity"][0]["decision"].startswith("copied")
    review = rep["reviews"][0]
    assert review["approved"] and all(c["ok"] for c in review["checks"])
    assert {c["name"] for c in review["checks"]} >= {"liquidity", "24h volume", "spread", "price since leader", "position size"}
    assert rep["positions"][0]["mark"] == pytest.approx(0.41)
    assert (tmp_path / "state.json").exists() and (tmp_path / "fills.jsonl").exists()

    # next hour: leader sells 40% (position endpoint says 60% remains) -> we sell 40% at the bid
    later = now + 3600
    api.activity_rows["0xgood"].append(tr("0xgood", "good", side="SELL", ts=later - 300, price=0.41, usdc=200, size=500))
    api.positions[("0xgood", "good")] = {"good": 750.0}
    rep2 = run_once(api, CopyConfig(), tmp_path, now=later, log=lambda *_: None)
    assert not rep2["reselected"]
    sells = [f for f in rep2["fills"] if f["side"] == "SELL"]
    assert len(sells) == 1 and sells[0]["price"] == pytest.approx(0.40)
    assert sells[0]["shares"] == pytest.approx(fill["shares"] * 0.4, rel=1e-3)
    assert len(rep2["_state"].equity_history) == 2
    assert rep2["activity"][0]["kind"] == "reduced"


def test_trade_review_rejects_illiquid_market_and_chased_price(tmp_path):
    api = FakeAPI(resolved=False, liquidity=200.0)                    # below the $1,000 floor
    now = T0 + 2 * 3600
    api.activity_rows = {"0xgood": [tr("0xgood", "good", ts=now - 600)]}
    st = paper.PaperState(tmp_path / "state.json", 10_000.0)
    st.followed = [{"wallet": "0xgood", "name": "good", "copy_return": 0.1, "max_dd": -0.02, "copied_buys": 5, "since": now}]
    st.selected_at, st.cursor = now, {"0xgood": now - 3600}
    st.save()
    rep = run_once(api, CopyConfig(), tmp_path, now=now, dry_run=True, log=lambda *_: None)
    assert rep["fills"] == []
    review = rep["reviews"][0]
    assert not review["approved"]
    failed = {c["name"]: c for c in review["checks"] if not c["ok"]}
    assert set(failed) == {"liquidity"} and failed["liquidity"]["value"] == "$200"
    assert rep["activity"][0]["decision"].startswith("skipped: liquidity")

    # liquid market, but the leader paid 0.25 and the ask is now 0.42: that is chasing
    api2 = FakeAPI(resolved=False)
    api2.activity_rows = {"0xgood": [tr("0xgood", "good", ts=now - 600, price=0.25, usdc=500)]}
    rep2 = run_once(api2, CopyConfig(), tmp_path, now=now, dry_run=True, log=lambda *_: None)
    failed2 = {c["name"] for c in rep2["reviews"][0]["checks"] if not c["ok"]}
    assert failed2 == {"price since leader"} and rep2["fills"] == []


def test_paper_tick_ignores_stale_and_dry_run_writes_nothing(tmp_path):
    api = FakeAPI(resolved=False)
    now = T0 + 24 * 3600
    api.activity_rows = {"0xgood": [tr("0xgood", "good", ts=now - 5 * 3600)]}
    # a job that was down for 8 hours: the cursor is old, the trade is stale
    st = paper.PaperState(tmp_path / "state.json", 10_000.0)
    st.followed = [{"wallet": "0xgood", "name": "good", "copy_return": 0.1, "max_dd": -0.02, "copied_buys": 5, "since": now}]
    st.selected_at, st.cursor = now, {"0xgood": now - 8 * 3600}
    st.save()
    rep = run_once(api, CopyConfig(), tmp_path, now=now, dry_run=True, log=lambda *_: None)
    assert rep["fills"] == [] and rep["skipped"] == {"stale": 1}
    assert not (tmp_path / "fills.jsonl").exists()
    # dry run must not advance the persisted cursor
    assert paper.PaperState(tmp_path / "state.json", 1).cursor == {"0xgood": now - 8 * 3600}


def test_backtest_fill_is_worse_of_leader_and_snapshot():
    from polycopy.backtest import make_exec_price
    api = FakeAPI()
    markets = {"good": api.market("good")}
    prices = PriceSource(api, markets)
    prices.load("good", "good", from_ts=T0)
    exec_price = make_exec_price(prices, CFG)
    snap = prices.at_or_after("good", T0 + 3600 + CFG.latency_min * 60)     # ~0.405
    # leader paid less than the later snapshot -> we pay the snapshot (+ slippage)
    assert exec_price("good", "BUY", T0 + 3600, 0.30) == pytest.approx(snap + CFG.slippage)
    # leader paid more than the snapshot -> we do not get to assume the better print
    assert exec_price("good", "BUY", T0 + 3600, 0.60) == pytest.approx(0.60 + CFG.slippage)
    # selling: the worse (lower) of the two, minus slippage
    assert exec_price("good", "SELL", T0 + 3600, 0.60) == pytest.approx(snap - CFG.slippage)
    assert exec_price("good", "SELL", T0 + 3600, 0.30) == pytest.approx(0.30 - CFG.slippage)
