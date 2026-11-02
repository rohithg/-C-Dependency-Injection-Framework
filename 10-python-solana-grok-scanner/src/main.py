#!/usr/bin/env python3
"""grok-trader: Solana new-token scanner + Grok risk read + paper trading.

    python src/main.py --demo               # full pipeline on 3 fictional tokens, no network
    python src/main.py --mode paper         # scan forever (every config.poll_seconds), paper trade, log
    python src/main.py --mode paper --once  # one cycle (what the GitHub Actions job runs)
    python src/main.py --dashboard          # http://localhost:8000

MODE defaults to "paper" and is the only mode that exists. There is no wallet,
no private key and no transaction-signing code in this project.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv                      # noqa: E402

from pipeline import run_cycle, load_config, ROOT, DATA, LOGS   # noqa: E402
from report import to_markdown, to_text, send_all, write_step_summary  # noqa: E402

NOTIFY_HOUR_UTC = 20


def main() -> int:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default=os.environ.get("MODE", "paper"))
    ap.add_argument("--demo", action="store_true", help="offline run on 3 fictional tokens")
    ap.add_argument("--once", action="store_true", help="one scan cycle, then exit")
    ap.add_argument("--dashboard", action="store_true", help="serve the local dashboard instead of scanning")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--data-dir", default=os.environ.get("SCANNER_DATA_DIR", str(DATA)))
    ap.add_argument("--log-dir", default=os.environ.get("SCANNER_LOG_DIR", str(LOGS)))
    ap.add_argument("--notify", action="store_true", help="send the status message after this cycle")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="scan and print, write nothing")
    args = ap.parse_args()

    if args.mode != "paper":
        print(f"MODE={args.mode!r}: live trading is not implemented and will not be. Set MODE=paper.")
        return 2
    cfg = load_config(Path(args.config))
    data_dir, log_dir = Path(args.data_dir), Path(args.log_dir)

    if args.dashboard:
        from dashboard import serve
        serve(args.port)
        return 0

    if args.demo:
        from demo import FakeDex, FakeRPC, FakeRugCheck, fake_grok_transport
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="grok-trader-demo-"))
        rep = run_cycle(cfg, FakeDex(), FakeRPC(), FakeRugCheck(), "demo-key", data_dir=tmp / "data", log_dir=tmp / "logs",
                        grok_transport=fake_grok_transport)
        # a second cycle an hour later with prices moved: the winner takes profit, one holder is stopped out
        rep2 = run_cycle(cfg, FakeDex({"DEMOgoodcat111111111111111111111111111111": 2.3}), FakeRPC(), FakeRugCheck(), "demo-key",
                         data_dir=tmp / "data", log_dir=tmp / "logs", now=time.time() + 3600, grok_transport=fake_grok_transport)
        print(to_markdown(rep, "demo"))
        print(to_markdown(rep2, "demo, +1h"))
        print(f"demo files written under {tmp} (logs/decisions.jsonl, data/paper_state.json)")
        return 0

    from feed import DexScreener
    from chain import SolanaRPC, RugCheck, PUBLIC_RPC
    api_key = os.environ.get("XAI_API_KEY") or None
    if not api_key:
        print("XAI_API_KEY not set: tokens that pass every hard rule will be logged but not bought (grok_required=true).")
    dex = DexScreener()
    rpc = SolanaRPC(os.environ.get("SOLANA_RPC_URL") or PUBLIC_RPC)
    rugcheck = RugCheck()

    while True:
        rep = run_cycle(cfg, dex, rpc, rugcheck, api_key, data_dir=data_dir, log_dir=log_dir, dry_run=args.dry_run)
        md, text = to_markdown(rep, "paper" + (", dry-run" if args.dry_run else "")), to_text(rep)
        print(text)
        if args.once:
            print("\n" + md)
            marker = data_dir / "last_notified.txt"
            today = dt.datetime.now(dt.timezone.utc)
            due = today.hour >= NOTIFY_HOUR_UTC and (not marker.exists() or marker.read_text().strip() != today.strftime("%Y-%m-%d"))
            if not args.no_notify and (args.notify or due):
                sent = [k for k, v in send_all(text, md).items() if v == "sent"]
                md += f"\n<sub>notifications: {', '.join(sent) or 'none configured'}</sub>\n"
                if sent and not args.dry_run:
                    marker.write_text(today.strftime("%Y-%m-%d"))
            write_step_summary(md)
            print(f"({rep['requests']} API requests)")
            return 0
        time.sleep(cfg.get("poll_seconds", 60))


if __name__ == "__main__":
    sys.exit(main())
