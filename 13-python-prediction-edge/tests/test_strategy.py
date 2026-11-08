from decimal import Decimal

from edge.models import Ladder, StrikeMarket
from edge.strategy import complete_set_buy, ladder_opportunities, maker_quote, yes_basket
from support import cfg, market


def test_two_cent_gross_edge_loses_to_crypto_fees():
    # Asks 0.49 + 0.49 look like 2 cents. Each taker fee at that price is about 1.75 cents.
    book = market("crypto", [("0.49", "100")], [("0.49", "100")], fee_rate="0.07")
    assert complete_set_buy(book, cfg()) is None


def test_fee_free_complete_set_is_bought_at_the_touch_only():
    book = market("free", [("0.45", "40"), ("0.50", "100")], [("0.45", "40")])
    opp = complete_set_buy(book, cfg())
    assert opp is not None
    assert opp.risk_free
    assert opp.size == Decimal("40")
    assert opp.net_profit == Decimal("4.00")
    assert opp.legs[0].price == Decimal("0.45")


def test_kalshi_style_complement_is_not_a_complete_set():
    # NO ask = 1 - YES bid. The sum of the asks is the spread, not a discount to $1.
    book = market(
        "binary",
        [("0.45", "10")], [("0.60", "10")],
        yes_bids=[("0.40", "10")], no_bids=[("0.55", "10")],
        fee_model="kalshi", fee_rate="0.07",
    )
    assert complete_set_buy(book, cfg()) is None


def test_ladder_buys_the_easier_yes_and_the_harder_no():
    ladder = _ladder("greater", [
        ("100", "0.40", "20", "0.30", "20"),
        ("110", "0.80", "20", "0.70", "20"),
    ])
    opps = ladder_opportunities(ladder, cfg(min_edge="0.01", min_profit="0.05"))
    assert len(opps) == 1
    opp = opps[0]
    assert opp.risk_free
    assert opp.size == Decimal("20")
    assert {leg.token_id for leg in opp.legs} == {"E100:yes", "E110:no"}
    # 20 shares, pays at least 20, costs 8 + 6 plus Kalshi fees 0.336 and 0.294.
    assert opp.net_profit == Decimal("5.3700")


def test_ladder_that_is_priced_in_order_is_left_alone():
    ladder = _ladder("greater", [
        ("100", "0.70", "20", "0.60", "20"),
        ("110", "0.40", "20", "0.30", "20"),
    ])
    assert ladder_opportunities(ladder, cfg()) == []


def test_less_than_ladder_treats_the_higher_cap_as_the_easier_contract():
    ladder = _ladder("less", [
        ("60", "0.80", "15", "0.70", "15"),
        ("70", "0.40", "15", "0.30", "15"),
    ])
    opps = ladder_opportunities(ladder, cfg())
    assert len(opps) == 1
    assert {leg.token_id for leg in opps[0].legs} == {"E70:yes", "E60:no"}


def test_maker_joins_the_bid_and_will_not_quote_through_a_tight_book():
    wide = market("wide", [("0.52", "100")], [("0.52", "100")], [("0.46", "100")], [("0.46", "100")])
    quote = maker_quote(wide, cfg())
    assert quote is not None
    prices = sorted(leg.price for leg in quote.quotes)
    # One side is improved a tick, and the pair still clears a cent.
    assert prices == [Decimal("0.46"), Decimal("0.47")]
    tight = market("tight", [("0.51", "100")], [("0.51", "100")], [("0.50", "100")], [("0.50", "100")])
    assert maker_quote(tight, cfg()) is None
    ghost = market("ghost", [("0.80", "100")], [("0.80", "100")], [("0.20", "100")], [("0.20", "100")])
    assert maker_quote(ghost, cfg()) is None


def test_yes_basket_pays_a_dollar_when_every_outcome_is_cheap():
    legs = [
        market("a", [("0.30", "20")], [("0.80", "20")], title="A"),
        market("b", [("0.30", "50")], [("0.80", "20")], title="B"),
        market("c", [("0.20", "40")], [("0.80", "20")], title="C"),
    ]
    opp = yes_basket(legs, cfg())
    assert opp is not None
    assert opp.risk_free
    assert opp.size == Decimal("20")
    assert opp.net_profit == Decimal("4.00")
    assert {leg.token_id for leg in opp.legs} == {"a:yes", "b:yes", "c:yes"}


def test_yes_basket_fees_take_the_two_cent_gap():
    legs = [
        market("a", [("0.49", "100")], [("0.60", "10")], fee_rate="0.07"),
        market("b", [("0.49", "100")], [("0.60", "10")], fee_rate="0.07"),
    ]
    assert yes_basket(legs, cfg()) is None
    priced = [
        market("a", [("0.30", "10")], [("0.80", "10")], fee_rate="0.05", title="A"),
        market("b", [("0.30", "10")], [("0.80", "10")], fee_rate="0.05", title="B"),
        market("c", [("0.30", "10")], [("0.80", "10")], fee_rate="0.05", title="C"),
    ]
    opp = yes_basket(priced, cfg())
    assert opp is not None
    # 10 shares pay $10, cost $9, and each leg's fee is 10 * 0.05 * 0.30 * 0.70.
    assert opp.net_profit == Decimal("0.685")


def test_yes_basket_refuses_a_single_name_or_a_touch_under_the_minimum():
    assert yes_basket([market("only", [("0.40", "20")], [("0.70", "20")])], cfg()) is None
    thin = [
        market("a", [("0.20", "4")], [("0.90", "10")], min_size="5"),
        market("b", [("0.20", "100")], [("0.90", "10")], min_size="5"),
    ]
    assert yes_basket(thin, cfg()) is None


def _ladder(kind, rows):
    strikes = []
    for strike, yes_ask, yes_ask_sz, yes_bid, yes_bid_sz in rows:
        no_ask = str(Decimal("1") - Decimal(yes_bid))
        no_bid = str(Decimal("1") - Decimal(yes_ask))
        book = market(
            f"E{strike}",
            [(yes_ask, yes_ask_sz)],
            [(no_ask, yes_bid_sz)],
            [(yes_bid, yes_bid_sz)],
            [(no_bid, yes_ask_sz)],
            fee_model="kalshi",
            fee_rate="0.07",
            taker_only=False,
            title=f"strike {strike}",
        )
        strikes.append(StrikeMarket(book, strike, kind))
    return Ladder("kalshi", "EVT", "ladder", kind, strikes)
