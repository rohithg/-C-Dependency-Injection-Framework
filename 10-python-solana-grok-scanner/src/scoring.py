"""Combine the hard checks and Grok's read into one decision.

    score = 10 - grok_risk  if every hard check PASSED and Grok answered
    score = None            otherwise (nothing to trade on)

Decision: BUY when score is a number and grok_risk <= grok_max_risk;
otherwise SKIP with the first failing reason. With `grok_required: false`
an all-PASS token with no Grok answer is bought on the hard rules alone
(score 5) - off by default, because the guide's rule is that UNKNOWN never
counts as PASS.
"""
from __future__ import annotations

from checks import Check, PASS


def decide(checks: list[Check], grok: dict | None, cfg: dict) -> dict:
    failed = [c for c in checks if c.status != PASS]
    if failed:
        c = failed[0]
        return {"action": "SKIP", "score": None, "reason": f"{c.name} {c.status}: {c.value} (rule {c.rule})",
                "failed": [f"{x.name}={x.status}" for x in failed]}
    risk = (grok or {}).get("risk")
    if risk is None:
        status = (grok or {}).get("status", "not asked")
        if cfg.get("grok_required", True):
            return {"action": "SKIP", "score": None, "reason": f"all hard checks passed; Grok read unavailable ({status})", "failed": ["grok=UNKNOWN"]}
        return {"action": "BUY", "score": 5, "reason": f"all hard checks passed; Grok not required ({status})", "failed": []}
    if risk > cfg["grok_max_risk"]:
        return {"action": "SKIP", "score": 10 - risk, "reason": f"Grok risk {risk}/10 > {cfg['grok_max_risk']}: " + "; ".join(grok.get("reasons") or [])[:300],
                "failed": ["grok=FAIL"]}
    return {"action": "BUY", "score": 10 - risk, "reason": f"all hard checks passed; Grok risk {risk}/10: " + "; ".join(grok.get("reasons") or [])[:300],
            "failed": []}
