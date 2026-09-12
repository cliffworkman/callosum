"""Add wanted_items.last_reason_code: structured OA-acquisition state (inc 588).

The re-check (`acquisition/wanted.py::run_recheck`) previously persisted only ``last_result`` — a HUMAN string
from ``AcquireOutcome.human_detail()``. Sorting/filtering/messaging the Wanted list then had to reconstruct the
state by parsing that prose (e.g. "HTTP 403"), making ``human_detail`` wording an accidental durable contract.

This adds the structured state as its own column so it flows end-to-end
(``AcquireOutcome.reason_code`` -> ``last_reason_code`` -> API ``acquisition_state`` -> frontend) with no string
inspection. Additive, nullable: pre-inc-588 rows keep NULL and a narrowly-scoped legacy classifier covers them
in the API until the row is next re-checked. A simple nullable column needs no batch_alter_table on SQLite.

Revision ID: 0082_wanted_reason_code
Revises: 0081_source_representations
Create Date: 2026-09-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0082_wanted_reason_code"
down_revision = "0081_source_representations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("wanted_items")}
    if "last_reason_code" in columns:
        return
    op.add_column("wanted_items", sa.Column("last_reason_code", sa.String(length=40), nullable=True))


def downgrade() -> None:
    # Additive column, like the other inc-5xx/0074+ migrations — 0001 owns eventual teardown.
    pass
