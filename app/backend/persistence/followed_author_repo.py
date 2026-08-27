"""Data access for followed-authors (backlog #29, inc 454; consolidated into Discover -> Feed 2026-08-27).
`add_followed_author` is idempotent on `author_id` (re-following updates the snapshot in place, never
duplicates).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select, update

from app.backend.persistence import feed_repo
from app.backend.persistence.schema import followed_authors


def list_followed_authors(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(select(followed_authors).order_by(followed_authors.c.display_name)).all()
    return [dict(r._mapping) for r in rows]


def get_followed_author(conn: Connection, author_id: str) -> dict[str, Any] | None:
    row = conn.execute(select(followed_authors).where(followed_authors.c.author_id == author_id)).mappings().first()
    return dict(row) if row is not None else None


def add_followed_author(
    conn: Connection, *, author_id: str, display_name: str, orcid: str | None, matched_by: str
) -> dict[str, Any]:
    """Idempotent on `author_id`: re-following updates the display_name/orcid/matched_by snapshot in place
    rather than erroring or duplicating."""
    existing = get_followed_author(conn, author_id)
    if existing is not None:
        conn.execute(
            update(followed_authors)
            .where(followed_authors.c.id == int(existing["id"]))
            .values(display_name=display_name, orcid=orcid, matched_by=matched_by)
        )
    else:
        conn.execute(
            insert(followed_authors).values(
                author_id=author_id, display_name=display_name, orcid=orcid, matched_by=matched_by
            )
        )
    return get_followed_author(conn, author_id) or {}


def remove_followed_author(conn: Connection, author_id: str) -> bool:
    """Unfollow. No-op (returns False) if not followed."""
    existing = get_followed_author(conn, author_id)
    if existing is None:
        return False
    conn.execute(delete(followed_authors).where(followed_authors.c.id == int(existing["id"])))
    return True


def set_last_refreshed(conn: Connection, author_id: str, *, refreshed_at: str) -> None:
    conn.execute(
        update(followed_authors).where(followed_authors.c.author_id == author_id).values(last_refreshed_at=refreshed_at)
    )


def backfill_feed_subscriptions(conn: Connection) -> int:
    """inc 455 self-heal: ensure every already-followed author (including one followed before this increment
    shipped) has a matching `feed_subscriptions` row, so their works flow into the Feed without the user having
    to re-follow. Idempotent (`add_subscription` is get-or-create) -- safe to call on every app boot, mirroring
    the existing `_upgrade_database_to_head` self-heal in `app.py`'s `lifespan()`. Returns the count added."""
    added = 0
    for author in list_followed_authors(conn):
        if feed_repo.find_subscription(conn, kind="followed_author", value=author["author_id"]) is None:
            feed_repo.add_subscription(
                conn, kind="followed_author", value=author["author_id"], label=author["display_name"]
            )
            added += 1
    return added
