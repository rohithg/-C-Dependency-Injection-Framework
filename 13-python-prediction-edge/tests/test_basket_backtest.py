from edge.basket_backtest import basket_quote, settle


def test_a_full_set_under_a_dollar_is_a_trade_and_pays_the_winner_count():
    quote = basket_quote([0.40, 0.40], [0.0, 0.0])
    assert quote is not None and quote["take"] and quote["cost"] == 0.8
    assert settle(quote["cost"], 1) == 0.2
    assert settle(quote["cost"], 0) == -0.8


def test_a_one_cent_haircut_can_push_the_set_through_a_dollar():
    cheap = basket_quote([0.49, 0.49], [0.0, 0.0], haircut=0.0)
    lifted = basket_quote([0.49, 0.49], [0.0, 0.0], haircut=0.01)
    assert cheap is not None and cheap["take"]
    assert lifted is not None and lifted["take"] is False


def test_a_missing_or_extreme_leg_is_not_a_basket():
    assert basket_quote([0.2], [0.0]) is None
    assert basket_quote([0.2, 1.0], [0.0, 0.0]) is None
