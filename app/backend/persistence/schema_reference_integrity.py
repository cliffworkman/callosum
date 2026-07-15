"""Reference-integrity tables for the Theory-pane Meta Reference List.

The entity identity is reusable across the library, but review state is deliberately scoped to the
specific citing-paper x reference-instance. A review applies to one active signal-set fingerprint only; a
materially changed signal set gets a fresh unreviewed row instead of inheriting an older dismissal.
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
    Text,
    UniqueConstraint,
    func,
)

from app.backend.persistence.schema_base import metadata

REFERENCE_REVIEW_STATES = ("unreviewed", "dismissed", "confirmed_problem")


reference_entities = Table(
    "reference_entities",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("normalized_key", String(255), nullable=False),
    Column("doi", String(255)),
    Column("openalex_work_id", String(255)),
    Column("semantic_scholar_paper_id", String(255)),
    Column("title", Text),
    Column("authors_json", JSON),
    Column("year", Integer),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("normalized_key", name="uq_reference_entities_normalized_key"),
    Index("ix_reference_entities_doi", "doi"),
)

reference_instances = Table(
    "reference_instances",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("citing_paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("reference_entity_id", ForeignKey("reference_entities.id", ondelete="SET NULL")),
    Column("instance_key", String(64), nullable=False),
    Column("source", String(60), nullable=False),
    Column("source_ordinal", Integer, nullable=False),
    Column("raw_text", Text, nullable=False),
    Column("title", Text),
    Column("authors_json", JSON),
    Column("year", Integer),
    Column("doi", String(255)),
    Column("context_json", JSON),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("citing_paper_id", "instance_key", name="uq_reference_instances_paper_key"),
    Index("ix_reference_instances_paper", "citing_paper_id"),
    Index("ix_reference_instances_entity", "reference_entity_id"),
)

reference_signals = Table(
    "reference_signals",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("citation_instance_id", ForeignKey("reference_instances.id", ondelete="CASCADE"), nullable=False),
    Column("detector_kind", String(60), nullable=False),
    Column("detector_status", String(60), nullable=False),
    Column("evidence_json", JSON, nullable=False),
    Column("source", String(100), nullable=False),
    Column("snapshot_marker", String(255), nullable=False),
    Column("signal_key", String(64), nullable=False),
    Column("detected_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint(
        "citation_instance_id", "detector_kind", "signal_key", name="uq_reference_signals_instance_kind_key"
    ),
    Index("ix_reference_signals_instance", "citation_instance_id"),
)

reference_reviews = Table(
    "reference_reviews",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("citation_instance_id", ForeignKey("reference_instances.id", ondelete="CASCADE"), nullable=False),
    Column("signal_fingerprint", String(64), nullable=False),
    Column("state", String(30), nullable=False, server_default="unreviewed"),
    Column("reviewed_at", DateTime),
    Column("reference_entity_id", Integer),
    Column("review_snapshot_json", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint(
        "state IN ('unreviewed', 'dismissed', 'confirmed_problem')",
        name="reference_review_state_valid",
    ),
    UniqueConstraint("citation_instance_id", "signal_fingerprint", name="uq_reference_reviews_instance_fingerprint"),
    Index("ix_reference_reviews_instance", "citation_instance_id"),
)
