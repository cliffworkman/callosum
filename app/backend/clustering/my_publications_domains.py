"""My-Publications research-domain decomposition (inc 83), split from ``my_publications`` for the 600-line cap
(inc D). Clusters the user's CONFIRMED My-Publications papers into research DOMAINS and persists the decomposition
to ``profile.research_domains``. LLM-free local clustering (reuses the inc-52 axis-suggestion machinery).

The domain **compute** phase (``_decompose_compute``) does no DB writes except the OpenAlex works cache (which
self-commits in a fetch-outside-lock job), so the async job can run it lock-free then persist in a short
transaction; ``decompose_domains`` is the unchanged all-in-one wrapper for direct callers (inc D)."""

from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy import Connection, and_, or_, select

from app.backend.clustering.abstract_clustering import AgglomerativeAbstractClusterer
from app.backend.clustering.axis_suggestion import (
    _l2_normalize,
    _label_from_terms,
    _paper_tokens,
    _top_terms_per_cluster,
)
from app.backend.clustering.my_publications import CONFIRMED_CONFIDENCE, _get_axis_id
from app.backend.embeddings.pipeline import paper_embedding_text
from app.backend.persistence.profile_repo import get_profile, set_research_domains
from app.backend.persistence.schema import cluster_node_papers, cluster_nodes, papers

MIN_DOMAIN_PAPERS = 4  # below this, clustering the own corpus isn't meaningful
TARGET_DOMAIN_SIZE = 4
MAX_DOMAINS = 8


def decompose_domains(conn: Connection, *, model, author_client) -> dict[str, Any]:
    """Cluster the user's CONFIRMED My-Publications papers into research DOMAINS (inc 83) and persist the
    decomposition (label + c-TF-IDF terms + paper ids) to ``profile.research_domains``. Also refreshes the OpenAlex
    works cache so the dashboard's impact-by-domain citations are current (metadata egress, NOT the Gemini gate).
    All-in-one on one connection (unchanged for direct callers); the async job runs ``_decompose_compute``
    (lock-free) then ``set_research_domains`` (a short write) separately so its fetch doesn't hold the lock (inc D)."""
    status, domains = _decompose_compute(conn, model=model, author_client=author_client)
    if status is not None:
        return status
    set_research_domains(conn, domains)
    return {"status": "ok", "domain_count": len(domains)}


def _decompose_compute(conn: Connection, *, model, author_client):
    """Compute phase (inc D): read the confirmed members, cluster into domains, and freshen the works cache — NO
    conn writes except the works cache (self-committing in a fetch-outside-lock job). Returns
    ``(status | None, domains)``; a non-None status short-circuits (no persist)."""
    profile = get_profile(conn)
    if not profile or not profile.get("openalex_author_id"):
        return {"status": "not-resolved"}, []
    rows = _confirmed_member_rows(conn)
    if len(rows) < MIN_DOMAIN_PAPERS:
        return {"status": "too-few", "count": len(rows)}, []

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
    _reapply_custom_labels(
        domains, profile.get("research_domains")
    )  # SP2 #15: keep user-renamed labels across re-decompose

    try:  # freshen per-work citations (an old cache lacks cited_by_count); failure leaves clustering intact
        author_client.fetch_author_works(conn, str(profile["openalex_author_id"]), refresh=True)
    except Exception:
        pass
    return None, domains


def _reapply_custom_labels(domains: list[dict[str, Any]], old_domains: Any) -> None:
    """SP2 (#15): carry user-renamed (``custom``) domain labels from the previous decomposition onto the freshly
    clustered domains by best paper-overlap (Jaccard ≥ 0.5), so Re-decompose doesn't wipe custom names. Mutates
    ``domains`` in place; each old custom label is reused at most once (highest-overlap new domain wins)."""
    snapshots = [
        (d.get("label"), {int(p) for p in (d.get("paper_ids") or [])})
        for d in (old_domains or [])
        if d.get("custom") and d.get("label")
    ]
    if not snapshots:
        return
    used: set[int] = set()
    for dom in domains:
        ids = {int(p) for p in (dom.get("paper_ids") or [])}
        if not ids:
            continue
        best_i, best_j = -1, 0.0
        for i, (_label, old_ids) in enumerate(snapshots):
            if i in used or not old_ids:
                continue
            jaccard = len(ids & old_ids) / len(ids | old_ids)
            if jaccard > best_j:
                best_i, best_j = i, jaccard
        if best_i >= 0 and best_j >= 0.5:
            dom["label"] = snapshots[best_i][0]
            dom["custom"] = True
            used.add(best_i)


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
