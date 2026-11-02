"""Descriptive wallet profile: win rate, sizing, consistency, categories."""
import pytest

from polycopy.analysis import analyze_wallet, category, profile_line

T0 = 1_700_000_000


def t(cid, side, usdc, size, ts, slug="will-x-happen", asset=None):
    return {"conditionId": cid, "asset": asset or cid, "side": side, "usdcSize": usdc, "size": size, "price": usdc / size,
            "timestamp": ts, "title": cid, "slug": slug}


def test_win_rate_counts_resolved_and_fully_exited_markets_only():
    trades = [
        t("m1", "BUY", 100, 200, T0),                       # resolved YES, held to the end -> +100
        t("m2", "BUY", 100, 200, T0 + 86400),               # resolved NO -> -100
        t("m3", "BUY", 100, 200, T0 + 2 * 86400),           # exited early at a profit -> +20
        t("m3", "SELL", 120, 200, T0 + 3 * 86400),
        t("m4", "BUY", 100, 200, T0 + 40 * 86400),          # still open, unresolved -> not decided
    ]
    markets = {
        "m1": {"resolved": True, "tokens": [{"token_id": "m1", "winner": True}]},
        "m2": {"resolved": True, "tokens": [{"token_id": "m2", "winner": False}]},
        "m4": {"resolved": False, "tokens": [{"token_id": "m4", "winner": False}]},
    }
    s = analyze_wallet(trades, markets)
    assert s["markets"] == 4 and s["decided_markets"] == 3
    assert s["win_rate"] == pytest.approx(2 / 3)
    assert s["realized_pnl"] == pytest.approx(100 - 100 + 20)
    assert s["avg_position_usd"] == pytest.approx(100.0)
    assert s["active_months"] >= 1 and s["profitable_months"] >= 1
    assert s["top_markets"][0]["title"] == "m3"               # highest volume (buy + sell)
    assert "win" in profile_line(s) and "avg $100/market" in profile_line(s)


def test_shares_from_splits_do_not_count_as_short_positions():
    # the wallet sold 300 shares it never bought on the CLOB (minted via split); no phantom payout or loss
    trades = [t("m1", "SELL", 150, 300, T0)]
    s = analyze_wallet(trades, {"m1": {"resolved": True, "tokens": [{"token_id": "m1", "winner": True}]}})
    assert s["realized_pnl"] == pytest.approx(150.0) and s["win_rate"] == 1.0


def test_category_from_slug():
    assert category("nba-okc-den-2026-04-10") == "sports"
    assert category("bitcoin-above-100k-on-june-30") == "crypto"
    assert category("btc-updown-5m-1779") == "short-horizon"
    assert category("will-the-democratic-party-control-the-house") == "politics"
    assert category("fed-decision-in-september") == "economics"
    assert category("will-it-rain-in-nyc") == "other"
    assert analyze_wallet([], {}) == {"trades": 0}
