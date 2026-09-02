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
    """Create or update identity fields, invalidating a cached author match when that identity changes."""
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
        identity_changed = any(existing.get(key) != values[key] for key in ("display_name", "name_variants", "orcid"))
        if identity_changed:
            values["openalex_author_id"] = None
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


def rename_domain(conn: Connection, paper_ids: list[int], label: str) -> bool:
    """SP2 (inc 118, #15): rename the research domain identified by its exact paper_ids set, marking it ``custom``
    so a Re-decompose preserves the name (by paper-overlap). Returns False if no domain matches."""
    existing = get_profile(conn)
    domains = (existing or {}).get("research_domains") or []
    target = {int(p) for p in paper_ids}
    for d in domains:
        if {int(p) for p in (d.get("paper_ids") or [])} == target:
            d["label"] = label.strip()[:80]
            d["custom"] = True
            set_research_domains(conn, domains)
            return True
    return False


def set_starred(conn: Connection, paper_id: int, starred: bool) -> None:
    """Star/unstar a paper in My Publications (inc 84). Stored as a sorted id list on the profile. No-op if
    the profile is unset."""
    existing = get_profile(conn)
    if existing is None:
        return
    ids = {int(x) for x in (existing.get("starred_paper_ids") or [])}
    if starred:
        ids.add(int(paper_id))
    else:
        ids.discard(int(paper_id))
    conn.execute(
        update(profile)
        .where(profile.c.id == int(existing["id"]))
        .values(starred_paper_ids=sorted(ids) or None, updated_at=func.current_timestamp())
    )


def replace_paper_id(conn: Connection, old_id: int, new_id: int) -> None:
    """Repoint any My-Publications references to ``old_id`` onto ``new_id`` (inc 161, paper merge): in
    ``starred_paper_ids`` and every ``research_domains[].paper_ids`` list, swap old→new and dedup, so a merged-away
    paper doesn't linger as a phantom/trashed entry. No-op if the profile is unset or has no such reference."""
    existing = get_profile(conn)
    if existing is None or old_id == new_id:
        return
    values: dict[str, Any] = {}

    starred = [int(x) for x in (existing.get("starred_paper_ids") or [])]
    if old_id in starred:
        swapped = {new_id if x == old_id else x for x in starred}
        values["starred_paper_ids"] = sorted(swapped) or None

    domains = existing.get("research_domains") or []
    changed = False
    for d in domains:
        ids = [int(x) for x in (d.get("paper_ids") or [])]
        if old_id in ids:
            d["paper_ids"] = sorted({new_id if x == old_id else x for x in ids})
            changed = True
    if changed:
        values["research_domains"] = domains

    if values:
        values["updated_at"] = func.current_timestamp()
        conn.execute(update(profile).where(profile.c.id == int(existing["id"])).values(**values))


def dismiss_work(conn: Connection, doi: str) -> None:
    """Dismiss an OpenAlex-indexed work from the missing-works review queue (inc 85), by normalized DOI. So it
    is not re-proposed. No-op if the profile is unset or the DOI is blank."""
    normalized = (doi or "").strip().lower()
    if not normalized:
        return
    existing = get_profile(conn)
    if existing is None:
        return
    dois = {str(d).strip().lower() for d in (existing.get("dismissed_work_dois") or []) if str(d).strip()}
    dois.add(normalized)
    conn.execute(
        update(profile)
        .where(profile.c.id == int(existing["id"]))
        .values(dismissed_work_dois=sorted(dois), updated_at=func.current_timestamp())
    )


def undismiss_work(conn: Connection, doi: str) -> None:
    """Un-dismiss a previously-dismissed missing work (inc 91), by normalized DOI — it returns to the
    missing-works review queue (mirror of inc-67's un-dismiss-duplicates). No-op if the profile is unset,
    the DOI is blank, or it wasn't dismissed."""
    normalized = (doi or "").strip().lower()
    if not normalized:
        return
    existing = get_profile(conn)
    if existing is None:
        return
    dois = {str(d).strip().lower() for d in (existing.get("dismissed_work_dois") or []) if str(d).strip()}
    if normalized not in dois:
        return
    dois.discard(normalized)
    conn.execute(
        update(profile)
        .where(profile.c.id == int(existing["id"]))
        .values(dismissed_work_dois=sorted(dois) or None, updated_at=func.current_timestamp())
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


def dismiss_gap(conn: Connection, key: str) -> None:
    """Dismiss a literature-gap candidate (inc 135) by a stable key (its OpenAlex id and/or DOI) so a re-run
    doesn't resurface it. Unlike the My-Pubs dismissals, the gap-finder doesn't require a profile, so this
    inserts a minimal profile row if none exists. No-op on a blank key."""
    normalized = (key or "").strip()
    if not normalized:
        return
    existing = get_profile(conn)
    if existing is None:
        conn.execute(insert(profile).values(dismissed_gap_works=[normalized]))
        return
    keys = {str(k).strip() for k in (existing.get("dismissed_gap_works") or []) if str(k).strip()}
    keys.add(normalized)
    conn.execute(
        update(profile)
        .where(profile.c.id == int(existing["id"]))
        .values(dismissed_gap_works=sorted(keys), updated_at=func.current_timestamp())
    )


def dismissed_gaps(conn: Connection) -> set[str]:
    """The set of dismissed gap keys (OpenAlex ids + DOIs); empty when the profile is unset."""
    existing = get_profile(conn)
    if existing is None:
        return set()
    return {str(k).strip() for k in (existing.get("dismissed_gap_works") or []) if str(k).strip()}
