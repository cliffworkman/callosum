"""Per-paper saved repeated-values checks (inc 469) — an append-only, user-curated log, mirroring
schema_debit_checks.py's shape exactly."""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Table, func

from app.backend.persistence.schema_base import metadata

paper_duplicate_value_checks = Table(
    "paper_duplicate_value_checks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("label", String(120)),  # optional user note, e.g. "Table 2, all reported means"
    Column("values_json", JSON, nullable=False),  # verbatim entered strings, in order
    Column("result_json", JSON, nullable=False),  # the server-recomputed DuplicateValuesComputeResponse
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_paper_duplicate_value_checks_paper_id", "paper_id"),
)
