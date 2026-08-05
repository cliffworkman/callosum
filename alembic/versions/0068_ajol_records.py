"""AJOL local mirror: the ajol_records table (backlog #40) -- a third-party CC-BY-4.0 compiled snapshot of AJOL
(African Journals Online) journal metadata (Alonso-Álvarez 2025, Zenodo DOI 10.5281/zenodo.14899380), matched to
Publishers candidates offline by ISSN/EISSN.

Additive + idempotent (like 0002-0067): guarded create, skipped on a fresh DB (0001 already has it via
metadata.create_all).

Revision ID: 0068_ajol_records
Revises: 0067_usage_events
Create Date: 2026-08-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0068_ajol_records"
down_revision = "0067_usage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "ajol_records" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "ajol_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("issn", sa.String(length=20)),
            sa.Column("eissn", sa.String(length=20)),
            sa.Column("journal", sa.Text()),
            sa.Column("country", sa.String(length=80)),
            sa.Column("jpps_status", sa.String(length=40)),
            sa.Column("is_diamond", sa.Boolean()),
            sa.Column("source_url", sa.Text()),
            sa.Column("retrieved_at", sa.String(length=40), nullable=False),
        )
        op.create_index("ix_ajol_records_issn", "ajol_records", ["issn"])
        op.create_index("ix_ajol_records_eissn", "ajol_records", ["eissn"])


def downgrade() -> None:
    # Additive table, like every other retraction/findings-cluster migration -- 0001 owns eventual teardown.
    pass
