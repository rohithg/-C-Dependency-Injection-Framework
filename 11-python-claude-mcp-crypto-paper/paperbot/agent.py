"""Offline rule agent: drives the same MCP tools Claude Code would, over stdio.

Used when Claude Code is not installed or not logged in, and in tests. It
follows prompts/trading_prompt.md literally (paperbot/strategy.py), so a
Claude round and a rule round can be compared.
"""
from __future__ import annotations

import json
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from . import strategy

SYMBOLS = ("BTC", "ETH", "SOL")


def _payload(result) -> dict:
    sc = getattr(result, "structuredContent", None)
    if sc:
        return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
    for c in result.content:
        if getattr(c, "type", "") == "text":
            try:
                return json.loads(c.text)
            except json.JSONDecodeError:
                return {"text": c.text}
    return {}


async def run_round(state_dir: str, log=print) -> dict:
    env = {**os.environ, "PAPERBOT_STATE_DIR": state_dir}
    params = StdioServerParameters(command=sys.executable, args=["-m", "paperbot.server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            log(f"tools: {', '.join(tools)}")
            acct = _payload(await s.call_tool("get_account", {}))
            if "error" in acct:
                return {"action": "error", "detail": acct["error"]}
            feats = {}
            for sym in SYMBOLS:
                c = _payload(await s.call_tool("get_candles", {"symbol": sym, "timeframe": "4h", "limit": 60}))
                feats[sym] = strategy.features([r["close"] for r in c.get("candles", [])]) if "candles" in c else None
                if feats[sym]:
                    log(strategy.describe(sym, feats[sym]))
            pos = acct.get("position")
            if pos:
                why = strategy.exit_reason(feats.get(pos["symbol"]), pos["entry_price"], pos["last_price"])
                if why:
                    res = _payload(await s.call_tool("sell_all", {"reason": f"{pos['symbol']}: {why}"}))
                else:
                    f = feats.get(pos["symbol"])
                    res = _payload(await s.call_tool("hold", {"reason": f"holding {pos['symbol']} {pos['unrealized_pct']:+.1%}; "
                                                              + (strategy.describe(pos['symbol'], f) if f else "no candles")}))
            else:
                pick = strategy.entry_candidate(feats)
                if pick:
                    sym, f = pick
                    usd = int(acct["equity_usd"] * strategy.ENTRY_FRACTION * 100) / 100
                    res = _payload(await s.call_tool("buy", {"symbol": sym, "usd_amount": usd, "reason": strategy.describe(sym, f)}))
                    if res.get("status") == "refused":
                        res = _payload(await s.call_tool("hold", {"reason": f"buy refused: {res.get('refused_because')}"}))
                else:
                    bits = "; ".join(strategy.describe(s_, f) for s_, f in feats.items() if f) or "no candles"
                    res = _payload(await s.call_tool("hold", {"reason": f"no entry qualifies ({bits})"}))
            acct_after = _payload(await s.call_tool("get_account", {}))
            return {"decision": res, "account": acct_after}
