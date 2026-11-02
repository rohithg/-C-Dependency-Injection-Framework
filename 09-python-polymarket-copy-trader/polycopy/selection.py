"""Pick who to follow.

Copyability replays each candidate's trades over the trailing `lookback_days`
through the exact copy rules (latency, fees, slippage, size caps) and ranks
wallets by what that copy portfolio returned. A wallet whose edge disappears
an hour later scores low no matter how rich it is.

Whale ranking sorts by dollars spent buying, unless `min_win_rate` is set.
Then a wallet is eligible only when its own already-settled markets won at
least that often and made money. Size alone does not qualify.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .analysis import record_as_of
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
    win_rate: float | None = None
    realized: float = 0.0       # leader's own settled PnL when win_rate is set
    decided: int = 0

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
                cfg: CopyConfig, markets: dict[str, dict] | None = None,
                api: PolymarketAPI | None = None) -> list[WalletScore]:
    """Who to copy in whale mode.

    With `min_win_rate` off, this is the biggest buyers in the window. With it
    on, a wallet qualifies only when markets that had already closed by
    `end_ts` won at least that often, there are at least `min_decided` of
    them, and the settled profit is positive. Those wallets are then ordered
    by that profit. A huge buyer who lost does not qualify. Bot and dormancy
    screening happens before this is called.
    """
    markets = markets if markets is not None else {}
    candidates = []
    for w, trades in histories.items():
        window = [t for t in trades if start_ts <= int(t["timestamp"]) < end_ts]
        buys = [t for t in window if t.get("side") == "BUY"]
        if len(buys) < cfg.min_copyable_trades:
            continue
        notional = sum(float(t.get("usdcSize") or 0) for t in buys)
        candidates.append((w, window, len(buys), notional))
    if cfg.min_win_rate <= 0:
        ranked = [WalletScore(w, names.get(w, w[:10]), 0.0, 0.0, n, n, {}, notional) for w, _, n, notional in candidates]
        ranked.sort(key=lambda s: -s.notional)
        return ranked[: cfg.follow_n]
    if api is not None:
        need = [t["conditionId"] for _, window, _, _ in candidates for t in window]
        missing = [c for c in dict.fromkeys(need) if c not in markets]
        if missing:
            markets.update(api.markets_bulk(missing) or {})
            for cid in missing:
                markets.setdefault(cid, None)
    ranked = []
    for w, window, n_buys, notional in candidates:
        stats = record_as_of(window, markets, end_ts)
        wr = stats.get("win_rate")
        decided = int(stats.get("decided_markets") or 0)
        pnl = float(stats.get("realized_pnl") or 0.0)
        if wr is None or wr < cfg.min_win_rate or decided < cfg.min_decided or pnl <= 0:
            continue
        ranked.append(WalletScore(w, names.get(w, w[:10]), 0.0, 0.0, n_buys, n_buys, {}, notional, wr, pnl, decided))
    ranked.sort(key=lambda s: (-s.realized, -(s.win_rate or 0.0), -s.notional))
    return ranked[: cfg.follow_n]


def scores_table(scores: list[WalletScore], n: int = 20) -> pd.DataFrame:
    rows = [{"wallet": s.name, "copy return": s.copy_return, "max dd": s.max_dd, "copied buys": s.copied_buys,
             "trades seen": s.seen, "score": s.score} for s in scores[:n]]
    return pd.DataFrame(rows)
