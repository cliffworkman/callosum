"""Schema owned by the registration-reference/comparison workflow."""

from sqlalchemy import (
    Boolean,
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

paper_registration_references = Table(
    "paper_registration_references",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("attachment_id", ForeignKey("attachments.id", ondelete="CASCADE")),
    Column("provider", String(100), nullable=False),
    Column("external_id", String(500), nullable=False),
    Column("canonical_url", Text),
    Column("visible_text", Text),
    Column("evidence_snippet", Text),
    Column("page", Integer),
    Column("extraction_method", String(100), nullable=False),
    Column("evidence_class", String(100), nullable=False),
    Column("explicitly_printed", Boolean, nullable=False, server_default="0"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint(
        "paper_id",
        "attachment_id",
        "provider",
        "external_id",
        "extraction_method",
        name="uq_registration_reference_source",
    ),
    CheckConstraint("page IS NULL OR page >= 1", name="registration_reference_page_positive"),
    Index("ix_registration_references_paper_id", "paper_id"),
    Index("ix_registration_references_attachment_id", "attachment_id"),
)
