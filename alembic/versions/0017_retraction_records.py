"""Retraction Watch local mirror (inc 132): the ``retraction_records`` table — a downloaded snapshot of the
Crossref-hosted Retraction Watch Database that the retraction producer matches DOIs against offline.

Additive + idempotent (like 0002-0016): a fresh DB already has the table from 0001's ``metadata.create_all``, so
the create is guarded and skipped there; an existing DB gets it here.

Revision ID: 0017_retraction_records
Revises: 0016_paper_findings
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017_retraction_records"
down_revision = "0016_paper_findings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "retraction_records" not in inspector.get_table_names():
        op.create_table(
            "retraction_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("original_doi", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("nature", sa.String(length=100)),
            sa.Column("date", sa.String(length=40)),
            sa.Column("reason", sa.Text()),
            sa.Column("notice_doi", sa.String(length=255)),
            sa.Column("notice_url", sa.Text()),
            sa.Column("retrieved_at", sa.String(length=40), nullable=False),
        )
        op.create_index("ix_retraction_records_original_doi", "retraction_records", ["original_doi"])


def downgrade() -> None:  # no-op (forward-only, like the rest)
    pass
