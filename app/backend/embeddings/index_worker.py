"""The index-build worker: one supervised process that loads one profile's model and indexes in bounded batches.

Run as ``python -m app.backend.embeddings.index_worker`` by ``IndexSupervisor`` (inc 610), never by hand. Keeping
the model and its inference in a separate process means a memory spike, a native crash or an external kill takes
down only this worker: the API server, the Library UI and Status keep running, and the durable row plus the
stored vectors are all the next attempt needs.

Exit codes are the worker's half of the contract. A process killed from outside returns none of them (a signal or
an arbitrary code), which the supervisor records as an interruption of unknown cause rather than guessing.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.backend.embeddings import index_runs
from app.backend.embeddings.index_lock import WorkerLock, lock_path
from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.profile_index import index_chunk_batch, pending_chunk_ids, repair_partial_vectors
from app.backend.embeddings.profiles import EmbeddingProfile, get_profile
from app.backend.embeddings.resources import ResourcePolicy, ResourceSnapshot, measure, process_rss_mb
from app.backend.embeddings.vector_store import VectorStore

EXIT_COMPLETE = 0
EXIT_UNEXPECTED = 1
EXIT_STOPPED = 3  # the user's pause/cancel intent was honoured between batches
EXIT_MODEL = 65  # model unavailable, corrupt, or contract mismatch: never retried automatically
EXIT_DATABASE_BUSY = 69
EXIT_ORPHANED = 70  # the owning app went away
EXIT_NOT_OWNER = 71  # another worker holds the row
EXIT_RESOURCES = 75  # low memory before a batch, or an allocation failure during one; work so far is committed

HEARTBEAT_SECONDS = 15.0


@dataclass
class WorkerOutcome:
    exit_code: int
    chunks_indexed: int = 0
    failure_kind: str | None = None
    diagnostic: str | None = None


def _scrub(message: str) -> str:
    """Technical diagnostics never carry the user's home path (and never passage text: none is ever logged)."""
    home = os.path.expanduser("~")
    return message.replace(home, "~") if home and home != "~" else message


def _is_allocation_failure(exc: BaseException) -> bool:
    if isinstance(exc, MemoryError):
        return True
    text = str(exc).lower()
    return isinstance(exc, RuntimeError) and ("alloc" in text or "out of memory" in text or "not enough memory" in text)


def _inference_mode():  # type: ignore[no-untyped-def]
    try:
        import torch

        return torch.inference_mode()
    except ImportError:  # fake models in tests
        return contextlib.nullcontext()


def run_worker(
    engine,  # type: ignore[no-untyped-def]
    *,
    profile: EmbeddingProfile,
    token: str,
    model: EmbeddingModel,
    vector_store: VectorStore,
    batch_size: int,
    probe: Callable[[], ResourceSnapshot] = measure,
    policy: ResourcePolicy | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> WorkerOutcome:
    """Index until done, stopped, or out of headroom. Every committed batch is final; nothing else is."""
    from sqlalchemy.exc import OperationalError

    if not index_runs.claim_for_worker(engine, profile.key, token=token, pid=os.getpid()):
        return WorkerOutcome(EXIT_NOT_OWNER, failure_kind="not_owner")
    policy = policy or ResourcePolicy.for_machine(probe())
    stop_beat = threading.Event()

    def beat() -> None:
        while not stop_beat.wait(HEARTBEAT_SECONDS):
            with contextlib.suppress(Exception):
                index_runs.heartbeat(engine, profile.key, token=token)

    threading.Thread(target=beat, name="index-heartbeat", daemon=True).start()
    done = 0
    try:
        repair_partial_vectors(engine, model, vector_store=vector_store, dimension=profile.dimension)
        queue = pending_chunk_ids(engine, model)
        size = max(1, int(batch_size))
        for start in range(0, len(queue), size):
            if index_runs.intent_of(engine, profile.key) != "run" or (should_stop is not None and should_stop()):
                return WorkerOutcome(EXIT_STOPPED, done)
            if policy.should_pause(probe()):
                return WorkerOutcome(EXIT_RESOURCES, done, "memory_pressure")
            batch = queue[start : start + size]

            def commit(conn, added: int) -> None:  # type: ignore[no-untyped-def]
                index_runs.checkpoint(
                    conn, profile.key, token=token, added=added, batch_size=size, rss_mb=process_rss_mb()
                )

            with _inference_mode():
                index_chunk_batch(engine, model=model, vector_store=vector_store, chunk_ids=batch, on_commit=commit)
            done += len(batch)
        return WorkerOutcome(EXIT_COMPLETE, done)
    except Exception as exc:  # classified below; the message is scrubbed and bounded by the repo
        diagnostic = _scrub(f"{type(exc).__name__}: {exc}")
        if _is_allocation_failure(exc):
            return WorkerOutcome(EXIT_RESOURCES, done, "allocation_failure", diagnostic)
        if isinstance(exc, OperationalError) and "locked" in str(exc).lower():
            return WorkerOutcome(EXIT_DATABASE_BUSY, done, "database_busy", diagnostic)
        from app.backend.embeddings.models import EmbeddingModelConfigurationError

        # The wrapper loads weights lazily, so a missing/corrupt checkpoint surfaces on the first batch.
        if isinstance(exc, EmbeddingModelConfigurationError) or (isinstance(exc, OSError) and done == 0):
            return WorkerOutcome(EXIT_MODEL, done, "model_unavailable", diagnostic)
        return WorkerOutcome(EXIT_UNEXPECTED, done, "unexpected_error", diagnostic)
    finally:
        stop_beat.set()


def _watch_parent(parent_pid: int) -> None:
    """Exit if the owning app disappears, so a crashed or killed app never leaves a worker holding the model.

    Windows waits on a handle to the parent (which pins its identity against PID reuse); POSIX notices being
    re-parented. An uncommitted batch is rolled back by SQLite; every committed batch stays.
    """
    if sys.platform == "win32":
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x00100000, False, int(parent_pid))  # SYNCHRONIZE
        if not handle:
            os._exit(EXIT_ORPHANED)
        kernel32.WaitForSingleObject(ctypes.c_void_p(handle), 0xFFFFFFFF)  # INFINITE: returns when it exits
        os._exit(EXIT_ORPHANED)
    while True:
        if os.getppid() != parent_pid:
            os._exit(EXIT_ORPHANED)
        time.sleep(2.0)


