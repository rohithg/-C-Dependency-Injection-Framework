"""One scan cycle: new tokens -> hard checks -> Grok -> score -> paper trade -> log.

`run_cycle` is the single entry point used by the CLI loop, the GitHub
Actions job and the offline demo; the data sources are passed in so the
demo can hand it fakes.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import time

from checks import gather_facts, run_checks, all_pass, checks_to_dicts
from feed import pair_summary, best_pair
from grok import ask_grok
from paper import PaperTrader
from scoring import decide

ROOT = Path(__file__).resolve().parent.parent
DATA, LOGS = ROOT / "data", ROOT / "logs"


def load_config(path: Path = ROOT / "config.json") -> dict:
    return json.loads(path.read_text())


class DecisionLog:
    """logs/decisions.jsonl: one line per token per decision (buy / skip / sell / error)."""

    def __init__(self, path: Path):
        self.path = path

    def write(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def tail(self, n: int = 50) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text().splitlines()[-n:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out


def run_cycle(cfg: dict, dex, rpc, rugcheck, api_key: str | None, *, data_dir: Path = DATA, log_dir: Path = LOGS,
              now: float | None = None, grok_transport=None, log=print, dry_run: bool = False) -> dict:
    now = now or time.time()
    stamp = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    seen_path = data_dir / "seen_tokens.json"
    seen: dict[str, float] = json.loads(seen_path.read_text()) if seen_path.exists() else {}
    trader = PaperTrader(data_dir / "paper_state.json", cfg, now)
    dlog = DecisionLog(log_dir / "decisions.jsonl")
    report = {"as_of": stamp, "scanned": [], "buys": [], "sells": [], "errors": 0, "counts": {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}}

    # ---- 1. manage what we hold: prices for every open position, exits -------------------
    prices: dict[str, dict] = {}
    if trader.positions:
        try:
            prices = dex.prices(list(trader.positions))
        except Exception as exc:
            log(f"price fetch failed: {exc}")
        for sell in trader.update(prices, now):
            rec = {"ts": stamp, "type": "sell", **sell}
            report["sells"].append(rec)
            if not dry_run:
                dlog.write(rec)
            log(f"SELL {sell['symbol']} {sell['pnl_pct']:+.0%} ${sell['pnl_usd']:+,.2f}: {sell['reason']}")

    # ---- 2. new tokens --------------------------------------------------------------------
    try:
        fresh = [t for t in dex.latest_solana_tokens() if t["tokenAddress"] not in seen and t["tokenAddress"] not in trader.positions]
    except Exception as exc:
        log(f"feed failed: {exc}")
        fresh = []
        report["errors"] += 1
    fresh = fresh[: cfg.get("max_tokens_per_cycle", 15)]
    for profile in fresh:
        token = profile["tokenAddress"]
        seen[token] = now
        rec = {"ts": stamp, "type": "decision", "token": token, "url": profile.get("url"), "description": (profile.get("description") or "")[:200]}
        try:
            pairs = dex.pairs(token)
            facts = gather_facts(token, pairs, rpc, rugcheck, log=log)
            checks = run_checks(facts, cfg)
            rec["symbol"] = (facts.get("pair") or {}).get("symbol")
            rec["facts"] = {k: v for k, v in facts.items() if k != "rugcheck"}
            rec["rugcheck_risks"] = (facts.get("rugcheck") or {}).get("risks")
            rec["checks"] = checks_to_dicts(checks)
            for c in checks:
                report["counts"][c.status] = report["counts"].get(c.status, 0) + 1
            grok = None
            if all_pass(checks):
                grok = ask_grok(facts, rec["checks"], api_key, model=cfg.get("grok_model", "grok-4.7"), transport=grok_transport)
                rec["grok"] = grok
            decision = decide(checks, grok, cfg)
            rec.update(decision)
            if decision["action"] == "BUY":
                ok, why = trader.can_buy(now, prices)
                if not ok:
                    rec["action"], rec["reason"] = "SKIP", f"passed, but {why}"
                else:
                    fill = trader.buy(token, facts["pair"], now, prices)
                    if fill:
                        rec["fill"] = {k: fill[k] for k in ("entry_price", "tokens", "cost_usd", "impact_at_entry", "stop", "take_profit")}
                        report["buys"].append(rec)
                        log(f"BUY {rec['symbol']} ${fill['cost_usd']:.2f} @ {fill['entry_price']:.3g} (impact {fill['impact_at_entry']:.1%}): {decision['reason'][:120]}")
                    else:
                        rec["action"], rec["reason"] = "SKIP", "passed, but position could not be opened"
        except Exception as exc:          # one bad token must not stop the cycle
            rec.update({"action": "ERROR", "reason": f"{type(exc).__name__}: {exc}"})
            report["errors"] += 1
            log(f"error on {token[:8]}: {exc}")
        report["scanned"].append(rec)
        if not dry_run:
            dlog.write(rec)
        if rec.get("action") != "BUY":
            log(f"SKIP {rec.get('symbol') or token[:8]}: {rec.get('reason', '')[:140]}")

    # ---- 3. persist -----------------------------------------------------------------------
    if not trader.positions and not report["buys"]:
        trader.equity_history.append([int(now), round(trader.equity(prices), 2)])
    cutoff = now - 7 * 86400
    seen = {k: v for k, v in seen.items() if v > cutoff}
    if not dry_run:
        data_dir.mkdir(parents=True, exist_ok=True)
        seen_path.write_text(json.dumps(seen))
        trader.save()
    report.update({
        "balance": trader.balance, "equity": trader.equity(prices), "start_balance": trader.start_balance, "started": trader.started,
        "positions": [{"token": t, **p} for t, p in trader.positions.items()], "stats": trader.stats(),
        "daily_loss": trader.daily_loss(prices), "halted": trader.halted_day == trader.day,
        "requests": {"dexscreener": getattr(dex, "requests_made", 0), "rpc": getattr(rpc, "requests_made", 0), "rugcheck": getattr(rugcheck, "requests_made", 0)},
    })
    return report
