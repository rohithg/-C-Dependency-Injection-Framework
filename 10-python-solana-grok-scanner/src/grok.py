"""Ask Grok (xAI, OpenAI-compatible chat API) for a 0-10 risk read on a token
that already passed every hard rule.

The reply is parsed as JSON and used as *data*: a number and a list of
strings. Nothing in it is executed or followed. If the key is missing, the
call fails, or the reply is not valid JSON with a risk number, the result
is UNKNOWN and the token is skipped.
"""
from __future__ import annotations

import json
import re

import requests

XAI_URL = "https://api.x.ai/v1/chat/completions"

SYSTEM = ("You are a risk analyst for newly launched Solana tokens. You receive on-chain and DEX numbers and must reply "
          "with ONLY a JSON object: {\"risk\": <integer 0-10, 10 = almost certain loss>, \"reasons\": [<short strings citing "
          "the numbers>], \"missing_data\": [<what you would want to know>]}. Assume most new tokens go to zero; a low risk "
          "number needs evidence in the numbers. No prose outside the JSON.")


def ask_grok(facts: dict, checks: list[dict], api_key: str | None, model: str = "grok-4.7", timeout: float = 60.0,
             transport=None) -> dict:
    """Returns {"risk": int|None, "reasons": [...], "missing_data": [...], "status": "ok"|"no_key"|"error"|"unparseable",
    "raw": str, "usage": {...}}. `transport(payload, headers) -> dict` can replace the HTTP call (tests, demo)."""
    if not api_key:
        return {"risk": None, "reasons": [], "missing_data": [], "status": "no_key", "raw": "", "usage": {}}
    payload = {
        "model": model, "temperature": 0.2,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": json.dumps({"facts": _for_model(facts), "hard_checks": checks}, default=str)}],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        if transport is not None:
            body = transport(payload, headers)
        else:
            r = requests.post(XAI_URL, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            body = r.json()
        raw = body["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        return {"risk": None, "reasons": [f"api error: {exc}"], "missing_data": [], "status": "error", "raw": "", "usage": {}}
    parsed = parse_reply(raw)
    parsed["usage"] = body.get("usage") or {}
    return parsed


def parse_reply(raw: str) -> dict:
    """Extract {"risk", "reasons", "missing_data"} from the model text; tolerate code fences and stray prose."""
    text = raw.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        text = m.group(0)
    try:
        obj = json.loads(text)
        risk = obj.get("risk")
        risk = int(round(float(risk))) if risk is not None else None
        if risk is None or not 0 <= risk <= 10:
            raise ValueError("risk out of range")
        reasons = [str(x)[:200] for x in (obj.get("reasons") or [])][:8]
        missing = [str(x)[:200] for x in (obj.get("missing_data") or [])][:8]
        return {"risk": risk, "reasons": reasons, "missing_data": missing, "status": "ok", "raw": raw[:2000]}
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
        return {"risk": None, "reasons": [], "missing_data": [], "status": "unparseable", "raw": raw[:2000]}


def _for_model(facts: dict) -> dict:
    """Only the numbers; no URLs, descriptions, or free text that could carry instructions."""
    pair = facts.get("pair") or {}
    return {
        "liquidity_usd": pair.get("liquidity_usd"), "pool_age_minutes": pair.get("pool_age_minutes"),
        "fdv_usd": pair.get("fdv_usd"), "volume_h1_usd": pair.get("volume_h1_usd"), "volume_h24_usd": pair.get("volume_h24_usd"),
        "price_change_h1_pct": pair.get("price_change_h1_pct"), "buys_h1": pair.get("buys_h1"), "sells_h1": pair.get("sells_h1"),
        "n_pools": facts.get("n_pools"), "dex": pair.get("dex"),
        "largest_holder_share": facts.get("largest_holder_share"), "top10_share": facts.get("top10_share"),
        "pool_share_of_supply": facts.get("pool_share"), "creator_share": facts.get("creator_share"),
        "mint_authority_enabled": facts.get("mint_authority") is not None if facts.get("mint_info_known") else None,
        "freeze_authority_enabled": facts.get("freeze_authority") is not None if facts.get("mint_info_known") else None,
        "lp_locked_pct": facts.get("lp_locked_pct"), "total_holders": (facts.get("rugcheck") or {}).get("total_holders"),
        "rugcheck_warn_flags": facts.get("warn_risks"), "rugcheck_score_normalised": (facts.get("rugcheck") or {}).get("score"),
    }
