"""Which wallets are even worth considering, and their trade history.

The leaderboard is a *starting* universe, not the follow list: it ranks by
headline PnL, which is dominated by high-frequency bots and whales whose edge
(speed, size, in-game sports) cannot be copied an hour later. The actual
follow list is chosen by `selection.score_wallets`, which measures what
copying each wallet under our rules would have earned.
"""
from __future__ import annotations

import time

from .api import PolymarketAPI
from .copy import CopyConfig

BOARDS = (("month", None), ("week", None), ("all", None), ("month", "politics"), ("month", "sports"))


def build_universe(api: PolymarketAPI, per_board: int = 50, boards=BOARDS) -> list[dict]:
    """Union of several leaderboards. Each wallet: {wallet, name, pnl, volume, boards}."""
    found: dict[str, dict] = {}
    for period, category in boards:
        for r in api.leaderboard(period, per_board, category=category):
            w = r["user_id"].lower()
            tag = f"{period}" + (f"/{category}" if category else "")
            if w in found:
                found[w]["boards"].append(tag)
                found[w]["pnl"] = max(found[w]["pnl"], float(r.get("pnl") or 0))
            else:
                found[w] = {"wallet": w, "name": r.get("user_name") or w[:10], "pnl": float(r.get("pnl") or 0),
                            "volume": float(r.get("volume") or 0), "boards": [tag]}
    return sorted(found.values(), key=lambda d: -d["pnl"])


def screen_universe(api: PolymarketAPI, wallets: list[dict], cfg: CopyConfig, log=print,
                    max_idle_days: int = 30) -> tuple[list[dict], dict[str, str]]:
    """Drop wallets whose recent trade rate marks them as uncopyable bots, and
    dormant wallets (big historical PnL, nothing to copy)."""
    kept, dropped = [], {}
    now = int(time.time())
    for w in wallets:
        rate, n, last_ts = api.trade_rate(w["wallet"])
        w["trades_per_day"], w["last_trade_ts"] = round(rate, 1), last_ts
        if n == 0:
            dropped[w["wallet"]] = "no trades"
        elif now - last_ts > max_idle_days * 86400:
            dropped[w["wallet"]] = f"idle {(now - last_ts) // 86400}d"
        elif rate > cfg.max_trades_per_day:
            dropped[w["wallet"]] = f"{rate:.0f} trades/day"
        else:
            kept.append(w)
    log(f"universe: {len(wallets)} wallets, {len(kept)} kept after trade-rate screen")
    return kept, dropped


def fetch_history(api: PolymarketAPI, wallet: str, since: int, until: int | None = None,
                  max_trades: int | None = 15_000) -> list[dict]:
    """Ascending TRADE activity for one wallet (cached per past week)."""
    rows = api.activity_since(wallet, since, until or int(time.time()), max_trades=max_trades)
    seen, out = set(), []
    for r in rows:                      # de-duplicate across window edges
        key = (r.get("transactionHash"), r["asset"], r["timestamp"], r["size"])
        if key in seen:
            continue
        seen.add(key)
        r["proxyWallet"] = r["proxyWallet"].lower()
        out.append(r)
    return out
