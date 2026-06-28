"""Literature Feed tables (backlog #28 SP2, inc 187).

Subscriptions (sources you follow — pull-only, opt-in) + the items polled from them, with per-item read/starred
state. Split out of ``schema.py`` (rule #1); registers on the shared ``metadata`` from ``schema_base`` (re-exported
from ``schema.py``, so ``from app.backend.persistence.schema import feed_items`` keeps working).
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

from app.backend.persistence.schema_base import metadata

# A source the user has chosen to follow. kind = "biorxiv_category" (later: "journal_issn", "pubmed_query"); value
# = the category / ISSN / query. UNIQUE(kind, value) so adding the same subscription is idempotent (get-or-create).
feed_subscriptions = Table(
    "feed_subscriptions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("kind", String(40), nullable=False),
    Column("value", String(500), nullable=False),
    Column("label", String(300)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("last_polled_at", DateTime),
    UniqueConstraint("kind", "value", name="uq_feed_subscriptions_kind_value"),
)

# One polled item per (subscription, dedup_key). Metadata is stored (the Feed persists across sessions); read/starred
# are the user's per-item state; `in_library` is computed at read time (not stored), like the Search tab. is_read /
# is_starred are 0/1 integers (sqlite has no native bool).
feed_items = Table(
    "feed_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("subscription_id", ForeignKey("feed_subscriptions.id", ondelete="CASCADE"), nullable=False),
    Column("dedup_key", String(500), nullable=False),
    Column("title", Text, nullable=False),
    Column("doi", String(255)),
    Column("authors", JSON),
    Column("journal", String(500)),
    Column("year", Integer),
    Column("url", Text),
    Column("abstract", Text),
    Column("posted_date", String(40)),
    Column("is_read", Integer, nullable=False, server_default="0"),
    Column("is_starred", Integer, nullable=False, server_default="0"),
    Column("first_seen_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("subscription_id", "dedup_key", name="uq_feed_items_subscription_dedup"),
    Index("ix_feed_items_subscription_id", "subscription_id"),
)
