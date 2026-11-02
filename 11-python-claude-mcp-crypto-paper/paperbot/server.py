"""MCP server exposing the paper account to Claude Code (mcp 2.x, MCPServer).

    python -m paperbot.server            # stdio transport, what .mcp.json launches

Read tools:  get_candles(symbol, timeframe, limit), get_account()
Write tools: buy(symbol, usd_amount, reason), sell_all(reason), hold(reason)
Every write goes through the risk gate inside the ledger; refusals come back
as normal results with `status: "refused"` so the model can read why.

Environment:
    PAPERBOT_STATE_DIR   where ledger.json / decisions.jsonl live (default ./state)
    PAPERBOT_FIXTURE     optional JSON file with {"candles": {...}, "prices": {...}}
                         used instead of Kraken (tests and --demo); never set in normal use
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server import MCPServer

from . import kraken
from .ledger import Ledger, SYMBOLS

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.environ.get("PAPERBOT_STATE_DIR") or ROOT / "state")

server = MCPServer(
    "paper-crypto",
    instructions=("Paper-money crypto account for a learning experiment. $100 of pretend money, 0.4% fee per fill, "
                  "one position at a time, max 25% of equity per entry, max 6 fills per day, no leverage, no shorting. "
                  "There is no real exchange behind these tools. Use get_candles and get_account to look, then call exactly "
                  "one of buy / sell_all / hold with a one-line reason."),
)


class _Data:
    """Kraken by default; a fixture file when PAPERBOT_FIXTURE is set."""

    def __init__(self):
        fx = os.environ.get("PAPERBOT_FIXTURE")
        self.fixture = json.loads(Path(fx).read_text()) if fx else None

    def candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        if self.fixture:
            rows = self.fixture["candles"][symbol][timeframe]
            return rows[-max(1, min(int(limit), kraken.MAX_CANDLES)):]
        return kraken.candles(symbol, timeframe, limit)

    def prices(self) -> dict[str, float]:
        if self.fixture:
            return {k: float(v) for k, v in self.fixture["prices"].items()}
        return kraken.last_prices(list(SYMBOLS))


data = _Data()


def ledger() -> Ledger:
    return Ledger(STATE_DIR)


@server.tool()
def get_candles(symbol: str, timeframe: str = "1h", limit: int = 100) -> dict:
    """Completed OHLCV candles from Kraken's public feed, oldest first. symbol: BTC | ETH | SOL;
    timeframe: 1h | 4h | 1d; limit: up to 720. The still-forming newest candle is excluded."""
    symbol = symbol.upper()
    try:
        rows = data.candles(symbol, timeframe, limit)
    except (ValueError, kraken.KrakenError) as exc:
        return {"error": str(exc)}
    return {"symbol": symbol, "timeframe": timeframe, "count": len(rows), "candles": rows}


@server.tool()
def get_account() -> dict:
    """Paper account: cash, equity, open position (if any), fees paid, fills today, and the risk rules in force."""
    try:
        prices = data.prices()
    except kraken.KrakenError as exc:
        return {"error": f"price feed unavailable: {exc}"}
    return ledger().account(prices)


@server.tool()
def buy(symbol: str, usd_amount: float, reason: str) -> dict:
    """Paper-buy `usd_amount` of symbol at the latest Kraken price (0.4% fee). Refused if a position is already open,
    if usd_amount exceeds 25% of equity or available cash, if 6 fills were already made today, or if equity is below
    50% of the $100 start. `reason` is one line and is logged."""
    try:
        prices = data.prices()
    except kraken.KrakenError as exc:
        return {"error": f"price feed unavailable: {exc}"}
    symbol = symbol.upper()
    return ledger().buy(symbol, float(usd_amount), str(reason)[:200], prices.get(symbol))


@server.tool()
def sell_all(reason: str) -> dict:
    """Paper-sell the whole open position at the latest Kraken price (0.4% fee). Refused if there is no position or
    6 fills were already made today. `reason` is one line and is logged."""
    try:
        prices = data.prices()
    except kraken.KrakenError as exc:
        return {"error": f"price feed unavailable: {exc}"}
    return ledger().sell_all(str(reason)[:200], prices)


@server.tool()
def hold(reason: str) -> dict:
    """Do nothing this round and log why (one line). Call this when neither buying nor selling is justified."""
    try:
        prices = data.prices()
    except kraken.KrakenError:
        prices = {}
    return ledger().hold(str(reason)[:200], prices)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
