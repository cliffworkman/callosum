"""My Publications Part 2 Layer 2 (inc 83): a ``profile.research_domains`` JSON column for the domain breakdown.

Additive and idempotent (like 0002–0010): a *fresh* database already has the column from 0001's
``metadata.create_all``, so the part is guarded and skipped there.

Revision ID: 0011_my_publication_domains
Revises: 0010_my_publications_summary
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_my_publication_domains"
down_revision = "0010_my_publications_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    profile_cols = {col["name"] for col in inspector.get_columns("profile")}
    if "research_domains" not in profile_cols:
        op.add_column("profile", sa.Column("research_domains", sa.JSON(), nullable=True))


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
