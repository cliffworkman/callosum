"""Additional per-paper URLs, split from schema.py to keep the core schema module small."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint, func

from app.backend.persistence.schema_base import metadata

paper_urls = Table(
    "paper_urls",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("url", Text, nullable=False),
    Column("label", String(120)),
    Column("position", Integer, nullable=False, server_default="0"),
    Column("source", String(100), nullable=False, server_default="user"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("paper_id", "url", name="uq_paper_urls_paper_url"),
    Index("ix_paper_urls_paper_id", "paper_id"),
)
