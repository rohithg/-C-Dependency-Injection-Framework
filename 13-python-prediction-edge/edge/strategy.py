"""When a book is a package worth at least $1.

Complete set (Polymarket)
    One YES and one NO of the same condition are worth $1. Buy both when the
    asks plus taker fees cost less than that. Sell both when the bids, after
    fees, bring in more than $1. YES and NO are different books, so the sum
    can leave $1. A Kalshi binary cannot: its NO ask is one minus its YES bid.

Strike ladder (Kalshi)
    On a "greater than" ladder the lower strike is the easier event. Buying
    YES there and NO on a higher strike pays $1 in both wings and $2 if the
    result lands between them. A "less than" ladder is the same shape with
    the easy end at the higher cap.

Maker quote (Polymarket)
    Makers pay no fee on taker-only markets. Rest a YES bid and a NO bid that
    add up to at most $1 minus the minimum edge, and only when each spread is
    tight enough that both sides can actually be hit. One fill is inventory.
"""

from __future__ import annotations

from decimal import Decimal

from .books import best_ask, best_bid, buy_limit, on_tick, sell_limit
from .config import Config
from .fees import maker_fee, taker_fee
from .models import BinaryMarket, Ladder, Leg, Opportunity, StrikeMarket
from .money import ONE, SIZE_QUANTUM, ZERO, floor_to


def complete_set_buy(market: BinaryMarket, config: Config | None = None) -> Opportunity | None:
    """Buy YES and NO. The pair pays $1 however the market resolves."""
    return _pair(
        market, config or Config(), "complete_set_buy",
        market.yes.asks, market.no.asks, "buy",
        "buy YES and NO; the pair pays $1",
    )


def complete_set_sell(market: BinaryMarket, config: Config | None = None) -> Opportunity | None:
    """Mint a pair for $1 and sell both sides into the bids."""
    return _pair(
        market, config or Config(), "complete_set_sell",
        market.yes.bids, market.no.bids, "sell",
        "sell YES and NO for more than the $1 the pair costs",
    )


def maker_quote(market: BinaryMarket, config: Config | None = None) -> Opportunity | None:
    """Rest both bids. The edge exists only if both are hit."""
    config = config or Config()
    y_bid, y_ask = best_bid(market.yes), best_ask(market.yes)
    n_bid, n_ask = best_bid(market.no), best_ask(market.no)
    if not (y_bid and y_ask and n_bid and n_ask):
        return None
    if y_bid.price >= y_ask.price or n_bid.price >= n_ask.price:
        return None
    if y_ask.price - y_bid.price > config.max_spread or n_ask.price - n_bid.price > config.max_spread:
        return None
    tick = _tick(market)
    qy, qn = _join(y_bid.price, y_ask.price, tick), _join(n_bid.price, n_ask.price, tick)
    if qy is None or qn is None:
        return None
    budget = ONE - config.min_edge
    if qy + qn > budget:
        return None
    if qy + tick + qn <= budget and qy + tick < y_ask.price:
        qy = qy + tick
    elif qn + tick + qy <= budget and qn + tick < n_ask.price:
        qn = qn + tick
    size = _cap_size(
        min(config.quote_size, y_bid.size, n_bid.size, y_ask.size, n_ask.size),
        qy + qn, market.yes.min_size, config.max_order_notional,
    )
    if size is None:
        return None
    y_fee, n_fee = maker_fee(market.yes, size, qy), maker_fee(market.no, size, qn)
    net = size * (ONE - qy - qn) - y_fee - n_fee - config.merge_gas_usd
    if net < config.min_profit:
        return None
    return Opportunity(
        kind="maker", title=market.title, size=size, edge_per_share=net / size, net_profit=net,
        legs=(), quotes=(
            _leg(market.yes, "buy", qy, size, y_fee, market.title),
            _leg(market.no, "buy", qn, size, n_fee, market.title),
        ),
        risk_free=False, market_ids=(market.market_id,),
        note="both bids have to fill; then the pair is worth $1",
    )


def ladder_opportunities(ladder: Ladder, config: Config | None = None) -> list[Opportunity]:
    """Buy the easier strike and sell the harder one, for every pair that clears fees."""
    config = config or Config()
    ordered = _easiest_first(ladder)
    if len(ordered) < 2:
        return []
    found: list[Opportunity] = []
    best_i: int | None = None
    best_bid_px = None
    best_bid_sz = ZERO
    for i in range(len(ordered) - 1, -1, -1):
        if best_i is not None:
            opp = _ladder_pair(ordered[i], ordered[best_i], config)
            if opp is not None:
                found.append(opp)
        bid = best_bid(ordered[i].market.yes)
        if bid is not None and (best_bid_px is None or bid.price > best_bid_px or (
            bid.price == best_bid_px and bid.size > best_bid_sz
        )):
            best_i = i
            best_bid_px = bid.price
            best_bid_sz = bid.size
    return found


