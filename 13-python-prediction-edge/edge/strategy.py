"""Structural trades.

Three packages have a payout of at least $1 no matter how the event lands.
Anything else in this file is a quote that tries to buy one of those packages
passively, or an explicit cross-venue hedge that can still break on the rules.

Complete set (Polymarket)
    One YES and one NO of the same condition merge to $1. Buying both is a
    win when the asks plus taker fees cost less than that. Selling both
    (mint, then hit the bids) is the mirror. YES and NO are different books,
    so the sum can leave $1. A Kalshi binary cannot: its NO ask is one minus
    its YES bid, and the matching engine already joins a crossed pair.

Strike ladder (Kalshi, and any book built the same way)
    On a "greater than" ladder a lower strike is the easier event. It implies
    nothing about a higher strike, but the higher strike implies the lower
    one. Buying YES on the easier strike and NO on the harder strike pays
    $1 in both wings and $2 in the band between them. The "less than" ladder
    is the same shape with the easy end at the higher cap.

Maker quote (Polymarket)
    Makers pay no fee on taker-only markets. Resting a YES bid and a NO bid
    that add up to at most $1 minus the minimum edge locks that edge if both
    are hit. One-sided fills are inventory, not an edge.

Basis (opt-in links file)
    Buy the cheap YES and the other venue's NO. Worst case is $1 only when
    the two contracts resolve the same way. They often do not, so this is
    never marked risk-free and live trading leaves it off.
"""

from __future__ import annotations

from decimal import Decimal

from .books import best_ask, best_bid, buy_limit, on_tick, sell_limit
from .config import Config
from .fees import maker_fee, taker_fee
from .models import BinaryMarket, Ladder, Leg, Opportunity, StrikeMarket, Watch
from .money import ONE, SIZE_QUANTUM, ZERO, floor_to


def plan_markets(binaries, ladders, links, config: Config):
    opportunities: list[Opportunity] = []
    watches: list[Watch] = []
    taker_markets: set[str] = set()

    for market in binaries:
        watch = watch_complete_set(market, config)
        if watch:
            watches.append(watch)
        if config.trade_taker:
            for builder in (complete_set_buy, complete_set_sell):
                opp = builder(market, config)
                if opp is not None:
                    opportunities.append(opp)
                    taker_markets.add(market.market_id)
        if config.trade_maker and market.market_id not in taker_markets:
            quote = maker_quote(market, config)
            if quote is not None:
                opportunities.append(quote)

    for ladder in ladders:
        watch = watch_ladder(ladder, config)
        if watch:
            watches.append(watch)
        if config.trade_ladders:
            opportunities.extend(ladder_opportunities(ladder, config))

    for link in links:
        if not config.trade_basis:
            continue
        found = basis_opportunity(link, config)
        if found is not None:
            opportunities.append(found)
        else:
            watch = watch_basis(link, config)
            if watch:
                watches.append(watch)

    opportunities.sort(key=lambda opp: opp.net_profit, reverse=True)
    return opportunities, watches


def complete_set_buy(market: BinaryMarket, config: Config) -> Opportunity | None:
    return _pair(
        market,
        config,
        kind="complete_set_buy",
        yes_levels=market.yes.asks,
        no_levels=market.no.asks,
        side="buy",
        note="buy YES and NO, hold the pair (merge is optional)",
    )


def complete_set_sell(market: BinaryMarket, config: Config) -> Opportunity | None:
    return _pair(
        market,
        config,
        kind="complete_set_sell",
        yes_levels=market.yes.bids,
        no_levels=market.no.bids,
        side="sell",
        note="mint a pair for $1 and sell both sides",
    )


