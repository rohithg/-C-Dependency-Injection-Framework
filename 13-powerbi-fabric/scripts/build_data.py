"""Regenerate bronze, gold, and the numbers quoted in the README."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harbor.model import generate, lesson_numbers  # noqa: E402


def main() -> None:
    counts = generate(ROOT)
    numbers = lesson_numbers(ROOT)
    payload = {"counts": counts, "slices": numbers}
    path = ROOT / "data" / "lesson.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
