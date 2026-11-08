from decimal import Decimal

from edge.fees import kalshi_fee, polymarket_taker_fee


def test_polymarket_table_at_fifty_cents_and_the_wing():
    # Published crypto table: 100 shares at 50c cost $1.75, at 1c cost $0.0693 before display rounding.
    assert polymarket_taker_fee(Decimal("100"), Decimal("0.50"), Decimal("0.07")) == Decimal("1.75")
    assert polymarket_taker_fee(Decimal("100"), Decimal("0.01"), Decimal("0.07")) == Decimal("0.06930")
    # Sports 100 shares at 50c is $1.25. Politics is $1.00. Geopolitics is free.
    assert polymarket_taker_fee(Decimal("100"), Decimal("0.50"), Decimal("0.05")) == Decimal("1.25")
    assert polymarket_taker_fee(Decimal("100"), Decimal("0.50"), Decimal("0.04")) == Decimal("1.00")
    assert polymarket_taker_fee(Decimal("100"), Decimal("0.50"), Decimal("0")) == 0


def test_exponent_scales_the_probability_term():
    # exponent 1 is p*(1-p). exponent 2 squares that term.
    once = polymarket_taker_fee(Decimal("100"), Decimal("0.50"), Decimal("0.07"), Decimal("1"))
    twice = polymarket_taker_fee(Decimal("100"), Decimal("0.50"), Decimal("0.07"), Decimal("2"))
    assert once == Decimal("1.75")
    assert twice == Decimal("0.4375")


def test_kalshi_fee_rounds_up_to_the_centicent():
    # 0.07 * 1 * 0.03 * 0.97 = 0.002037, which has to round up to 0.0021.
    assert kalshi_fee(Decimal("1"), Decimal("0.03"), Decimal("0.07")) == Decimal("0.0021")
    # An amount already on the grid stays put. 0.07 * 10 * 0.5 * 0.5 = 0.175.
    assert kalshi_fee(Decimal("10"), Decimal("0.50"), Decimal("0.07")) == Decimal("0.175")
    assert kalshi_fee(Decimal("10"), Decimal("0.50"), Decimal("0.0175")) == Decimal("0.0438")
