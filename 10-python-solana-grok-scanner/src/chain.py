"""On-chain facts about a token: supply, largest holders, mint/freeze
authority (Solana JSON-RPC), and LP lock / rug signals (rugcheck.xyz).

The public RPC endpoint is shared and rate-limits `getTokenLargestAccounts`
aggressively (429 within seconds in testing). We back off and, if it still
fails, fall back to the holder list in rugcheck's report so the check can
return a number instead of UNKNOWN. Anything we could not determine is
returned as None and the rules treat None as FAIL.
"""
from __future__ import annotations

import time

import requests

PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
RUGCHECK = "https://api.rugcheck.xyz/v1"


class SolanaRPC:
    def __init__(self, url: str = PUBLIC_RPC, timeout: float = 20.0, log=print, cooldown: float = 600.0):
        self.url, self.timeout, self.log = url, timeout, log
        self._s = requests.Session()
        self.requests_made = 0
        self.cooldown = cooldown
        self._blocked_until: dict[str, float] = {}      # method -> time; set after a 429 give-up

    def call(self, method: str, *params, retries: int = 3):
        if time.time() < self._blocked_until.get(method, 0):
            return None                                 # still rate-limited; callers fall back to rugcheck
        delay = 1.0
        for attempt in range(retries):
            try:
                r = self._s.post(self.url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": list(params)}, timeout=self.timeout)
                self.requests_made += 1
                if r.status_code in (429, 403) or r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                body = r.json()
                if "error" in body:
                    if body["error"].get("code") == 429:
                        raise requests.HTTPError("RPC 429")
                    return None
                return body.get("result")
            except (requests.RequestException, ValueError) as exc:
                if attempt == retries - 1:
                    if "429" in str(exc):
                        self._blocked_until[method] = time.time() + self.cooldown
                        self.log(f"rpc {method} rate-limited; not retrying it for {self.cooldown / 60:.0f} min (using rugcheck data instead)")
                    else:
                        self.log(f"rpc {method} gave up: {exc}")
                    return None
                time.sleep(delay)
                delay *= 2

    def token_supply(self, mint: str) -> float | None:
        res = self.call("getTokenSupply", mint)
        try:
            return float(res["value"]["uiAmount"])
        except (TypeError, KeyError):
            return None

    def largest_accounts(self, mint: str) -> list[dict] | None:
        """[{address, uiAmount}] for the 20 largest token accounts, or None."""
        res = self.call("getTokenLargestAccounts", mint)
        try:
            return [{"address": v["address"], "amount": float(v["uiAmount"] or 0.0)} for v in res["value"]]
        except (TypeError, KeyError):
            return None

    def mint_info(self, mint: str) -> dict | None:
        """{mint_authority, freeze_authority, decimals, supply} from the parsed mint account."""
        res = self.call("getAccountInfo", mint, {"encoding": "jsonParsed"})
        try:
            info = res["value"]["data"]["parsed"]["info"]
            return {"mint_authority": info.get("mintAuthority"), "freeze_authority": info.get("freezeAuthority"),
                    "decimals": info.get("decimals"), "supply": float(info.get("supply") or 0) / 10 ** int(info.get("decimals") or 0)}
        except (TypeError, KeyError, ValueError):
            return None


class RugCheck:
    """rugcheck.xyz public report: LP lock %, creator, top holders (with the
    owning program, so pools can be told apart from people), named risks."""

    def __init__(self, timeout: float = 20.0, log=print):
        self._s = requests.Session()
        self.timeout, self.log = timeout, log
        self.requests_made = 0

    def report(self, mint: str) -> dict | None:
        try:
            r = self._s.get(f"{RUGCHECK}/tokens/{mint}/report", timeout=self.timeout)
            self.requests_made += 1
            if r.status_code != 200:
                return None
            d = r.json()
        except (requests.RequestException, ValueError) as exc:
            self.log(f"rugcheck failed for {mint[:8]}: {exc}")
            return None
        markets = d.get("markets") or []
        lp_pcts = [float((m.get("lp") or {}).get("lpLockedPct") or 0.0) for m in markets if (m.get("lp") or {}).get("lpLockedUSD")]
        return {
            "creator": d.get("creator"), "creator_balance": float(d.get("creatorBalance") or 0.0),
            "mint_authority": d.get("mintAuthority"), "freeze_authority": d.get("freezeAuthority"),
            "top_holders": [{"address": h.get("address"), "owner": h.get("owner"), "amount": float(h.get("uiAmount") or 0.0),
                             "pct": float(h.get("pct") or 0.0), "insider": bool(h.get("insider"))} for h in d.get("topHolders") or []],
            "known_accounts": {k: (v or {}).get("type") for k, v in (d.get("knownAccounts") or {}).items()},
            "lp_locked_pct": max(lp_pcts) if lp_pcts else None,          # of the funded pool(s)
            "risks": [{"name": r.get("name"), "level": r.get("level"), "description": r.get("description")} for r in d.get("risks") or []],
            "score": d.get("score_normalised"), "rugged": bool(d.get("rugged")), "total_holders": d.get("totalHolders"),
            "launchpad": d.get("launchpad") or d.get("deployPlatform"),
        }
