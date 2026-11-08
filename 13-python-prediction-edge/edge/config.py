"""Run configuration. Missing file means the safe paper defaults."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from .money import D


@dataclass
class Config:
    bankroll: object = "1000"
    max_order_notional: object = "25"
    max_market_notional: object = "50"
    max_event_notional: object = "75"
    max_open_notional: object = "250"
    max_unpaired_notional: object = "20"
    max_daily_loss: object = "25"
    max_leg_loss: object = "0.02"
    min_edge: object = "0.01"
    min_profit: object = "0.05"
    max_spread: object = "0.10"
    min_basis_edge: object = "0.03"
    latency_haircut: object = "0.001"
    merge_gas_usd: object = "0.01"
    quote_size: object = "20"
    max_book_age_ms: int = 20000
    poly_event_limit: int = 12
    kalshi_series: tuple[str, ...] = ("KXBTCD", "KXETHD", "KXINXU")
    kalshi_events_per_series: int = 1
    trade_taker: bool = True
    trade_maker: bool = True
    trade_ladders: bool = True
    trade_basis: bool = True
    live_enabled: bool = False
    live_basis: bool = False
    loop_seconds: int = 20
    links_file: str = ""

    def __post_init__(self) -> None:
        for name in (
            "bankroll", "max_order_notional", "max_market_notional", "max_event_notional", "max_open_notional",
            "max_unpaired_notional", "max_daily_loss", "max_leg_loss", "min_edge",
            "min_profit", "min_basis_edge", "max_spread", "latency_haircut", "merge_gas_usd", "quote_size",
        ):
            setattr(self, name, D(getattr(self, name)))
        self.kalshi_series = tuple(self.kalshi_series)
        self.max_book_age_ms = int(self.max_book_age_ms)
        self.poly_event_limit = int(self.poly_event_limit)
        self.kalshi_events_per_series = int(self.kalshi_events_per_series)
        self.loop_seconds = int(self.loop_seconds)
        if self.max_order_notional <= 0 or self.bankroll <= 0:
            raise ValueError("max_order_notional and bankroll must be positive")

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        if not path:
            return cls()
        import json
        raw = json.loads(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("config must be a JSON object")
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(raw) - known)
        if unknown:
            raise ValueError(f"unknown config keys: {', '.join(unknown)}")
        if "kalshi_series" in raw:
            raw["kalshi_series"] = tuple(raw["kalshi_series"])
        cfg = cls(**raw)
        if cfg.min_edge < 0 or cfg.min_profit < 0 or cfg.min_basis_edge < 0:
            raise ValueError("min_edge, min_profit, and min_basis_edge must be >= 0")
        return cfg
