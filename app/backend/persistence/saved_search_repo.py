"""Data access for saved searches (inc 208, A1).

A saved search is a *named bundle of the existing library facets* (q / search_field / item_type / axis / tag /
needs_review / signal / sort), stored as a JSON `params` blob and recalled from the library header. A metadata
predicate over the existing GET /papers filters — distinct from a semantic axis. Local; name is UNIQUE (re-saving a
name overwrites). Bound-param SQLAlchemy Core (rule #3). Extracted to its own module (like tags_repo / dedup_repo)
so repository.py stays under the 600-line cap.
"""

from __future__ import annotations

from sqlalchemy import Connection, RowMapping, delete, insert, select, update

from app.backend.persistence.schema import saved_searches

SAVED_SEARCH_NAME_MAX = 100


def list_saved_searches(conn: Connection) -> list[RowMapping]:
    """Every saved search as ``{id, name, params}``, ordered case-insensitively by name."""
    from sqlalchemy import func

    stmt = select(saved_searches.c.id, saved_searches.c.name, saved_searches.c.params).order_by(
        func.lower(saved_searches.c.name)
    )
    return list(conn.execute(stmt).mappings())


def upsert_saved_search(conn: Connection, name: str, params: dict) -> RowMapping:
    """Create the saved search, or overwrite its params if the (UNIQUE) name already exists. Returns
    ``{id, name, params}``. Caller commits."""
    clean = name.strip()[:SAVED_SEARCH_NAME_MAX]
    existing = conn.execute(select(saved_searches.c.id).where(saved_searches.c.name == clean)).scalar()
    if existing is not None:
        conn.execute(update(saved_searches).where(saved_searches.c.id == existing).values(params=params))
        sid = int(existing)
    else:
        sid = int(conn.execute(insert(saved_searches).values(name=clean, params=params)).inserted_primary_key[0])
    return (
        conn.execute(
            select(saved_searches.c.id, saved_searches.c.name, saved_searches.c.params).where(
                saved_searches.c.id == sid
            )
        )
        .mappings()
        .one()
    )


def delete_saved_search(conn: Connection, search_id: int) -> bool:
    """Delete a saved search. False if no such id. Caller commits."""
    result = conn.execute(delete(saved_searches).where(saved_searches.c.id == search_id))
    return bool(result.rowcount)