def maker_quote(market: BinaryMarket, config: Config) -> Opportunity | None:
    y_bid = best_bid(market.yes)
    y_ask = best_ask(market.yes)
    n_bid = best_bid(market.no)
    n_ask = best_ask(market.no)
    if not (y_bid and y_ask and n_bid and n_ask):
        return None
    # A 30-cent spread is not a quote. The only way both bids fill is if the
    # market collapses onto one of them, and that fill is the one you did not want.
    if y_bid.price >= y_ask.price or n_bid.price >= n_ask.price:
        return None
    if y_ask.price - y_bid.price > config.max_spread or n_ask.price - n_bid.price > config.max_spread:
        return None
    tick = _tick(market)
    qy = _join(y_bid.price, y_ask.price, tick)
    qn = _join(n_bid.price, n_ask.price, tick)
    if qy is None or qn is None:
        return None
    budget = ONE - config.min_edge
    if qy + qn > budget:
        return None
    if qy + tick + qn <= budget and qy + tick < y_ask.price:
        qy = qy + tick
    elif qn + tick + qy <= budget and qn + tick < n_ask.price:
        qn = qn + tick
    size = min(config.quote_size, y_bid.size, n_bid.size, y_ask.size, n_ask.size)
    size = _cap_size(size, qy + qn, market.yes.min_size, config.max_order_notional)
    if size is None:
        return None
    y_fee = maker_fee(market.yes, size, qy)
    n_fee = maker_fee(market.no, size, qn)
    net = size * (ONE - qy - qn) - y_fee - n_fee - config.merge_gas_usd
    if net < config.min_profit:
        return None
    edge = net / size
    quotes = (
        _leg(market.yes, "buy", qy, size, y_fee, market.title),
        _leg(market.no, "buy", qn, size, n_fee, market.title),
    )
    return Opportunity(
        kind="maker",
        title=market.title,
        size=size,
        edge_per_share=edge,
        net_profit=net,
        legs=(),
        quotes=quotes,
        risk_free=False,
        market_ids=(market.market_id,),
        note="resting bids; profit only if both are hit, then the pair is worth $1",
        event_id=market.event_id,
        book_ts_ms=_ts(market),
    )


def ladder_opportunities(ladder: Ladder, config: Config) -> list[Opportunity]:
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


def basis_opportunity(link, config: Config) -> Opportunity | None:
    best: Opportunity | None = None
    # same_yes: the hedge is YES on one venue and NO on the other.
    # flipped labels: the hedge is the same named side on both venues.
    pairs = ((True, False), (False, True)) if link.same_yes else ((True, True), (False, False))
    for left_yes, right_yes in pairs:
        opp = _basis_leg(link, config, left_yes, right_yes)
        if opp is not None and (best is None or opp.net_profit > best.net_profit):
            best = opp
    return best


def watch_complete_set(market: BinaryMarket, config: Config) -> Watch | None:
    edge, detail = _touch_pair_edge(market, config, buy=True)
    if edge is None:
        return None
    return Watch(market.venue, market.title, "complete_set_buy", edge, detail)


def watch_ladder(ladder: Ladder, config: Config) -> Watch | None:
    opps = ladder_opportunities(ladder, _watch_config(config))
    if not opps:
        ordered = _easiest_first(ladder)
        if len(ordered) < 2:
            return None
        return Watch(ladder.venue, ladder.title, "ladder", ZERO, "no two-sided strikes")
    top = max(opps, key=lambda opp: opp.edge_per_share)
    return Watch(ladder.venue, top.title, "ladder", top.edge_per_share, top.note)


def watch_basis(link, config: Config) -> Watch | None:
    opp = basis_opportunity(link, _watch_config(config))
    if opp is None:
        return Watch("cross", link.name, "basis", ZERO, "one side has no ask")
    return Watch("cross", opp.title, "basis", opp.edge_per_share, opp.note)


