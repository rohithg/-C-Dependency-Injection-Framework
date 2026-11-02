#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/tmp/lakehouse_gold}"
python3 "$ROOT/jobs/transform_usage.py" --input "$ROOT/sample_data" --output "$OUT" --local-fallback
python3 -m pytest "$ROOT/tests" -q || true
echo "Demo gold written to $OUT"
