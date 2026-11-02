"""Copy rules, portfolio accounting, book walking - pure logic, no network."""
import json

import pytest

from polycopy.copy import (CopyConfig, Portfolio, LeaderBook, copy_trade, copyable, precheck, taker_fee,
                           fill_from_book, clip_price)
from polycopy.selection import rank_whales

CFG = CopyConfig()
T0 = 1_700_000_000


def trade(side="BUY", price=0.40, usdc=500.0, ts=T0, wallet="0xabc", token="tok1", cid="cid1", slug="will-x-happen", size=None):
    size = size if size is not None else usdc / price
    return {"proxyWallet": wallet, "timestamp": ts, "conditionId": cid, "asset": token, "side": side, "size": size,
            "usdcSize": usdc, "price": price, "outcome": "Yes", "title": "Will X happen?", "slug": slug}


def market(end_h=72.0, fee=0.0, cid="cid1", resolved=False, winner="tok1"):
    return {"condition_id": cid, "slug": "will-x-happen", "closed": resolved, "resolved": resolved,
            "end_ts": T0 + int(end_h * 3600), "fee_rate": fee,
            "tokens": [{"token_id": "tok1", "outcome": "Yes", "winner": winner == "tok1"},
                       {"token_id": "tok2", "outcome": "No", "winner": winner == "tok2"}]}


def test_taker_fee_matches_polymarket_table():
    # docs: 100 shares at 0.50 in a sports (0.05) market -> $1.25; at 0.10 -> $0.45
    assert taker_fee(100, 0.5, 0.05) == pytest.approx(1.25)
    assert taker_fee(100, 0.1, 0.05) == pytest.approx(0.45)
    assert taker_fee(100, 0.5, 0.0) == 0.0


def test_filters():
    assert copyable(trade(), market(), CFG) is None
    assert copyable(trade(), market(end_h=1.5), CFG).startswith("ends in")
    assert copyable(trade(slug="btc-updown-5m-123"), market(), CFG) == "short-horizon market"
    assert copyable(trade(usdc=5), market(), CFG) == "dust"
    assert copyable(trade(price=0.99, usdc=500), market(), CFG).startswith("price")
    assert copyable(trade(), None, CFG) == "unknown market"
    assert precheck(trade(side="SELL", usdc=1), CFG) is None       # sells are never dust-filtered


def test_buy_sizing_and_fee():
    port = Portfolio(10_000.0)
    leaders = LeaderBook()
    fill, why = copy_trade(trade(), market(fee=0.05), port, leaders, CFG, lambda tok, side, ts, lp: 0.41)
    assert why == "copied" and fill.side == "BUY" and fill.price == 0.41
    cost = fill.shares * fill.price + fill.fee
    assert cost == pytest.approx(100.0, abs=0.01)                 # 1% of equity incl. fee
    assert port.cash == pytest.approx(10_000 - cost)
    assert port.positions["tok1"].by_wallet["0xabc"] == pytest.approx(fill.shares)


def test_buy_never_larger_than_leaders_own_trade():
    port = Portfolio(10_000.0)
    fill, why = copy_trade(trade(usdc=40.0), market(), port, LeaderBook(), CFG, lambda tok, side, ts, lp: 0.40)
    assert why == "copied"
    assert fill.shares * fill.price + fill.fee == pytest.approx(40.0, abs=0.01)   # capped at leader's $40, not 1% ($100)
    uncapped = CopyConfig(max_leader_multiple=0)
    fill, _ = copy_trade(trade(usdc=40.0), market(), Portfolio(10_000.0), LeaderBook(), uncapped, lambda tok, side, ts, lp: 0.40)
    assert fill.shares * fill.price + fill.fee == pytest.approx(100.0, abs=0.01)