def _pair(market, config, kind, yes_levels, no_levels, side, note) -> Opportunity | None:
    y = _top(yes_levels)
    n = _top(no_levels)
    if y is None or n is None:
        return None
    tick = _tick(market)
    if side == "buy":
        y_px = buy_limit(y.price, config.latency_haircut, tick)
        n_px = buy_limit(n.price, config.latency_haircut, tick)
    else:
        y_px = sell_limit(y.price, config.latency_haircut, tick)
        n_px = sell_limit(n.price, config.latency_haircut, tick)
    if y_px is None or n_px is None:
        return None
    size = _cap_size(min(y.size, n.size), y_px + n_px, market.yes.min_size, config.max_order_notional)
    if size is None:
        return None
    y_fee = taker_fee(market.yes, size, y_px)
    n_fee = taker_fee(market.no, size, n_px)
    if kind == "complete_set_buy":
        net = size - (y_px * size + n_px * size + y_fee + n_fee) - config.merge_gas_usd
    else:
        net = (y_px * size - y_fee) + (n_px * size - n_fee) - size - config.merge_gas_usd
    if net < config.min_profit:
        return None
    edge = net / size
    if edge < config.min_edge:
        return None
    legs = (
        _leg(market.yes, side, y_px, size, y_fee, market.title),
        _leg(market.no, side, n_px, size, n_fee, market.title),
    )
    return Opportunity(
        kind=kind,
        title=market.title,
        size=size,
        edge_per_share=edge,
        net_profit=net,
        legs=legs,
        risk_free=True,
        market_ids=(market.market_id,),
        note=note,
        event_id=market.event_id,
        book_ts_ms=_ts(market),
    )


def _ladder_pair(easy: StrikeMarket, hard: StrikeMarket, config: Config) -> Opportunity | None:
    yes = best_ask(easy.market.yes)
    no = best_ask(hard.market.no)
    if yes is None or no is None:
        return None
    tick = easy.market.yes.tick or hard.market.yes.tick or Decimal("0.01")
    y_px = buy_limit(yes.price, config.latency_haircut, tick)
    n_px = buy_limit(no.price, config.latency_haircut, tick)
    if y_px is None or n_px is None:
        return None
    size = _cap_size(min(yes.size, no.size), y_px + n_px, max(easy.market.yes.min_size, Decimal("1")), config.max_order_notional)
    if size is None:
        return None
    y_fee = taker_fee(easy.market.yes, size, y_px)
    n_fee = taker_fee(hard.market.no, size, n_px)
    net = size - (y_px * size + n_px * size + y_fee + n_fee)
    if net < config.min_profit or net / size < config.min_edge:
        return None
    title = f"{easy.market.title} vs {hard.market.title}"
    legs = (
        _leg(easy.market.yes, "buy", y_px, size, y_fee, easy.market.title),
        _leg(hard.market.no, "buy", n_px, size, n_fee, hard.market.title),
    )
    return Opportunity(
        kind="ladder",
        title=title,
        size=size,
        edge_per_share=net / size,
        net_profit=net,
        legs=legs,
        risk_free=True,
        market_ids=(easy.market.market_id, hard.market.market_id),
        note="worst case pays $1, the band between the strikes pays $2",
        event_id=easy.market.event_id,
        book_ts_ms=min(easy.market.yes.ts_ms, hard.market.no.ts_ms),
    )


def _basis_leg(link, config, left_is_yes: bool, right_is_yes: bool) -> Opportunity | None:
    left_book = link.left.yes if left_is_yes else link.left.no
    right_book = link.right.yes if right_is_yes else link.right.no
    # A hedge is YES on one contract and NO on the matched contract.
    # Callers pass the books that should be bought. Both are bought at the ask.
    left_ask = best_ask(left_book)
    right_ask = best_ask(right_book)
    if left_ask is None or right_ask is None:
        return None
    tick = left_book.tick or right_book.tick or Decimal("0.01")
    l_px = buy_limit(left_ask.price, config.latency_haircut, tick)
    r_px = buy_limit(right_ask.price, config.latency_haircut, tick)
    if l_px is None or r_px is None:
        return None
    size = _cap_size(min(left_ask.size, right_ask.size), l_px + r_px, left_book.min_size, config.max_order_notional)
    if size is None:
        return None
    l_fee = taker_fee(left_book, size, l_px)
    r_fee = taker_fee(right_book, size, r_px)
    net = size - (l_px * size + r_px * size + l_fee + r_fee)
    need = config.min_basis_edge
    if net < config.min_profit or net / size < need:
        return None
    legs = (
        _leg(left_book, "buy", l_px, size, l_fee, link.left.title),
        _leg(right_book, "buy", r_px, size, r_fee, link.right.title),
    )
    return Opportunity(
        kind="basis",
        title=link.name,
        size=size,
        edge_per_share=net / size,
        net_profit=net,
        legs=legs,
        risk_free=False,
        market_ids=(link.left.market_id, link.right.market_id),
        note="hedged only if both contracts resolve on the same fact",
        book_ts_ms=min(left_book.ts_ms, right_book.ts_ms),
    )


