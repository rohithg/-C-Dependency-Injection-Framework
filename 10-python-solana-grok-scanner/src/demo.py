"""Three fictional tokens and fake data sources so the whole pipeline can be
exercised offline (`python src/main.py --demo`). Nothing here touches the
network.

    GOODCAT  passes every hard rule; the fake Grok returns risk 3  -> paper BUY
    RUGPULL  mint authority still enabled, LP unlocked               -> SKIP on hard rules
    WHALE    one wallet holds 35% of supply                          -> SKIP on concentration
"""
from __future__ import annotations

import time

NOW = time.time()
MS = 1000


def _pair(addr: str, symbol: str, liq: float, age_min: float, price: float, base_tokens: float) -> dict:
    return {"chainId": "solana", "dexId": "pumpswap", "pairAddress": f"POOL{symbol}", "url": f"https://dexscreener.com/solana/{addr}",
            "baseToken": {"address": addr, "symbol": symbol, "name": symbol.title()},
            "priceUsd": str(price), "liquidity": {"usd": liq, "base": base_tokens, "quote": liq / 2 / 180},
            "fdv": price * 1_000_000_000, "marketCap": price * 1_000_000_000,
            "volume": {"h1": liq * 0.8, "h24": liq * 6}, "priceChange": {"h1": 12.5}, "txns": {"h1": {"buys": 240, "sells": 180}},
            "pairCreatedAt": int((NOW - age_min * 60) * MS)}


TOKENS = {
    "DEMOgoodcat111111111111111111111111111111": _pair("DEMOgoodcat111111111111111111111111111111", "GOODCAT", 62_000, 45, 0.000052, 180_000_000),
    "DEMOrugpull222222222222222222222222222222": _pair("DEMOrugpull222222222222222222222222222222", "RUGPULL", 31_000, 25, 0.000011, 120_000_000),
    "DEMOwhale3333333333333333333333333333333": _pair("DEMOwhale3333333333333333333333333333333", "WHALE", 48_000, 90, 0.00030, 90_000_000),
}
SUPPLY = 1_000_000_000.0


class FakeDex:
    requests_made = 0

    def __init__(self, price_moves: dict[str, float] | None = None):
        self.price_moves = price_moves or {}

    def latest_solana_tokens(self):
        return [{"chainId": "solana", "tokenAddress": a, "url": p["url"], "description": f"demo token {p['baseToken']['symbol']}"} for a, p in TOKENS.items()]

    def pairs(self, token):
        return [TOKENS[token]] if token in TOKENS else []

    def prices(self, tokens):
        out = {}
        for t in tokens:
            if t in TOKENS:
                p = dict(TOKENS[t])
                p["priceUsd"] = str(float(p["priceUsd"]) * self.price_moves.get(t, 1.0))
                out[t] = p
        return out


class FakeRPC:
    requests_made = 0

    def mint_info(self, mint):
        if "rugpull" in mint:
            return {"mint_authority": "DEMOdeployerXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", "freeze_authority": None, "decimals": 6, "supply": SUPPLY}
        return {"mint_authority": None, "freeze_authority": None, "decimals": 6, "supply": SUPPLY}

    def token_supply(self, mint):
        return SUPPLY

    def largest_accounts(self, mint):
        pool = TOKENS[mint]["liquidity"]["base"]
        if "whale" in mint:
            people = [350_000_000, 40_000_000, 30_000_000] + [8_000_000] * 10
        else:
            people = [45_000_000, 30_000_000, 22_000_000, 15_000_000] + [9_000_000] * 12
        return [{"address": f"ACC{i}", "amount": a} for i, a in enumerate([pool] + people)]


class FakeRugCheck:
    requests_made = 0

    def report(self, mint):
        locked = 0.0 if "rugpull" in mint else 100.0
        return {"creator": "DEMOcreator", "creator_balance": 12_000_000 if "goodcat" in mint else 0.0,
                "mint_authority": None, "freeze_authority": None, "top_holders": [], "known_accounts": {},
                "lp_locked_pct": locked, "risks": [] if locked else [{"name": "Low amount of LP Providers", "level": "warn", "description": ""}],
                "score": 1 if locked else 3000, "rugged": False, "total_holders": 2_400, "launchpad": "pump.fun"}


def fake_grok_transport(payload, headers):
    """Pretends to be api.x.ai: low risk for the clean token, high for anything else."""
    import json
    user = json.loads(payload["messages"][1]["content"])
    facts = user["facts"]
    risk = 3 if (facts.get("lp_locked_pct") or 0) >= 90 and (facts.get("largest_holder_share") or 1) < 0.1 else 8
    content = json.dumps({"risk": risk, "reasons": [f"liquidity ${facts['liquidity_usd']:,.0f}", f"top-10 share {facts['top10_share']:.0%}",
                                                     f"LP locked {facts['lp_locked_pct']:.0f}%"], "missing_data": ["deployer history"]})
    return {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 400, "completion_tokens": 60}}
