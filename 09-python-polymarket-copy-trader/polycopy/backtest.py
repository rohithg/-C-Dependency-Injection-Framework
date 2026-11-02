"""Replay leader trades through the copy rules with hourly price history.

Execution model: a leader trade at time t is seen by our hourly job and
filled at the first recorded price at or after t + latency, worse by
`slippage`. Positions are marked daily at 00:00 UTC on the last recorded
price and paid out at resolution. Markets are fetched lazily and cached.
"""
from __future__ import annotations

import bisect
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import datetime as dt
import math

import pandas as pd

from .api import PolymarketAPI
from .copy import CopyConfig, Portfolio, LeaderBook, copy_trade, precheck, clip_price, ts_day, Fill

TRADING_DAYS = 365          # prediction markets trade every day
STALE_AFTER = 6 * 3600      # no price within this many seconds of target -> no fill
PREFETCH_WORKERS = 8        # parallel price-history downloads


class PriceSource:
    """Hourly price history per token with point-in-time lookups."""

    def __init__(self, api: PolymarketAPI, markets: dict[str, dict]):
        self.api = api
        self.markets = markets
        self._ts: dict[str, list[int]] = {}
        self._px: dict[str, list[float]] = {}

    def load(self, token: str, condition_id: str, from_ts: int | None = None) -> None:
        """Fetch history from `from_ts` (first time we need a price, e.g. the
        first leader trade in that market) through the market's end."""
        if token in self._ts:
            return
        m = self.markets.get(condition_id) or {}
        closed = bool(m.get("closed") or m.get("resolved"))
        end = (m.get("closed_ts") or m.get("end_ts") or 0) + 86400 if closed else None
        pts = self.api.price_history(token, 60, closed=closed,
                                     start_ts=None if from_ts is None else from_ts - 86400, end_ts=end)
        pts = sorted(pts)
        self._ts[token] = [p[0] for p in pts]
        self._px[token] = [p[1] for p in pts]

    def at_or_after(self, token: str, ts: int, within: int = STALE_AFTER) -> float | None:
        t, p = self._ts.get(token, []), self._px.get(token, [])
        i = bisect.bisect_left(t, ts)
        if i < len(t) and t[i] - ts <= within:
            return p[i]
        if i > 0 and ts - t[i - 1] <= within:        # nothing after yet: use the latest known
            return p[i - 1]
        return None

    def at_or_before(self, token: str, ts: int) -> float | None:
        t, p = self._ts.get(token, []), self._px.get(token, [])
        i = bisect.bisect_right(t, ts)
        return p[i - 1] if i > 0 else None

    def last_ts(self, token: str) -> int | None:
        t = self._ts.get(token, [])
        return t[-1] if t else None


def prefetch(trades: list[dict], markets: dict[str, dict], prices: PriceSource, cfg: CopyConfig,
             api: PolymarketAPI, start_ts: int, end_ts: int, workers: int = PREFETCH_WORKERS) -> None:
    """Load every market and price history the replay of `trades` can need:
    markets in Gamma batches, price histories on a small thread pool.
    Serially this is the slow part of a backtest (tens of thousands of markets)."""
    first: dict[str, tuple[str, int]] = {}
    for tr in trades:
        if not (start_ts <= tr["timestamp"] < end_ts) or tr["side"] != "BUY" or precheck(tr, cfg):
            continue
        first.setdefault(tr["asset"], (tr["conditionId"], tr["timestamp"]))
    cids = {cid for cid, _ in first.values() if cid not in markets}
    if cids:
        markets.update(api.markets_bulk(cids))
        for cid in cids:
            markets.setdefault(cid, None)
    todo = [(tok, cid, t0) for tok, (cid, t0) in first.items() if markets.get(cid) and tok not in prices._ts]
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda a: prices.load(*a), todo))


def make_exec_price(prices: PriceSource, cfg: CopyConfig):
    """Pessimistic fill: the worse of the leader's own price and the hourly
    snapshot after our latency, plus slippage. Hourly snapshots of thin books
    can print absurd levels for a moment (a 0.80 token at 0.016 for an hour);
    assuming we filled size there would make the backtest a lottery."""
    def exec_price(token: str, side: str, ts: int, leader_price: float) -> float | None:
        snap = prices.at_or_after(token, ts + cfg.latency_min * 60)
        if snap is None:
            return None
        if side == "BUY":
            return clip_price(max(snap, leader_price) + cfg.slippage)
        return clip_price(min(snap, leader_price) - cfg.slippage)
    return exec_price


def resolution_payout(market: dict, token: str) -> float | None:
    if not market.get("resolved"):
        return None
    for t in market["tokens"]:
        if t["token_id"] == token:
            return 1.0 if t["winner"] else 0.0
    return None


@dataclass
class SimResult:
    equity: pd.Series                      # daily, UTC midnight
    fills: list[Fill]
    skipped: dict[str, int] = field(default_factory=dict)
    copied_buys: int = 0
    seen: int = 0


