"""Copy-trading rules and the paper portfolio. Pure logic, no network.

A *trade* is a dict as returned by data-api /activity (type TRADE):
    proxyWallet, timestamp, conditionId, asset (token id), side BUY|SELL,
    size (shares), usdcSize, price, outcome, title, slug
A *market* is the dict produced by PolymarketAPI.market().

Sizing is deliberately simple and bankroll-relative rather than mirroring the
leader's dollar size (their bankrolls are 10-1000x ours and unknown
historically): every copied BUY risks `trade_fraction` of current equity,
subject to a per-market cap, and a copied SELL unwinds the same fraction of
our position that the leader unwound of theirs.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
import math
from typing import Callable

TOKEN_MIN, TOKEN_MAX = 0.001, 0.999


@dataclass(frozen=True)
class CopyConfig:
    follow_n: int = 10                 # wallets copied at a time
    latency_min: int = 60              # minutes between leader's fill and our (hourly cron) fill
    min_hours_to_end: float = 3.0      # skip markets that end sooner than this after the trade (hourly job + 60 min latency)
    min_price: float = 0.03            # skip near-certain / lottery-ticket prices
    max_price: float = 0.97
    min_usdc: float = 25.0             # ignore the leader's dust trades (median leader BUY is ~$26)
    trade_fraction: float = 0.01       # equity risked per copied buy
    max_market_fraction: float = 0.05  # cap on cost basis in one market
    max_leader_multiple: float = 1.0   # our notional per copied buy <= leader's notional x this (0 = no cap)
    slippage: float = 0.01             # price paid above/below the reference on each side
    max_trades_per_day: float = 100.0  # wallets busier than this are bots we cannot follow
    min_copyable_trades: int = 15      # for scoring a wallet
    lookback_days: int = 90            # scoring window
    rebalance_days: int = 30           # how often the followed set is re-picked
    skip_slug_parts: tuple[str, ...] = ("updown", "-5m-", "-15m-", "-1h-", "up-or-down")

    def to_json(self, path):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def from_json(cls, path) -> "CopyConfig":
        with open(path) as f:
            raw = json.load(f)
        if "skip_slug_parts" in raw:
            raw["skip_slug_parts"] = tuple(raw["skip_slug_parts"])
        return cls(**raw)


DEFAULT = CopyConfig()


def taker_fee(shares: float, price: float, fee_rate: float) -> float:
    """Polymarket taker fee: shares x rate x p x (1-p)."""
    return shares * fee_rate * price * (1.0 - price)


def precheck(trade: dict, cfg: CopyConfig) -> str | None:
    """Cheap filters that need no market lookup. None = passes."""
    if trade.get("side") not in ("BUY", "SELL"):
        return "not a trade"
    slug = (trade.get("slug") or "").lower()
    if any(p in slug for p in cfg.skip_slug_parts):
        return "short-horizon market"
    if trade["side"] == "BUY":
        if float(trade.get("usdcSize", 0)) < cfg.min_usdc:
            return "dust"
        p = float(trade["price"])
        if not (cfg.min_price <= p <= cfg.max_price):
            return f"price {p:.2f} out of range"
    return None


def copyable(trade: dict, market: dict | None, cfg: CopyConfig) -> str | None:
    """None if we would copy this trade, else the reason we skip it."""
    why = precheck(trade, cfg)
    if why:
        return why
    if market is None:
        return "unknown market"
    slug = (market.get("slug") or "").lower()
    if any(p in slug for p in cfg.skip_slug_parts):
        return "short-horizon market"
    end_ts = market.get("end_ts")
    if end_ts is None:
        return "no end date"
    hours = (end_ts - int(trade["timestamp"])) / 3600
    if hours < cfg.min_hours_to_end:
        return f"ends in {hours:.0f}h"
    return None


# --------------------------------------------------------------------------- portfolio

@dataclass
class Position:
    token: str
    condition_id: str
    shares: float = 0.0
    cost: float = 0.0                              # USDC paid incl. fees (basis)
    by_wallet: dict[str, float] = field(default_factory=dict)   # shares attributed to each leader
    title: str = ""
    outcome: str = ""
    end_ts: int | None = None


@dataclass
class Fill:
    ts: int
    wallet: str
    token: str
    condition_id: str
    side: str
    shares: float
    price: float
    fee: float
    leader_price: float
    title: str
    outcome: str
    note: str = ""

    @property
    def notional(self) -> float:
        return self.shares * self.price


class Portfolio:
    def __init__(self, cash: float = 10_000.0):
        self.cash = cash
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []
        self.realized: float = 0.0
        self.fees_paid: float = 0.0
        self.last_equity: float = cash

    # ---- accounting ---------------------------------------------------------
    def market_cost(self, condition_id: str) -> float:
        return sum(p.cost for p in self.positions.values() if p.condition_id == condition_id)

    def value(self, price_of: Callable[[str], float | None]) -> float:
        total = self.cash
        for p in self.positions.values():
            px = price_of(p.token)
            if px is None:                       # no quote: carry at cost
                total += p.cost
            else:
                total += p.shares * px
        self.last_equity = total
        return total

    def buy(self, ts: int, wallet: str, token: str, condition_id: str, shares: float, price: float,
            fee_rate: float, leader_price: float, title: str = "", outcome: str = "", end_ts: int | None = None,
            note: str = "") -> Fill | None:
        fee = taker_fee(shares, price, fee_rate)
        cost = shares * price + fee
        if shares <= 0 or cost > self.cash + 1e-9:
            return None
        self.cash -= cost
        self.fees_paid += fee
        pos = self.positions.setdefault(token, Position(token, condition_id, title=title, outcome=outcome, end_ts=end_ts))
        pos.shares += shares
        pos.cost += cost
        pos.by_wallet[wallet] = pos.by_wallet.get(wallet, 0.0) + shares
        f = Fill(ts, wallet, token, condition_id, "BUY", shares, price, fee, leader_price, title, outcome, note)
        self.fills.append(f)
        return f

    def sell(self, ts: int, wallet: str, token: str, shares: float, price: float, fee_rate: float,
             leader_price: float, note: str = "") -> Fill | None:
        pos = self.positions.get(token)
        if pos is None or shares <= 0:
            return None
        shares = min(shares, pos.shares)
        fee = taker_fee(shares, price, fee_rate)
        proceeds = shares * price - fee
        basis = pos.cost * shares / pos.shares
        self.cash += proceeds
        self.fees_paid += fee
        self.realized += proceeds - basis
        pos.cost -= basis
        pos.shares -= shares
        if wallet in pos.by_wallet:
            pos.by_wallet[wallet] = max(0.0, pos.by_wallet[wallet] - shares)
        if pos.shares <= 1e-9:
            del self.positions[token]
        f = Fill(ts, wallet, token, pos.condition_id, "SELL", shares, price, fee, leader_price, pos.title, pos.outcome, note)
        self.fills.append(f)
        return f

    def resolve(self, token: str, payout: float, ts: int) -> Fill | None:
        """Market resolved: each share pays `payout` (1 or 0) USDC, no fee."""
        pos = self.positions.pop(token, None)
        if pos is None:
            return None
        proceeds = pos.shares * payout
        self.cash += proceeds
        self.realized += proceeds - pos.cost
        f = Fill(ts, "", token, pos.condition_id, "RESOLVE", pos.shares, payout, 0.0, payout, pos.title, pos.outcome)
        self.fills.append(f)
        return f

    # ---- persistence --------------------------------------------------------
    def to_dict(self) -> dict:
        return {"cash": self.cash, "realized": self.realized, "fees_paid": self.fees_paid, "last_equity": self.last_equity,
                "positions": {k: asdict(v) for k, v in self.positions.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "Portfolio":
        p = cls(d["cash"])
        p.realized, p.fees_paid, p.last_equity = d.get("realized", 0.0), d.get("fees_paid", 0.0), d.get("last_equity", d["cash"])
        p.positions = {k: Position(**v) for k, v in d.get("positions", {}).items()}
        return p


# --------------------------------------------------------------------------- copying one trade

class LeaderBook:
    """Shares each leader holds per token, rebuilt from the trades we have seen,
    so a SELL can be expressed as 'fraction of position unwound'."""

    def __init__(self):
        self.shares: dict[tuple[str, str], float] = {}

    def apply(self, trade: dict) -> float:
        """Update with the leader's trade; return the fraction of the position it unwound (SELL) or 0."""
        key = (trade["proxyWallet"].lower(), trade["asset"])
        before = self.shares.get(key, 0.0)
        size = float(trade["size"])
        if trade["side"] == "BUY":
            self.shares[key] = before + size
            return 0.0
        after = max(0.0, before - size)
        self.shares[key] = after
        if before <= 0:
            return 1.0                    # we never saw the buy: treat as a full exit
        return min(1.0, size / before)


