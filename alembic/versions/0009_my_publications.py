"""My Publications (inc 78): an ``axes.kind`` column + the ``profile`` and ``my_publication_decisions`` tables.

Additive and idempotent per-part (like 0002–0008): a *fresh* database already has all of this from 0001's
``metadata.create_all``, so each part is guarded and skipped there.

Revision ID: 0009_my_publications
Revises: 0008_wanted_items
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_my_publications"
down_revision = "0008_wanted_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    axes_cols = {col["name"] for col in inspector.get_columns("axes")}
    if "kind" not in axes_cols:
        op.add_column("axes", sa.Column("kind", sa.String(40), nullable=False, server_default="standard"))

    tables = set(inspector.get_table_names())
    if "profile" not in tables:
        op.create_table(
            "profile",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("display_name", sa.Text(), nullable=True),
            sa.Column("name_variants", sa.JSON(), nullable=True),
            sa.Column("orcid", sa.String(64), nullable=True),
            sa.Column("openalex_author_id", sa.String(64), nullable=True),
            sa.Column("my_publications_dismissed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )
    if "my_publication_decisions" not in tables:
        op.create_table(
            "my_publication_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("decision", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("paper_id", name="uq_my_publication_decisions_paper_id"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
