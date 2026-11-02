from __future__ import annotations

import argparse
import json
from pathlib import Path

from senior_etl.pipeline import SeniorPlatform
from senior_etl.seed import seed_senior_landing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="senior_etl", description="Senior DE enterprise ETL platform")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Write enterprise landing-zone files")
    p_seed.set_defaults(func=lambda a: _seed())

    p_run = sub.add_parser("run", help="Run a new idempotent batch")
    p_run.add_argument("--batch-id", default=None)
    p_run.set_defaults(func=lambda a: _run(a.batch_id, replay=False))

    p_replay = sub.add_parser("replay", help="Replay/backfill a batch_id idempotently")
    p_replay.add_argument("--batch-id", required=True)
    p_replay.set_defaults(func=lambda a: _run(a.batch_id, replay=True))

    args = parser.parse_args(argv)
    return args.func(args)


def _seed() -> int:
    root = Path(__file__).resolve().parent
    seed_senior_landing(root)
    print(f"Seeded landing zone at {root / 'data' / 'landing'}")
    return 0


def _run(batch_id: str | None, replay: bool) -> int:
    root = Path(__file__).resolve().parent
    if not (root / "data" / "landing" / "orders.csv").exists():
        seed_senior_landing(root)
    platform = SeniorPlatform(root=root, batch_id=batch_id)
    report = platform.run(force_replay=replay)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
