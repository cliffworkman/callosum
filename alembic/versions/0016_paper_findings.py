"""Findings subsystem (inc 130): the ``paper_findings`` table — the shared FACT-vs-CANDIDATE store every METHODS
check emits into.

Additive + idempotent (like 0002-0015): a fresh DB already has the table from 0001's ``metadata.create_all``, so
the create is guarded and skipped there; an existing DB gets it here.

Revision ID: 0016_paper_findings
Revises: 0015_summary_overview
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0016_paper_findings"
down_revision = "0015_summary_overview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "paper_findings" not in inspector.get_table_names():
        op.create_table(
            "paper_findings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("tier", sa.String(length=20)),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("content_key", sa.String(length=64), nullable=False),
            sa.Column("review_state", sa.String(length=20)),
            sa.Column("review_reason", sa.Text()),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.UniqueConstraint("paper_id", "source", "content_key", name="uq_paper_findings_paper_source_key"),
            sa.Index("ix_paper_findings_paper_id", "paper_id"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