def _pair(market, config, kind, yes_levels, no_levels, side, note) -> Opportunity | None:
    y, n = _top(yes_levels), _top(no_levels)
    if y is None or n is None:
        return None
    tick = _tick(market)
    limit = buy_limit if side == "buy" else sell_limit
    y_px, n_px = limit(y.price, config.latency_haircut, tick), limit(n.price, config.latency_haircut, tick)
    if y_px is None or n_px is None:
        return None
    size = _cap_size(min(y.size, n.size), y_px + n_px, market.yes.min_size, config.max_order_notional)
    if size is None:
        return None
    y_fee, n_fee = taker_fee(market.yes, size, y_px), taker_fee(market.no, size, n_px)
    if kind == "complete_set_buy":
        net = size - (y_px * size + n_px * size + y_fee + n_fee) - config.merge_gas_usd
    else:
        net = (y_px * size - y_fee) + (n_px * size - n_fee) - size - config.merge_gas_usd
    if net < config.min_profit or net / size < config.min_edge:
        return None
    return Opportunity(
        kind=kind, title=market.title, size=size, edge_per_share=net / size, net_profit=net,
        legs=(
            _leg(market.yes, side, y_px, size, y_fee, market.title),
            _leg(market.no, side, n_px, size, n_fee, market.title),
        ),
        risk_free=True, market_ids=(market.market_id,), note=note,
    )


def _ladder_pair(easy: StrikeMarket, hard: StrikeMarket, config: Config) -> Opportunity | None:
    yes, no = best_ask(easy.market.yes), best_ask(hard.market.no)
    if yes is None or no is None:
        return None
    tick = easy.market.yes.tick or hard.market.yes.tick or Decimal("0.01")
    y_px, n_px = buy_limit(yes.price, config.latency_haircut, tick), buy_limit(no.price, config.latency_haircut, tick)
    if y_px is None or n_px is None:
        return None
    size = _cap_size(min(yes.size, no.size), y_px + n_px, max(easy.market.yes.min_size, ONE), config.max_order_notional)
    if size is None:
        return None
    y_fee, n_fee = taker_fee(easy.market.yes, size, y_px), taker_fee(hard.market.no, size, n_px)
    net = size - (y_px * size + n_px * size + y_fee + n_fee)
    if net < config.min_profit or net / size < config.min_edge:
        return None
    return Opportunity(
        kind="ladder", title=f"{easy.market.title} vs {hard.market.title}",
        size=size, edge_per_share=net / size, net_profit=net,
        legs=(
            _leg(easy.market.yes, "buy", y_px, size, y_fee, easy.market.title),
            _leg(hard.market.no, "buy", n_px, size, n_fee, hard.market.title),
        ),
        risk_free=True, market_ids=(easy.market.market_id, hard.market.market_id),
        note="worst case pays $1; the band between the strikes pays $2",
    )


def _easiest_first(ladder: Ladder) -> list[StrikeMarket]:
    if ladder.kind in ("greater", "greater_or_equal"):
        return sorted(ladder.strikes, key=lambda s: s.strike)
    if ladder.kind in ("less", "less_or_equal"):
        return sorted(ladder.strikes, key=lambda s: s.strike, reverse=True)
    return []


def _join(bid: Decimal, ask: Decimal, tick: Decimal) -> Decimal | None:
    price = on_tick(min(bid, ask - tick), tick)
    if price <= 0 or price >= ask:
        return None
    return price


def _cap_size(size: Decimal, pair_price: Decimal, min_size: Decimal, max_notional: Decimal) -> Decimal | None:
    if pair_price <= 0 or size <= 0:
        return None
    capped = floor_to(min(size, max_notional / pair_price), SIZE_QUANTUM)
    if capped <= 0 or capped < min_size or capped * pair_price > max_notional + Decimal("0.0000001"):
        return None
    return capped


def _leg(book, side: str, price, size, fee, title: str) -> Leg:
    return Leg(book.venue, book.market_id, book.token_id, book.outcome, side, price, size, fee, title)


def _tick(market: BinaryMarket) -> Decimal:
    tick = market.yes.tick or market.no.tick
    return tick if tick > 0 else Decimal("0.01")


def _top(levels):
    for level in levels:
        if level.size > 0 and ZERO < level.price < ONE:
            return level
    return None
