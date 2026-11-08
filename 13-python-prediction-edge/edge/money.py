"""Decimal helpers. Prices and sizes never pass through binary floats."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

ZERO = Decimal("0")
ONE = Decimal("1")
CENT = Decimal("0.01")
CENTICENT = Decimal("0.0001")
POLY_QUANTUM = Decimal("0.00001")
SIZE_QUANTUM = Decimal("0.01")


def D(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        return ZERO
    return Decimal(str(value))


def floor_to(value: Decimal, quantum: Decimal) -> Decimal:
    if quantum <= 0:
        return value
    return (value / quantum).to_integral_value(ROUND_FLOOR) * quantum


def ceil_to(value: Decimal, quantum: Decimal) -> Decimal:
    if quantum <= 0:
        return value
    return (value / quantum).to_integral_value(ROUND_CEILING) * quantum


def round_half_up(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def money(value: Decimal) -> str:
    return f"{value.quantize(CENT):f}"
