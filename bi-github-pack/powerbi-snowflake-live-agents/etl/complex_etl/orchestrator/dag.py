from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TaskResult:
    name: str
    ok: bool
    attempts: int
    duration_ms: float
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    name: str
    fn: Callable[[], dict[str, Any] | None]
    depends_on: list[str] = field(default_factory=list)
    retries: int = 0


class DagRunner:
    """Simple topological DAG executor with retries and run metrics."""

    def __init__(self, tasks: list[Task]):
        self.tasks = {t.name: t for t in tasks}
        self.results: dict[str, TaskResult] = {}

    def _topo(self) -> list[str]:
        pending = set(self.tasks)
        done: list[str] = []
        while pending:
            ready = [
                n
                for n in pending
                if all(d in done for d in self.tasks[n].depends_on)
            ]
            if not ready:
                raise RuntimeError(f"Cycle or missing dependency among: {sorted(pending)}")
            # stable order for determinism
            ready.sort()
            for n in ready:
                done.append(n)
                pending.remove(n)
        return done

    def run(self) -> dict[str, TaskResult]:
        for name in self._topo():
            task = self.tasks[name]
            attempts = 0
            last_err: str | None = None
            meta: dict[str, Any] = {}
            t0 = time.perf_counter()
            ok = False
            while attempts <= task.retries:
                attempts += 1
                try:
                    meta = task.fn() or {}
                    ok = True
                    last_err = None
                    break
                except Exception as exc:  # noqa: BLE001 - surface in run report
                    last_err = f"{exc}\n{traceback.format_exc()}"
                    if attempts <= task.retries:
                        time.sleep(0.05 * attempts)
            duration_ms = (time.perf_counter() - t0) * 1000
            self.results[name] = TaskResult(
                name=name,
                ok=ok,
                attempts=attempts,
                duration_ms=duration_ms,
                error=last_err,
                meta=meta,
            )
            if not ok:
                raise RuntimeError(f"Task {name} failed after {attempts} attempt(s): {last_err}")
        return self.results