def copy_trade(trade: dict, market: dict | None, portfolio: Portfolio, leaders: LeaderBook, cfg: CopyConfig,
               exec_price: Callable[[str, str, int, float], float | None], equity: float | None = None,
               fraction_override: float | None = None) -> tuple[Fill | None, str]:
    """Mirror one leader trade into the portfolio.

    exec_price(token, side, ts, leader_price) -> the price we would get for
    `side` at time `ts` (already including latency and slippage), or None if
    unknown. Returns (fill or None, reason).
    """
    wallet = trade["proxyWallet"].lower()
    unwound = leaders.apply(trade)
    token, cid, ts = trade["asset"], trade["conditionId"], int(trade["timestamp"])
    if trade["side"] == "SELL":
        pos = portfolio.positions.get(token)
        if pos is None or pos.by_wallet.get(wallet, 0.0) <= 0:
            return None, "not holding"
    why = copyable(trade, market, cfg)
    if why:
        return None, why
    leader_px = float(trade["price"])
    fee_rate = float(market.get("fee_rate") or 0.0)
    equity = equity if equity is not None else portfolio.last_equity

    if trade["side"] == "BUY":
        px = exec_price(token, "BUY", ts, leader_px)
        if px is None:
            return None, "no price"
        if px > cfg.max_price:
            return None, f"moved to {px:.2f}"
        budget = cfg.trade_fraction * equity
        if cfg.max_leader_multiple > 0:          # we cannot take more liquidity than the leader did
            budget = min(budget, cfg.max_leader_multiple * float(trade.get("usdcSize", 0)))
        room = cfg.max_market_fraction * equity - portfolio.market_cost(cid)
        budget = min(budget, room, portfolio.cash)
        if budget < 1.0:
            return None, "market cap reached" if room < 1.0 else "no cash"
        shares = budget / (px * (1 + fee_rate * (1 - px)))     # so cost incl. fee ~= budget
        fill = portfolio.buy(ts, wallet, token, cid, shares, px, fee_rate, leader_px, trade.get("title", ""),
                             trade.get("outcome", ""), market.get("end_ts"))
        return fill, "copied" if fill else "rejected"

    pos = portfolio.positions[token]
    frac = fraction_override if fraction_override is not None else unwound
    shares = pos.by_wallet[wallet] * frac
    if shares * leader_px < 1.0:
        return None, "dust"
    px = exec_price(token, "SELL", ts, leader_px)
    if px is None:
        return None, "no price"
    fill = portfolio.sell(ts, wallet, token, shares, px, fee_rate, leader_px)
    return fill, "copied" if fill else "rejected"


def clip_price(p: float) -> float:
    return min(TOKEN_MAX, max(TOKEN_MIN, p))


def fill_from_book(book: dict | None, side: str, notional: float | None = None, shares: float | None = None) -> tuple[float, float] | None:
    """Walk a live order book. BUY spends up to `notional`; SELL sells `shares`.
    Returns (shares, average price) or None if the book is empty."""
    levels = (book or {}).get("asks" if side == "BUY" else "bids") or []
    if not levels:
        return None
    got, spent = 0.0, 0.0
    for price, size in levels:
        if side == "BUY":
            take = min(size, (notional - spent) / price) if notional is not None else 0.0
        else:
            take = min(size, shares - got)
        if take <= 1e-9:
            break
        got += take
        spent += take * price
        if side == "BUY" and spent >= notional - 1e-9:
            break
        if side == "SELL" and got >= shares - 1e-9:
            break
    if got <= 0:
        return None
    return got, spent / got


def ts_day(ts: int) -> int:
    return ts - ts % 86400


def fmt_usd(x: float) -> str:
    return f"${x:,.0f}" if abs(x) >= 100 else f"${x:,.2f}"
