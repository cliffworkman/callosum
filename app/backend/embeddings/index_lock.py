"""OS-level ownership of an index build: one live worker per library file and profile (inc 610).

The worker holds an exclusive lock on ``<library>.index-<profile>.lock`` for its whole life. The operating system
releases it the instant the process ends -- normal exit, crash, or an external kill that runs no cleanup code --
so "is a worker alive?" is answered by trying the lock, not by trusting a PID (which can be reused) or a
heartbeat (which goes stale only after a delay). It also stops two Callosum processes opened on the same library
(e.g. a dev server beside the desktop app) from running two workers. Standard library only: the packaged runtime
does not ship psutil.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

from sqlalchemy.engine import make_url


def named_lock_path(db_url: str, name: str) -> Path | None:
    """``<library>.<name>.lock`` beside the library file. None for a database without a file (in-memory tests),
    which no other process can open anyway."""
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return None
    return Path(url.database).with_name(f"{Path(url.database).name}.{name}.lock")


def lock_path(db_url: str, profile_key: str) -> Path | None:
    return named_lock_path(db_url, f"index-{profile_key}")


def launch_lease_path(db_url: str, profile_key: str) -> Path | None:
    """Held by the *app process* that launched the current worker, from before the launch until it observes the exit
    (inc 617). The worker's own lock only exists once the worker has started; without this lease a second Callosum
    process could mistake a worker that is still starting for a dead one and launch another."""
    return named_lock_path(db_url, f"index-{profile_key}.launch")


class WorkerLock:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._fd: int | None = None

    def acquire(self) -> bool:
        if self.path is None:
            return True
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def release(self) -> None:
        if self._fd is None:
            return
        with contextlib.suppress(OSError):
            if sys.platform == "win32":
                import msvcrt

                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None


def held_elsewhere(path: Path | None) -> bool:
    """True while another holder (any process, or another handle in this one) has the lock at ``path``."""
    if path is None:
        return False
    probe = WorkerLock(path)
    if probe.acquire():
        probe.release()
        return False
    return True


def try_lock(path: Path | None) -> WorkerLock | None:
    """Acquire without waiting. None when another holder has it; a no-op lock for a file-less database."""
    lock = WorkerLock(path) if path is not None else None
    if lock is not None and not lock.acquire():
        return None
    return lock or _NO_FILE


def worker_holds_lock(db_url: str, profile_key: str) -> bool:
    """True while some live process (in any Callosum instance) is building this index."""
    return held_elsewhere(lock_path(db_url, profile_key))


_NO_FILE = WorkerLock(None)  # stands in for a lock no other process could contend for
