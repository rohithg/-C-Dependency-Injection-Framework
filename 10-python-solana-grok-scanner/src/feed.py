"""New-token feed and pool data from the DEX Screener public API (no key).

Endpoints used (all documented at docs.dexscreener.com/api/reference):
    GET /token-profiles/latest/v1          latest token profiles, 60 req/min
    GET /token-pairs/v1/{chain}/{token}    all pools of one token
    GET /tokens/v1/{chain}/{a,b,c}         pools for up to 30 tokens (prices for open positions)
"""
from __future__ import annotations

import time

import requests

BASE = "https://api.dexscreener.com"
CHAIN = "solana"


class DexScreener:
    def __init__(self, timeout: float = 20.0, pause: float = 1.1, log=print):
        self._s = requests.Session()
        self._s.headers["User-Agent"] = "grok-trader-paper/0.1"
        self.timeout, self.pause, self.log = timeout, pause, log
        self.requests_made = 0

    def _get(self, path: str, retries: int = 4):
        delay = 2.0
        for attempt in range(retries):
            time.sleep(self.pause)                      # stay well under 60 req/min
            try:
                r = self._s.get(BASE + path, timeout=self.timeout)
                self.requests_made += 1
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(f"{r.status_code}")
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError) as exc:
                if attempt == retries - 1:
                    raise
                self.log(f"dexscreener retry {path} ({exc}) in {delay:.0f}s")
                time.sleep(delay)
                delay *= 2

    def latest_solana_tokens(self) -> list[dict]:
        """Newest token profiles on Solana: [{tokenAddress, url, description, ...}]."""
        rows = self._get("/token-profiles/latest/v1") or []
        return [r for r in rows if r.get("chainId") == CHAIN and r.get("tokenAddress")]

    def pairs(self, token: str) -> list[dict]:
        return self._get(f"/token-pairs/v1/{CHAIN}/{token}") or []

    def prices(self, tokens: list[str]) -> dict[str, dict]:
        """{token: best pool} for up to 30 tokens per request."""
        out: dict[str, dict] = {}
        for i in range(0, len(tokens), 30):
            chunk = tokens[i:i + 30]
            for p in self._get(f"/tokens/v1/{CHAIN}/{','.join(chunk)}") or []:
                tok = (p.get("baseToken") or {}).get("address")
                if tok and (tok not in out or liquidity_usd(p) > liquidity_usd(out[tok])):
                    out[tok] = p
        return out


def best_pair(pairs: list[dict]) -> dict | None:
    """The pool with the most USD liquidity, i.e. the one we would trade in."""
    return max(pairs, key=liquidity_usd) if pairs else None


def liquidity_usd(pair: dict | None) -> float:
    return float(((pair or {}).get("liquidity") or {}).get("usd") or 0.0)


def pool_age_minutes(pair: dict, now: float | None = None) -> float | None:
    created = pair.get("pairCreatedAt")
    if not created:
        return None
    return ((now or time.time()) - created / 1000.0) / 60.0


def pair_summary(pair: dict) -> dict:
    """The numbers we keep, log, and show Grok."""
    return {
        "dex": pair.get("dexId"), "pair": pair.get("pairAddress"),
        "symbol": (pair.get("baseToken") or {}).get("symbol"), "name": (pair.get("baseToken") or {}).get("name"),
        "price_usd": float(pair.get("priceUsd") or 0.0), "liquidity_usd": liquidity_usd(pair),
        "fdv_usd": float(pair.get("fdv") or 0.0), "market_cap_usd": float(pair.get("marketCap") or 0.0),
        "volume_h1_usd": float((pair.get("volume") or {}).get("h1") or 0.0),
        "volume_h24_usd": float((pair.get("volume") or {}).get("h24") or 0.0),
        "price_change_h1_pct": (pair.get("priceChange") or {}).get("h1"),
        "buys_h1": ((pair.get("txns") or {}).get("h1") or {}).get("buys"),
        "sells_h1": ((pair.get("txns") or {}).get("h1") or {}).get("sells"),
        "pool_age_minutes": pool_age_minutes(pair),
        "url": pair.get("url"),
    }
