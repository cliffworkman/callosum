"""My Publications (inc 84): a ``profile.starred_paper_ids`` JSON column for starred key publications.

Additive and idempotent (like 0002–0011): a *fresh* database already has the column from 0001's
``metadata.create_all``, so the part is guarded and skipped there.

Revision ID: 0012_my_publication_stars
Revises: 0011_my_publication_domains
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_my_publication_stars"
down_revision = "0011_my_publication_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    profile_cols = {col["name"] for col in inspector.get_columns("profile")}
    if "starred_paper_ids" not in profile_cols:
        op.add_column("profile", sa.Column("starred_paper_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
