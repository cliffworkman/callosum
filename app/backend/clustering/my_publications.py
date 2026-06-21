"""My Publications resolver (inc 78) — the LLM-free service that populates the user's own-papers axis.

Resolve the profile identity to an OpenAlex author (ORCID-first), fetch their works, intersect the local
library by DOI (→ **confirmed** members), add a conservative name-only fallback (→ **candidates** the user
confirms/rejects), and write memberships into the special ``kind="my_publications"`` axis. Honors the
decisions store (rejected excluded; confirmed kept as manual overrides). Also exposes the cache-based import
hook ``maybe_add_to_my_publications`` (zero extra egress). No model tokens are consumed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, and_, delete, insert, select

from app.backend.clustering.axis_assignments import (
    add_manual_assignment,
    ensure_axis_node,
    manual_assignment_paper_ids,
)
from app.backend.persistence.profile_repo import get_decisions, get_profile, set_openalex_author_id
from app.backend.persistence.repository import get_paper
from app.backend.persistence.schema import axes, cluster_node_papers, papers
from integrations.api_cache import get_cached
from integrations.openalex.author import OPENALEX_WORKS_PROVIDER

MY_PUBLICATIONS_KIND = "my_publications"
MY_PUBLICATIONS_LABEL = "My Publications"
CONFIRMED_CONFIDENCE = 0.95  # DOI/OpenAlex-confirmed → renders "assigned"
CANDIDATE_CONFIDENCE = 0.25  # name-only fallback → renders "uncertain" (a candidate to confirm/reject)


def resolve_my_publications(conn: Connection, *, author_client, force: bool = False) -> dict[str, Any]:
    """Resolve + (re)write the My Publications axis memberships. Returns a status summary."""
    profile = get_profile(conn)
    if not profile or not ((profile.get("display_name") or "").strip() or (profile.get("orcid") or "").strip()):
        return {"status": "no-identity"}
    if profile.get("my_publications_dismissed") and not force:
        return {"status": "dismissed"}

    author = author_client.resolve_author(conn, orcid=profile.get("orcid"), name=profile.get("display_name"))
    if author is None:
        return {"status": "no-match", "name": (profile.get("display_name") or "").strip() or None}
    set_openalex_author_id(conn, author.author_id)

    works = author_client.fetch_author_works(conn, author.author_id)
    work_dois = {w.doi for w in works if w.doi}

    doi_matched = _live_papers_by_doi(conn, work_dois) if work_dois else set()
    name_candidates = _name_only_candidates(conn, _family_tokens(profile)) - doi_matched

    decisions = get_decisions(conn)
    rejected, confirmed = decisions["rejected"], decisions["confirmed"]

    axis_id = _get_or_create_axis(conn)
    node_id = ensure_axis_node(conn, axis_id)
    # Rewrite the AUTO memberships (confidence IS NOT NULL); preserve manual/confirmed (NULL) ones.
    conn.execute(
        delete(cluster_node_papers).where(
            and_(cluster_node_papers.c.cluster_node_id == node_id, cluster_node_papers.c.confidence.is_not(None))
        )
    )
    for paper_id in sorted(confirmed):  # decisions.confirmed → manual member (NULL), survives every run
        add_manual_assignment(conn, axis_id=axis_id, paper_id=paper_id)
    manual_ids = manual_assignment_paper_ids(conn, axis_id) | confirmed

    confirmed_written = 0
    for paper_id in sorted(doi_matched):
        if paper_id in manual_ids or paper_id in rejected:
            continue
        conn.execute(insert(cluster_node_papers).values(cluster_node_id=node_id, paper_id=paper_id, confidence=CONFIRMED_CONFIDENCE))
        confirmed_written += 1
    candidates_written = 0
    for paper_id in sorted(name_candidates):
        if paper_id in manual_ids or paper_id in rejected:
            continue
        conn.execute(insert(cluster_node_papers).values(cluster_node_id=node_id, paper_id=paper_id, confidence=CANDIDATE_CONFIDENCE))
        candidates_written += 1

    return {
        "status": "ok",
        "axis_id": axis_id,
        "name": author.display_name or (profile.get("display_name") or "").strip() or None,
        "matched_by": author.matched_by,
        "indexed_works": author.works_count,
        "in_library": len(doi_matched),
        "confirmed": confirmed_written + len(manual_ids),
        "candidates": candidates_written,
    }


def maybe_add_to_my_publications(conn: Connection, paper_id: int) -> None:
    """Import hook: if this paper's DOI is among the cached works of the resolved author, add it as a confirmed
    member of the My Publications axis. A pure DB op (no egress); a no-op when the feature is unused."""
    profile = get_profile(conn)
    if not profile or not profile.get("openalex_author_id") or profile.get("my_publications_dismissed"):
        return
    cached = get_cached(conn, OPENALEX_WORKS_PROVIDER, str(profile["openalex_author_id"]))
    if cached is None or not isinstance(cached["response_json"], dict):
        return
    work_dois = {str(w.get("doi")).lower() for w in (cached["response_json"].get("works") or []) if w.get("doi")}
    if not work_dois:
        return
    try:
        paper = get_paper(conn, paper_id)
    except Exception:
        return
    doi = (paper["doi"] or "").strip().lower()
    if not doi or doi not in work_dois:
        return
    if paper_id in get_decisions(conn)["rejected"]:
        return
    axis_id = _get_axis_id(conn)
    if axis_id is None:  # the axis doesn't exist until the first resolve
        return
    node_id = ensure_axis_node(conn, axis_id)
    already = conn.execute(
        select(cluster_node_papers.c.paper_id).where(
            and_(cluster_node_papers.c.cluster_node_id == node_id, cluster_node_papers.c.paper_id == paper_id)
        )
    ).first()
    if already is None:
        conn.execute(insert(cluster_node_papers).values(cluster_node_id=node_id, paper_id=paper_id, confidence=CONFIRMED_CONFIDENCE))


def _get_axis_id(conn: Connection) -> int | None:
    return conn.execute(select(axes.c.id).where(axes.c.kind == MY_PUBLICATIONS_KIND).limit(1)).scalar_one_or_none()


def _get_or_create_axis(conn: Connection) -> int:
    existing = _get_axis_id(conn)
    if existing is not None:
        return int(existing)
    return int(
        conn.execute(
            insert(axes).values(
                label=MY_PUBLICATIONS_LABEL,
                description="Your own publications, resolved via OpenAlex.",
                kind=MY_PUBLICATIONS_KIND,
            )
        ).inserted_primary_key[0]
    )


def _live_papers_by_doi(conn: Connection, dois: set[str]) -> set[int]:
    rows = conn.execute(
        select(papers.c.id).where(
            and_(papers.c.deleted_at.is_(None), papers.c.doi.is_not(None), papers.c.doi.in_({d.lower() for d in dois}))
        )
    )
    return {int(r[0]) for r in rows}


def _name_only_candidates(conn: Connection, family_tokens: set[str]) -> set[int]:
    """Live papers WITHOUT a DOI whose first-author family matches a profile name token — the conservative,
    flagged last-resort fallback (candidates, never auto-confirmed)."""
    if not family_tokens:
        return set()
    rows = conn.execute(
        select(papers.c.id, papers.c.first_author_family_name).where(
            and_(papers.c.deleted_at.is_(None), papers.c.doi.is_(None))
        )
    )
    out: set[int] = set()
    for pid, family in rows:
        if family and family.strip().lower() in family_tokens:
            out.add(int(pid))
    return out


def _family_tokens(profile: dict[str, Any]) -> set[str]:
    """Last-name tokens from the display name + variants (lower-cased), for the name-only fallback."""
    names = [profile.get("display_name") or ""] + list(profile.get("name_variants") or [])
    tokens = set()
    for name in names:
        parts = str(name).strip().split()
        if parts:
            tokens.add(parts[-1].lower())
    return tokens
