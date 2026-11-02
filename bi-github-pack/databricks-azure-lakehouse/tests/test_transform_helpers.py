"""Lightweight tests — pandas path validates aggregation contract without Java."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def test_pandas_fallback_produces_gold():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "gold"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "jobs" / "transform_usage.py"),
                "--input",
                str(ROOT / "sample_data"),
                "--output",
                str(out),
                "--local-fallback",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert (out / "usage_daily.parquet").exists() or (out / "usage_daily.csv").exists(), proc.stdout
