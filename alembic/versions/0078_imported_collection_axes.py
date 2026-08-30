"""Map an imported source collection to the user-owned axis created from it.

The one-to-one provenance link makes the explicit "create axes from imported folders" action
idempotent without adding import-only fields to the general axes table. Deleting either side
removes the link; it never deletes the other user-owned object.

Revision ID: 0078_imported_collection_axes
Revises: 0077_drop_followed_author_candidates
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0078_imported_collection_axes"
down_revision = "0077_drop_followed_author_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "imported_collection_axes" in inspector.get_table_names():
        return
    if not {"collections", "axes"}.issubset(inspector.get_table_names()):
        return
    op.create_table(
        "imported_collection_axes",
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "axis_id",
            sa.Integer(),
            sa.ForeignKey("axes.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )


def downgrade() -> None:
    # Additive provenance; down-migrations are not a supported Callosum workflow.
    pass
