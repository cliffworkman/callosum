"""Data access for followed-authors (backlog #29, inc 454): the subscription list plus its derived candidate
cache. `add_followed_author` is idempotent on `author_id` (re-following updates the snapshot in place, never
duplicates); `remove_followed_author` cascades — it also purges that author's cached candidates, so an unfollow
can never leave an orphaned row behind. `read_followed_author_candidates` re-checks membership in
`followed_authors` defensively (an `author_id IN (...)` filter) so a failed cascade can never resurface a stale
candidate after unfollow.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select, update

from app.backend.clustering.followed_authors import FollowedAuthorCandidate
from app.backend.persistence.schema import followed_author_candidates, followed_authors


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
    """Unfollow + cascade-purge its candidate cache. No-op (returns False) if not followed."""
    existing = get_followed_author(conn, author_id)
    if existing is None:
        return False
    conn.execute(delete(followed_authors).where(followed_authors.c.id == int(existing["id"])))
    conn.execute(delete(followed_author_candidates).where(followed_author_candidates.c.author_id == author_id))
    return True


def set_last_refreshed(conn: Connection, author_id: str, *, refreshed_at: str) -> None:
    conn.execute(
        update(followed_authors).where(followed_authors.c.author_id == author_id).values(last_refreshed_at=refreshed_at)
    )


def replace_followed_author_candidates(
    conn: Connection, author_id: str, candidates: list[FollowedAuthorCandidate], *, computed_at: str
) -> None:
    """Replace ALL cached rows for `author_id` with `candidates` (authoritative per-author refresh)."""
    conn.execute(delete(followed_author_candidates).where(followed_author_candidates.c.author_id == author_id))
    if not candidates:
        return
    conn.execute(
        insert(followed_author_candidates),
        [
            {
                "author_id": c.author_id,
                "author_display_name": c.author_display_name,
                "openalex_work_id": c.openalex_work_id,
                "doi": c.doi,
                "title": c.title,
                "year": c.year,
                "cited_by_count": c.cited_by_count,
                "computed_at": computed_at,
            }
            for c in candidates
        ],
    )


def read_followed_author_candidates(conn: Connection) -> list[dict[str, Any]]:
    """The union across every CURRENTLY-followed author (an `author_id IN (...)` subquery against
    followed_authors — a defensive filter so an unfollow's cascade-delete failing open can never resurface a
    stale row), newest work first. SQLite sorts NULL as smallest, so `.desc()` naturally puts a NULL year last."""
    stmt = (
        select(followed_author_candidates)
        .where(followed_author_candidates.c.author_id.in_(select(followed_authors.c.author_id)))
        .order_by(followed_author_candidates.c.year.desc(), followed_author_candidates.c.id)
    )
    return [dict(r._mapping) for r in conn.execute(stmt).all()]
