from decimal import Decimal

from edge.crypto15m import settlement_up_prob, sigma_1m
from edge.weekscan import poly_fee, print_at, score_side, score_window


def test_print_at_uses_the_latest_fresh_trade_and_drops_a_stale_one():
    history = [{"t": 100, "p": 0.40}, {"t": 150, "p": 0.55}, {"t": 190, "p": 0.99}]
    assert print_at(history, 160, max_age=60) == 0.55
    assert print_at(history, 160, max_age=5) is None
    assert print_at([{"t": 200, "p": 0.2}], 160) is None


def test_two_to_three_cents_is_a_take_and_a_wider_edge_is_not():
    # A coin-flip spot against a 45 cent print clears more than 3 cents, so it is not a take.
    closes = [100.0 + (i % 3) * 0.02 for i in range(40)]
    wide = score_window(spot=100, strike=100, closes=closes, up_px=0.45, down_px=0.55, up_won=True)
    assert wide is not None and wide["take"] is False and wide["side"] == "up"

    scored = score_side(0.50, 0.45)
    assert scored is not None and scored[0] > 3

    # Build a print whose fee-adjusted edge lands inside the band.
    sigma = sigma_1m(closes)
    prob = settlement_up_prob(100, 100, sigma, 1.0)
    price = 0.45
    for _ in range(8):
        price = prob - 0.025 - poly_fee(price)
    band = score_window(spot=100, strike=100, closes=closes, up_px=price, down_px=0.99, up_won=False)
    assert band is not None and band["take"] and band["side"] == "up"
    assert band["pnl"] < 0
    assert score_side(0.5, 0.45, Decimal("0.07"))[1] > 0
