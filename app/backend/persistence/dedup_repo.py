"""Data access for persistent "not a duplicate" dismissals.

The duplicate-detection scan (`clustering/duplicate_detection.py`) drops dismissed pairs before its
union-find; the manage-dismissals UI lists + un-dismisses them. Extracted from `repository.py` (inc 67) to
keep that module under the 600-line cap — the dedup-dismiss concern is self-contained (all four functions
operate on `dismissed_duplicate_pairs`). Canonical pairs are stored `(low < high)`.
"""

from __future__ import annotations

from sqlalchemy import Connection, RowMapping, delete, insert, select

from app.backend.persistence.schema import dismissed_duplicate_pairs, papers


def get_dismissed_duplicate_pairs(conn: Connection) -> set[tuple[int, int]]:
    """Canonical (low, high) paper-id pairs the user marked "not a duplicate"."""
    return {
        (int(row.paper_id_low), int(row.paper_id_high))
        for row in conn.execute(
            select(dismissed_duplicate_pairs.c.paper_id_low, dismissed_duplicate_pairs.c.paper_id_high)
        )
    }


def dismiss_duplicate_pairs(conn: Connection, pairs: list[tuple[int, int]]) -> None:
    """Record canonical (low < high) pairs as not-duplicates; re-dismissing a pair is a no-op (OR IGNORE)."""
    for low, high in pairs:
        conn.execute(
            insert(dismissed_duplicate_pairs).prefix_with("OR IGNORE").values(paper_id_low=low, paper_id_high=high)
        )


def list_dismissed_duplicate_pairs(conn: Connection) -> list[RowMapping]:
    """The dismissed (low, high) pairs with each paper's title, for the manage-dismissals UI (inc 67)."""
    low_p = papers.alias("low_p")
    high_p = papers.alias("high_p")
    stmt = (
        select(
            dismissed_duplicate_pairs.c.paper_id_low,
            low_p.c.title.label("low_title"),
            dismissed_duplicate_pairs.c.paper_id_high,
            high_p.c.title.label("high_title"),
        )
        .select_from(
            dismissed_duplicate_pairs.join(low_p, low_p.c.id == dismissed_duplicate_pairs.c.paper_id_low).join(
                high_p, high_p.c.id == dismissed_duplicate_pairs.c.paper_id_high
            )
        )
        .order_by(dismissed_duplicate_pairs.c.id)
    )
    return list(conn.execute(stmt).mappings())


def undismiss_duplicate_pair(conn: Connection, low: int, high: int) -> bool:
    """Remove a canonical (low, high) dismissal so the pair can be flagged again. False if it wasn't dismissed."""
    result = conn.execute(
        delete(dismissed_duplicate_pairs).where(
            dismissed_duplicate_pairs.c.paper_id_low == low,
            dismissed_duplicate_pairs.c.paper_id_high == high,
        )
    )
    return bool(result.rowcount)