def test_market_cap_limits_repeated_buys():
    port = Portfolio(10_000.0)
    leaders = LeaderBook()
    reasons = []
    for i in range(8):
        f, why = copy_trade(trade(ts=T0 + i), market(), port, leaders, CFG, lambda tok, side, ts, lp: 0.40)
        reasons.append(why)
    assert reasons[:5] == ["copied"] * 5 and reasons[5] == "market cap reached"
    assert port.market_cost("cid1") == pytest.approx(500.0, abs=0.5)


def test_sell_mirrors_fraction_of_leader_exit():
    port = Portfolio(10_000.0)
    leaders = LeaderBook()
    copy_trade(trade(size=1000, usdc=400), market(), port, leaders, CFG, lambda tok, side, ts, lp: 0.40)
    held = port.positions["tok1"].shares
    # leader sells 25% of their 1000 shares -> we sell 25% of ours
    f, why = copy_trade(trade(side="SELL", size=250, usdc=100, price=0.5, ts=T0 + 10), market(), port, leaders, CFG,
                        lambda tok, side, ts, lp: 0.49)
    assert why == "copied" and f.side == "SELL"
    assert f.shares == pytest.approx(held * 0.25)
    assert port.realized > 0                                        # bought 0.40, sold 0.49
    # a sell by a wallet we never copied in this token is ignored
    f, why = copy_trade(trade(side="SELL", size=10, usdc=5, wallet="0xother", ts=T0 + 11), market(), port, leaders, CFG,
                        lambda tok, side, ts, lp: 0.49)
    assert f is None and why == "not holding"


def test_unseen_leader_sell_is_full_exit():
    lb = LeaderBook()
    assert lb.apply(trade(side="SELL", size=10)) == 1.0
    lb.apply(trade(size=100))
    assert lb.apply(trade(side="SELL", size=30)) == pytest.approx(0.3)


def test_resolution_pays_out():
    port = Portfolio(1_000.0)
    port.buy(T0, "0xabc", "tok1", "cid1", 100, 0.40, 0.0, 0.40)
    port.resolve("tok1", 1.0, T0 + 100)
    assert port.cash == pytest.approx(1_000 - 40 + 100)
    assert port.realized == pytest.approx(60.0)
    assert not port.positions


def test_roundtrip_serialisation():
    port = Portfolio(1_000.0)
    port.buy(T0, "0xabc", "tok1", "cid1", 100, 0.40, 0.02, 0.40, title="t", outcome="Yes", end_ts=T0 + 999)
    again = Portfolio.from_dict(port.to_dict())
    assert again.cash == pytest.approx(port.cash) and again.positions["tok1"].shares == 100


def test_fill_from_book_walks_levels():
    book = {"asks": [(0.40, 100), (0.42, 100)], "bids": [(0.39, 50), (0.38, 500)]}
    shares, avg = fill_from_book(book, "BUY", notional=60.0)
    assert shares == pytest.approx(60 / 0.40 * 1, rel=0.2) and avg >= 0.40
    shares, avg = fill_from_book(book, "BUY", notional=63.0)           # 100 @0.40 = 40, then 23 @0.42
    assert shares == pytest.approx(100 + 23 / 0.42) and 0.40 < avg < 0.42
    shares, avg = fill_from_book(book, "SELL", shares=100)
    assert shares == 100 and avg == pytest.approx((50 * 0.39 + 50 * 0.38) / 100)
    assert fill_from_book({"asks": [], "bids": []}, "BUY", notional=10) is None


def test_clip_price():
    assert clip_price(1.2) == 0.999 and clip_price(-0.1) == 0.001


def test_config_json_roundtrip(tmp_path):
    cfg = CopyConfig(follow_n=3, skip_slug_parts=("a", "b"))
    cfg.to_json(tmp_path / "c.json")
    assert CopyConfig.from_json(tmp_path / "c.json") == cfg


def _buy(wallet, ts, usdc, side="BUY"):
    return {"proxyWallet": wallet, "timestamp": ts, "side": side, "usdcSize": usdc}


