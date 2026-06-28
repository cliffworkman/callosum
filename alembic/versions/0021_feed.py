"""Literature Feed (inc 187): ``feed_subscriptions`` (sources you follow) + ``feed_items`` (polled items with
per-item read/starred state). Backlog #28 SP2.

Additive + idempotent (like 0002-0020): a fresh DB already has the tables from 0001's ``metadata.create_all``, so
each create is guarded and skipped there; an existing DB gets them here.

Revision ID: 0021_feed
Revises: 0020_suppressed_paper_tags
Create Date: 2026-06-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0021_feed"
down_revision = "0020_suppressed_paper_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "feed_subscriptions" not in tables:
        op.create_table(
            "feed_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("value", sa.String(length=500), nullable=False),
            sa.Column("label", sa.String(length=300)),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("last_polled_at", sa.DateTime()),
            sa.UniqueConstraint("kind", "value", name="uq_feed_subscriptions_kind_value"),
        )
    if "feed_items" not in tables:
        op.create_table(
            "feed_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "subscription_id",
                sa.Integer(),
                sa.ForeignKey("feed_subscriptions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("dedup_key", sa.String(length=500), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("doi", sa.String(length=255)),
            sa.Column("authors", sa.JSON()),
            sa.Column("journal", sa.String(length=500)),
            sa.Column("year", sa.Integer()),
            sa.Column("url", sa.Text()),
            sa.Column("abstract", sa.Text()),
            sa.Column("posted_date", sa.String(length=40)),
            sa.Column("is_read", sa.Integer(), server_default="0", nullable=False),
            sa.Column("is_starred", sa.Integer(), server_default="0", nullable=False),
            sa.Column("first_seen_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.UniqueConstraint("subscription_id", "dedup_key", name="uq_feed_items_subscription_dedup"),
            sa.Index("ix_feed_items_subscription_id", "subscription_id"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
