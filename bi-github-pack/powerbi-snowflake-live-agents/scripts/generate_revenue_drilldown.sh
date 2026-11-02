#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m generator.cli generate --manifest examples/revenue-drilldown/manifest.yaml --clean "$@"
