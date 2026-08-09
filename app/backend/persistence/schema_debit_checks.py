"""Per-paper saved DEBIT checks (inc 467) — an append-only, user-curated log, mirroring
schema_grim_checks.py's paper_grim_checks shape exactly (a user may legitimately save the same
mean/SD/N combo twice under different labels, e.g. reported in the abstract vs. a table)."""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Table, func

from app.backend.persistence.schema_base import metadata

paper_debit_checks = Table(
    "paper_debit_checks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("label", String(120)),  # optional user note, e.g. "Table 2, treatment response rate"
    Column("mean", String(40), nullable=False),  # verbatim reported string (DebitRequest.mean shape)
    Column("sd", String(40), nullable=False),
    Column("n", Integer, nullable=False),
    Column("result_json", JSON, nullable=False),  # the server-recomputed DebitComputeResponse, frozen at save time
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_paper_debit_checks_paper_id", "paper_id"),
)
