"""Hard PASS / FAIL / UNKNOWN rules. UNKNOWN never counts as PASS.

`gather_facts` does the network work (DEX Screener pool, Solana RPC,
rugcheck) and returns plain numbers; `run_checks` is pure and testable.

One thing the simple "largest holder <= 10%" rule gets wrong: on every new
token the biggest holder is the AMM pool itself (it holds the token side of
the liquidity). Pool accounts are identified - by matching the pool's token
balance reported by DEX Screener and by the owner / known-account data in
rugcheck - and excluded before concentration is measured.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from feed import best_pair, pair_summary, liquidity_usd

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
POOL_TYPES = ("amm", "lp", "pool", "raydium", "meteora", "orca", "pump", "market", "vault", "locker")


@dataclass
class Check:
    name: str
    status: str
    value: str
    rule: str

    @property
    def ok(self) -> bool:
        return self.status == PASS


def gather_facts(token: str, pairs: list[dict], rpc, rugcheck, log=print) -> dict:
    """Everything the rules and Grok need, as numbers. None = could not determine."""
    pair = best_pair(pairs)
    facts: dict = {"token": token, "pair": pair_summary(pair) if pair else None, "n_pools": len(pairs),
                   "total_liquidity_usd": sum(liquidity_usd(p) for p in pairs)}
    if pair is None:
        return facts
    pool_token_balances = [float((p.get("liquidity") or {}).get("base") or 0.0) for p in pairs]
    pool_addresses = {p.get("pairAddress") for p in pairs if p.get("pairAddress")}

    mint = rpc.mint_info(token) if rpc else None
    supply = (mint or {}).get("supply") or (rpc.token_supply(token) if rpc else None)
    facts["mint_authority"] = (mint or {}).get("mint_authority") if mint else None
    facts["freeze_authority"] = (mint or {}).get("freeze_authority") if mint else None
    facts["mint_info_known"] = mint is not None

    rc = rugcheck.report(token) if rugcheck else None
    facts["rugcheck"] = rc
    if not facts["mint_info_known"] and rc:                   # RPC down: rugcheck saw the mint account too
        facts["mint_authority"], facts["freeze_authority"] = rc["mint_authority"], rc["freeze_authority"]
        facts["mint_info_known"] = True
    known = (rc or {}).get("known_accounts") or {}
    owner_of = {h["address"]: h.get("owner") for h in (rc or {}).get("top_holders") or []}

    holders = rpc.largest_accounts(token) if rpc else None
    source = "rpc"
    if holders is None and rc and rc["top_holders"]:
        holders = [{"address": h["address"], "amount": h["amount"], "owner": h.get("owner")} for h in rc["top_holders"]]
        source = "rugcheck"
    facts["holders_source"] = source if holders is not None else None
    facts["supply"] = supply or (sum(h["amount"] for h in holders) / (sum(h["pct"] for h in rc["top_holders"]) / 100.0)
                                 if holders is not None and rc and rc["top_holders"] and sum(h["pct"] for h in rc["top_holders"]) > 0 else None)

    people: list[float] = []
    pools: list[float] = []
    if holders is not None:
        for h in holders:
            owner = h.get("owner") or owner_of.get(h["address"])
            is_pool = (h["address"] in pool_addresses or owner in pool_addresses
                       or any(k in str(known.get(h["address"]) or known.get(owner) or "").lower() for k in POOL_TYPES)
                       or any(b > 0 and abs(h["amount"] - b) / b < 0.02 for b in pool_token_balances))
            (pools if is_pool else people).append(h["amount"])
    people.sort(reverse=True)
    sup = facts["supply"] or 0.0
    facts["largest_holder_share"] = people[0] / sup if people and sup else (0.0 if holders is not None and sup and not people else None)
    facts["top10_share"] = sum(people[:10]) / sup if sup and holders is not None else None
    facts["pool_share"] = sum(pools) / sup if sup and holders is not None else None
    facts["lp_locked_pct"] = (rc or {}).get("lp_locked_pct")
    facts["creator_share"] = ((rc or {}).get("creator_balance") or 0.0) / sup if rc and sup else None
    facts["danger_risks"] = [r["name"] for r in (rc or {}).get("risks") or [] if (r.get("level") or "").lower() == "danger"]
    facts["warn_risks"] = [r["name"] for r in (rc or {}).get("risks") or [] if (r.get("level") or "").lower() == "warn"]
    return facts


def run_checks(facts: dict, cfg: dict) -> list[Check]:
    out: list[Check] = []
    pair = facts.get("pair")
    if not pair:
        return [Check("pool", FAIL, "none", "token has no DEX pool")]

    liq = pair["liquidity_usd"]
    out.append(Check("liquidity", PASS if liq >= cfg["min_liquidity_usd"] else FAIL, f"${liq:,.0f}", f">= ${cfg['min_liquidity_usd']:,.0f}"))

    age = pair.get("pool_age_minutes")
    if age is None:
        out.append(Check("pool age", UNKNOWN, "unknown", f">= {cfg['min_pool_age_minutes']} min"))
    else:
        ok = cfg["min_pool_age_minutes"] <= age <= cfg["max_pool_age_hours"] * 60
        out.append(Check("pool age", PASS if ok else FAIL, f"{age:.0f} min", f"{cfg['min_pool_age_minutes']} min - {cfg['max_pool_age_hours']} h"))

    out.append(_share("largest holder (ex-pool)", facts.get("largest_holder_share"), cfg["max_single_holder"]))
    out.append(_share("top-10 holders (ex-pool)", facts.get("top10_share"), cfg["max_top10_share"]))

    if cfg.get("require_mint_disabled", True):
        out.append(_authority("mint authority", facts))
    if cfg.get("require_freeze_disabled", True):
        out.append(_authority("freeze authority", facts))

    if cfg.get("require_lp_locked", True):
        lp = facts.get("lp_locked_pct")
        if lp is None:
            out.append(Check("LP locked/burned", UNKNOWN, "unknown", f">= {cfg['min_lp_locked_pct']}% (UNKNOWN = FAIL)"))
        else:
            out.append(Check("LP locked/burned", PASS if lp >= cfg["min_lp_locked_pct"] else FAIL, f"{lp:.0f}%", f">= {cfg['min_lp_locked_pct']}%"))

    if cfg.get("fail_on_rugcheck_danger", True):
        rc = facts.get("rugcheck")
        if rc is None:
            out.append(Check("rug signals", UNKNOWN, "no report", "rugcheck.xyz danger flags"))
        else:
            danger = facts.get("danger_risks") or []
            rugged = rc.get("rugged")
            status = FAIL if (danger or rugged) else PASS
            out.append(Check("rug signals", status, "rugged" if rugged else (", ".join(danger) or "none"), "no danger-level flags"))
    return out


def _share(name: str, share: float | None, limit: float) -> Check:
    if share is None:
        return Check(name, UNKNOWN, "unknown", f"<= {limit:.0%}")
    return Check(name, PASS if share <= limit else FAIL, f"{share:.1%}", f"<= {limit:.0%}")


def _authority(name: str, facts: dict) -> Check:
    if not facts.get("mint_info_known"):
        return Check(name, UNKNOWN, "unknown", "disabled (null)")
    value = facts.get(name.replace(" ", "_"))
    return Check(name, PASS if value is None else FAIL, "disabled" if value is None else f"enabled ({str(value)[:8]}...)", "disabled (null)")


def all_pass(checks: list[Check]) -> bool:
    return bool(checks) and all(c.ok for c in checks)


def checks_to_dicts(checks: list[Check]) -> list[dict]:
    return [asdict(c) for c in checks]
