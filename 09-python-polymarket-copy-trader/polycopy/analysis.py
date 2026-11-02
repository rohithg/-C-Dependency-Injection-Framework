"""Describe how a wallet actually trades: realised profit, win rate,
consistency, typical position size and favourite markets.

These numbers are *descriptive* (what the leader did), not what copying them
would have earned; that is `selection.score_wallets`. They are shown next to
each followed wallet so the daily report reads like a trader profile rather
than a bare score.

Limitation: only CLOB trades and resolutions are visible here. Splits, merges
and early redemptions are separate activity types that this project does not
copy, so a market maker who buys both sides and merges them back into USDC
shows up as a large loss. Treat the profile as "how they trade", not as an
audited P&L.
"""
from __future__ import annotations

from collections import defaultdict
import datetime as dt
import statistics


def analyze_wallet(trades: list[dict], markets: dict[str, dict]) -> dict:
    """`trades` are the wallet's TRADE activity rows (any order); `markets`
    maps condition_id -> market dict (missing ids are treated as unresolved).

    Per market: PnL = sell proceeds - buy cost + payout of what is still held
    if the market resolved. A market counts as *decided* once it resolved or
    the wallet fully exited; win rate is wins / decided markets.
    """
    if not trades:
        return {"trades": 0}
    by_market: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "proceeds": 0.0, "net": defaultdict(float),
                                                      "title": "", "slug": "", "last_ts": 0})
    monthly: dict[str, float] = defaultdict(float)
    buy_sizes: list[float] = []
    for t in trades:
        cid = t["conditionId"]
        m = by_market[cid]
        usd = float(t.get("usdcSize", 0) or 0)
        size = float(t.get("size", 0) or 0)
        m["title"] = m["title"] or t.get("title", "")
        m["slug"] = m["slug"] or t.get("slug", "")
        m["last_ts"] = max(m["last_ts"], int(t["timestamp"]))
        if t["side"] == "BUY":
            m["cost"] += usd
            m["net"][t["asset"]] += size
            buy_sizes.append(usd)
        elif t["side"] == "SELL":
            m["proceeds"] += usd
            m["net"][t["asset"]] -= size
    wins = decided = 0
    realized = 0.0
    rows = []
    for cid, m in by_market.items():
        mk = markets.get(cid) or {}
        winners = {tok["token_id"] for tok in mk.get("tokens", []) if tok.get("winner")}
        resolved = bool(mk.get("resolved"))
        held = {tok: s for tok, s in m["net"].items() if s > 1e-6}      # negative = shares from splits/merges
        payout = sum(s for tok, s in held.items() if tok in winners) if resolved else 0.0
        pnl = m["proceeds"] - m["cost"] + payout
        is_decided = resolved or not held
        if is_decided:
            decided += 1
            wins += pnl > 0
            realized += pnl
            month = dt.datetime.fromtimestamp(m["last_ts"], dt.timezone.utc).strftime("%Y-%m")
            monthly[month] += pnl
        rows.append({"title": m["title"], "slug": m["slug"], "volume": m["cost"] + m["proceeds"], "cost": m["cost"],
                     "pnl": pnl if is_decided else None, "decided": is_decided, "won": (pnl > 0) if is_decided else None})
    rows.sort(key=lambda r: -r["volume"])
    months = sorted(monthly)
    first = min(int(t["timestamp"]) for t in trades)
    last = max(int(t["timestamp"]) for t in trades)
    return {
        "trades": len(trades),
        "markets": len(by_market),
        "decided_markets": decided,
        "win_rate": wins / decided if decided else None,
        "realized_pnl": realized,
        "avg_position_usd": statistics.mean(m["cost"] for m in by_market.values() if m["cost"] > 0) if any(m["cost"] > 0 for m in by_market.values()) else 0.0,
        "median_trade_usd": statistics.median(buy_sizes) if buy_sizes else 0.0,
        "profitable_months": sum(1 for mo in months if monthly[mo] > 0),
        "active_months": len(months),
        "consistency": (sum(1 for mo in months if monthly[mo] > 0) / len(months)) if months else None,
        "trades_per_day": len(trades) / max(1.0, (last - first) / 86400),
        "top_markets": rows[:5],
        "categories": _categories(rows),
        "first_ts": first, "last_ts": last,
    }


def wallet_profile(api, trades: list[dict], markets: dict[str, dict]) -> dict:
    """analyze_wallet() with the markets it needs fetched in bulk (cached)."""
    missing = {t["conditionId"] for t in trades} - set(markets)
    if missing:
        markets.update(api.markets_bulk(missing))
        for cid in missing:
            markets.setdefault(cid, None)
    return analyze_wallet(trades, markets)


def _categories(rows: list[dict]) -> dict[str, float]:
    """Share of volume by rough market type, read off the slug."""
    tot = sum(r["volume"] for r in rows) or 1.0
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[category(r["slug"])] += r["volume"] / tot
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


SPORTS = ("nba-", "nfl-", "mlb-", "nhl-", "ufc-", "epl-", "mls-", "atp-", "wta-", "cfb-", "cbb-", "ncaa", "fifwc-", "ucl-",
          "lal-", "sea-", "bun-", "fra-", "-vs-", "f1-", "pga-", "lol-", "cs2-", "dota")
CRYPTO = ("bitcoin", "btc", "ethereum", "eth-", "solana", "sol-", "xrp", "doge", "crypto")
POLITICS = ("election", "president", "senate", "governor", "congress", "nominee", "trump", "mayor", "parliament", "prime-minister",
            "knesset", "chancellor", "vote", "poll", "party", "coalition")
ECON = ("fed-", "interest-rate", "inflation", "cpi", "gdp", "recession", "tariff", "jobs", "unemployment")


def category(slug: str) -> str:
    s = (slug or "").lower()
    if any(k in s for k in ("updown", "up-or-down", "-5m-", "-15m-", "-1h-")):
        return "short-horizon"
    if any(k in s for k in CRYPTO):
        return "crypto"
    if any(k in s for k in SPORTS):
        return "sports"
    if any(k in s for k in ECON):
        return "economics"
    if any(k in s for k in POLITICS):
        return "politics"
    return "other"


def profile_line(stats: dict) -> str:
    """One compact line for tables: '78% win (142 decided), avg $1,520, 7/9 months up, mostly politics'."""
    if not stats or not stats.get("trades"):
        return "no history"
    parts = []
    if stats.get("win_rate") is not None:
        parts.append(f"{stats['win_rate']:.0%} win ({stats['decided_markets']} decided)")
    parts.append(f"avg ${stats.get('avg_position_usd', 0):,.0f}/market")
    if stats.get("active_months"):
        parts.append(f"{stats['profitable_months']}/{stats['active_months']} months up")
    cats = stats.get("categories") or {}
    if cats:
        top = next(iter(cats))
        parts.append(f"mostly {top} ({cats[top]:.0%})")
    return ", ".join(parts)
