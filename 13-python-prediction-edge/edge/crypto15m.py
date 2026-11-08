"""One decision per Kalshi 15-minute crypto cycle.

This is the Krypt Trader final-minute rule, measured on public data: at the
start of the last minute, a settlement model prices the side, the taker fee
for one contract is subtracted, and the cycle is a trade only when that net
edge is between 2 and 3 cents. A wider history is not used. Fifteen-minute
crypto books change character inside a month, so the sample is one week.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FEE_COEFF = 0.07
EDGE_LOW_CENTS = 2.0
EDGE_HIGH_CENTS = 3.0
SIGMA_WINDOW = 30
_SETTLE_PRINTS = 60


def taker_fee_dollars(price: float, contracts: int = 1) -> float:
    """Kalshi's per-order fee, rounded up to the next cent, then split per contract."""
    p = max(0.0, min(1.0, float(price)))
    raw = FEE_COEFF * p * (1.0 - p)
    if contracts <= 0:
        return raw
    return math.ceil(raw * contracts * 100.0) / 100.0 / contracts


def sigma_1m(closes: list[float], window: int = SIGMA_WINDOW) -> float | None:
    """Sample standard deviation of the last `window` one-minute simple returns."""
    if len(closes) < window + 1:
        return None
    tail = closes[-(window + 1):]
    rets = [tail[i] / tail[i - 1] - 1.0 for i in range(1, len(tail)) if tail[i - 1] > 0]
    if len(rets) < window:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    if var <= 0:
        return None
    return math.sqrt(var)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def settlement_up_prob(spot: float, strike: float, sigma: float, mins_left: float = 1.0) -> float | None:
    """P(spot average over the final minute finishes above the strike).

    Called with one minute left and no prints in yet, which is the quote
    available at the start of the final minute.
    """
    if spot <= 0 or strike <= 0 or sigma <= 0:
        return None
    n_future = max(1, min(_SETTLE_PRINTS, int(round(max(0.0, mins_left) * 60.0))))
    sigma_1s = sigma / math.sqrt(60.0)
    var = (
        (spot * sigma_1s) ** 2
        * (n_future * (n_future + 1) * (2 * n_future + 1) / 6.0)
        / float(_SETTLE_PRINTS ** 2)
    )
    if var <= 0:
        return None
    return max(0.0, min(1.0, _norm_cdf((spot - strike) / math.sqrt(var))))


@dataclass(frozen=True)
class CycleQuote:
    asset: str
    ticker: str
    close_time: str
    spot: float
    strike: float
    sigma: float
    yes_ask: float
    no_ask: float | None
    up_won: bool | None = None


@dataclass(frozen=True)
class CycleDecision:
    asset: str
    ticker: str
    close_time: str
    side: str
    ask: float
    edge_cents: float
    up_prob: float
    fee: float
    take: bool


def decide(quote: CycleQuote, contracts: int = 1) -> CycleDecision | None:
    """Pick the side whose fee-adjusted edge is the larger one."""
    prob = settlement_up_prob(quote.spot, quote.strike, quote.sigma, 1.0)
    if prob is None:
        return None
    scored: list[tuple[float, str, float]] = []
    if 0.01 < quote.yes_ask < 0.99:
        fee = taker_fee_dollars(quote.yes_ask, contracts)
        edge = prob * 100.0 - quote.yes_ask * 100.0 - fee * 100.0
        scored.append((edge, "up", quote.yes_ask))
    if quote.no_ask is not None and 0.01 < quote.no_ask < 0.99:
        fee = taker_fee_dollars(quote.no_ask, contracts)
        edge = (1.0 - prob) * 100.0 - quote.no_ask * 100.0 - fee * 100.0
        scored.append((edge, "down", quote.no_ask))
    if not scored:
        return None
    edge, side, ask = max(scored, key=lambda row: row[0])
    fee = taker_fee_dollars(ask, contracts)
    return CycleDecision(
        asset=quote.asset, ticker=quote.ticker, close_time=quote.close_time,
        side=side, ask=ask, edge_cents=round(edge, 2), up_prob=prob, fee=fee,
        take=EDGE_LOW_CENTS <= edge <= EDGE_HIGH_CENTS,
    )


def settle_pnl(decision: CycleDecision, up_won: bool, contracts: int = 1) -> float:
    """Dollars for a one-contract hold to the window's result."""
    won = up_won if decision.side == "up" else not up_won
    payout = 1.0 if won else 0.0
    return (payout - decision.ask - decision.fee) * contracts
