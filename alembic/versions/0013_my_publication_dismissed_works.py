"""My Publications (inc 85): a ``profile.dismissed_work_dois`` JSON column for the missing-works review queue.

Additive and idempotent (like 0002–0012): a *fresh* database already has the column from 0001's
``metadata.create_all``, so the part is guarded and skipped there.

Revision ID: 0013_my_publication_dismissed_works
Revises: 0012_my_publication_stars
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_my_publication_dismissed_works"
down_revision = "0012_my_publication_stars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    profile_cols = {col["name"] for col in inspector.get_columns("profile")}
    if "dismissed_work_dois" not in profile_cols:
        op.add_column("profile", sa.Column("dismissed_work_dois", sa.JSON(), nullable=True))


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
