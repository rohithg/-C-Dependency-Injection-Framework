from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class WatermarkStore:
    """Persists incremental high-water marks between runs."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, str] = {}
        if path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    def get(self, key: str, default: str = "1970-01-01T00:00:00Z") -> str:
        return self._data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def bump_now(self, key: str) -> str:
        value = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.set(key, value)
        return value

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2) + "\n", encoding="utf-8")
