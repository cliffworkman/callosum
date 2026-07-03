"""SP2b (inc 259): the assisted-extraction candidate table + the ma_cells.origin provenance column.

Additive + guarded (mirrors 0033); no down-migration by design.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0034_extraction_proposals"
down_revision = "0033_extraction_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ma_proposals" not in tables:
        op.create_table(
            "ma_proposals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("row_id", sa.Integer(), sa.ForeignKey("ma_rows.id", ondelete="CASCADE"), nullable=False),
            sa.Column("field_key", sa.String(length=80), nullable=False),
            sa.Column("value", sa.Text()),
            sa.Column("quote", sa.Text()),
            sa.Column("page", sa.Integer()),
            sa.Column("bbox_json", sa.Text()),
            sa.Column("anchor_state", sa.String(length=20), nullable=False),
            sa.Column("reason", sa.String(length=40)),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.UniqueConstraint("row_id", "field_key", name="uq_ma_proposals_row_field"),
        )
        op.create_index("ix_ma_proposals_row_id", "ma_proposals", ["row_id"])

    if "ma_cells" in tables:
        cols = {c["name"] for c in inspector.get_columns("ma_cells")}
        if "origin" not in cols:
            op.add_column("ma_cells", sa.Column("origin", sa.String(length=20)))


def downgrade() -> None:
    # No down-migration by design (the SP2a/0033 pattern).
    return
