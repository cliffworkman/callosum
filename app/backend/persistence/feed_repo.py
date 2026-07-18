"""Data access for the literature Feed (backlog #28 SP2, inc 187): subscription CRUD + item upsert/list +
per-item read/starred state. Bound-param SQL only (rule #3). `in_library` is NOT stored here — it's computed at
read time by the service (like the Search tab), so importing a paper is reflected without a feed refresh."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, RowMapping, and_, delete, func, insert, select, update

from app.backend.persistence.schema import feed_items, feed_subscriptions, papers


def add_subscription(conn: Connection, *, kind: str, value: str, label: str | None = None) -> RowMapping:
    """Get-or-create by (kind, value). Returns the row (existing or new)."""
    existing = (
        conn.execute(
            select(feed_subscriptions).where(
                and_(feed_subscriptions.c.kind == kind, feed_subscriptions.c.value == value)
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return existing
    sub_id = int(
        conn.execute(insert(feed_subscriptions).values(kind=kind, value=value, label=label)).inserted_primary_key[0]
    )
    return conn.execute(select(feed_subscriptions).where(feed_subscriptions.c.id == sub_id)).mappings().one()


def list_subscriptions(conn: Connection) -> list[RowMapping]:
    return list(conn.execute(select(feed_subscriptions).order_by(feed_subscriptions.c.id)).mappings().all())


def remove_subscription(conn: Connection, sub_id: int) -> bool:
    """Delete a subscription (FK CASCADE drops its items). Returns True if a row was removed."""
    result = conn.execute(delete(feed_subscriptions).where(feed_subscriptions.c.id == sub_id))
    return bool(result.rowcount)


def touch_subscription(conn: Connection, sub_id: int) -> None:
    conn.execute(
        update(feed_subscriptions)
        .where(feed_subscriptions.c.id == sub_id)
        .values(last_polled_at=func.current_timestamp())
    )


def upsert_items(conn: Connection, subscription_id: int, entries: list[dict[str, Any]]) -> int:
    """INSERT OR IGNORE each entry on (subscription_id, dedup_key) — re-polls don't duplicate or reset read state.
    Returns the count of NEW rows inserted."""
    new = 0
    for e in entries:
        result = conn.execute(
            insert(feed_items)
            .prefix_with("OR IGNORE")
            .values(
                subscription_id=subscription_id,
                dedup_key=e["dedup_key"],
                title=e["title"],
                doi=e.get("doi"),
                authors=list(e.get("authors") or []),
                journal=e.get("journal"),
                year=e.get("year"),
                url=e.get("url"),
                abstract=e.get("abstract"),
                posted_date=e.get("posted_date"),
            )
        )
        new += int(result.rowcount or 0)
    return new


def list_items(
    conn: Connection,
    *,
    unread_only: bool = False,
    starred_only: bool = False,
    subscription_id: int | None = None,
    limit: int = 200,
) -> list[RowMapping]:
    stmt = select(feed_items)
    clauses = []
    if unread_only:
        clauses.append(feed_items.c.is_read == 0)
    if starred_only:
        clauses.append(feed_items.c.is_starred == 1)
    if subscription_id is not None:
        clauses.append(feed_items.c.subscription_id == subscription_id)
    if clauses:
        stmt = stmt.where(and_(*clauses))
    # newest posting first; id as a stable tiebreak
    stmt = stmt.order_by(feed_items.c.posted_date.desc(), feed_items.c.id.desc()).limit(limit)
    return list(conn.execute(stmt).mappings().all())


def set_item_state(
    conn: Connection, item_id: int, *, is_read: bool | None = None, is_starred: bool | None = None
) -> bool:
    values: dict[str, Any] = {}
    if is_read is not None:
        values["is_read"] = 1 if is_read else 0
    if is_starred is not None:
        values["is_starred"] = 1 if is_starred else 0
    if not values:
        return False
    result = conn.execute(update(feed_items).where(feed_items.c.id == item_id).values(**values))
    return bool(result.rowcount)


def mark_all_read(conn: Connection, *, subscription_id: int | None = None) -> int:
    stmt = update(feed_items).values(is_read=1).where(feed_items.c.is_read == 0)
    if subscription_id is not None:
        stmt = stmt.where(feed_items.c.subscription_id == subscription_id)
    return int(conn.execute(stmt).rowcount or 0)


def unread_count(conn: Connection) -> int:
    return int(
        conn.execute(select(func.count()).select_from(feed_items).where(feed_items.c.is_read == 0)).scalar() or 0
    )


def list_library_journals(conn: Connection) -> list[dict[str, Any]]:
    """Distinct journals (``papers.venue``) present in the LIVE library with paper counts, most-frequent first —
    powers the Feed's "Suggest" journals modal + typeahead. Reads the user's own library data; local, no egress."""
    stmt = (
        select(papers.c.venue, func.count().label("count"))
        .where(papers.c.venue.is_not(None), papers.c.venue != "", papers.c.deleted_at.is_(None))
        .group_by(papers.c.venue)
        .order_by(func.count().desc(), papers.c.venue)
    )
    return [{"journal": r[0], "count": int(r[1])} for r in conn.execute(stmt)]
