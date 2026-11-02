from __future__ import annotations

import argparse
import json
from pathlib import Path

from complex_etl.config_loader import PipelineConfig
from complex_etl.pipeline import run_complex_pipeline
from complex_etl.seed import seed_complex_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="complex_etl", description="Complex medallion ETL platform")
    sub = parser.add_subparsers(dest="command", required=True)

    seed_p = sub.add_parser("seed", help="Write complex demo sources (CSV/JSON/CDC)")
    seed_p.set_defaults(func=lambda a: _seed())

    run_p = sub.add_parser("run", help="Execute full DAG bronze→silver→gold")
    run_p.add_argument("--no-day2", action="store_true", help="Skip customer day2 SCD2 snapshot")
    run_p.set_defaults(func=lambda a: _run(not a.no_day2))

    args = parser.parse_args(argv)
    return args.func(args)


def _seed() -> int:
    root = Path(__file__).resolve().parent
    seed_complex_sources(root)
    print(f"Seeded sources under {root / 'data'}")
    return 0


def _run(apply_day2: bool) -> int:
    # Ensure package root is complex_etl/; config_loader parents[1] expects etl/
    cfg = PipelineConfig.create(root=Path(__file__).resolve().parents[1])
    # seed if missing
    if not (cfg.raw_dir / "orders.csv").exists():
        seed_complex_sources(cfg.root)
    result = run_complex_pipeline(cfg, apply_day2_customers=apply_day2)
    print(json.dumps(result, indent=2))
    print(f"\nGold lake: {cfg.gold_dir}")
    print(f"Reports:   {cfg.report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
