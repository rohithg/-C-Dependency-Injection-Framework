from __future__ import annotations

import json
from pathlib import Path

import polars as pl


def read_csv_source(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema_length=1000)


def read_json_source(path: Path) -> pl.DataFrame:
    return pl.read_json(path)


def read_cdc_log(path: Path, since_iso: str) -> pl.DataFrame:
    """CDC JSONL: op in {I,U,D}, commit_ts, payload fields."""
    if not path.exists():
        return pl.DataFrame()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(rows)
    return df.filter(pl.col("commit_ts") > since_iso).sort("commit_ts")


def fetch_fx_api_paginated(cache_dir: Path, pages: int = 2) -> pl.DataFrame:
    """
    Simulate a paginated FX rates API.
    Reads/writes cache JSON pages so the pipeline is offline-reproducible.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pl.DataFrame] = []
    for page in range(1, pages + 1):
        page_path = cache_dir / f"fx_page_{page}.json"
        if not page_path.exists():
            # deterministic mock payload
            payload = {
                "page": page,
                "rates": [
                    {
                        "as_of_date": "2026-01-05" if page == 1 else "2026-02-01",
                        "from_currency": "EUR",
                        "to_currency": "USD",
                        "rate": 1.08 if page == 1 else 1.09,
                    },
                    {
                        "as_of_date": "2026-01-05" if page == 1 else "2026-02-01",
                        "from_currency": "GBP",
                        "to_currency": "USD",
                        "rate": 1.27 if page == 1 else 1.26,
                    },
                ],
            }
            page_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload = json.loads(page_path.read_text(encoding="utf-8"))
        frames.append(pl.DataFrame(payload["rates"]))
    return pl.concat(frames, how="vertical_relaxed") if frames else pl.DataFrame()