def simulate(trades: list[dict], markets: dict[str, dict], prices: PriceSource, cfg: CopyConfig,
             start_ts: int, end_ts: int, portfolio: Portfolio | None = None, leaders: LeaderBook | None = None,
             follow: set[str] | None = None, api: PolymarketAPI | None = None) -> SimResult:
    """Replay `trades` (ascending by timestamp, may include many wallets) from
    start_ts to end_ts. Only trades of wallets in `follow` (or all, if None)
    open new positions; every wallet's trades update LeaderBook and can close
    positions attributed to that wallet."""
    portfolio = portfolio or Portfolio()
    leaders = leaders or LeaderBook()
    if api is not None:
        prefetch(trades, markets, prices, cfg, api, start_ts, end_ts)
    exec_price = make_exec_price(prices, cfg)
    skipped: dict[str, int] = {}
    fills: list[Fill] = []
    copied_buys = seen = 0

    def price_of(token: str, ts: int):
        return prices.at_or_before(token, ts)

    def mark_and_resolve(ts: int) -> float:
        for token, pos in list(portfolio.positions.items()):
            m = markets.get(pos.condition_id) or {}
            payout = resolution_payout(m, token)
            if payout is not None:
                last = prices.last_ts(token) or 0
                if ts >= max(m.get("end_ts") or 0, last):
                    f = portfolio.resolve(token, payout, ts)
                    if f:
                        fills.append(f)
        return portfolio.value(lambda tok: price_of(tok, ts))

    day = ts_day(start_ts)
    equity_rows: list[tuple[int, float]] = []
    i = bisect.bisect_left([t["timestamp"] for t in trades], start_ts)
    while day < end_ts:
        next_day = day + 86400
        while i < len(trades) and trades[i]["timestamp"] < next_day:
            tr = trades[i]; i += 1
            if tr["timestamp"] < start_ts:
                continue
            seen += 1
            w = tr["proxyWallet"]
            if follow is not None and w not in follow and tr["side"] == "BUY":
                leaders.apply(tr)
                continue
            holding = tr["asset"] in portfolio.positions
            if tr["side"] == "SELL" and not holding:
                leaders.apply(tr)
                continue
            why = precheck(tr, cfg)
            if why:
                leaders.apply(tr)
                key = _reason_key(why)
                skipped[key] = skipped.get(key, 0) + 1
                continue
            # only now is a market lookup (1-2 cached requests) worth it
            m = markets.get(tr["conditionId"])
            if m is None and api is not None and tr["conditionId"] not in markets:
                m = markets[tr["conditionId"]] = api.market(tr["conditionId"])
            if m is not None:
                prices.load(tr["asset"], tr["conditionId"], from_ts=tr["timestamp"])
            fill, why = copy_trade(tr, m, portfolio, leaders, cfg, exec_price)
            if fill:
                fills.append(fill)
                copied_buys += fill.side == "BUY"
            else:
                key = _reason_key(why)
                skipped[key] = skipped.get(key, 0) + 1
        eq = mark_and_resolve(next_day)
        equity_rows.append((next_day, eq))
        day = next_day
    idx = pd.to_datetime([r[0] for r in equity_rows], unit="s")
    return SimResult(pd.Series([r[1] for r in equity_rows], index=idx), fills, skipped, copied_buys, seen)


def _reason_key(why: str) -> str:
    """Collapse parameterised reasons ('ends in 3h', 'price 0.99 out of range') into buckets."""
    if why.startswith("ends in"):
        return "ends too soon"
    if why.startswith("price "):
        return "price out of range"
    if why.startswith("moved to"):
        return "moved past max price"
    return why


# --------------------------------------------------------------------------- metrics

def summarize(equity: pd.Series) -> dict[str, float]:
    eq = equity.dropna()
    if len(eq) < 2:
        return {}
    r = eq.pct_change().dropna()
    days = (eq.index[-1] - eq.index[0]).days or 1
    total = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (1 + total) ** (365 / days) - 1 if total > -1 else -1.0
    vol = r.std() * math.sqrt(TRADING_DAYS)
    dd = (eq / eq.cummax() - 1).min()
    return {"Total": total, "CAGR": cagr, "Vol": vol, "Sharpe": (r.mean() / r.std() * math.sqrt(TRADING_DAYS)) if r.std() > 0 else float("nan"),
            "MaxDD": dd, "Days": days}


def format_summary(name: str, s: dict[str, float]) -> str:
    if not s:
        return f"{name:<34s} (no data)"
    return (f"{name:<34s} total {s['Total']:+7.1%}  CAGR {s['CAGR']:+7.1%}  Vol {s['Vol']:6.1%}  "
            f"Sharpe {s['Sharpe']:5.2f}  MaxDD {s['MaxDD']:7.1%}")


def month_starts(start: dt.date, end: dt.date) -> list[int]:
    out, d = [], dt.date(start.year, start.month, 1)
    while d <= end:
        out.append(int(dt.datetime(d.year, d.month, 1, tzinfo=dt.timezone.utc).timestamp()))
        d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out
