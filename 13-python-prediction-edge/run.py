"""Scan, paper-trade, replay, or (gated) live-trade the structural edge."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from edge.config import Config
from edge.kalshi import KalshiPublic
from edge.live import broker_from_env, execute, gate
from edge.paper import Account, index_books, run_cycle
from edge.polymarket import PolymarketPublic
from edge.replay import run_document
from edge.report import render
from edge.risk import allow
from edge.strategy import plan_markets

ROOT = Path(__file__).resolve().parent
PT = ZoneInfo("America/Los_Angeles")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prediction-edge", description=__doc__)
    parser.add_argument("--config", default="", help="JSON config. Missing file uses the paper defaults.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="read the live books and show what a paper account would do")
    paper = sub.add_parser("paper", help="run the paper account and save it")
    paper.add_argument("--loop", action="store_true", help="keep cycling until the process is stopped or the account halts")
    paper.add_argument("--state", default="", help="account file, default state/account.json")
    replay = sub.add_parser("replay", help="play a recorded book through the paper account")
    replay.add_argument("path", nargs="?", default=str(ROOT / "examples" / "replay.json"))
    live = sub.add_parser("live", help="send taker orders. Refuses unless every safety gate is open.")
    live.add_argument("--live", action="store_true", help="required. Without this flag the command only prints the gate.")
    args = parser.parse_args(argv)

    config = Config.load(args.config) if args.config else Config.load(ROOT / "config.json") if (ROOT / "config.json").exists() else Config()
    if args.cmd == "replay":
        return _replay(Path(args.path))
    if args.cmd == "scan":
        return _scan(config)
    if args.cmd == "paper":
        return _paper(config, args)
    if args.cmd == "live":
        return _live(config, args.live)
    return 2


def _scan(config: Config) -> int:
    print("Throwaway paper pass. Nothing is saved and no order is sent.")
    binaries, ladders, links, notes = _fetch(config)
    for note in notes:
        print(note)
    account = Account(config.bankroll)
    result = run_cycle(account, binaries, ladders, links, config, _now(), _now_ms())
    print(render(result, account, _now()))
    print()
    n_ladders = len(ladders)
    ladder_word = "ladder" if n_ladders == 1 else "ladders"
    print(f"Read {len(binaries)} Polymarket markets and {n_ladders} Kalshi {ladder_word} "
          f"({sum(len(ladder.strikes) for ladder in ladders)} strikes).")
    return 0


def _paper(config: Config, args) -> int:
    path = Path(args.state) if args.state else ROOT / "state" / "account.json"
    account = Account.load(path, config.bankroll)
    while True:
        if (ROOT / "state" / "KILL").exists():
            account.halted = True
        binaries, ladders, links, notes = _fetch(config)
        for note in notes:
            print(note)
        result = run_cycle(account, binaries, ladders, links, config, _now(), _now_ms())
        account.save(path)
        print(render(result, account, _now()))
        if not args.loop or account.halted:
            return 0
        time.sleep(config.loop_seconds)


def _live(config: Config, flagged: bool) -> int:
    reason = gate(config, flagged)
    if reason:
        print(reason)
        print("Paper mode is the one that runs without keys: python run.py paper")
        return 2
    path = ROOT / "state" / "live.json"
    account = Account.load(path, config.bankroll)
    if (ROOT / "state" / "KILL").exists():
        account.halted = True
    binaries, ladders, links, notes = _fetch(config)
    for note in notes:
        print(note)
    now, now_ms = _now(), _now_ms()
    account.ensure_baseline(now)
    opportunities, watches = plan_markets(binaries, ladders, links, config)
    chosen = []
    skipped = []
    used: set[str] = set()
    for opp in opportunities:
        live_kind = opp.kind in ("complete_set_buy", "ladder") or (opp.kind == "basis" and config.live_basis)
        if not live_kind:
            continue
        if any(market_id in used for market_id in opp.market_ids):
            skipped.append((opp, "overlaps a better trade"))
            continue
        ok, why = allow(account, opp, config, now_ms)
        if not ok:
            skipped.append((opp, why))
            continue
        chosen.append(opp)
        used.update(opp.market_ids)
    from edge.paper import CycleResult
    preview = CycleResult([], skipped, [], [], watches, opportunities)
    print(render(preview, account, now))
    if account.halted:
        print("Account is halted. No orders sent.")
        account.save(path)
        return 2
    if not chosen:
        print("No live order. Maker quotes are paper-only.")
        account.save(path)
        return 0
    print()
    print(f"Sending {len(chosen)} taker package(s).")
    books = index_books(binaries, ladders, links)
    acted = execute(chosen, broker_from_env(), account, binaries, books, config)
    for line in acted:
        print(line)
    account.mark(books, now)
    account.save(path)
    print(f"equity ${account.last_equity}  halted {account.halted}")
    return 1 if account.halted else 0


def _replay(path: Path) -> int:
    account, results, _config = run_document(path)
    for result in results:
        print(render(result, account))
        print()
    print(f"Replay finished. Equity ${account.last_equity} from the recorded books.")
    return 0


def _fetch(config: Config):
    notes = []
    binaries = []
    ladders = []
    links = []
    try:
        binaries = PolymarketPublic().active_binaries(config.poly_event_limit)
    except Exception as exc:
        notes.append(f"Polymarket read failed: {exc}")
    try:
        ladders = KalshiPublic().ladders(config.kalshi_series, config.kalshi_events_per_series)
    except Exception as exc:
        notes.append(f"Kalshi read failed: {exc}")
    if config.links_file:
        try:
            links = _links(Path(config.links_file))
        except Exception as exc:
            notes.append(f"Link file failed: {exc}")
    return binaries, ladders, links, notes


def _links(path: Path):
    """Explicit pairs only. An empty id is a placeholder and is skipped."""
    from edge.models import BasisLink

    raw = json.loads(path.read_text())
    poly, kalshi = PolymarketPublic(), KalshiPublic()
    links = []
    for row in raw.get("links") or []:
        condition = row.get("polymarket_condition_id") or ""
        ticker = row.get("kalshi_ticker") or ""
        if not condition or not ticker:
            continue
        left = poly.by_condition(condition)
        right = kalshi.by_ticker(ticker)
        if left is None or right is None:
            continue
        links.append(BasisLink(row.get("name") or f"{condition[:8]}-{ticker}", left, right, bool(row.get("same_yes", True))))
    return links


def _now() -> datetime:
    return datetime.now(PT)


def _now_ms() -> int:
    return int(time.time() * 1000)


if __name__ == "__main__":
    sys.exit(main())
