"""Add paper_sections and chunks.grobid_section_id (backlog #30 Stage 2: GROBID section scoping).

paper_sections is a sibling table to chunks, holding GROBID's own section structure (title, page
range, order) verbatim -- never a retrofit of the pre-existing chunks.section heuristic column, which
this migration does not touch. chunks.grobid_section_id is a nullable, additive FK so existing chunk
rows are unaffected.

Revision ID: 0074_paper_sections
Revises: 0073_received_shares
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0074_paper_sections"
down_revision = "0073_received_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "paper_sections" not in inspector.get_table_names():
        op.create_table(
            "paper_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("section_kind", sa.Text()),
            sa.Column("page_start", sa.Integer(), nullable=False),
            sa.Column("page_end", sa.Integer(), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
        )
        op.create_index("ix_paper_sections_paper_id", "paper_sections", ["paper_id"])

    chunk_columns = {c["name"] for c in inspector.get_columns("chunks")}
    if "grobid_section_id" not in chunk_columns:
        # SQLite's ALTER dialect can't add a column with a FOREIGN KEY constraint directly (Alembic
        # raises NotImplementedError: "No support for ALTER of constraints in SQLite dialect") -- batch
        # mode's copy-and-move strategy is required, same as 0002/0003/0004/0024/0031/0032/0040.
        with op.batch_alter_table("chunks") as batch:
            batch.add_column(
                sa.Column(
                    "grobid_section_id",
                    sa.Integer(),
                    sa.ForeignKey("paper_sections.id", ondelete="SET NULL"),
                )
            )


def downgrade() -> None:
    # Additive table + column, like 0052/0054-0057/0070-0073 -- 0001 owns eventual metadata teardown.
    pass
