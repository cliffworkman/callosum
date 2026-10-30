"""Subprocess entry for inc 610's recovery tests: the production worker ``main`` with a fake encoder.

Launched by ``SubprocessLauncher(config, module="tests.index_worker_fake")`` so the tests exercise a real separate
process -- real exit codes, real external kills -- without loading any model. ``CALLOSUM_FAKE_INDEX_MODE``:
``normal``; ``slow`` (sleeps per batch so a test can kill it mid-build); ``oom`` (raises MemoryError);
``missing`` (raises OSError like an uncached checkpoint).
"""

from __future__ import annotations

import os
import sys
import time

from app.backend.embeddings import index_worker
from app.backend.embeddings.vector_store import SQLiteVecVectorStore


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


if __name__ == "__main__":
    sys.exit(index_worker.main(model_factory=FakeProfileEncoder, vector_store_factory=SQLiteVecVectorStore))
