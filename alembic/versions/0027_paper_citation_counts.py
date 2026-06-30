"""Per-paper OpenAlex cited-by count (inc 210, A2): ``paper_citation_counts`` — a refreshable external metric
stored separately from the canonical ``papers`` row. Backlog #28-adjacent / A2.

Additive + idempotent (like 0002-0025): a fresh DB already has the table from 0001's ``metadata.create_all``
(it's registered on the shared metadata via schema_findings), so the create is guarded and skipped there; an
existing DB gets it here. Downgrade is a no-op (0001's metadata loop drops it; downgrades aren't supported).

Revision ID: 0027_paper_citation_counts
Revises: 0026_chunks_fts
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0027_paper_citation_counts"
down_revision = "0026_chunks_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "paper_citation_counts" in set(sa.inspect(bind).get_table_names()):
        return  # already built (fresh DB via create_all)
    op.create_table(
        "paper_citation_counts",
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("cited_by_count", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
    )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