def load_profile_model(profile: EmbeddingProfile, *, local_files_only: bool, batch_size: int) -> EmbeddingModel:
    from app.backend.model_runtime import ModelRuntimeRegistry

    return ModelRuntimeRegistry().get_embedding_model(  # type: ignore[return-value]
        name=profile.model_name,
        version=profile.model_version,
        normalization=profile.normalization,
        batch_size=batch_size,
        revision=profile.revision,
        query_prefix=profile.query_prefix,
        document_prefix=profile.document_prefix,
        expected_pooling=profile.pooling,
        expected_max_seq_length=profile.max_seq_length,
        lazy_indexing=profile.lazy_indexing,
        profile_key=profile.key,
        local_files_only=local_files_only,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="index_worker")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, model_factory=None, vector_store_factory=None) -> int:  # type: ignore[no-untyped-def]
    """Process entry. ``model_factory``/``vector_store_factory`` exist for the subprocess tests' fake worker
    module; production passes neither and loads the pinned profile checkpoint."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    threading.Thread(target=_watch_parent, args=(args.parent_pid,), name="parent-watch", daemon=True).start()
    from app.backend.embeddings.vector_store import SQLiteVecVectorStore
    from app.backend.persistence.database import make_engine

    path = lock_path(args.db_url, args.profile)
    lock = WorkerLock(path) if path is not None else None
    if lock is not None and not lock.acquire():
        return EXIT_NOT_OWNER  # another live worker (any Callosum process) is building this index
    engine = make_engine(args.db_url)
    profile = get_profile(args.profile)
    try:
        if args.threads > 0:
            with contextlib.suppress(ImportError):
                import torch

                torch.set_num_threads(args.threads)
        try:
            model = (model_factory or load_profile_model)(
                profile, local_files_only=args.local_files_only, batch_size=args.batch_size
            )
        except Exception as exc:
            outcome = WorkerOutcome(
                EXIT_MODEL, failure_kind="model_unavailable", diagnostic=_scrub(f"{type(exc).__name__}: {exc}")
            )
        else:
            store = (vector_store_factory or SQLiteVecVectorStore)()
            outcome = run_worker(
                engine, profile=profile, token=args.token, model=model, vector_store=store, batch_size=args.batch_size
            )
        if outcome.failure_kind is not None:
            with contextlib.suppress(Exception):
                index_runs.update_run(
                    engine, profile.key, failure_kind=outcome.failure_kind, diagnostic=outcome.diagnostic
                )
        return outcome.exit_code
    finally:
        engine.dispose()
        if lock is not None:
            lock.release()  # also released by the OS if this process is killed


if __name__ == "__main__":
    sys.exit(main())
