"""TOP Factor local mirror: the top_factor_records table (backlog #40) -- a downloaded snapshot of the Center
for Open Science's per-journal transparency/openness rubric CSV, matched to Publishers candidates offline by
ISSN/EISSN.

Additive + idempotent (like 0002-0065): guarded create, skipped on a fresh DB (0001 already has it via
metadata.create_all).

Revision ID: 0066_top_factor_records
Revises: 0065_wip_reference_integrity
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0066_top_factor_records"
down_revision = "0065_wip_reference_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "top_factor_records" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "top_factor_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("issn", sa.String(length=20)),
            sa.Column("eissn", sa.String(length=20)),
            sa.Column("journal", sa.Text()),
            sa.Column("categories_json", sa.JSON(), nullable=False),
            sa.Column("total", sa.Integer(), nullable=False),
            sa.Column("retrieved_at", sa.String(length=40), nullable=False),
        )
        op.create_index("ix_top_factor_records_issn", "top_factor_records", ["issn"])
        op.create_index("ix_top_factor_records_eissn", "top_factor_records", ["eissn"])


def downgrade() -> None:
    # Additive table, like every other retraction/findings-cluster migration -- 0001 owns eventual teardown.
    pass
