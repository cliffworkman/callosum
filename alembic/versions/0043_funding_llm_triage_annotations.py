"""funding_llm_triage_annotations.

Revision ID: 0043_funding_llm_triage_annotations
Revises: 0042_paper_urls
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

from alembic import op

revision = "0043_funding_llm_triage_annotations"
down_revision = "0042_paper_urls"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    if "funding_llm_triage_annotations" not in _tables():
        op.create_table(
            "funding_llm_triage_annotations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("funding_search_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("item_kind", sa.String(length=40), nullable=False),
            sa.Column("canonical_item_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=80), nullable=False),
            sa.Column("show_in_triage", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rationale", sa.Text()),
            sa.Column("fit_dimensions_json", sqlite.JSON(), nullable=False),
            sa.Column("concerns_json", sqlite.JSON(), nullable=False),
            sa.Column("basis", sa.Text()),
            sa.Column("provider_id", sa.String(length=120), nullable=False, server_default="configured-llm"),
            sa.Column("prompt_version", sa.String(length=120)),
            sa.Column("evidence_fingerprint", sa.String(length=80)),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="current"),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.CheckConstraint(
                "item_kind IN ('opportunity', 'scheme', 'prospect')",
                name="ck_funding_llm_triage_annotations_funding_llm_triage_item_kind",
            ),
            sa.UniqueConstraint("run_id", "item_kind", "canonical_item_id", name="uq_funding_llm_triage_item"),
        )
        op.create_index("ix_funding_llm_triage_run", "funding_llm_triage_annotations", ["run_id"])


def downgrade() -> None:
    pass
