"""Top-of-book helpers.

A taker order is sized to the touch only. A limit sent at a deeper level's
price would also lift everything in front of it, and those shares can
disappear before the order arrives. Paying the touch, and no further, keeps
the paper fill and the live limit the same number.
"""

from __future__ import annotations

from decimal import Decimal

from .money import ONE, ZERO, ceil_to, floor_to
from .models import Book, Level


def top(levels: list[Level]) -> Level | None:
    for level in levels:
        if level.size > 0 and ZERO < level.price < ONE:
            return level
    return None


def best_bid(book: Book) -> Level | None:
    return top(book.bids)


def best_ask(book: Book) -> Level | None:
    return top(book.asks)


def buy_limit(ask: Decimal, haircut: Decimal, tick: Decimal) -> Decimal | None:
    """Worst price we are willing to pay, rounded up onto the tick grid."""
    price = ceil_to(ask + haircut, tick if tick > 0 else Decimal("0.0001"))
    if price <= 0 or price >= 1:
        return None
    return price


def sell_limit(bid: Decimal, haircut: Decimal, tick: Decimal) -> Decimal | None:
    price = floor_to(bid - haircut, tick if tick > 0 else Decimal("0.0001"))
    if price <= 0 or price >= 1:
        return None
    return price


def on_tick(price: Decimal, tick: Decimal) -> Decimal:
    return floor_to(price, tick if tick > 0 else Decimal("0.0001"))


def consume_ask(book: Book, size: Decimal) -> None:
    left = size
    for level in book.asks:
        if left <= 0:
            return
        take = min(level.size, left)
        level.size -= take
        left -= take


def consume_bid(book: Book, size: Decimal) -> None:
    left = size
    for level in book.bids:
        if left <= 0:
            return
        take = min(level.size, left)
        level.size -= take
        left -= take
