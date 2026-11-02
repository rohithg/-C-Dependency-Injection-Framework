"""Read-only access to Polymarket's public APIs (no key needed).

    data-api.polymarket.com   leaderboard, per-wallet trade activity, positions
    clob.polymarket.com       order books, midpoints, price history, resolution
    gamma-api.polymarket.com  market metadata (fee schedule, end date, slug)

Everything that is immutable once observed (past activity, closed markets,
price history of closed markets) is cached on disk so a backtest can be
re-run offline and the hourly paper trader stays well inside rate limits.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Iterable

import requests

DATA = "https://data-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"
ACTIVITY_PAGE = 500
ACTIVITY_MAX_OFFSET = 5000          # documented hard cap of the /activity endpoint
PRICE_WINDOW = 14 * 86400           # /prices-history rejects startTs..endTs spans longer than this
MARKET_BATCH = 50                   # condition_ids per Gamma /markets call


class PolymarketAPI:
    def __init__(self, cache_dir: Path = CACHE_DIR, timeout: float = 30.0, pause: float = 0.05, log=None):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.pause = pause                  # politeness delay between requests
        self.requests_made = 0
        self.log = log or (lambda *_: None)
        self._s = requests.Session()
        self._s.headers.update({"User-Agent": "polycopy-paper/0.1 (+github actions)"})

    # ------------------------------------------------------------------ http
    def _get(self, url: str, params: dict | None = None, retries: int = 6) -> Any:
        delay = 1.0
        for attempt in range(retries):
            try:
                time.sleep(self.pause)
                r = self._s.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(f"{r.status_code} {r.text[:120]}", response=r)
                self.requests_made += 1
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
                if attempt == retries - 1:
                    raise
                self.log(f"retry {url} ({exc}) in {delay:.0f}s")
                time.sleep(delay)
                delay = min(delay * 2, 30)

    def _cached(self, key: str, fetch, ttl_hours: float | None = None) -> Any:
        """Disk cache; ttl_hours=None means immutable."""
        path = self._cache_path(key)
        if path.exists():
            if ttl_hours is None or time.time() - path.stat().st_mtime < ttl_hours * 3600:
                return json.loads(path.read_text())
        data = fetch()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return data

    # ------------------------------------------------------------ leaderboard
    def leaderboard(self, time_period: str = "month", limit: int = 100, sort_by: str = "PNL",
                    category: str | None = None) -> list[dict]:
        """Top wallets by realised PnL (or VOLUME). time_period: day|week|month|all."""
        out: list[dict] = []
        cursor = None
        while len(out) < limit:
            params = {"time_period": time_period, "limit": min(50, limit - len(out)), "sort_by": sort_by}
            if category:
                params["category"] = category
            if cursor:
                params["cursor"] = cursor
            data = self._get(f"{DATA}/v2/leaderboard", params) or {}
            rows = data.get("data", [])
            out.extend(rows)
            cursor = data.get("pagination", {}).get("next_cursor")
            if not rows or not data.get("pagination", {}).get("has_more") or not cursor:
                break
        return out[:limit]

    # --------------------------------------------------------------- activity
    def activity(self, wallet: str, start: int, end: int, max_trades: int | None = None) -> list[dict]:
        """All TRADE activity of `wallet` with start <= timestamp < end.

        The endpoint allows at most offset 5000, so windows that hold more are
        split recursively. Windows that end in the past are cached forever.
        Returns rows newest first, as the API does.
        """
        now = int(time.time())
        immutable = end < now - 3600

        def fetch():
            return self._activity_window(wallet, start, end, max_trades)

        key = f"activity:{wallet}:{start}:{end}:{max_trades}"
        return self._cached(key, fetch) if immutable else fetch()

    def _activity_window(self, wallet: str, start: int, end: int, max_trades: int | None) -> list[dict]:
        rows: list[dict] = []
        offset = 0
        while True:
            page = self._get(f"{DATA}/activity", {"user": wallet, "type": "TRADE", "limit": ACTIVITY_PAGE,
                                                   "offset": offset, "start": start, "end": end}) or []
            rows.extend(page)
            if len(page) < ACTIVITY_PAGE:
                return rows
            if max_trades is not None and len(rows) >= max_trades:
                return rows
            offset += ACTIVITY_PAGE
            if offset >= ACTIVITY_MAX_OFFSET:
                if end - start <= 60:
                    return rows            # >5000 trades in one minute: give up on the remainder
                mid = (start + end) // 2
                self.log(f"splitting activity window for {wallet[:8]} ({start}-{end})")
                newer = self._activity_window(wallet, mid, end, max_trades)
                if max_trades is not None and len(newer) >= max_trades:
                    return newer
                return newer + self._activity_window(wallet, start, mid, None if max_trades is None else max_trades - len(newer))

    def activity_since(self, wallet: str, since: int, until: int | None = None, step_days: int = 7,
                       max_trades: int | None = None) -> list[dict]:
        """Walk from `until` (default now) back to `since` in weekly windows,
        newest first, stopping once `max_trades` have been collected (so a cap
        truncates the *oldest* history). Windows are aligned to whole weeks so
        the cache is reusable across runs."""
        until = until or int(time.time())
        rows: list[dict] = []
        step = step_days * 86400
        t2 = until
        while t2 > since:
            t = max(since, (t2 - 1) // step * step) if t2 % step == 0 else max(since, t2 // step * step)
            if t == t2:
                t = max(since, t2 - step)
            rows.extend(self.activity(wallet, t, t2, None if max_trades is None else max_trades - len(rows)))
            if max_trades is not None and len(rows) >= max_trades:
                self.log(f"{wallet[:8]}: history capped at {max_trades} trades (back to {t})")
                break
            t2 = t
        rows.sort(key=lambda r: r["timestamp"])
        return rows

    def trade_rate(self, wallet: str) -> tuple[float, int, int]:
        """(trades per day, sample size, last trade timestamp) estimated from the
        wallet's latest 500 trades. One request; used to drop high-frequency
        bots and dormant accounts before fetching history."""
        page = self._get(f"{DATA}/activity", {"user": wallet, "type": "TRADE", "limit": ACTIVITY_PAGE}) or []
        if len(page) < 2:
            return 0.0, len(page), (page[0]["timestamp"] if page else 0)
        span = max(page[0]["timestamp"] - page[-1]["timestamp"], 60)
        return len(page) * 86400 / span, len(page), page[0]["timestamp"]

    def position(self, wallet: str, condition_id: str) -> dict[str, float]:
        """Live {token_id: shares} the wallet currently holds in one market."""
        rows = self._get(f"{DATA}/positions", {"user": wallet, "market": condition_id, "sizeThreshold": 0}) or []
        return {r["asset"]: float(r["size"]) for r in rows}

    def portfolio_value(self, wallet: str) -> float | None:
        data = self._get(f"{DATA}/value", {"user": wallet}) or []
        return float(data[0]["value"]) if data else None

    # ---------------------------------------------------------------- markets
    def market(self, condition_id: str) -> dict | None:
        """Metadata + resolution of one market (see `markets_bulk`)."""
        return self.markets_bulk([condition_id]).get(condition_id)

    def markets_bulk(self, condition_ids: Iterable[str]) -> dict[str, dict]:
        """{condition_id: market} for many markets in as few requests as possible.

        Gamma answers up to ~100 `condition_ids` per call but only returns
        open markets unless `closed=true` is passed, so unresolved ids are
        tried both ways. Resolution is read from Gamma's final outcome prices
        (exactly "1"/"0" once resolved), which matched the CLOB `winner` flags
        on every market checked. Resolved markets are cached forever, open
        ones for an hour.
        """
        out: dict[str, dict] = {}
        missing: list[str] = []
        now = time.time()
        for cid in dict.fromkeys(condition_ids):
            path = self._cache_path(f"market:{cid}")
            if path.exists():
                cached = json.loads(path.read_text()) or {}
                if cached.get("resolved") or now - cached.get("fetched_at", 0) < 3600:
                    if not cached.get("missing"):
                        out[cid] = cached
                    continue
            missing.append(cid)
        for i in range(0, len(missing), MARKET_BATCH):
            batch = missing[i:i + MARKET_BATCH]
            found: dict[str, dict] = {}
            for extra in ({}, {"closed": "true"}):
                todo = [c for c in batch if c not in found]
                if not todo:
                    break
                rows = self._get(f"{GAMMA}/markets", [("condition_ids", c) for c in todo] + [("limit", len(todo)), *extra.items()]) or []
                for g in rows:
                    m = _market_from_gamma(g)
                    if m:
                        found[m["condition_id"]] = m
            for cid in batch:
                m = found.get(cid)
                path = self._cache_path(f"market:{cid}")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(m or {"condition_id": cid, "missing": True, "fetched_at": int(now)}))
                if m:
                    out[cid] = m
        return out

    def _cache_path(self, key: str) -> Path:
        h = hashlib.sha1(key.encode()).hexdigest()
        return self.cache_dir / h[:2] / (h + ".json")

    def price_history(self, token_id: str, fidelity_minutes: int = 60, closed: bool = False,
                      start_ts: int | None = None, end_ts: int | None = None) -> list[tuple[int, float]]:
        """(timestamp, price) points for a token.

        `interval=max` only works while a market is open; once it closes the
        CLOB answers that query with an empty list and the history has to be
        pulled with explicit startTs/endTs windows of at most 14 days. Windows
        are aligned to whole days so they cache well; windows entirely in the
        past are cached forever.
        """
        def fetch_max():
            data = self._get(f"{CLOB}/prices-history", {"market": token_id, "interval": "max", "fidelity": fidelity_minutes}) or {}
            return [(int(p["t"]), float(p["p"])) for p in data.get("history", [])]

        if not closed:
            pts = self._cached(f"prices:{token_id}:{fidelity_minutes}", fetch_max, ttl_hours=6)
            if pts or start_ts is None:
                return [tuple(p) for p in pts]
        if start_ts is None:
            return []
        now = int(time.time())
        end_ts = min(end_ts or now, now)
        t = start_ts // 86400 * 86400
        out: list[tuple[int, float]] = []
        while t < end_ts:
            t2 = min(t + PRICE_WINDOW, end_ts // 86400 * 86400 + 86400)

            def fetch(t=t, t2=t2):
                data = self._get(f"{CLOB}/prices-history", {"market": token_id, "startTs": t, "endTs": t2,
                                                             "fidelity": fidelity_minutes}) or {}
                return [(int(p["t"]), float(p["p"])) for p in data.get("history", [])]

            immutable = t2 < now - 3600
            pts = self._cached(f"prices:{token_id}:{fidelity_minutes}:{t}:{t2}", fetch, ttl_hours=None if immutable else 1)
            out.extend(tuple(p) for p in pts if t <= p[0] < t2)
            t = t2
        return out

    def book(self, token_id: str) -> dict | None:
        """Live order book: {'bids': [(price, size)...] best first, 'asks': [...] best first}."""
        data = self._get(f"{CLOB}/book", {"token_id": token_id})
        if not data or "bids" not in data:
            return None
        bids = sorted(((float(b["price"]), float(b["size"])) for b in data.get("bids", [])), reverse=True)
        asks = sorted(((float(a["price"]), float(a["size"])) for a in data.get("asks", [])))
        return {"bids": bids, "asks": asks}

    def midpoints(self, token_ids: Iterable[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for tid in token_ids:
            data = self._get(f"{CLOB}/midpoint", {"token_id": tid})
            if data and data.get("mid") is not None:
                out[tid] = float(data["mid"])
        return out


def _market_from_gamma(g: dict) -> dict | None:
    """Normalise a Gamma market row into the dict the rest of the code uses."""
    cid = g.get("conditionId")
    if not cid:
        return None
    try:
        token_ids = json.loads(g.get("clobTokenIds") or "[]")
        outcomes = json.loads(g.get("outcomes") or "[]")
        prices = [float(p) for p in json.loads(g.get("outcomePrices") or "[]")]
    except (ValueError, TypeError):
        return None
    closed = bool(g.get("closed"))
    tokens = []
    for i, tid in enumerate(token_ids):
        price = prices[i] if i < len(prices) else 0.0
        tokens.append({"token_id": tid, "outcome": outcomes[i] if i < len(outcomes) else str(i),
                       "winner": closed and price == 1.0, "price": price})
    fee_rate = 0.0
    if g.get("feesEnabled") and g.get("feeSchedule"):
        fee_rate = float(g["feeSchedule"].get("rate") or 0.0)
    end_iso = g.get("endDate")
    return {
        "condition_id": cid, "question": g.get("question"), "slug": g.get("slug"), "closed": closed,
        "accepting_orders": bool(g.get("acceptingOrders")), "end_date": end_iso, "end_ts": _iso_ts(end_iso),
        "closed_ts": _iso_ts(g.get("closedTime")), "fee_rate": fee_rate, "tokens": tokens,
        "resolved": closed and any(t["winner"] for t in tokens),
        "neg_risk": bool(g.get("negRisk")), "fetched_at": int(time.time()),
    }


def _iso_ts(iso: str | None) -> int | None:
    if not iso:
        return None
    iso = iso.strip().replace("Z", "+00:00")
    if " " in iso and "T" not in iso:          # Gamma closedTime: '2026-06-14 06:38:22+00'
        iso = iso.replace(" ", "T")
    if iso.endswith("+00"):
        iso += ":00"
    try:
        return int(dt.datetime.fromisoformat(iso).timestamp())
    except ValueError:
        return None
