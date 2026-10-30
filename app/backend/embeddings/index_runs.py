"""Read/write the durable index-build row (``embedding_index_runs``) and derive its truthful state (inc 610).

The supervisor and the worker share this module. All writes are short ``run_write`` units; the worker's progress
checkpoint is written inside the same transaction as the vectors it describes (``checkpoint``), so the row can
never claim a batch that was rolled back. Counts here are snapshots: ``reconcile_counts`` re-derives them from the
``embeddings`` table, which is the only authority on what is indexed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Connection, Engine, insert, select, update

from app.backend.embeddings.profiles import EmbeddingProfile, profile_coverage
from app.backend.persistence.schema import embedding_index_runs
from app.backend.persistence.sqlite_retry import run_write

ACTIVE_STATES = ("queued", "running", "pausing", "retrying", "waiting_resources")
_DETAIL_CAP = 400
_DIAGNOSTIC_CAP = 1500


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_run(conn: Connection, profile_key: str) -> dict | None:
    row = conn.execute(select(embedding_index_runs).where(embedding_index_runs.c.profile_key == profile_key)).mappings()
    found = row.first()
    return dict(found) if found else None


def list_runs(conn: Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(select(embedding_index_runs)).mappings()]


def _bounded(value: str | None, cap: int) -> str | None:
    return None if value is None else value[:cap]


def update_run(engine: Engine, profile_key: str, **values: object) -> None:
    if "failure_detail" in values:
        values["failure_detail"] = _bounded(values["failure_detail"], _DETAIL_CAP)  # type: ignore[arg-type]
    if "diagnostic" in values:
        values["diagnostic"] = _bounded(values["diagnostic"], _DIAGNOSTIC_CAP)  # type: ignore[arg-type]
    values["updated_at"] = now()

    def write(conn: Connection) -> None:
        conn.execute(
            update(embedding_index_runs).where(embedding_index_runs.c.profile_key == profile_key).values(**values)
        )

    run_write(engine, write)


def upsert_requested(engine: Engine, profile: EmbeddingProfile, *, batch_size: int) -> dict:
    """Record the user's request to run (start or manual resume): resets the retry budget, keeps everything else.

    A manual request always clears a terminal failure or cancellation -- that is the explicit Resume action.
    """

    def write(conn: Connection) -> dict:
        existing = get_run(conn, profile.key)
        coverage = profile_coverage(conn, profile)
        values = {
            "model_version": profile.model_version,
            "state": "queued",
            "intent": "run",
            "eligible_chunks": coverage["eligible_chunks"],
            "indexed_chunks": coverage["indexed_chunks"],
            "failures_without_progress": 0,
            "next_retry_at": None,
            "failure_kind": None,
            "failure_detail": None,
            "updated_at": now(),
        }
        if existing is None:
            conn.execute(insert(embedding_index_runs).values(profile_key=profile.key, batch_size=batch_size, **values))
        else:
            if existing["model_version"] != profile.model_version:
                values["batch_size"] = batch_size  # a different model version is a different build
            conn.execute(
                update(embedding_index_runs).where(embedding_index_runs.c.profile_key == profile.key).values(**values)
            )
        return get_run(conn, profile.key) or {}

    return run_write(engine, write)


def reconcile_counts(engine: Engine, profile: EmbeddingProfile) -> dict:
    """Re-derive eligible/indexed from stored vectors (never from a progress callback) and save the snapshot."""

    def write(conn: Connection) -> dict:
        coverage = profile_coverage(conn, profile)
        conn.execute(
            update(embedding_index_runs)
            .where(embedding_index_runs.c.profile_key == profile.key)
            .values(
                eligible_chunks=coverage["eligible_chunks"],
                indexed_chunks=coverage["indexed_chunks"],
                updated_at=now(),
            )
        )
        return coverage

    return run_write(engine, write)


def claim_for_worker(engine: Engine, profile_key: str, *, token: str, pid: int) -> bool:
    """Compare-and-set: only the worker whose token the supervisor recorded may take the row."""

    def write(conn: Connection) -> bool:
        result = conn.execute(
            update(embedding_index_runs)
            .where(embedding_index_runs.c.profile_key == profile_key, embedding_index_runs.c.worker_token == token)
            .values(worker_pid=pid, state="running", heartbeat_at=now(), updated_at=now())
        )
        return result.rowcount == 1

    return run_write(engine, write)


def checkpoint(
    conn: Connection, profile_key: str, *, token: str, added: int, batch_size: int, rss_mb: int | None
) -> None:
    """Called inside the batch's own transaction: progress, heartbeat and batch size commit with the vectors."""
    row = conn.execute(
        select(embedding_index_runs.c.indexed_chunks, embedding_index_runs.c.peak_worker_rss_mb).where(
            embedding_index_runs.c.profile_key == profile_key, embedding_index_runs.c.worker_token == token
        )
    ).first()
    if row is None:
        return  # superseded worker: its vectors are still valid, but it no longer owns the row
    stamp = now()
    conn.execute(
        update(embedding_index_runs)
        .where(embedding_index_runs.c.profile_key == profile_key)
        .values(
            indexed_chunks=int(row[0]) + added,
            heartbeat_at=stamp,
            last_checkpoint_at=stamp,
            batch_size=batch_size,
            peak_worker_rss_mb=max(int(row[1] or 0), int(rss_mb or 0)) or None,
            updated_at=stamp,
        )
    )


def heartbeat(engine: Engine, profile_key: str, *, token: str) -> None:
    def write(conn: Connection) -> None:
        conn.execute(
            update(embedding_index_runs)
            .where(embedding_index_runs.c.profile_key == profile_key, embedding_index_runs.c.worker_token == token)
            .values(heartbeat_at=now())
        )

    run_write(engine, write)


def intent_of(engine: Engine, profile_key: str) -> str | None:
    with engine.connect() as conn:
        return conn.execute(
            select(embedding_index_runs.c.intent).where(embedding_index_runs.c.profile_key == profile_key)
        ).scalar_one_or_none()
