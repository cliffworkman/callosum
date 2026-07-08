"""Reversible-merge bookkeeping — the merge_operations undo-snapshot table (backlog #17/#16).

Split onto the shared ``schema_base`` metadata (rule #1; the schema_findings/schema_summaries pattern);
re-exported from ``schema.py`` so ``from …schema import merge_operations`` keeps working. One row per merge:
the canonical survivor, the merged-away paper, a self-contained JSON reversal snapshot, and a status the
un-merge flips to ``undone``.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, func

from app.backend.persistence.schema_base import enum_check, metadata

MERGE_STATUSES = ("active", "undone")

merge_operations = Table(
    "merge_operations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("canonical_paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("merged_paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("snapshot_json", Text, nullable=False),
    Column("status", String(20), nullable=False, server_default="active"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("undone_at", DateTime),
    enum_check("status", MERGE_STATUSES, "merge_status_valid"),
    Index("ix_merge_operations_canonical", "canonical_paper_id"),
)
