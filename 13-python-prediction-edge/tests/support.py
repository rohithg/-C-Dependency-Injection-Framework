"""Small market builder for the offline tests."""

from edge.config import Config
from edge.replay import binary_from_dict


def cfg(**overrides) -> Config:
    raw = {
        "bankroll": "1000",
        "max_order_notional": "100",
        "max_market_notional": "200",
        "max_open_notional": "500",
        "max_daily_loss": "25",
        "max_leg_loss": "0.02",
        "max_unpaired_notional": "20",
        "min_edge": "0.01",
        "min_profit": "0.05",
        "min_basis_edge": "0.03",
        "latency_haircut": "0",
        "merge_gas_usd": "0",
        "quote_size": "10",
    }
    raw.update(overrides)
    return Config(**raw)


def market(market_id, yes_asks, no_asks, yes_bids=(), no_bids=(), fee_rate="0", fee_model="polymarket",
           title="", tick="0.01", min_size="1", taker_only=True, ts_ms=0):
    return binary_from_dict({
        "venue": "kalshi" if fee_model == "kalshi" else "polymarket",
        "market_id": market_id,
        "title": title or market_id,
        "tick": tick,
        "min_size": min_size,
        "fee_model": fee_model,
        "fee_rate": fee_rate,
        "taker_only": taker_only,
        "maker_rate": "0.0175" if fee_model == "kalshi" else "0",
        "ts_ms": ts_ms,
        "yes": {"token_id": f"{market_id}:yes", "bids": list(yes_bids), "asks": list(yes_asks)},
        "no": {"token_id": f"{market_id}:no", "bids": list(no_bids), "asks": list(no_asks)},
    })
