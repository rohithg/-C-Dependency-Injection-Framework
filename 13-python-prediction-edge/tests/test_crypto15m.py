from edge.crypto15m import CycleQuote, decide, settlement_up_prob, settle_pnl, sigma_1m, taker_fee_dollars


def test_one_contract_fee_rounds_up_to_the_next_cent():
    # 0.07 * 0.50 * 0.50 = 0.0175, and a one-lot order pays $0.02.
    assert taker_fee_dollars(0.50, 1) == 0.02


def test_flat_spot_is_a_coin_flip_and_a_two_cent_gap_is_taken():
    closes = [100.0 + (i % 3) * 0.02 for i in range(40)]
    sigma = sigma_1m(closes)
    assert sigma is not None and sigma > 0
    prob = settlement_up_prob(100.0, 100.0, sigma, 1.0)
    assert prob is not None and abs(prob - 0.5) < 0.02
    # Up ask 0.45 against a coin flip is several cents before the 2 cent fee.
    quote = CycleQuote("BTC", "T", "2026-11-08T22:45:00Z", 100.0, 100.0, sigma, 0.45, 0.55)
    decision = decide(quote)
    assert decision is not None
    assert decision.side == "up"
    assert decision.take is (2.0 <= decision.edge_cents <= 3.0)


def test_a_two_to_three_cent_edge_is_the_only_trade_and_settles_both_ways():
    # Build asks so the up side clears about 2.5 cents on a known probability.
    sigma = 0.001
    prob = settlement_up_prob(101.0, 100.0, sigma, 1.0)
    assert prob is not None and prob > 0.9
    fee = taker_fee_dollars(0.90, 1)
    ask = prob - fee - 0.025
    quote = CycleQuote("ETH", "T", "t", 101.0, 100.0, sigma, ask, 0.99)
    decision = decide(quote)
    assert decision is not None and decision.take and decision.side == "up"
    assert abs(decision.edge_cents - 2.5) < 0.15
    win = settle_pnl(decision, up_won=True)
    loss = settle_pnl(decision, up_won=False)
    assert win > 0
    assert loss < 0

    wide = CycleQuote("ETH", "T", "t", 101.0, 100.0, sigma, ask - 0.05, 0.99)
    bigger = decide(wide)
    assert bigger is not None and bigger.edge_cents > 3.0 and bigger.take is False
