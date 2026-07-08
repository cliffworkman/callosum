"""papers.merged_into — marks a paper merged away into a canonical record (backlog #17). Additive + guarded."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0036_papers_merged_into"
down_revision = "0035_merge_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("papers")}
    if "merged_into" not in cols:
        # No inline FK: SQLite can't add a column with a REFERENCES clause via ALTER. The ORM-level self-FK
        # (schema.py) is what the app relies on; the column is a plain nullable Integer at the DB level.
        op.add_column("papers", sa.Column("merged_into", sa.Integer()))


def downgrade() -> None:
    return
