"""Thresholds for the strategy. These decide whether a book is a trade."""

from __future__ import annotations

from dataclasses import dataclass

from .money import D


@dataclass
class Config:
    min_edge: object = "0.01"
    min_profit: object = "0.05"
    max_spread: object = "0.10"
    latency_haircut: object = "0"
    merge_gas_usd: object = "0"
    quote_size: object = "20"
    max_order_notional: object = "100"

    def __post_init__(self) -> None:
        for name in (
            "min_edge", "min_profit", "max_spread", "latency_haircut",
            "merge_gas_usd", "quote_size", "max_order_notional",
        ):
            setattr(self, name, D(getattr(self, name)))
        if self.max_order_notional <= 0:
            raise ValueError("max_order_notional must be positive")
