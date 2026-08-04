"""Reference-integrity signals for a WIP manuscript's linked Library references (backlog #48).

Deliberately NOT a retrofit of `reference_entities`/`reference_instances` (Library-paper reference-integrity,
`schema_reference_integrity.py`) or of the generic `wip_tool_runs`/`wip_findings` (`schema_wip_provenance.py`).
`reference_instances.citing_paper_id` is a NOT NULL FK to `papers.id` -- a `wip_manuscripts.id` cannot go
there. The generic WIP tables assume a manuscript-*file* content basis (`wip_tool_runs.snapshot_id`/`file_id`,
`wip_findings.file_id` are all NOT NULL) -- this tool's staleness dimension is `wip_references` cited-set
membership, which has nothing to do with file text. `wip_references.id` is already the canonical, deduped
`(manuscript_id, paper_id)` identity (its own unique constraint), so there is no need for an
entities/instances dedup layer either -- signals attach directly to a `wip_references` row.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)

from app.backend.persistence.schema_base import metadata

WIP_REFERENCE_REVIEW_STATES = ("unreviewed", "dismissed", "confirmed_problem")

wip_reference_signals = Table(
    "wip_reference_signals",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("manuscript_id", Integer, ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False),
    Column("reference_id", Integer, ForeignKey("wip_references.id", ondelete="CASCADE"), nullable=False),
    Column("detector_kind", String(60), nullable=False),
    Column("detector_status", String(60), nullable=False),
    Column("evidence_json", JSON, nullable=False),
    Column("source", String(100), nullable=False),
    Column("snapshot_marker", String(255), nullable=False),
    Column("signal_key", String(64), nullable=False),
    Column("detected_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("reference_id", "detector_kind", "signal_key", name="uq_wip_reference_signals_ref_kind_key"),
    Index("ix_wip_reference_signals_reference", "reference_id"),
    Index("ix_wip_reference_signals_manuscript", "manuscript_id"),
)

wip_reference_reviews = Table(
    "wip_reference_reviews",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("reference_id", Integer, ForeignKey("wip_references.id", ondelete="CASCADE"), nullable=False),
    Column("signal_fingerprint", String(64), nullable=False),
    Column("state", String(30), nullable=False, server_default="unreviewed"),
    Column("reviewed_at", DateTime),
    Column("review_snapshot_json", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint(
        "state IN ('unreviewed', 'dismissed', 'confirmed_problem')",
        name="wip_reference_review_state_valid",
    ),
    UniqueConstraint("reference_id", "signal_fingerprint", name="uq_wip_reference_reviews_ref_fingerprint"),
    Index("ix_wip_reference_reviews_reference", "reference_id"),
)
