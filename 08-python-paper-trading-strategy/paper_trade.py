#!/usr/bin/env python3
"""Run one TVM rebalance against an Alpaca paper account.

    export APCA_API_KEY_ID=... APCA_API_SECRET_KEY=...
    python paper_trade.py --dry-run        # show the plan, send nothing
    python paper_trade.py                  # submit orders (paper account only)
    python paper_trade.py --fake           # no credentials: simulate with a fake $100k account

Schedule it once per trading day, e.g. 15:50 America/New_York (see
.github/workflows/paper-trade.yml for a cron example).
"""
from __future__ import annotations

import argparse
import sys
import warnings

from tvm.config import TVMConfig, DEFAULT
from tvm.data import load_closes
from tvm.trader import run_once

warnings.filterwarnings("ignore", category=FutureWarning)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="JSON file overriding TVMConfig fields")
    ap.add_argument("--dry-run", action="store_true", help="compute and print orders without submitting")
    ap.add_argument("--fake", action="store_true", help="use an in-memory fake broker (no credentials needed)")
    ap.add_argument("--no-live-prices", action="store_true", help="use last daily close only, even if market is open")
    ap.add_argument("--force", action="store_true", help="rebalance to target even if inside the band")
    ap.add_argument("--refresh", action="store_true", help="bypass the price cache")
    args = ap.parse_args()

    cfg = TVMConfig.from_json(args.config) if args.config else DEFAULT
    symbols = sorted({cfg.trend_symbol, *cfg.risk_assets})
    closes = load_closes(symbols, start="2015-01-01", refresh=args.refresh).dropna()

    if args.fake:
        from tvm.broker import FakeBroker
        broker = FakeBroker(is_open=False)
    else:
        from tvm.broker import AlpacaBroker
        broker = AlpacaBroker()

    run_once(broker, closes, cfg, dry_run=args.dry_run, use_live_prices=not args.no_live_prices, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
