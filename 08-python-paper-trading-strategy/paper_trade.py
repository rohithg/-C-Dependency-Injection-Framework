#!/usr/bin/env python3
"""Run one TVM rebalance against an Alpaca paper account.

    export APCA_API_KEY_ID=... APCA_API_SECRET_KEY=...
    python paper_trade.py --dry-run        # show the plan, send nothing
    python paper_trade.py                  # submit orders (paper account only)
    python paper_trade.py --fake           # no credentials: simulate with a fake $100k account

Or via --mode (used by the GitHub Actions workflow):
    --mode preview   same as --fake --dry-run; works without any credentials
    --mode dry-run   real account, no orders
    --mode live      real paper account, orders submitted
    --mode notify-test   send a test message through every configured channel and exit

If --mode is omitted and credentials are missing, falls back to preview so a
run from a fresh checkout never fails for lack of setup.

Schedule it once per trading day, e.g. 15:50 America/New_York (see
.github/workflows/paper-trade.yml).
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings

from tvm.config import TVMConfig, DEFAULT
from tvm.data import load_closes
from tvm.trader import run_once
from tvm.report import performance_vs_benchmark, to_markdown, write_step_summary
from tvm.notify import to_text, send_all

warnings.filterwarnings("ignore", category=FutureWarning)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="JSON file overriding TVMConfig fields")
    ap.add_argument("--mode", choices=["preview", "dry-run", "live", "notify-test"], help="see module docstring")
    ap.add_argument("--no-notify", action="store_true", help="skip SMS/push notifications")
    ap.add_argument("--dry-run", action="store_true", help="compute and print orders without submitting")
    ap.add_argument("--fake", action="store_true", help="use an in-memory fake broker (no credentials needed)")
    ap.add_argument("--no-live-prices", action="store_true", help="use last daily close only, even if market is open")
    ap.add_argument("--force", action="store_true", help="rebalance to target even if inside the band")
    ap.add_argument("--refresh", action="store_true", help="bypass the price cache")
    args = ap.parse_args()

    if args.mode == "notify-test":
        results = send_all("TVM paper trading: test message. Daily updates will arrive here after each run.")
        print(results)
        write_step_summary("## Notification test\n\n" + "\n".join(f"- {k}: {v}" for k, v in results.items()) + "\n")
        return 0 if any(v == "sent" for v in results.values()) else 1

    have_keys = bool(os.environ.get("APCA_API_KEY_ID") and os.environ.get("APCA_API_SECRET_KEY"))
    mode = args.mode
    if mode is None:
        if args.fake or not have_keys:
            mode = "preview"
        else:
            mode = "dry-run" if args.dry_run else "live"
    if mode in ("dry-run", "live") and not have_keys:
        print(f"--mode {mode} needs APCA_API_KEY_ID / APCA_API_SECRET_KEY; falling back to preview", file=sys.stderr)
        mode = "preview"
    fake, dry_run = mode == "preview", mode != "live"

    cfg = TVMConfig.from_json(args.config) if args.config else DEFAULT
    symbols = sorted({cfg.trend_symbol, *cfg.risk_assets, cfg.benchmark_symbol})
    closes = load_closes(symbols, start="2015-01-01", refresh=args.refresh)
    signal_closes = closes[sorted({cfg.trend_symbol, *cfg.risk_assets})].dropna()

    if fake:
        from tvm.broker import FakeBroker
        broker = FakeBroker(is_open=False)
    else:
        from tvm.broker import AlpacaBroker
        broker = AlpacaBroker()

    report = run_once(broker, signal_closes, cfg, dry_run=dry_run, use_live_prices=not args.no_live_prices, force=args.force)
    perf = None if fake else performance_vs_benchmark(broker, closes[cfg.benchmark_symbol])
    md = to_markdown(report, perf, cfg, mode=mode)
    text = to_text(report, perf, cfg, mode=mode)
    print("\n" + md)
    print(text)
    if not args.no_notify:
        results = send_all(text)
        sent = [k for k, v in results.items() if v == "sent"]
        errors = {k: v for k, v in results.items() if v.startswith("error")}
        md += f"\n<sub>notifications: sent via {', '.join(sent) or 'none configured'}" + (f"; errors: {errors}" if errors else "") + "</sub>\n"
    if write_step_summary(md):
        print("(summary written to GitHub step summary)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
