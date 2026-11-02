#!/usr/bin/env python3
"""One hourly tick of the Polymarket copy-trading paper account.

    python paper_trade.py                 # copy new leader trades, mark, report (state in state/)
    python paper_trade.py --reselect      # also re-pick the followed wallets now (slow: ~10-20 min)
    python paper_trade.py --dry-run       # compute and print, write nothing
    python paper_trade.py --notify        # send the daily status now (otherwise once/day after 20:00 UTC)
    python paper_trade.py --mode notify-test

No API keys are needed: Polymarket's data endpoints are public and the
account is simulated locally. Run it every hour (see
.github/workflows/polymarket-copy.yml).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import sys
import warnings

from polycopy.api import PolymarketAPI
from polycopy.copy import CopyConfig, DEFAULT
from polycopy.paper import run_once, STATE_DIR
from polycopy.report import to_markdown, to_text, send_all, write_step_summary

warnings.filterwarnings("ignore", category=FutureWarning)
NOTIFY_HOUR_UTC = 20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="JSON overriding CopyConfig fields")
    ap.add_argument("--mode", choices=["live", "dry-run", "notify-test"], default=os.environ.get("MODE", "live"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reselect", action="store_true", help="re-pick followed wallets now")
    ap.add_argument("--notify", action="store_true", help="send the status message this run")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--cash", type=float, default=float(os.environ.get("POLY_START_CASH", 10_000)))
    ap.add_argument("--state-dir", default=os.environ.get("POLY_STATE_DIR"))
    args = ap.parse_args()

    if args.mode == "notify-test":
        res = send_all("Polymarket copy trading: test message. Daily updates will arrive here.", "")
        print(res)
        return 0 if any(v == "sent" for v in res.values()) else 1

    cfg = CopyConfig.from_json(args.config) if args.config else DEFAULT
    dry = args.dry_run or args.mode == "dry-run"
    state_dir = Path(args.state_dir) if args.state_dir else STATE_DIR
    api = PolymarketAPI(log=lambda m: print("   ", m))
    report = run_once(api, cfg, state_dir, start_cash=args.cash, reselect=args.reselect, dry_run=dry)
    state = report.pop("_state")

    mode = "dry-run" if dry else ""
    md, text = to_markdown(report, mode), to_text(report, mode)
    print("\n" + md + "\n" + text)

    today = dt.datetime.now(dt.timezone.utc)
    due = today.hour >= NOTIFY_HOUR_UTC and state.last_notified != today.strftime("%Y-%m-%d")
    if not args.no_notify and (args.notify or due):
        results = send_all(text, md)
        sent = [k for k, v in results.items() if v == "sent"]
        md += f"\n<sub>notifications: {', '.join(sent) or 'none configured'}</sub>\n"
        if sent and not dry:
            state.last_notified = today.strftime("%Y-%m-%d")
            state.save()
    if write_step_summary(md):
        print("(summary written to GitHub step summary)")
    print(f"({api.requests_made} API requests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
