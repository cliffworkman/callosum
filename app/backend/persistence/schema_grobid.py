"""GROBID's own section structure (backlog #30 Stage 2) -- a sibling table to `chunks`, not a retrofit of it.
`chunks.section` (the pre-existing heuristic column) is never written by anything in this module; this is
additive, opt-in, richer data that coexists with it. See the provenance rule in the design doc."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Integer, Table, Text

from app.backend.persistence.schema_base import metadata

paper_sections = Table(
    "paper_sections",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("title", Text, nullable=False),  # verbatim from GROBID -- never normalized
    Column("section_kind", Text),  # nullable; the canonical family classify_section_title() derived, or None
    Column("page_start", Integer, nullable=False),
    Column("page_end", Integer, nullable=False),
    Column("order_index", Integer, nullable=False),
    Index("ix_paper_sections_paper_id", "paper_id"),
)
