"""Gap-finder dismissals (inc 135): a ``profile.dismissed_gap_works`` JSON column — the OpenAlex ids / DOIs the
user dismissed from the literature-gap candidate list, so a re-run doesn't resurface them.

Additive + idempotent (like the other profile-column migrations 0010-0013): a fresh DB already has the column
from 0001's ``metadata.create_all``, so the add is guarded and skipped there; an existing DB gets it here.

Revision ID: 0018_profile_dismissed_gaps
Revises: 0017_retraction_records
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0018_profile_dismissed_gaps"
down_revision = "0017_retraction_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = (
        {c["name"] for c in inspector.get_columns("profile")} if "profile" in inspector.get_table_names() else set()
    )
    if "profile" in inspector.get_table_names() and "dismissed_gap_works" not in columns:
        op.add_column("profile", sa.Column("dismissed_gap_works", sa.JSON()))


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
