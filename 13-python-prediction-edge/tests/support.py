"""Small market builder for the strategy tests."""

from edge.config import Config
from edge.models import BinaryMarket, Book, Level


def cfg(**overrides) -> Config:
    raw = {
        "min_edge": "0.01",
        "min_profit": "0.05",
        "max_spread": "0.10",
        "latency_haircut": "0",
        "merge_gas_usd": "0",
        "quote_size": "10",
        "max_order_notional": "100",
    }
    raw.update(overrides)
    return Config(**raw)


def market(market_id, yes_asks, no_asks, yes_bids=(), no_bids=(), fee_rate="0", fee_model="polymarket",
           title="", tick="0.01", min_size="1", taker_only=True):
    venue = "kalshi" if fee_model == "kalshi" else "polymarket"
    maker = "0.0175" if fee_model == "kalshi" else "0"

    def book(outcome, bids, asks):
        return Book(
            venue, market_id, f"{market_id}:{outcome}", outcome,
            [Level(p, s) for p, s in bids], [Level(p, s) for p, s in asks],
            tick, min_size, fee_model, fee_rate, 1, 1, maker, taker_only, 0, title or market_id,
        )

    return BinaryMarket(venue, market_id, title or market_id, book("yes", yes_bids, yes_asks), book("no", no_bids, no_asks))
