"""Add the ``llm_cache`` table (content-addressed cache for token-expensive LLM generation).

The cache key is a content hash of everything that determines the output (model + prompt-version +
normalized inputs), so the cache invalidates automatically when any input changes. Stored in SQLite so the
savings survive restarts. Idempotent like 0002–0004: a *fresh* database already has the table from 0001's
``metadata.create_all``, so this is a no-op there.

Revision ID: 0005_llm_generation_cache
Revises: 0004_paper_soft_delete
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_llm_generation_cache"
down_revision = "0004_paper_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("llm_cache"):
        return  # fresh database: 0001's create_all already built the final schema. No-op.
    op.create_table(
        "llm_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("namespace", sa.String(length=50), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.String(length=255), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("length(trim(namespace)) > 0", name="ck_llm_cache_namespace_non_empty"),
        sa.CheckConstraint("length(trim(input_hash)) > 0", name="ck_llm_cache_input_hash_non_empty"),
        sa.UniqueConstraint("namespace", "input_hash", name="uq_llm_cache_namespace_input_hash"),
    )


def downgrade() -> None:
    # No-op by design: ``llm_cache`` is part of the schema metadata, so the teardown is owned by 0001's
    # metadata-wide downgrade (dropping it here too would double-drop when downgrading to base). Downgrades
    # are not a supported workflow (CLAUDE.md: no down-migrations by design).
    return
