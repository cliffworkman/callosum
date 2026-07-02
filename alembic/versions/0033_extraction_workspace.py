"""Meta-analysis extraction workspace (inc 253): ``ma_projects`` / ``ma_rows`` / ``ma_cells``.

A project (a named dataset + an extraction template) has rows (one effect each, optionally linked to a paper) whose
cells carry a hand-entered value + its exact source provenance. Extract/structure/convert/export only.

Additive + idempotent (like 0021-0032): a fresh DB already has the tables from 0001's ``metadata.create_all`` (they
live on the shared metadata), so each create is guarded + skipped there; an existing DB gets them here. No-op
downgrade (0001's metadata drops them).

Revision ID: 0033_extraction_workspace
Revises: 0032_summary_imported_json
Create Date: 2026-07-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0033_extraction_workspace"
down_revision = "0032_summary_imported_json"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "ma_projects" not in tables:
        op.create_table(
            "ma_projects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(300), nullable=False),
            sa.Column("protocol_note", sa.Text()),
            sa.Column("design", sa.String(40), nullable=False),
            sa.Column("template_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        )
    if "ma_rows" not in tables:
        op.create_table(
            "ma_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("ma_projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("paper_id", sa.Integer()),
            sa.Column("label", sa.String(500)),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("converted_json", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        )
        op.create_index("ix_ma_rows_project_id", "ma_rows", ["project_id"])
    if "ma_cells" not in tables:
        op.create_table(
            "ma_cells",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("row_id", sa.Integer(), sa.ForeignKey("ma_rows.id", ondelete="CASCADE"), nullable=False),
            sa.Column("field_key", sa.String(80), nullable=False),
            sa.Column("value", sa.Text()),
            sa.Column("page", sa.Integer()),
            sa.Column("quote", sa.Text()),
            sa.Column("bbox_json", sa.Text()),
            sa.UniqueConstraint("row_id", "field_key", name="uq_ma_cells_row_field"),
        )
        op.create_index("ix_ma_cells_row_id", "ma_cells", ["row_id"])


def downgrade() -> None:
    # No-op by design (mirrors 0021-0032): the tables live in 0001's `metadata`, whose downgrade drops them.
    return
