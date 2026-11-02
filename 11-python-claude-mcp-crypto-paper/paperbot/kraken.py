"""Kraken public market data. No key, no account, read-only.

    GET https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60   (max 720 candles)
    GET https://api.kraken.com/0/public/Ticker?pair=XBTUSD              (last trade price)

The newest OHLC candle is still forming, so it is dropped.
"""
from __future__ import annotations

import time

import requests

BASE = "https://api.kraken.com/0/public"
PAIRS = {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"}
# Kraken answers with legacy keys for some pairs (XXBTZUSD for XBTUSD, XETHZUSD for ETHUSD)
RESULT_KEYS = {"BTC": ("XXBTZUSD", "XBTUSD"), "ETH": ("XETHZUSD", "ETHUSD"), "SOL": ("SOLUSD",)}
TIMEFRAMES = {"1h": 60, "4h": 240, "1d": 1440}
MAX_CANDLES = 720                      # Kraken returns at most 720 candles per call


class KrakenError(RuntimeError):
    pass


def _get(path: str, params: dict, timeout: float = 20.0, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            if data.get("error"):
                raise KrakenError("; ".join(data["error"]))
            return data["result"]
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries - 1:
                raise KrakenError(str(exc)) from exc
            time.sleep(1.5 * (attempt + 1))
    raise KrakenError("unreachable")


def candles(symbol: str, timeframe: str = "1h", limit: int = 200) -> list[dict]:
    """Completed candles, oldest first: {time, open, high, low, close, volume}."""
    if symbol not in PAIRS:
        raise ValueError(f"unknown symbol {symbol!r}; choose from {sorted(PAIRS)}")
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unknown timeframe {timeframe!r}; choose from {sorted(TIMEFRAMES)}")
    limit = max(1, min(int(limit), MAX_CANDLES))
    result = _get("OHLC", {"pair": PAIRS[symbol], "interval": TIMEFRAMES[timeframe]})
    rows = next(v for k, v in result.items() if k != "last")
    rows = rows[:-1]                   # the newest candle is still forming
    out = [{"time": int(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
            "close": float(r[4]), "volume": float(r[6])} for r in rows]
    return out[-limit:]


def last_prices(symbols: list[str] | None = None) -> dict[str, float]:
    """Last trade price per symbol from the public ticker."""
    symbols = symbols or sorted(PAIRS)
    result = _get("Ticker", {"pair": ",".join(PAIRS[s] for s in symbols)})
    out = {}
    for s in symbols:
        key = next((k for k in RESULT_KEYS[s] if k in result), None)
        if key is None:
            raise KrakenError(f"no ticker for {s} in {sorted(result)}")
        out[s] = float(result[key]["c"][0])
    return out
