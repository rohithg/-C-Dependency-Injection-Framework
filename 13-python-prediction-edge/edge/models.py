"""Market and order types shared by the scanners, the paper account, and live submission."""

from __future__ import annotations

from dataclasses import dataclass, field

from .money import ZERO, D


@dataclass
class Level:
    price: object
    size: object

    def __post_init__(self) -> None:
        self.price = D(self.price)
        self.size = D(self.size)


@dataclass
class Book:
    """One outcome token. Bids and asks are best-first."""

    venue: str
    market_id: str
    token_id: str
    outcome: str
    bids: list[Level]
    asks: list[Level]
    tick: object
    min_size: object
    fee_model: str
    fee_rate: object
    fee_exponent: object = 1
    fee_multiplier: object = 1
    maker_rate: object = 0
    taker_only: bool = True
    ts_ms: int = 0
    title: str = ""

    def __post_init__(self) -> None:
        self.tick = D(self.tick)
        self.min_size = D(self.min_size)
        self.fee_rate = D(self.fee_rate)
        self.fee_exponent = D(self.fee_exponent)
        self.fee_multiplier = D(self.fee_multiplier)
        self.maker_rate = D(self.maker_rate)
        self.bids = [_as_level(x) for x in self.bids]
        self.asks = [_as_level(x) for x in self.asks]
        self.bids.sort(key=lambda lvl: lvl.price, reverse=True)
        self.asks.sort(key=lambda lvl: lvl.price)


@dataclass
class BinaryMarket:
    venue: str
    market_id: str
    title: str
    yes: Book
    no: Book
    event_id: str = ""


@dataclass
class StrikeMarket:
    market: BinaryMarket
    strike: object
    kind: str

    def __post_init__(self) -> None:
        self.strike = D(self.strike)


@dataclass
class Ladder:
    """Strikes on one event that nest: a higher bar implies a lower bar."""

    venue: str
    event_id: str
    title: str
    kind: str
    strikes: list[StrikeMarket]


@dataclass
class BasisLink:
    """An explicit, hand-checked pair. This is not risk-free: rules can differ."""

    name: str
    left: BinaryMarket
    right: BinaryMarket
    same_yes: bool = True


@dataclass(frozen=True)
class Leg:
    venue: str
    market_id: str
    token_id: str
    outcome: str
    side: str
    price: object
    size: object
    fee: object
    title: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", D(self.price))
        object.__setattr__(self, "size", D(self.size))
        object.__setattr__(self, "fee", D(self.fee))

    @property
    def notional(self):
        return self.price * self.size


@dataclass(frozen=True)
class Opportunity:
    kind: str
    title: str
    size: object
    edge_per_share: object
    net_profit: object
    legs: tuple[Leg, ...]
    risk_free: bool
    market_ids: tuple[str, ...]
    note: str
    event_id: str = ""
    book_ts_ms: int = 0
    quotes: tuple[Leg, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "size", D(self.size))
        object.__setattr__(self, "edge_per_share", D(self.edge_per_share))
        object.__setattr__(self, "net_profit", D(self.net_profit))

    @property
    def orders(self) -> tuple[Leg, ...]:
        return self.quotes if self.kind == "maker" else self.legs

    @property
    def cash_needed(self):
        if self.kind == "complete_set_sell":
            return self.size
        return sum((leg.notional + leg.fee for leg in self.orders), ZERO)


@dataclass(frozen=True)
class Watch:
    venue: str
    title: str
    kind: str
    edge_per_share: object
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_per_share", D(self.edge_per_share))


@dataclass
class Plan:
    opportunities: list[Opportunity] = field(default_factory=list)
    watches: list[Watch] = field(default_factory=list)


def _as_level(value) -> Level:
    if isinstance(value, Level):
        return value
    price, size = value
    return Level(price, size)
