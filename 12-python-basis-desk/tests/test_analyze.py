"""The reading is a pure function of the market. No network."""
import datetime as dt

from basis.analyze import analyze
from basis.markets import normalize, slug_from_query

NOW = dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.timezone.utc)


def market(**over):
    base = {
        "question": "Will it rain?",
        "slug": "will-it-rain",
        "description": "Resolves Yes if the official gauge reports rain.",
        "resolution_source": "The city gauge",
        "end": "2026-12-01T00:00:00Z",
        "outcomes": [{"name": "Yes", "price": 0.62}, {"name": "No", "price": 0.38}],
        "liquidity": 50_000,
        "volume_24h": 20_000,
        "spread": 0.01,
        "closed": False,
        "accepting": True,
    }
    base.update(over)
    return base


def test_a_liquid_contested_market_is_a_watch_with_the_payoff():
    read = analyze(market(), NOW)
    assert read["stance"] == "WATCH"
    assert all(c["ok"] for c in read["checks"])
    yes = next(p for p in read["payoff"] if p["name"] == "Yes")
    assert yes["loss_if_loses"] == 100
    assert yes["profit_if_wins"] == round(100 / 0.62 - 100, 2)
    assert "62.0¢" in read["headline"]
    assert "10¢" in read["exit"]


def test_a_decided_price_is_a_pass():
    read = analyze(market(outcomes=[{"name": "Yes", "price": 0.004}, {"name": "No", "price": 0.996}]), NOW)
    assert read["stance"] == "PASS"
    assert any(c["name"] == "called" and not c["ok"] for c in read["checks"])


def test_a_thin_or_late_market_is_a_pass():
    thin = analyze(market(liquidity=100, volume_24h=10), NOW)
    assert thin["stance"] == "PASS"
    late = analyze(market(end="2026-11-02T14:00:00Z"), NOW)
    assert late["stance"] == "PASS"
    closed = analyze(market(closed=True, accepting=False), NOW)
    assert closed["stance"] == "PASS"


def test_slug_from_a_polymarket_link_and_gamma_string_fields():
    assert slug_from_query("https://polymarket.com/event/fed-decision-in-december") == "fed-decision-in-december"
    assert slug_from_query("will-it-rain") == "will-it-rain"
    assert slug_from_query("will it rain") is None
    parsed = normalize({
        "question": "Will it rain?",
        "slug": "will-it-rain",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.62", "0.38"]',
        "liquidity": "5000",
        "volume24hr": "1000",
    })
    assert parsed["outcomes"][0] == {"name": "Yes", "price": 0.62}
    assert parsed["liquidity"] == 5000
