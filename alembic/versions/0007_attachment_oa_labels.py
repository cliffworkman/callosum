"""Add open-access acquisition label columns to ``attachments``.

Set when a copy is fetched from an OA database (the legally-clear acquisition lane): the OA color, version,
resolving source, landing page, license, and a bronze-instability flag. Idempotent like 0002–0006: a *fresh*
database already has these columns from 0001's ``metadata.create_all``, so this is a no-op there.

Revision ID: 0007_attachment_oa_labels
Revises: 0006_dismissed_duplicate_pairs
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_attachment_oa_labels"
down_revision = "0006_dismissed_duplicate_pairs"
branch_labels = None
depends_on = None

_NEW_COLUMNS = (
    ("oa_color", sa.String(20)),
    ("oa_version", sa.String(20)),
    ("oa_source", sa.String(100)),
    ("oa_landing_page_url", sa.Text()),
    ("oa_license", sa.String(100)),
    ("oa_bronze_unstable", sa.Integer()),
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("attachments")}
    if "oa_color" in existing:
        return  # fresh database: 0001's create_all already built the final schema. No-op.
    for name, type_ in _NEW_COLUMNS:
        op.add_column("attachments", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    # No-op by design (the columns live in the schema metadata; teardown is owned by 0001's metadata-wide
    # downgrade). Downgrades aren't a supported workflow.
    return
