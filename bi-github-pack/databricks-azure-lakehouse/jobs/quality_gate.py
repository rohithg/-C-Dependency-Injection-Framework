#!/usr/bin/env python3
"""Post-transform quality gate on gold usage mart (pandas-friendly)."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    args = ap.parse_args()
    path = Path(args.gold)
    file = path / "usage_daily.csv" if (path / "usage_daily.csv").exists() else path / "usage_daily.parquet"
    if not file.exists():
        # directory of parquet partitions
        files = list(path.rglob("*.csv")) + list(path.rglob("*.parquet"))
        if not files:
            print("No gold files"); sys.exit(1)
        file = files[0]
    df = pd.read_csv(file) if file.suffix == ".csv" else pd.read_parquet(file)
    assert len(df) > 0, "empty gold"
    assert (df["event_count"] > 0).all(), "non-positive event_count"
    assert df["bytes_total"].min() >= 0, "negative bytes"
    print(f"quality_gate OK rows={len(df)} regions={df['region'].nunique()}")


if __name__ == "__main__":
    main()
