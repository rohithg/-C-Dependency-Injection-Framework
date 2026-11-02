"""Minimal broker interface + Alpaca paper-trading implementation.

Only the handful of REST calls the strategy needs are wrapped; no SDK so the
dependency footprint stays at `requests`. A `FakeBroker` is provided for
dry runs and tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Protocol

import pandas as pd
import requests


@dataclass
class Account:
    equity: float
    cash: float
    positions: dict[str, float]      # symbol -> market value (USD)

    def weights(self) -> dict[str, float]:
        return {s: v / self.equity for s, v in self.positions.items()} if self.equity else {}


@dataclass
class Order:
    symbol: str
    notional: float                  # signed: >0 buy, <0 sell
    liquidate: bool = False          # close the whole position regardless of notional


class Broker(Protocol):
    def account(self) -> Account: ...
    def market_is_open(self) -> bool: ...
    def latest_price(self, symbol: str) -> float | None: ...
    def submit(self, order: Order) -> dict: ...
    def cancel_open_orders(self) -> None: ...
    def equity_history(self) -> "pd.Series": ...


class AlpacaBroker:
    """Alpaca paper account. Needs APCA_API_KEY_ID / APCA_API_SECRET_KEY."""

    def __init__(self, key: str | None = None, secret: str | None = None,
                 base_url: str = "https://paper-api.alpaca.markets",
                 data_url: str = "https://data.alpaca.markets", timeout: float = 20.0):
        self.key = key or os.environ.get("APCA_API_KEY_ID")
        self.secret = secret or os.environ.get("APCA_API_SECRET_KEY")
        if not self.key or not self.secret:
            raise RuntimeError("set APCA_API_KEY_ID and APCA_API_SECRET_KEY for an Alpaca paper account")
        if "paper" not in base_url:
            raise RuntimeError("refusing to run against a non-paper Alpaca endpoint")
        self.base_url, self.data_url, self.timeout = base_url.rstrip("/"), data_url.rstrip("/"), timeout
        self._s = requests.Session()
        self._s.headers.update({"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret})

    def _get(self, url: str, **params):
        r = self._s.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def account(self) -> Account:
        acct = self._get(f"{self.base_url}/v2/account")
        positions = {p["symbol"]: float(p["market_value"]) for p in self._get(f"{self.base_url}/v2/positions")}
        return Account(equity=float(acct["equity"]), cash=float(acct["cash"]), positions=positions)

    def market_is_open(self) -> bool:
        return bool(self._get(f"{self.base_url}/v2/clock")["is_open"])

    def latest_price(self, symbol: str) -> float | None:
        try:
            data = self._get(f"{self.data_url}/v2/stocks/{symbol}/trades/latest", feed="iex")
            return float(data["trade"]["p"])
        except Exception:
            return None

    def today_bar(self, symbol: str) -> dict | None:
        """Today's (partial) daily OHLCV candle, for the Kronos forecaster."""
        try:
            import datetime as dt
            start = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
            data = self._get(f"{self.data_url}/v2/stocks/{symbol}/bars", timeframe="1Day", start=start, feed="iex", limit=1)
            bar = (data.get("bars") or [None])[-1]
            if not bar:
                return None
            return {"open": float(bar["o"]), "high": float(bar["h"]), "low": float(bar["l"]),
                    "close": float(bar["c"]), "volume": float(bar["v"])}
        except Exception:
            return None

    def submit(self, order: Order) -> dict:
        if order.liquidate:
            r = self._s.delete(f"{self.base_url}/v2/positions/{order.symbol}", timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        payload = {
            "symbol": order.symbol,
            "notional": f"{abs(order.notional):.2f}",
            "side": "buy" if order.notional > 0 else "sell",
            "type": "market",
            "time_in_force": "day",
        }
        r = self._s.post(f"{self.base_url}/v2/orders", json=payload, timeout=self.timeout)
        if r.status_code == 422:
            # symbol not fractionable: fall back to whole shares
            price = self.latest_price(order.symbol)
            if not price:
                r.raise_for_status()
            qty = int(abs(order.notional) // price)
            if qty == 0:
                return {"status": "skipped", "reason": "order smaller than one share"}
            payload.pop("notional")
            payload["qty"] = str(qty)
            r = self._s.post(f"{self.base_url}/v2/orders", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def cancel_open_orders(self) -> None:
        self._s.delete(f"{self.base_url}/v2/orders", timeout=self.timeout).raise_for_status()

    def equity_history(self) -> pd.Series:
        """Daily account equity (end of day) for the past year, indexed by date."""
        data = self._get(f"{self.base_url}/v2/account/portfolio/history",
                         period="1A", timeframe="1D", intraday_reporting="market_hours")
        idx = pd.to_datetime(pd.Series(data.get("timestamp", [])), unit="s").dt.normalize()
        eq = pd.Series([float(v) if v is not None else float("nan") for v in data.get("equity", [])],
                       index=idx, name="equity").dropna()
        return eq[eq > 0]


@dataclass
class FakeBroker:
    """In-memory broker for tests and --dry-run. Fills instantly at `prices`."""
    equity: float = 100_000.0
    positions: dict[str, float] = field(default_factory=dict)
    prices: dict[str, float] = field(default_factory=dict)
    is_open: bool = True
    submitted: list[Order] = field(default_factory=list)

    def account(self) -> Account:
        cash = self.equity - sum(self.positions.values())
        return Account(self.equity, cash, dict(self.positions))

    def market_is_open(self) -> bool:
        return self.is_open

    def latest_price(self, symbol: str) -> float | None:
        return self.prices.get(symbol)

    def today_bar(self, symbol: str) -> dict | None:
        return None

    def submit(self, order: Order) -> dict:
        self.submitted.append(order)
        if order.liquidate:
            self.positions.pop(order.symbol, None)
        else:
            self.positions[order.symbol] = self.positions.get(order.symbol, 0.0) + order.notional
            if abs(self.positions[order.symbol]) < 0.01:
                del self.positions[order.symbol]
        return {"status": "filled", "symbol": order.symbol}

    def cancel_open_orders(self) -> None:
        pass

    def equity_history(self) -> pd.Series:
        idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=5)
        return pd.Series(self.equity, index=idx, name="equity")