def _touch_pair_edge(market: BinaryMarket, config: Config, buy: bool):
    y = best_ask(market.yes) if buy else best_bid(market.yes)
    n = best_ask(market.no) if buy else best_bid(market.no)
    if y is None or n is None:
        return None, ""
    tick = _tick(market)
    if buy:
        y_px = buy_limit(y.price, config.latency_haircut, tick)
        n_px = buy_limit(n.price, config.latency_haircut, tick)
    else:
        y_px = sell_limit(y.price, config.latency_haircut, tick)
        n_px = sell_limit(n.price, config.latency_haircut, tick)
    if y_px is None or n_px is None:
        return None, ""
    size = min(y.size, n.size, Decimal("100"))
    y_fee = taker_fee(market.yes, size, y_px)
    n_fee = taker_fee(market.no, size, n_px)
    gross = (ONE - y.price - n.price) if buy else (y.price + n.price - ONE)
    net = size - y_px * size - n_px * size - y_fee - n_fee if buy else y_px * size + n_px * size - y_fee - n_fee - size
    edge = net / size
    detail = f"asks {y.price}+{n.price} gross {gross:.4f} fee {(y_fee + n_fee) / size:.4f} net {edge:.4f}"
    return edge, detail


def _watch_config(config: Config) -> Config:
    """Same fees and haircut, with the profit bar removed so near-misses still price."""
    return Config(
        bankroll=config.bankroll,
        max_order_notional=config.max_order_notional,
        max_market_notional=config.max_market_notional,
        max_open_notional=config.max_open_notional,
        max_unpaired_notional=config.max_unpaired_notional,
        max_daily_loss=config.max_daily_loss,
        max_leg_loss=config.max_leg_loss,
        min_edge="-1",
        min_profit="-1000000",
        min_basis_edge="-1",
        latency_haircut=config.latency_haircut,
        merge_gas_usd="0",
        quote_size=config.quote_size,
        max_book_age_ms=config.max_book_age_ms,
        trade_taker=True,
        trade_maker=False,
        trade_ladders=True,
        trade_basis=True,
    )


def _easiest_first(ladder: Ladder) -> list[StrikeMarket]:
    kind = ladder.kind
    if kind in ("greater", "greater_or_equal"):
        return sorted(ladder.strikes, key=lambda s: s.strike)
    if kind in ("less", "less_or_equal"):
        return sorted(ladder.strikes, key=lambda s: s.strike, reverse=True)
    return []


def _join(bid: Decimal, ask: Decimal, tick: Decimal) -> Decimal | None:
    raw = min(bid, ask - tick)
    price = on_tick(raw, tick)
    if price <= 0 or price >= ask:
        return None
    return price


def _cap_size(size: Decimal, pair_price: Decimal, min_size: Decimal, max_notional: Decimal) -> Decimal | None:
    if pair_price <= 0 or size <= 0:
        return None
    capped = min(size, max_notional / pair_price)
    capped = floor_to(capped, SIZE_QUANTUM)
    if capped <= 0 or capped < min_size:
        return None
    if capped * pair_price > max_notional + Decimal("0.0000001"):
        return None
    return capped


def _leg(book, side: str, price, size, fee, title: str) -> Leg:
    return Leg(book.venue, book.market_id, book.token_id, book.outcome, side, price, size, fee, title)


def _tick(market: BinaryMarket) -> Decimal:
    tick = market.yes.tick or market.no.tick
    return tick if tick > 0 else Decimal("0.01")


def _ts(market: BinaryMarket) -> int:
    stamps = [market.yes.ts_ms, market.no.ts_ms]
    live = [ts for ts in stamps if ts]
    return min(live) if live else 0


def _top(levels):
    for level in levels:
        if level.size > 0 and ZERO < level.price < ONE:
            return level
    return None
