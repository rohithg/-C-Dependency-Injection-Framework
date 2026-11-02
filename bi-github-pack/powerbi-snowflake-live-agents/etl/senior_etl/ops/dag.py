from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TaskSpec:
    name: str
    fn: Callable[[], dict[str, Any] | None]
    depends_on: list[str] = field(default_factory=list)
    retries: int = 1
    parallel_group: str | None = None  # tasks with same group can fan-out


@dataclass
class TaskOutcome:
    name: str
    ok: bool
    attempts: int
    duration_ms: float
    meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class EnterpriseDag:
    """
    DAG with:
    - topological schedule
    - fan-out: independent ready tasks in the same wave run concurrently
    - retries + hard fail circuit
    """

    def __init__(self, tasks: list[TaskSpec], max_workers: int = 4):
        self.tasks = {t.name: t for t in tasks}
        self.max_workers = max_workers
        self.outcomes: dict[str, TaskOutcome] = {}

    def run(self) -> dict[str, TaskOutcome]:
        remaining = set(self.tasks)
        done: set[str] = set()
        while remaining:
            ready = [
                n
                for n in remaining
                if all(d in done for d in self.tasks[n].depends_on)
            ]
            if not ready:
                raise RuntimeError(f"Deadlock/cycle among {sorted(remaining)}")
            ready.sort()
            # Execute ready wave concurrently
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(ready))) as pool:
                futures = {pool.submit(self._exec, self.tasks[n]): n for n in ready}
                for fut in as_completed(futures):
                    name = futures[fut]
                    outcome = fut.result()
                    self.outcomes[name] = outcome
                    if not outcome.ok:
                        raise RuntimeError(
                            f"Task {name} failed: {outcome.error}"
                        )
                    done.add(name)
                    remaining.remove(name)
        return self.outcomes

    def _exec(self, task: TaskSpec) -> TaskOutcome:
        attempts = 0
        err = None
        meta: dict[str, Any] = {}
        t0 = time.perf_counter()
        while attempts <= task.retries:
            attempts += 1
            try:
                meta = task.fn() or {}
                return TaskOutcome(
                    name=task.name,
                    ok=True,
                    attempts=attempts,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    meta=meta,
                )
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                time.sleep(0.02 * attempts)
        return TaskOutcome(
            name=task.name,
            ok=False,
            attempts=attempts,
            duration_ms=(time.perf_counter() - t0) * 1000,
            error=err,
        )
