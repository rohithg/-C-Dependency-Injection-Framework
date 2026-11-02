from __future__ import annotations

import argparse
from pathlib import Path

from retail_etl.config import EtlConfig
from retail_etl.pipeline import run_pipeline
from retail_etl.seed import write_seed_data


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[1]
    if args.seed:
        write_seed_data(root / "data" / "raw")
        print(f"Seeded raw CSVs in {root / 'data' / 'raw'}")
        if args.seed_only:
            return 0
    cfg = EtlConfig.from_env(root=root, load_snowflake=args.load_snowflake)
    result = run_pipeline(cfg)
    print("ETL complete")
    for name, n in sorted(result.rows.items()):
        if name.startswith("raw_"):
            continue
        print(f"  {name}: {n} rows")
    print(f"Parquet: {cfg.out_dir}")
    print(f"Manifest: {result.manifest}")
    print(f"Snowflake loaded: {result.snowflake_loaded}")
    return 0


def cmd_apply_views(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[1]
    cfg = EtlConfig.from_env(root=root, load_snowflake=True)
    if not cfg.snowflake_ready():
        raise SystemExit("Snowflake credentials required for apply-views")
    from retail_etl.load.snowflake_load import apply_powerbi_views

    views = root.parent / "snowflake" / "views"
    apply_powerbi_views(cfg, views)
    print(f"Applied views from {views}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retail_etl", description="Retail ETL (Polars → Parquet/Snowflake)")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run extract → transform → load")
    run_p.add_argument("--seed", action="store_true", help="Write demo raw CSVs before run")
    run_p.add_argument("--seed-only", action="store_true", help="Only write seed files")
    run_p.add_argument(
        "--load-snowflake",
        action="store_true",
        help="Also COPY marts into Snowflake (requires SF_* env)",
    )
    run_p.set_defaults(func=cmd_run)

    views_p = sub.add_parser("apply-views", help="Create Power BI secure views in Snowflake")
    views_p.set_defaults(func=cmd_apply_views)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
