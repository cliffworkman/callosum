"""Data access for the My Publications profile + decisions (inc 78).

The ``profile`` table is single-row (single-user-local). The ``my_publication_decisions`` table records the
user's confirm/reject choices so they survive re-matching. Bound-param (rule #3). Split out (like
``tags_repo``/``wanted_repo``) to keep ``repository.py`` under the 600-line cap.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, func, insert, select, update

from app.backend.persistence.schema import my_publication_decisions, profile


def get_profile(conn: Connection) -> dict[str, Any] | None:
    """The single profile row (the lowest id), or None if the profile has never been set."""
    row = conn.execute(select(profile).order_by(profile.c.id).limit(1)).mappings().first()
    return dict(row) if row is not None else None


def upsert_profile(
    conn: Connection,
    *,
    display_name: str | None,
    name_variants: list[str],
    orcid: str | None,
) -> dict[str, Any]:
    """Create or update the single profile row's identity fields. Leaves the cached ``openalex_author_id`` and
    the ``my_publications_dismissed`` flag untouched (the resolver / delete manage those)."""
    existing = get_profile(conn)
    values = {
        "display_name": (display_name or "").strip() or None,
        "name_variants": [v.strip() for v in (name_variants or []) if v and v.strip()],
        "orcid": (orcid or "").strip() or None,
        "updated_at": func.current_timestamp(),
    }
    if existing is None:
        conn.execute(insert(profile).values(**values))
    else:
        conn.execute(update(profile).where(profile.c.id == int(existing["id"])).values(**values))
    return get_profile(conn) or {}


def set_openalex_author_id(conn: Connection, author_id: str | None) -> None:
    existing = get_profile(conn)
    if existing is None:
        return
    conn.execute(
        update(profile)
        .where(profile.c.id == int(existing["id"]))
        .values(openalex_author_id=author_id, updated_at=func.current_timestamp())
    )


def set_my_publications_dismissed(conn: Connection, dismissed: bool) -> None:
    existing = get_profile(conn)
    if existing is None:
        return
    conn.execute(
        update(profile)
        .where(profile.c.id == int(existing["id"]))
        .values(my_publications_dismissed=1 if dismissed else 0, updated_at=func.current_timestamp())
    )


def set_research_summary(conn: Connection, text: str | None) -> None:
    """Persist the dashboard's editable research summary (inc 81). No-op if the profile is unset."""
    existing = get_profile(conn)
    if existing is None:
        return
    conn.execute(
        update(profile)
        .where(profile.c.id == int(existing["id"]))
        .values(research_summary=(text or "").strip() or None, updated_at=func.current_timestamp())
    )


def set_research_domains(conn: Connection, domains: list[dict[str, Any]] | None) -> None:
    """Persist the dashboard's domain decomposition (inc 83) — a list of {label, terms, paper_ids}. No-op if
    the profile is unset."""
    existing = get_profile(conn)
    if existing is None:
        return
    conn.execute(
        update(profile)
        .where(profile.c.id == int(existing["id"]))
        .values(research_domains=domains or None, updated_at=func.current_timestamp())
    )


def get_decisions(conn: Connection) -> dict[str, set[int]]:
    """{'confirmed': {paper_id, …}, 'rejected': {…}} — applied by the resolver every run."""
    out: dict[str, set[int]] = {"confirmed": set(), "rejected": set()}
    for row in conn.execute(select(my_publication_decisions.c.paper_id, my_publication_decisions.c.decision)):
        decision = str(row[1])
        if decision in out:
            out[decision].add(int(row[0]))
    return out


def set_decision(conn: Connection, paper_id: int, decision: str) -> None:
    """Upsert a confirm/reject decision for a paper (one row per paper)."""
    conn.execute(delete(my_publication_decisions).where(my_publication_decisions.c.paper_id == paper_id))
    conn.execute(insert(my_publication_decisions).values(paper_id=paper_id, decision=decision))
