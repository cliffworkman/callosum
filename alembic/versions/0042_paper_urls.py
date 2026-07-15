"""paper_urls.

Revision ID: 0042_paper_urls
Revises: 0041_saved_funding_refresh_events
Create Date: 2026-07-13
"""

from __future__ import annotations

import json

import sqlalchemy as sa

from alembic import op

revision = "0042_paper_urls"
down_revision = "0041_saved_funding_refresh_events"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    if "paper_urls" not in _tables():
        op.create_table(
            "paper_urls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("label", sa.String(length=120)),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(length=100), nullable=False, server_default="user"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("paper_id", "url", name="uq_paper_urls_paper_url"),
        )
        op.create_index("ix_paper_urls_paper_id", "paper_urls", ["paper_id"])
    _backfill_from_csl_extra_urls()


def _backfill_from_csl_extra_urls() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, csl_json FROM papers")).mappings()
    for row in rows:
        try:
            csl = row["csl_json"] if isinstance(row["csl_json"], dict) else json.loads(row["csl_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        urls = csl.get("extra_urls") if isinstance(csl, dict) else None
        if not isinstance(urls, list):
            continue
        for pos, raw in enumerate(urls):
            url = str(raw).strip() if raw is not None else ""
            if not url:
                continue
            bind.execute(
                sa.text(
                    "INSERT OR IGNORE INTO paper_urls (paper_id, url, position, source) "
                    "VALUES (:paper_id, :url, :position, 'csl-extra-url')"
                ),
                {"paper_id": int(row["id"]), "url": url, "position": pos},
            )


def downgrade() -> None:
    pass
