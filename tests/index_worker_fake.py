"""Subprocess entry for inc 610's recovery tests: the production worker ``main`` with a fake encoder.

Launched by ``SubprocessLauncher(config, module="tests.index_worker_fake")`` so the tests exercise a real separate
process -- real exit codes, real external kills -- without loading any model. ``CALLOSUM_FAKE_INDEX_MODE``:
``normal``; ``slow`` (sleeps per batch so a test can kill it mid-build); ``oom`` (raises MemoryError);
``missing`` (raises OSError like an uncached checkpoint).

Inc 616 disk simulation, without touching the real disk: ``CALLOSUM_FAKE_FREE_BYTES`` makes the worker's free-disk
probe report that many bytes; ``CALLOSUM_FAKE_MAX_PAGES`` caps the worker's own SQLite connections with
``PRAGMA max_page_count`` so a write past it fails with SQLite's genuine ``database or disk is full``.
"""

from __future__ import annotations

import os
import sys
import time

from sqlalchemy import event

from app.backend.embeddings import disk_guard, index_worker
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.persistence import database


class FakeProfileEncoder:
    def __init__(self, profile, *, local_files_only: bool, batch_size: int) -> None:  # type: ignore[no-untyped-def]
        self.name = profile.model_name
        self.version = profile.model_version
        self.normalization = profile.normalization
        self.dimension = profile.dimension
        self.lazy_indexing = False
        self.mode = os.environ.get("CALLOSUM_FAKE_INDEX_MODE", "normal")

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        if self.mode == "oom":
            raise MemoryError("simulated allocation failure")
        if self.mode == "missing":
            raise OSError("simulated: checkpoint not in the local cache")
        if self.mode == "slow":
            time.sleep(0.4)
        return [[1.0] + [0.0] * (self.dimension - 1) for _ in texts]

    encode_documents = encode_texts


def _simulate_disk() -> None:
    free = os.environ.get("CALLOSUM_FAKE_FREE_BYTES")
    if free is not None:
        usage = type("Usage", (), {"free": int(free)})()
        original_check = disk_guard.check
        disk_guard.check = lambda *a, **k: original_check(*a, **{**k, "usage": lambda _path: usage})
    pages = os.environ.get("CALLOSUM_FAKE_MAX_PAGES")
    if pages is not None:
        original_make = database.make_engine

        def capped(*args, **kwargs):  # type: ignore[no-untyped-def]
            engine = original_make(*args, **kwargs)
            event.listen(engine, "connect", lambda conn, _r: conn.execute(f"PRAGMA max_page_count = {int(pages)}"))
            return engine

        database.make_engine = capped


if __name__ == "__main__":
    _simulate_disk()
    sys.exit(index_worker.main(model_factory=FakeProfileEncoder, vector_store_factory=SQLiteVecVectorStore))
