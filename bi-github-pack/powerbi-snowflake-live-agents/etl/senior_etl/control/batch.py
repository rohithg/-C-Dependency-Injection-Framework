from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class BatchRecord:
    batch_id: str
    status: str  # RUNNING | SUCCESS | FAILED | REPLAYED
    started_at: str
    finished_at: str | None = None
    source_files: dict[str, str] = field(default_factory=dict)  # name -> checksum
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempt: int = 1


class BatchControlStore:
    """Persistent batch control table (JSONL) for idempotency and replay."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def _read_all(self) -> list[dict]:
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def get(self, batch_id: str) -> dict | None:
        for row in reversed(self._read_all()):
            if row.get("batch_id") == batch_id:
                return row
        return None

    def start(self, batch_id: str, source_files: dict[str, str], attempt: int = 1) -> BatchRecord:
        rec = BatchRecord(
            batch_id=batch_id,
            status="RUNNING",
            started_at=datetime.now(timezone.utc).isoformat(),
            source_files=source_files,
            attempt=attempt,
        )
        self._append(rec)
        return rec

    def succeed(self, batch_id: str, metrics: dict[str, Any]) -> None:
        self._finalize(batch_id, "SUCCESS", metrics=metrics)

    def fail(self, batch_id: str, error: str) -> None:
        self._finalize(batch_id, "FAILED", error=error)

    def mark_replayed(self, batch_id: str, metrics: dict[str, Any]) -> None:
        self._finalize(batch_id, "REPLAYED", metrics=metrics)

    def already_successful(self, batch_id: str) -> bool:
        row = self.get(batch_id)
        return bool(row and row.get("status") in {"SUCCESS", "REPLAYED"})

    def _finalize(
        self,
        batch_id: str,
        status: str,
        metrics: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        prev = self.get(batch_id) or {}
        rec = BatchRecord(
            batch_id=batch_id,
            status=status,
            started_at=prev.get("started_at", datetime.now(timezone.utc).isoformat()),
            finished_at=datetime.now(timezone.utc).isoformat(),
            source_files=prev.get("source_files", {}),
            metrics=metrics or prev.get("metrics", {}),
            error=error,
            attempt=int(prev.get("attempt", 1)),
        )
        self._append(rec)

    def _append(self, rec: BatchRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(rec)) + "\n")


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
