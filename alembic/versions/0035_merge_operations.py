"""merge_operations — the reversible-merge undo snapshot store (backlog #17/#16).

Additive + guarded (the 0034 idiom); no down-migration by design. The CHECK is named with the short suffix so
env.py's naming convention expands it to ``ck_merge_operations_merge_status_valid`` (a full name would double).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0035_merge_operations"
down_revision = "0034_extraction_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "merge_operations" not in set(inspector.get_table_names()):
        op.create_table(
            "merge_operations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "canonical_paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("merged_paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("snapshot_json", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("undone_at", sa.DateTime()),
            sa.CheckConstraint("status IN ('active', 'undone')", name="merge_status_valid"),
        )
        op.create_index("ix_merge_operations_canonical", "merge_operations", ["canonical_paper_id"])


def downgrade() -> None:
    return
