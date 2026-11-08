"""Venue fee schedules.

Polymarket (takers only, official schedule):

    fee = shares * rate * (p * (1 - p)) ** exponent

rounded half-up to 0.00001 USDC. Exponent is 1 on every market checked
against the published table, which gives `shares * rate * p * (1 - p)`.
Makers pay nothing when the market is taker-only.

Kalshi (July 2026 schedule):

    taker = round_up(multiplier * 0.07 * contracts * p * (1 - p))
    maker = round_up(multiplier * 0.0175 * contracts * p * (1 - p))

rounded up so the fee lands on a centicent ($0.0001).
"""

from __future__ import annotations

from decimal import Decimal

from .money import CENTICENT, ONE, POLY_QUANTUM, ZERO, ceil_to, round_half_up

KALSHI_TAKER = Decimal("0.07")
KALSHI_MAKER = Decimal("0.0175")


def polymarket_taker_fee(shares: Decimal, price: Decimal, rate: Decimal, exponent: Decimal = ONE) -> Decimal:
    if shares <= 0 or rate <= 0 or price <= 0 or price >= 1:
        return ZERO
    raw = shares * rate * (price * (ONE - price)) ** exponent
    return round_half_up(raw, POLY_QUANTUM)


def kalshi_fee(contracts: Decimal, price: Decimal, rate: Decimal, multiplier: Decimal = ONE) -> Decimal:
    if contracts <= 0 or rate <= 0 or multiplier <= 0 or price <= 0 or price >= 1:
        return ZERO
    raw = multiplier * rate * contracts * price * (ONE - price)
    return ceil_to(raw, CENTICENT)


def taker_fee(book, size: Decimal, price: Decimal) -> Decimal:
    if book.fee_model == "kalshi":
        return kalshi_fee(size, price, book.fee_rate, book.fee_multiplier)
    return polymarket_taker_fee(size, price, book.fee_rate, book.fee_exponent)


def maker_fee(book, size: Decimal, price: Decimal) -> Decimal:
    if book.taker_only:
        return ZERO
    if book.fee_model == "kalshi":
        rate = book.maker_rate if book.maker_rate > 0 else KALSHI_MAKER
        return kalshi_fee(size, price, rate, book.fee_multiplier)
    return polymarket_taker_fee(size, price, book.fee_rate, book.fee_exponent)
