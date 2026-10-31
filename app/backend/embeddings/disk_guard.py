"""Free-disk guard for embedding-profile index builds (inc 616).

An Arctic S build adds vectors to the library database for every eligible passage: roughly 1.5-3.7 GB for a
4,000-paper library. An unattended build must never knowingly fill the disk holding the library: that endangers
other applications and the library's own WAL checkpoint. This module answers one question before every batch --
is there room for the next few batches *and* a reserve that nothing here may consume? -- and recognises a full
disk when SQLite reports one anyway.

The floor is deliberately additive: ``reserve + WAL allowance + 2 x (next LOOKAHEAD_BATCHES batches)``. The audit's
first sketch, ``max(1 GB, 2 x next batches)``, lets a batch eat into the reserve (with the max, the reserve and the
in-flight need overlap instead of stacking) and leaves no room for WAL growth. The requirement covers only the
next bounded step, never the whole build, so a large library on a small disk still progresses in increments; the
full estimate is reported separately and is never a precondition.

The guard measures the filesystem that holds the database file. The model cache may live on a different volume;
its downloads keep their own check in ``model_provisioning`` (which reuses ``free_bytes`` from here), and neither
check can block the other. Nothing here ever deletes data to make room.
"""

from __future__ import annotations

import errno
import shutil
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import make_url

# Measured on a disposable synthetic library with the real sqlite-vec store and 384-dimension vectors (inc 616):
# 1,662 bytes of database growth per indexed passage (vector + embeddings row + index entries). Rounded up ~23%.
BYTES_PER_CHUNK = 2048
LOOKAHEAD_BATCHES = 4
# Written pages pass through the WAL before the checkpoint copies them into the main file: count them twice.
WAL_FACTOR = 2
# The autocheckpoint holds the WAL near 4 MB; a long reader pinning a snapshot can let it grow well past that.
WAL_ALLOWANCE_BYTES = 64 * 2**20
RESERVE_BYTES = 2**30  # left for the operating system, other applications and the library's own checkpoint
# A running worker is stopped (between SQLite transactions, so nothing committed is lost) if something else on
# the machine drives free space below this while a batch is in flight.
HARD_STOP_BYTES = 256 * 2**20
RECHECK_SECONDS = 60.0

DiskUsage = Callable[[Path], object]  # shutil.disk_usage-shaped: returns an object with ``.free``


def free_bytes(path: Path, usage: DiskUsage = shutil.disk_usage) -> int:
    """Free bytes on the filesystem that holds ``path`` (or its nearest existing ancestor)."""
    probe = Path(path)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return int(usage(probe).free)  # type: ignore[attr-defined]


def library_dir(db_url: str) -> Path | None:
    """The directory holding the SQLite file; None for a database without one (in-memory tests)."""
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return None
    return Path(url.database).resolve().parent


def required_free_bytes(batch_size: int) -> int:
    in_flight = max(1, int(batch_size)) * BYTES_PER_CHUNK * LOOKAHEAD_BATCHES * WAL_FACTOR
    return RESERVE_BYTES + WAL_ALLOWANCE_BYTES + in_flight


def estimated_remaining_bytes(remaining_chunks: int) -> int:
    return max(0, int(remaining_chunks)) * BYTES_PER_CHUNK


@dataclass(frozen=True)
class DiskCheck:
    ok: bool
    free_bytes: int | None  # None: unmeasurable (no file, or the probe failed) -- never blocks
    required_bytes: int
    estimated_remaining_bytes: int

    def row_values(self) -> dict[str, int | None]:
        """Numbers only: the durable row and the API never carry the library's path."""
        return {
            "disk_required_bytes": self.required_bytes,
            "disk_free_bytes": self.free_bytes,
            "disk_estimated_bytes": self.estimated_remaining_bytes,
        }


def check(db_url: str, *, batch_size: int, remaining_chunks: int, usage: DiskUsage | None = None) -> DiskCheck:
    required = required_free_bytes(batch_size)
    estimate = estimated_remaining_bytes(remaining_chunks)
    directory = library_dir(db_url)
    try:
        free = None if directory is None else free_bytes(directory, usage or shutil.disk_usage)
    except OSError:
        free = None  # an unreadable volume is not evidence of a full one; SQLITE_FULL still stops the batch
    return DiskCheck(free is None or free >= required, free, required, estimate)


def must_stop(db_url: str, usage: DiskUsage | None = None) -> bool:
    directory = library_dir(db_url)
    if directory is None:
        return False
    try:
        return free_bytes(directory, usage or shutil.disk_usage) < HARD_STOP_BYTES
    except OSError:
        return False


def is_disk_full(exc: BaseException) -> bool:
    """SQLite's SQLITE_FULL ("database or disk is full") or an OS ENOSPC, however deeply wrapped."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, OSError) and current.errno == errno.ENOSPC:
            return True
        if isinstance(current, sqlite3.Error) and (
            getattr(current, "sqlite_errorcode", None) == 13 or "database or disk is full" in str(current).lower()
        ):
            return True
        if "database or disk is full" in str(current).lower():
            return True
        current = getattr(current, "orig", None) or current.__cause__ or current.__context__
    return False
