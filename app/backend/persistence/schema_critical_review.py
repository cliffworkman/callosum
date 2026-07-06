"""Critical-review candidate store (backlog #12).

A `critical_review_candidates` row is an AI-proposed (Tier-2) critique of a single paper — physically isolated
from any trusted signal, exactly like inc-259's `ma_proposals`: it exists only as a candidate a human accepts or
rejects. Split onto the shared `schema_base` metadata (the inc-137 leaf pattern) and re-exported from `schema.py`.
Every candidate carries its verbatim anchor quote (the #13 auditability bar); a rejected candidate's `signature`
is remembered so it is never re-proposed.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text, func

from app.backend.persistence.schema_base import enum_check, metadata

CRITICAL_REVIEW_STATUSES = ("pending", "accepted", "rejected")

critical_review_candidates = Table(
    "critical_review_candidates",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("concern", Text, nullable=False),  # the critique, about the WORK — never the authors (A-A veto)
    Column("anchor_quote", Text, nullable=False),  # verbatim from the paper (#13 bar: canonical_text_contains)
    Column("page", Integer),
    Column("stance", String(20)),  # the NLI stance label backing the concern, when applicable
    Column("confidence", Float),
    Column("status", String(20), nullable=False, server_default="pending"),
    Column("signature", String(80), nullable=False),  # stable hash → a rejected concern is never re-proposed
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("status", CRITICAL_REVIEW_STATUSES, "cr_status_valid"),
    Index("ix_cr_candidates_paper_id", "paper_id"),
)
