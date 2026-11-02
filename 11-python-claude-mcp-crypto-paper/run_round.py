#!/usr/bin/env python3
"""Run one decision round, then rebuild dashboard.html.

    python run_round.py                 # Claude Code if installed and logged in, else the rule agent
    python run_round.py --agent rules   # offline rule agent (same MCP tools, same rules)
    python run_round.py --agent claude  # force Claude Code (`claude -p ...` with the paper-crypto MCP server)

Paper money only. Nothing here can reach an exchange or a wallet.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from paperbot.ledger import Ledger          # noqa: E402
from paperbot import kraken                 # noqa: E402
from build_dashboard import build           # noqa: E402

TOOLS = ",".join(f"mcp__paper-crypto__{t}" for t in ("get_candles", "get_account", "buy", "sell_all", "hold"))


def claude_available() -> bool:
    return shutil.which("claude") is not None


def run_claude(prompt: str, state_dir: Path, log=print) -> dict:
    env = {**os.environ, "PAPERBOT_STATE_DIR": str(state_dir)}
    cmd = ["claude", "-p", prompt, "--mcp-config", str(ROOT / ".mcp.json"), "--strict-mcp-config",
           "--allowedTools", TOOLS, "--output-format", "json", "--max-turns", "15"]
    log("$ claude -p <trading prompt> --mcp-config .mcp.json --allowedTools <paper-crypto tools> --output-format json")
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        return {"agent": "claude", "error": (r.stderr or r.stdout)[-2000:]}
    try:
        out = json.loads(r.stdout)
        return {"agent": "claude", "result": out.get("result"), "cost_usd": out.get("total_cost_usd"),
                "turns": out.get("num_turns")}
    except json.JSONDecodeError:
        return {"agent": "claude", "result": r.stdout[-2000:]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", choices=["auto", "claude", "rules"], default="auto")
    ap.add_argument("--state-dir", default=os.environ.get("PAPERBOT_STATE_DIR", str(ROOT / "state")))
    ap.add_argument("--prompt", default=str(ROOT / "prompts" / "trading_prompt.md"))
    args = ap.parse_args()
    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    agent = args.agent
    if agent == "auto":
        agent = "claude" if claude_available() else "rules"
        if agent == "rules":
            print("claude CLI not found; using the offline rule agent (same MCP tools, same rules)")
    if agent == "claude" and not claude_available():
        print("claude CLI not installed; install Claude Code or use --agent rules", file=sys.stderr)
        return 2

    started = dt.datetime.now(dt.timezone.utc)
    if agent == "claude":
        outcome = run_claude(Path(args.prompt).read_text(), state_dir)
    else:
        outcome = {"agent": "rules", **asyncio.run(__import__("paperbot.agent", fromlist=["run_round"]).run_round(str(state_dir)))}

    # mark equity at the latest price (fixture when PAPERBOT_FIXTURE is set, Kraken otherwise)
    fx = os.environ.get("PAPERBOT_FIXTURE")
    prices = {k: float(v) for k, v in json.loads(Path(fx).read_text())["prices"].items()} if fx else kraken.last_prices()
    ledger = Ledger(state_dir)
    equity = ledger.mark(prices)
    last = ledger.decisions()[-1] if ledger.decisions() else {}
    rec = {"time": started.strftime("%Y-%m-%d %H:%M:%S UTC"), "agent": agent, "equity": round(equity, 4),
           "decision": {k: last.get(k) for k in ("action", "status", "symbol", "size_usd", "reason", "refused_because")},
           **({"claude": {k: outcome.get(k) for k in ("result", "cost_usd", "turns", "error")}} if agent == "claude" else {})}
    with (state_dir / "rounds.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")
    out = build(state_dir, ROOT / "dashboard.html")
    s = ledger.stats()
    print(f"\n{rec['time']}  agent={agent}  {last.get('action', '?').upper()} {last.get('symbol') or ''} "
          f"[{last.get('status')}] {last.get('reason', '')}")
    if last.get("refused_because"):
        print(f"  refused: {last['refused_because']}")
    print(f"equity ${s['equity']:.2f} ({s['return']:+.2%}), fees ${s['fees_paid']:.2f}, max drop {s['max_drawdown']:.1%}, "
          f"refused {s['refused']}, holds {s['holds']}  ->  {out}")
    return 0 if "error" not in outcome else 1


if __name__ == "__main__":
    sys.exit(main())
