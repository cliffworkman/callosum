"""My Publications resolver (inc 78) — the LLM-free service that populates the user's own-papers axis.

Resolve the profile identity to an OpenAlex author (ORCID-first), fetch their works, intersect the local
library by DOI (→ **confirmed** members), add a conservative name-only fallback (→ **candidates** the user
confirms/rejects), and write memberships into the special ``kind="my_publications"`` axis. Honors the
decisions store (rejected excluded; confirmed kept as manual overrides). Also exposes the cache-based import
hook ``maybe_add_to_my_publications`` (zero extra egress). No model tokens are consumed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy import Connection, and_, delete, insert, or_, select

from app.backend.clustering.abstract_clustering import AgglomerativeAbstractClusterer
from app.backend.clustering.axis_assignments import (
    add_manual_assignment,
    ensure_axis_node,
    manual_assignment_paper_ids,
)
from app.backend.clustering.axis_suggestion import (
    _l2_normalize,
    _label_from_terms,
    _paper_tokens,
    _top_terms_per_cluster,
)
from app.backend.embeddings.pipeline import paper_embedding_text
from app.backend.metadata.abstract_display import abstract_plain_text
from app.backend.persistence.profile_repo import (
    get_decisions,
    get_profile,
    set_openalex_author_id,
    set_research_domains,
)
from app.backend.persistence.repository import get_paper
from app.backend.persistence.schema import axes, cluster_node_papers, cluster_nodes, papers
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
        conn.execute(
            insert(cluster_node_papers).values(
                cluster_node_id=node_id, paper_id=paper_id, confidence=CONFIRMED_CONFIDENCE
            )
        )
        confirmed_written += 1
    candidates_written = 0
    for paper_id in sorted(name_candidates):
        if paper_id in manual_ids or paper_id in rejected:
            continue
        conn.execute(
            insert(cluster_node_papers).values(
                cluster_node_id=node_id, paper_id=paper_id, confidence=CANDIDATE_CONFIDENCE
            )
        )
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
        conn.execute(
            insert(cluster_node_papers).values(
                cluster_node_id=node_id, paper_id=paper_id, confidence=CONFIRMED_CONFIDENCE
            )
        )


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


def build_dashboard(conn: Connection, *, author_client) -> dict[str, Any]:
    """Assemble the My Publications impact dashboard (Layer 1, inc 81) from ALREADY-CACHED OpenAlex data + the
    local library — a cache-only read that makes NO network call (gated on the profile having been resolved).
    Returns a status summary; the caller renders by status. Headline metrics are OpenAlex's authoritative
    figures (works_count over the whole indexed record, NOT the library subset), shown verbatim + attributed."""
    profile = get_profile(conn)
    if not profile or not ((profile.get("display_name") or "").strip() or (profile.get("orcid") or "").strip()):
        return {"status": "no-identity"}
    if not profile.get("openalex_author_id"):
        return {"status": "not-resolved"}

    author = author_client.cached_author(conn, orcid=profile.get("orcid"), name=profile.get("display_name"))
    if author is None:
        return {"status": "not-resolved"}

    works = author_client.fetch_author_works(conn, author.author_id)  # cache-first; warm when author_id is set
    pubs_by_year: dict[int, int] = {}
    for work in works:
        if work.year:
            pubs_by_year[work.year] = pubs_by_year.get(work.year, 0) + 1
    work_dois = {w.doi for w in works if w.doi}
    in_library = len(_live_papers_by_doi(conn, work_dois)) if work_dois else 0

    cached_works = get_cached(conn, OPENALEX_WORKS_PROVIDER, author.author_id)
    as_of = str(cached_works["fetched_at"]) if cached_works is not None and cached_works.get("fetched_at") else None

    return {
        "status": "ok",
        "name": author.display_name or (profile.get("display_name") or "").strip() or None,
        "as_of": as_of,
        "metrics": {
            "works_count": author.works_count,
            "cited_by_count": author.cited_by_count,
            "h_index": author.h_index,
            "i10_index": author.i10_index,
        },
        "pubs_by_year": [{"year": y, "count": pubs_by_year[y]} for y in sorted(pubs_by_year)],
        "counts_by_year": [dict(c) for c in author.counts_by_year],
        "indexed_works": author.works_count,
        "in_library": in_library,
        "gap": max(0, author.works_count - in_library),
        "research_summary": profile.get("research_summary"),
        "domains": _dashboard_domains(conn, profile.get("research_domains"), works),
    }


def my_publication_documents(
    conn: Connection, *, limit: int = 100, only_paper_ids: set[int] | None = None
) -> list[dict[str, str]]:
    """The titles (+ JATS-stripped abstract) of the papers in the My Publications axis — the grounded input
    for the research-summary generation. Live papers only; capped. ``only_paper_ids`` (inc 84) restricts to a
    subset (the user's starred papers). Empty list if the axis has no members (or none of the subset match)."""
    axis_id = _get_axis_id(conn)
    if axis_id is None:
        return []
    node_id = conn.execute(
        select(cluster_nodes.c.id)
        .where(and_(cluster_nodes.c.axis_id == int(axis_id), cluster_nodes.c.parent_id.is_(None)))
        .limit(1)
    ).scalar_one_or_none()
    if node_id is None:
        return []
    where = [cluster_node_papers.c.cluster_node_id == int(node_id), papers.c.deleted_at.is_(None)]
    if only_paper_ids is not None:
        if not only_paper_ids:
            return []
        where.append(papers.c.id.in_({int(p) for p in only_paper_ids}))
    rows = conn.execute(
        select(papers.c.title, papers.c.abstract)
        .select_from(cluster_node_papers.join(papers, papers.c.id == cluster_node_papers.c.paper_id))
        .where(and_(*where))
        .limit(limit)
    )
    documents: list[dict[str, str]] = []
    for title, abstract in rows:
        if title:
            documents.append({"title": str(title), "abstract": abstract_plain_text(abstract) if abstract else ""})
    return documents


MIN_DOMAIN_PAPERS = 4  # below this, clustering the own corpus isn't meaningful
TARGET_DOMAIN_SIZE = 4
MAX_DOMAINS = 8


def decompose_domains(conn: Connection, *, model, author_client) -> dict[str, Any]:
    """Cluster the user's CONFIRMED My-Publications papers into research DOMAINS (inc 83) and persist the
    decomposition (label + c-TF-IDF terms + paper ids) to ``profile.research_domains``. LLM-free local
    clustering (reuses the inc-52 axis-suggestion machinery); also refreshes the OpenAlex works cache so the
    dashboard's impact-by-domain citations are current (metadata egress, NOT the Gemini gate). Returns a status."""
    profile = get_profile(conn)
    if not profile or not profile.get("openalex_author_id"):
        return {"status": "not-resolved"}
    rows = _confirmed_member_rows(conn)
    if len(rows) < MIN_DOMAIN_PAPERS:
        return {"status": "too-few", "count": len(rows)}

    vectors = _l2_normalize(np.array(model.encode_texts([paper_embedding_text(row) for row in rows]), dtype=float))
    n = len(rows)
    k = max(2, min(round(n / TARGET_DOMAIN_SIZE), MAX_DOMAINS, n))
    labels = AgglomerativeAbstractClusterer().fit_predict(vectors.tolist(), cluster_count=k)
    grouped: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        grouped.setdefault(int(label), []).append(index)
    groups = sorted(grouped.values(), key=lambda members: -len(members))

    term_lists = _top_terms_per_cluster([[_paper_tokens(rows[i]) for i in members] for members in groups])
    domains = [
        {"label": _label_from_terms(terms), "terms": terms, "paper_ids": [int(rows[i]["id"]) for i in members]}
        for members, terms in zip(groups, term_lists, strict=False)
    ]

    try:  # freshen per-work citations (an old cache lacks cited_by_count); failure leaves clustering intact
        author_client.fetch_author_works(conn, str(profile["openalex_author_id"]), refresh=True)
    except Exception:
        pass
    set_research_domains(conn, domains)
    return {"status": "ok", "domain_count": len(domains)}


def _confirmed_member_rows(conn: Connection) -> list:
    """Full paper rows for the my_publications axis's CONFIRMED in-library members — confidence IS NULL (manual)
    or >= CONFIRMED_CONFIDENCE; the 0.25 name-only candidates are excluded (don't characterize 'your domains'
    with unconfirmed papers)."""
    axis_id = _get_axis_id(conn)
    if axis_id is None:
        return []
    node_id = conn.execute(
        select(cluster_nodes.c.id)
        .where(and_(cluster_nodes.c.axis_id == int(axis_id), cluster_nodes.c.parent_id.is_(None)))
        .limit(1)
    ).scalar_one_or_none()
    if node_id is None:
        return []
    rows = conn.execute(
        select(papers)
        .select_from(cluster_node_papers.join(papers, papers.c.id == cluster_node_papers.c.paper_id))
        .where(
            and_(
                cluster_node_papers.c.cluster_node_id == int(node_id),
                papers.c.deleted_at.is_(None),
                or_(
                    cluster_node_papers.c.confidence.is_(None),
                    cluster_node_papers.c.confidence >= CONFIRMED_CONFIDENCE,
                ),
            )
        )
        .order_by(papers.c.id)
    ).mappings()
    return list(rows)


def _dashboard_domains(conn: Connection, domains_json: Any, works: list) -> list[dict[str, Any]]:
    """Enrich the persisted domains with per-domain impact: paper count, summed OpenAlex citations, and the
    member papers' years (for the dashboard's client-side chart re-filter). Sorted by citations (impact)."""
    if not domains_json or not isinstance(domains_json, list):
        return []
    work_by_doi = {w.doi: w for w in works if w.doi}
    all_ids = sorted({int(pid) for d in domains_json for pid in (d.get("paper_ids") or [])})
    if not all_ids:
        return []
    info: dict[int, tuple[str | None, int | None]] = {}
    for row in conn.execute(
        select(papers.c.id, papers.c.doi, papers.c.year).where(
            and_(papers.c.id.in_(all_ids), papers.c.deleted_at.is_(None))
        )
    ):
        info[int(row[0])] = ((str(row[1]).strip().lower() if row[1] else None), row[2])
    out: list[dict[str, Any]] = []
    for domain in domains_json:
        pids = [int(p) for p in (domain.get("paper_ids") or []) if int(p) in info]
        citations = 0
        years: list[int] = []
        for pid in pids:
            doi, paper_year = info[pid]
            work = work_by_doi.get(doi) if doi else None
            citations += work.cited_by_count if work else 0
            year = work.year if (work and work.year) else paper_year
            if year:
                years.append(int(year))
        out.append(
            {
                "label": domain.get("label") or "Domain",
                "terms": list(domain.get("terms") or []),
                "paper_count": len(pids),
                "citation_count": citations,
                "paper_years": sorted(years),
            }
        )
    out.sort(key=lambda d: -d["citation_count"])
    return out
