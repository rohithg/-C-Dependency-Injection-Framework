"""Pick who to follow.

Copyability replays each candidate's trades over the trailing `lookback_days`
through the exact copy rules (latency, fees, slippage, size caps) and ranks
wallets by what that copy portfolio returned. A wallet whose edge disappears
an hour later scores low no matter how rich it is.

Whale ranking ignores that replay and sorts by dollars spent buying. That is
size, not skill: a wallet that lost money trading huge is still a whale.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .api import PolymarketAPI
from .backtest import PriceSource, simulate, summarize, prefetch
from .copy import CopyConfig, Portfolio, LeaderBook


@dataclass
class WalletScore:
    wallet: str
    name: str
    copy_return: float          # return of a fixed bankroll copying only this wallet
    max_dd: float
    copied_buys: int
    seen: int
    skipped: dict[str, int]
    notional: float = 0.0       # trailing BUY volume, set by rank_whales

    @property
    def score(self) -> float:
        # return per unit of drawdown, mildly; drawdown floor avoids dividing by ~0
        return self.copy_return / max(0.02, -self.max_dd)


def score_wallets(histories: dict[str, list[dict]], names: dict[str, str], markets: dict[str, dict],
                  prices: PriceSource, cfg: CopyConfig, start_ts: int, end_ts: int,
                  api: PolymarketAPI | None = None, log=print) -> list[WalletScore]:
    out = []
    if api is not None:
        prefetch([t for h in histories.values() for t in h], markets, prices, cfg, api, start_ts, end_ts)
    for w, trades in histories.items():
        window = [t for t in trades if start_ts <= t["timestamp"] < end_ts]
        if len(window) < cfg.min_copyable_trades:
            continue
        res = simulate(window, markets, prices, cfg, start_ts, end_ts, Portfolio(10_000.0), LeaderBook(), api=api)
        if res.copied_buys < cfg.min_copyable_trades:
            continue
        s = summarize(res.equity)
        out.append(WalletScore(w, names.get(w, w[:10]), s.get("Total", 0.0), s.get("MaxDD", 0.0), res.copied_buys, res.seen, res.skipped))
    out.sort(key=lambda x: -x.score)
    return out


def choose(scores: list[WalletScore], cfg: CopyConfig) -> list[WalletScore]:
    """Top-N with a positive copy return; fewer than N if not enough qualify."""
    return [s for s in scores if s.copy_return > 0][: cfg.follow_n]


def rank_whales(histories: dict[str, list[dict]], names: dict[str, str], start_ts: int, end_ts: int,
                cfg: CopyConfig) -> list[WalletScore]:
    """Biggest traders in the window, by dollars they spent buying.

    This is size, not skill: a wallet that lost money trading huge is still a
    whale. Bot and dormancy screening happens before this is called.
    """
    ranked = []
    for w, trades in histories.items():
        buys = [t for t in trades if start_ts <= int(t["timestamp"]) < end_ts and t.get("side") == "BUY"]
        if len(buys) < cfg.min_copyable_trades:
            continue
        notional = sum(float(t.get("usdcSize") or 0) for t in buys)
        ranked.append(WalletScore(w, names.get(w, w[:10]), 0.0, 0.0, len(buys), len(buys), {}, notional))
    ranked.sort(key=lambda s: -s.notional)
    return ranked[: cfg.follow_n]


def scores_table(scores: list[WalletScore], n: int = 20) -> pd.DataFrame:
    rows = [{"wallet": s.name, "copy return": s.copy_return, "max dd": s.max_dd, "copied buys": s.copied_buys,
             "trades seen": s.seen, "score": s.score} for s in scores[:n]]
    return pd.DataFrame(rows)
