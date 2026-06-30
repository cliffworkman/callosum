"""Curated Axis (A7, inc 211): a nullable ``cluster_node_papers.position`` for manual member ordering on a
curated axis (NULL on keyword axes — order stays papers.id).

Additive + idempotent (like 0021-0027): a fresh DB already has the column from 0001's ``metadata.create_all``
(it's on the schema Table), so the add is guarded + skipped there; an existing DB gets it here. No-op downgrade.

Revision ID: 0028_cluster_node_paper_position
Revises: 0027_paper_citation_counts
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0028_cluster_node_paper_position"
down_revision = "0027_paper_citation_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("cluster_node_papers")}
    if "position" not in cols:
        op.add_column("cluster_node_papers", sa.Column("position", sa.Integer(), nullable=True))


def downgrade() -> None:
    # No-op by design (the column lives in 0001's metadata; downgrades aren't a supported workflow).
    return
