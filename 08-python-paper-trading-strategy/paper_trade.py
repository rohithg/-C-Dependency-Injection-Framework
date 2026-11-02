#!/usr/bin/env python3
"""Run one TVM rebalance against a paper account.

    python paper_trade.py                  # no credentials: built-in $100k paper account, persisted in state/
    python paper_trade.py --fake           # no credentials, nothing saved: today's signal on a throwaway account

    export APCA_API_KEY_ID=... APCA_API_SECRET_KEY=...   # optional: use an Alpaca paper account instead
    python paper_trade.py --dry-run        # show the plan, send nothing
    python paper_trade.py                  # submit orders (Alpaca paper account only)

Strategies (--strategy, or env TVM_STRATEGY):
    adaptive   TVM expert ensemble (default)
    fixed      the single fixed TVM rule set
    kronos     Kronos candlestick foundation model (needs requirements-kronos.txt;
               rule via --kronos-rule, default "calibrated")

Or via --mode (used by the GitHub Actions workflow):
    --mode paper     built-in paper account (state/paper_account.json), fills at the daily close; no credentials
    --mode preview   same as --fake --dry-run; works without any credentials, saves nothing
    --mode dry-run   Alpaca paper account, no orders
    --mode live      Alpaca paper account, orders submitted
    --mode notify-test   send a test message through every configured channel and exit

Without Alpaca credentials, --mode live/dry-run fall back to paper/preview so
the scheduled job keeps a running paper account from day one.

Schedule it once per trading day, e.g. 15:40 America/New_York (see
.github/workflows/paper-trade.yml).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import warnings

from tvm.config import TVMConfig, DEFAULT
from tvm.adaptive import AdaptiveConfig
from tvm.data import load_closes, load_ohlcv
from tvm.kronos_signal import KronosConfig, RULES
from tvm.trader import run_once, STATE_DIR
from tvm.report import performance_vs_benchmark, to_markdown, write_step_summary
from tvm.notify import to_text, send_all

warnings.filterwarnings("ignore", category=FutureWarning)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="JSON file overriding TVMConfig fields")
    ap.add_argument("--mode", choices=["paper", "preview", "dry-run", "live", "notify-test"], help="see module docstring")
    ap.add_argument("--no-notify", action="store_true", help="skip SMS/push notifications")
    ap.add_argument("--strategy", choices=["adaptive", "fixed", "kronos"],
                    default=os.environ.get("TVM_STRATEGY", "adaptive"), help="see module docstring")
    ap.add_argument("--fixed", action="store_true", help="alias for --strategy fixed")
    ap.add_argument("--kronos-rule", choices=RULES, default=os.environ.get("KRONOS_RULE", "calibrated"))
    ap.add_argument("--kronos-variant", choices=["mini", "small", "base"], default=os.environ.get("KRONOS_VARIANT", "small"))
    ap.add_argument("--state-dir", default=os.environ.get("TVM_STATE_DIR"),
                    help="where tvm_state.json / trade_log.jsonl live (default state/, or state/kronos for --strategy kronos)")
    ap.add_argument("--dry-run", action="store_true", help="compute and print orders without submitting")
    ap.add_argument("--fake", action="store_true", help="use an in-memory fake broker (no credentials needed)")
    ap.add_argument("--no-live-prices", action="store_true", help="use last daily close only, even if market is open")
    ap.add_argument("--force", action="store_true", help="rebalance to target even if inside the band")
    ap.add_argument("--refresh", action="store_true", help="bypass the price cache")
    args = ap.parse_args()

    strategy = "fixed" if args.fixed else args.strategy
    if args.mode == "notify-test":
        results = send_all(f"{strategy} paper trading: test message. Daily updates will arrive here after each run.")
        print(results)
        write_step_summary("## Notification test\n\n" + "\n".join(f"- {k}: {v}" for k, v in results.items()) + "\n")
        return 0 if any(v == "sent" for v in results.values()) else 1

    have_keys = bool(os.environ.get("APCA_API_KEY_ID") and os.environ.get("APCA_API_SECRET_KEY"))
    mode = args.mode
    if mode is None:
        if args.fake:
            mode = "preview"
        elif not have_keys:
            mode = "preview" if args.dry_run else "paper"
        else:
            mode = "dry-run" if args.dry_run else "live"
    if mode in ("dry-run", "live") and not have_keys:
        fallback = "paper" if mode == "live" else "preview"
        print(f"--mode {mode} needs APCA_API_KEY_ID / APCA_API_SECRET_KEY; falling back to {fallback}", file=sys.stderr)
        mode = fallback
    fake, dry_run = mode == "preview", mode not in ("live", "paper")

    cfg = TVMConfig.from_json(args.config) if args.config else DEFAULT
    adaptive = AdaptiveConfig(max_leverage=cfg.max_leverage) if strategy == "adaptive" else None
    kronos = bars = None
    if strategy == "kronos":
        kronos = KronosConfig(variant=args.kronos_variant, rule=args.kronos_rule,
                              max_leverage=2.0 if args.kronos_rule == "confidence" else 1.0)
        bars = {s: load_ohlcv(s, start="2000-01-01", refresh=args.refresh) for s in kronos.symbols}
    state_dir = Path(args.state_dir) if args.state_dir else (STATE_DIR / "kronos" if strategy == "kronos" else STATE_DIR)
    tradable = {cfg.cash_symbol, *cfg.risk_assets, *cfg.leveraged_2x.values()}
    symbols = sorted({cfg.trend_symbol, *cfg.risk_assets, cfg.benchmark_symbol, *tradable})
    # the ensemble scores experts on realised history, so give it a long window
    closes = load_closes(symbols, start="2015-01-01" if strategy == "fixed" else "2007-01-01", refresh=args.refresh)
    signal_cols = sorted({cfg.trend_symbol, *cfg.risk_assets} | (set() if strategy == "fixed" else tradable))
    signal_closes = closes[signal_cols].dropna(subset=sorted({cfg.trend_symbol, *cfg.risk_assets}))

    if fake:
        from tvm.broker import FakeBroker
        broker = FakeBroker(is_open=False)
    elif mode == "paper":
        from tvm.broker import LocalPaperBroker
        last = closes.ffill().iloc[-1]
        prices = {s: float(last[s]) for s in tradable if s in last.index and last[s] == last[s]}
        broker = LocalPaperBroker(state_dir / "paper_account.json", prices, as_of=str(closes.index[-1].date()))
    else:
        from tvm.broker import AlpacaBroker
        broker = AlpacaBroker()

    report = run_once(broker, signal_closes, cfg, dry_run=dry_run, use_live_prices=not args.no_live_prices,
                      force=args.force, adaptive=adaptive, kronos=kronos, bars=bars, state_dir=state_dir)
    if mode == "paper":
        broker.mark()
    perf = None if fake else performance_vs_benchmark(broker, closes[cfg.benchmark_symbol])
    md = to_markdown(report, perf, cfg, mode=mode)
    text = to_text(report, perf, cfg, mode=mode)
    print("\n" + md)
    print(text)
    if not args.no_notify:
        results = send_all(text, markdown=md)
        sent = [k for k, v in results.items() if v == "sent"]
        errors = {k: v for k, v in results.items() if v.startswith("error")}
        md += f"\n<sub>notifications: sent via {', '.join(sent) or 'none configured'}" + (f"; errors: {errors}" if errors else "") + "</sub>\n"
    if write_step_summary(md):
        print("(summary written to GitHub step summary)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
