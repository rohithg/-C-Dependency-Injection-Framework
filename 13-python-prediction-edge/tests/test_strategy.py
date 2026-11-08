from decimal import Decimal

from edge.models import BasisLink, Ladder, StrikeMarket
from edge.strategy import basis_opportunity, complete_set_buy, ladder_opportunities, maker_quote
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


def test_basis_buys_yes_against_the_other_venues_no():
    left = market("poly", [("0.40", "20")], [("0.70", "20")], title="poly")
    right = market("kal", [("0.55", "20")], [("0.40", "20")], [("0.60", "20")], [("0.45", "20")],
                   fee_model="kalshi", fee_rate="0.07", title="kalshi")
    # right NO ask is 0.40, so YES-poly + NO-kalshi costs about 0.80 before fees.
    opp = basis_opportunity(BasisLink("same event", left, right, same_yes=True), cfg(min_profit="0.05", min_basis_edge="0.03"))
    assert opp is not None
    assert opp.risk_free is False
    assert {leg.token_id for leg in opp.legs} == {"poly:yes", "kal:no"}


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
