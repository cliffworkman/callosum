"""Summary / citation-mapping / evidence-quote tables — the verification-output core.

Split out of ``schema.py`` (inc 262) onto the shared ``schema_base`` ``metadata`` to keep it under the 600-line
cap (rule #1) — the inc-137 ``schema_findings`` pattern. Imports ONLY ``metadata`` + the shared CHECK helpers from
``schema_base`` (never from ``schema``), so there is no circular import; ``schema.py`` re-exports these names for
backward-compatibility. The ``chunk_id`` foreign keys reference ``chunks`` (defined in ``schema.py``) as a lazy
string FK, resolved against the shared metadata regardless of table-definition order.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    CheckConstraint,
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

from app.backend.persistence.schema_base import (
    CITATION_MAPPING_STATUSES,
    enum_check,
    metadata,
    non_empty_check,
)

summaries = Table(
    "summaries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("scope_type", String(100), nullable=False),
    Column("scope_ref_json", JSON),
    Column("content", Text),
    Column("overview_json", JSON),  # inc 124: per-sentence traceable Overview [{text, claim_ordinals:[int]}]
    # A nullable lifecycle keeps pre-494 rows backward-readable: NULL + an overview is treated as complete;
    # NULL without one is treated as not_requested, never as queued provider work.
    Column("overview_status", String(32)),
    Column("overview_updated_at", DateTime),
    Column(
        "imported_json", JSON
    ),  # B2 SP2 (inc 235): a RELAYED synthesis's self-contained display blob (status="imported")
    Column("generated_by", String(255)),
    Column("chunk_version_verified_against", String(255), nullable=False),
    Column("embedding_version_verified_against", String(255), nullable=False),
    Column("verification_version", String(255)),
    Column("status", String(100), nullable=False, server_default="created"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    non_empty_check("chunk_version_verified_against", "summary_chunk_version_non_empty"),
    non_empty_check("embedding_version_verified_against", "summary_embedding_version_non_empty"),
)

summary_sentences = Table(
    "summary_sentences",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("summary_id", ForeignKey("summaries.id", ondelete="CASCADE"), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("summary_id", "ordinal", name="uq_summary_sentences_summary_ordinal"),
    CheckConstraint("ordinal >= 0", name="summary_sentence_ordinal_nonnegative"),
)

citation_mappings = Table(
    "citation_mappings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("summary_sentence_id", ForeignKey("summary_sentences.id", ondelete="CASCADE"), nullable=False),
    Column("chunk_id", ForeignKey("chunks.id", ondelete="SET NULL")),
    Column("status", String(50), nullable=False),
    Column("chunk_version_verified_against", String(255), nullable=False),
    Column("embedding_version_verified_against", String(255), nullable=False),
    Column("verification_version", String(255)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("status", CITATION_MAPPING_STATUSES, "status_valid"),
    non_empty_check("chunk_version_verified_against", "mapping_chunk_version_non_empty"),
    non_empty_check("embedding_version_verified_against", "mapping_embedding_version_non_empty"),
    Index("ix_citation_mappings_sentence_id", "summary_sentence_id"),
    Index("ix_citation_mappings_chunk_id", "chunk_id"),
)

evidence_quotes = Table(
    "evidence_quotes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("citation_mapping_id", ForeignKey("citation_mappings.id", ondelete="CASCADE"), nullable=False),
    Column("chunk_id", ForeignKey("chunks.id", ondelete="SET NULL")),
    Column("quote_text", Text, nullable=False),
    Column("page_start", Integer),
    Column("page_end", Integer),
    Column("bbox_json", JSON),
    Column("retrieval_confidence", Float, nullable=False),
    Column("quote_confidence", Float, nullable=False),
    Column("support_confidence", Float, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("retrieval_confidence >= 0 AND retrieval_confidence <= 1", name="retrieval_confidence_0_1"),
    CheckConstraint("quote_confidence >= 0 AND quote_confidence <= 1", name="quote_confidence_0_1"),
    CheckConstraint("support_confidence >= 0 AND support_confidence <= 1", name="support_confidence_0_1"),
    CheckConstraint(
        "page_end IS NULL OR page_start IS NULL OR page_end >= page_start", name="evidence_page_end_after_start"
    ),
    Index("ix_evidence_quotes_mapping_id", "citation_mapping_id"),
)
