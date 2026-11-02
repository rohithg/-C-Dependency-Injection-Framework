"""Read Polymarket's public Gamma API. No key, no wallet, no orders."""
from __future__ import annotations

import json
from urllib.parse import urlparse

import requests

GAMMA = "https://gamma-api.polymarket.com"


class MarketClient:
    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout
        self._s = requests.Session()
        self._s.headers["User-Agent"] = "basis-desk/0.1"

    def board(self, limit: int = 8) -> list[dict]:
        events = self._get("/events", {
            "active": "true", "closed": "false", "limit": 20,
            "order": "volume24hr", "ascending": "false",
        }) or []
        picked = []
        for event in events:
            markets = [normalize(m, event) for m in event.get("markets") or []]
            markets = [m for m in markets if m["outcomes"] and not m["closed"]]
            if not markets:
                continue
            markets.sort(key=lambda m: -m["volume_24h"])
            picked.append(markets[0])
            if len(picked) >= limit:
                break
        return picked

    def lookup(self, query: str) -> list[dict]:
        query = (query or "").strip()
        if not query:
            return []
        slug = slug_from_query(query)
        if slug and slug == query.strip().strip("/").split("/")[-1] and " " not in query:
            found = self._by_slug(slug)
            if found:
                return found
        return self.search(query)

    def search(self, query: str, limit: int = 8) -> list[dict]:
        data = self._get("/public-search", {"q": query}) or {}
        out = []
        for event in data.get("events") or []:
            for raw in event.get("markets") or []:
                market = normalize(raw, event)
                if market["outcomes"]:
                    out.append(market)
                if len(out) >= limit:
                    return out
        return out

    def _by_slug(self, slug: str) -> list[dict]:
        markets = self._get("/markets", {"slug": slug}) or []
        if markets:
            return [normalize(markets[0])]
        events = self._get("/events", {"slug": slug}) or []
        if not events:
            return []
        event = events[0]
        found = []
        for raw in event.get("markets") or []:
            market = normalize(raw, event)
            if market["outcomes"] and not market["closed"]:
                found.append(market)
        found.sort(key=lambda m: -m["volume_24h"])
        return found[:12]

    def _get(self, path: str, params: dict):
        response = self._s.get(GAMMA + path, params=params, timeout=self.timeout)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def slug_from_query(query: str) -> str | None:
    text = query.strip()
    if not text or " " in text:
        return None
    if "polymarket.com" in text:
        path = [p for p in urlparse(text).path.split("/") if p]
        if not path:
            return None
        return path[-1]
    if all(c.isalnum() or c == "-" for c in text):
        return text
    return None


def normalize(raw: dict, event: dict | None = None) -> dict:
    names = _as_list(raw.get("outcomes"))
    prices = _as_list(raw.get("outcomePrices"))
    outcomes = []
    for name, price in zip(names, prices):
        try:
            value = float(price)
        except (TypeError, ValueError):
            continue
        outcomes.append({"name": str(name), "price": value})
    slug = raw.get("slug") or ""
    return {
        "question": raw.get("question") or (event or {}).get("title") or slug,
        "slug": slug,
        "url": f"https://polymarket.com/event/{(event or {}).get('slug') or slug}" if slug else "",
        "description": (raw.get("description") or (event or {}).get("description") or "").strip(),
        "resolution_source": raw.get("resolutionSource") or (event or {}).get("resolutionSource") or "",
        "end": raw.get("endDate") or (event or {}).get("endDate"),
        "outcomes": outcomes,
        "volume": _num(raw.get("volume")),
        "volume_24h": _num(raw.get("volume24hr")),
        "liquidity": _num(raw.get("liquidity")),
        "spread": _maybe_num(raw.get("spread")),
        "closed": bool(raw.get("closed")),
        "accepting": bool(raw.get("acceptingOrders", True)) and not bool(raw.get("closed")),
    }


def _as_list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return list(value or [])


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _maybe_num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
