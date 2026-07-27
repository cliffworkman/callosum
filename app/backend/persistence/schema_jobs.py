"""Generic async-job bookkeeping tables (``jobs`` + ``job_errors``).

Split out of ``schema.py`` (inc 400 — that file crossed the 600-line cap when the new
``paper_statcheck_cache`` table landed) to keep it under rule #1's cap. Imports the shared
``metadata``/``enum_check`` from ``schema_base`` — NOT from ``schema`` — so there is no circular
import; ``schema.py`` re-exports these names, so ``from app.backend.persistence.schema import jobs``
keeps working.
"""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, func

from app.backend.persistence.schema_base import enum_check, metadata

JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")

jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("job_type", String(100), nullable=False),
    Column("status", String(50), nullable=False),
    Column("input_json", JSON),
    Column("output_json", JSON),
    Column("progress_json", JSON),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("started_at", DateTime),
    Column("finished_at", DateTime),
    enum_check("status", JOB_STATUSES, "job_status_valid"),
)

job_errors = Table(
    "job_errors",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("message", Text, nullable=False),
    Column("details_json", JSON),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_job_errors_job_id", "job_id"),
)
