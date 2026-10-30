"""Durable lifecycle of one embedding-profile index build per library (inc 610).

The in-memory ``JobStore`` forgets everything when the process dies, and an externally killed worker never runs
its cleanup code. This row survives both: it records who owns the build, what the user asked for, what the last
attempt did and why it stopped, so the next app launch can reconcile it against the vectors actually stored.
It never stands in for coverage: indexed counts here are snapshots, and completion is always re-derived from the
``embeddings`` table.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Table, Text, func

from app.backend.persistence.schema_base import enum_check, metadata

INDEX_RUN_STATES = (
    "queued",
    "running",
    "pausing",
    "paused",
    "waiting_resources",
    "interrupted",
    "retrying",
    "failed",
    "completed",
    "cancelled",
)
INDEX_RUN_INTENTS = ("run", "pause", "cancel")

embedding_index_runs = Table(
    "embedding_index_runs",
    metadata,
    Column("profile_key", String(40), primary_key=True),  # one build per profile per library
    Column("model_version", Text, nullable=False),
    Column("state", String(24), nullable=False),
    Column("intent", String(12), nullable=False),
    Column("eligible_chunks", Integer, nullable=False, server_default="0"),
    Column("indexed_chunks", Integer, nullable=False, server_default="0"),
    Column("batch_size", Integer, nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("failures_without_progress", Integer, nullable=False, server_default="0"),
    Column("worker_pid", Integer),
    Column("worker_token", String(40)),
    Column("worker_started_at", DateTime),
    Column("heartbeat_at", DateTime),
    Column("last_checkpoint_at", DateTime),
    Column("next_retry_at", DateTime),
    Column("failure_kind", String(40)),
    Column("failure_detail", Text),  # user-facing, sanitized: no passages, no paths
    Column("diagnostic", Text),  # bounded technical tail (exit code, exception class); never passage text
    Column("peak_worker_rss_mb", Integer),
    Column("min_available_mb", Integer),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("state", INDEX_RUN_STATES, "ck_embedding_index_runs_state"),
    enum_check("intent", INDEX_RUN_INTENTS, "ck_embedding_index_runs_intent"),
)
