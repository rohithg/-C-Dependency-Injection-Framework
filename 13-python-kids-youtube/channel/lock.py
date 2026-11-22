"""A one-file lock so two daily jobs cannot render the same episode."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


class Busy(RuntimeError):
    pass


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_pid(path: Path) -> int:
    try:
        return int(path.read_text().strip() or "0")
    except (OSError, ValueError):
        return 0


@contextmanager
def file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            if _alive(_read_pid(path)):
                raise Busy(f"A daily job is already running ({path})")
            try:
                path.unlink()
            except FileNotFoundError:
                pass
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        path.unlink(missing_ok=True)