def _market(cid, closed_ts, win=True):
    return {"resolved": True, "closed_ts": closed_ts, "tokens": [{"token_id": cid, "winner": win}]}


def _settled(wallet, cid, ts, usdc, win):
    """One buy whose market closes a day later. A win pays the shares (size = usdc / 0.5)."""
    return _buy(wallet, ts, usdc), cid, win


def test_rank_whales_keeps_only_wallets_at_the_win_rate_bar():
    # 16 settled markets each. `good` wins 12 ($100 cost, $200 payout -> +100). `big` wins 8 and bought more.
    trades = {"good": [], "big": []}
    markets = {}
    for i in range(16):
        ts = 1_000 + i * 86_400
        for name, win, usdc in (("good", i < 12, 100), ("big", i < 8, 5_000)):
            cid = f"{name}-{i}"
            trades[name].append({"proxyWallet": name, "timestamp": ts, "side": "BUY", "usdcSize": usdc,
                                 "size": usdc / 0.5, "conditionId": cid, "asset": cid})
            markets[cid] = _market(cid, ts + 86_400, win=win)
    cfg = CopyConfig(min_copyable_trades=15, follow_n=5, min_win_rate=0.70, min_decided=15)
    ranked = rank_whales({"good": trades["good"], "big": trades["big"]}, {"good": "Good"}, 0, 1_000 + 20 * 86_400, cfg, markets)
    assert [s.wallet for s in ranked] == ["good"]
    assert ranked[0].win_rate == pytest.approx(0.75)
    assert ranked[0].decided == 16 and ranked[0].realized > 0


def test_rank_whales_orders_by_buy_notional_inside_the_window():
    hist = {
        "small": [_buy("small", 100, 50)] * 15,                                          # $750
        "big": [_buy("big", 100, 1000)] * 15,                                            # $15,000
        "seller": [_buy("seller", 100, 5000, side="SELL")] * 20 + [_buy("seller", 100, 10)] * 15,
        "old": [_buy("old", 10, 99_999)] * 20,                                           # before the window
        "few": [_buy("few", 100, 99_999)] * 3,                                           # under min_copyable_trades
    }
    cfg = CopyConfig(min_copyable_trades=15, follow_n=2)
    ranked = rank_whales(hist, {"big": "Big"}, 50, 200, cfg)
    assert [s.wallet for s in ranked] == ["big", "small"]
    assert ranked[0].name == "Big" and ranked[0].notional == 15_000
    assert ranked[1].notional == 750


def test_from_json_ignores_comment_and_rejects_bad_select_by(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"_comment": "size is not skill", "select_by": "whale", "follow_n": 5}))
    cfg = CopyConfig.from_json(path)
    assert cfg.select_by == "whale" and cfg.follow_n == 5 and cfg.trade_fraction == CopyConfig().trade_fraction
    path.write_text(json.dumps({"select_by": "pnl"}))
    with pytest.raises(ValueError):
        CopyConfig.from_json(path)


def test_report_shows_whale_volume_and_label(monkeypatch):
    from polycopy.report import to_markdown, to_text
    report = {
        "as_of": "2026-11-02 12:00 UTC", "equity": 10_000.0, "return": 0.0, "started": "2026-11-02",
        "start_cash": 10_000, "cash": 5_000.0, "realized": 0.0, "fees_paid": 12.0, "max_dd": -0.02,
        "fills": [], "skipped": {}, "positions": [], "watching": 5,
        "followed": [{"wallet": "0xabc", "name": "whale", "copy_return": 0.0, "max_dd": 0.0, "copied_buys": 20,
                      "whale_volume": 1_250_000, "profile": "mostly politics", "top_markets": []}],
    }
    md = to_markdown(report)
    assert "Trailing buy volume" in md and "$1,250,000" in md and "Copy return" not in md
    monkeypatch.setenv("POLY_LABEL", "Whale copy")
    assert to_text(report).startswith("Whale copy 11/02")
