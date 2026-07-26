"""Domain-scoped My Publications citation-gap snapshots.

Revision ID: 0053_domain_scoped_citation_gaps
Revises: 0052_my_publication_citation_gaps
"""

from __future__ import annotations

import json

import sqlalchemy as sa

from alembic import op

revision = "0053_domain_scoped_citation_gaps"
down_revision = "0052_my_publication_citation_gaps"
branch_labels = None
depends_on = None

_TABLE = "my_publication_citation_gap_cache"
_LEGACY = "my_publication_citation_gap_cache_legacy"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        _create_scoped_table()
        return
    if "scope_key" in {column["name"] for column in inspector.get_columns(_TABLE)}:
        return

    rows = list(
        bind.execute(
            sa.text(f"SELECT id, candidates, coverage, computed_at FROM {_TABLE}")  # noqa: S608
        ).mappings()
    )
    op.rename_table(_TABLE, _LEGACY)
    _create_scoped_table()
    scoped = sa.table(
        _TABLE,
        sa.column("id", sa.Integer()),
        sa.column("scope_key", sa.String()),
        sa.column("scope", sa.JSON()),
        sa.column("candidates", sa.JSON()),
        sa.column("coverage", sa.JSON()),
        sa.column("computed_at", sa.String()),
    )
    for row in rows:
        bind.execute(
            scoped.insert().values(
                id=row["id"],
                scope_key="all",
                scope={"kind": "all", "domain_keys": [], "domain_labels": [], "paper_ids": []},
                candidates=_legacy_json(row["candidates"], []),
                coverage=_legacy_json(row["coverage"], {}),
                computed_at=row["computed_at"],
            )
        )
    op.drop_table(_LEGACY)


def _create_scoped_table() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(80), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("coverage", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("scope_key", name="uq_my_publication_citation_gap_scope_key"),
    )


def _legacy_json(value, fallback):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return value


def downgrade() -> None:
    pass
