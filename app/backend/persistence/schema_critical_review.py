"""Critical-review candidate store (backlog #12).

A `critical_review_candidates` row is an AI-proposed (Tier-2) critique of a single paper — physically isolated
from any trusted signal, exactly like inc-259's `ma_proposals`: it exists only as a candidate a human accepts or
rejects. Split onto the shared `schema_base` metadata (the inc-137 leaf pattern) and re-exported from `schema.py`.
Every candidate carries its verbatim anchor quote (the #13 auditability bar); a rejected candidate's `signature`
is remembered so it is never re-proposed.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

from app.backend.persistence.schema_base import enum_check, metadata

CRITICAL_REVIEW_STATUSES = ("pending", "accepted", "rejected")
CRITICAL_REVIEW_TRIAGE_LABELS = ("prioritize", "uncertain", "likely_noise")

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
    # set critical review (#12): the model's related set papers for a cross-paper candidate — its FRAMING, not a
    # verified link (only the anchor_quote is #13-verified). NULL for single-paper candidates.
    Column("related_paper_ids_json", JSON),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("status", CRITICAL_REVIEW_STATUSES, "cr_status_valid"),
    Index("ix_cr_candidates_paper_id", "paper_id"),
)

# Optional, reversible LLM triage over a persisted Tier-2 candidate (mirrors
# registration_comparison_triage_annotations exactly). One row per candidate — candidates have no "run" grouping
# concept (accept/reject already act per-candidate-id, paper-agnostic), so this is keyed by candidate_id alone.
critical_review_candidate_triage = Table(
    "critical_review_candidate_triage",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("candidate_id", ForeignKey("critical_review_candidates.id", ondelete="CASCADE"), nullable=False),
    Column("label", String(40), nullable=False),
    Column("show_in_triage", Integer, nullable=False, server_default="0"),
    Column("rationale", Text),
    Column("concerns_json", JSON, nullable=False),
    Column("basis", Text),
    Column("provider_id", String(120), nullable=False),
    Column("model_id", String(200)),
    Column("prompt_version", String(120), nullable=False),
    Column("evidence_fingerprint", String(128), nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("label", CRITICAL_REVIEW_TRIAGE_LABELS, "cr_candidate_triage_label_valid"),
    UniqueConstraint("candidate_id", name="uq_cr_candidate_triage_candidate"),
    Index("ix_cr_candidate_triage_candidate", "candidate_id"),
)
