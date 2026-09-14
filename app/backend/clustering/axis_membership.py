"""Canonical axis-membership resolution — the ONE place "which papers are in this axis" is computed (inc 602).

Extracted so axis-scoped Ask (#82), the gap-finder (inc 63), and the axes read endpoint all consume the same
membership + tier logic rather than textually-identical copies. Membership is the stored `cluster_node_papers`
rows for the axis (below-threshold is never written by scoring, so a row's existence already means the paper
cleared the floor). The assigned/uncertain/manual tier is a *display* classification recomputed from the stored
confidence against the axis cutoff — NOT a persisted adoption state, and never researcher "endorsement."

All bound-param (rule #3). Pure data access; no network, no model.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import Connection, Select, select

from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.paper_query_repo import DEFAULT_AXIS_CUTOFF
from app.backend.persistence.schema import attachments, chunks, cluster_node_papers, cluster_nodes, papers

MemberTier = Literal["manual", "assigned", "uncertain"]
# The two Ask-eligibility policies exposed to the user (the interstitial toggle). "assigned" = confident members
# only (deliberate manual adds + scored-above-cutoff); "all" additionally includes the "uncertain" tier
# (scored-but-below-cutoff — "a candidate to confirm"). below-threshold papers are in neither (never stored).
EligibilityTier = Literal["assigned", "all"]


def axis_member_paper_ids_select(axis_id: int) -> Select:
    """A correlated ``Select`` of the axis's member paper_ids (all stored members). Used in an ``.in_()`` so a
    large axis never materializes a Python id list into a bound-parameter set (SQLITE_MAX_VARIABLE_NUMBER)."""
    return (
        select(cluster_node_papers.c.paper_id)
        .join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
        .where(cluster_nodes.c.axis_id == axis_id)
    )


def classify_member(confidence: float | None, cutoff: float) -> MemberTier:
    """The canonical member tier (identical to the axes read endpoint's own rule): a NULL confidence is a manual
    human override; a score at/above the axis cutoff is `assigned`; a stored score below it is `uncertain`
    (a candidate to confirm, never a verdict)."""
    if confidence is None:
        return "manual"
    return "assigned" if confidence >= cutoff else "uncertain"


def axis_cutoff(scoring_gain: float | None) -> float:
    """The axis's absolute assignment cutoff: its stored `scoring_gain`, or the default when unset."""
    return float(scoring_gain) if scoring_gain is not None else DEFAULT_AXIS_CUTOFF


def _member_rows(conn: Connection, axis_id: int) -> dict[int, float | None]:
    """Live member papers → the most-favorable confidence across the axis's nodes (a paper in root+subcategory
    appears once; a manual/NULL confidence in any node wins, since a deliberate add is always eligible)."""
    stmt = (
        select(cluster_node_papers.c.paper_id, cluster_node_papers.c.confidence)
        .join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
        .join(papers, papers.c.id == cluster_node_papers.c.paper_id)
        .where(cluster_nodes.c.axis_id == axis_id, papers.c.deleted_at.is_(None))
    )
    best: dict[int, float | None] = {}
    for pid, conf in conn.execute(stmt):
        pid = int(pid)
        if pid not in best:
            best[pid] = conf
        elif best[pid] is None or conf is None:
            best[pid] = None  # manual wins
        else:
            best[pid] = max(float(best[pid]), float(conf))
    return best


def papers_with_usable_fulltext(conn: Connection, paper_ids: list[int]) -> set[int]:
    """Of ``paper_ids``, those with ≥1 article-fulltext chunk on a live paper — the EXACT eligibility the Ask
    retrieval pool uses (``attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES)`` + live filter), reused so
    the pre-run disclosure count and the actual retrieval corpus cannot drift."""
    if not paper_ids:
        return set()
    stmt = (
        select(chunks.c.paper_id)
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .join(papers, papers.c.id == chunks.c.paper_id)
        .where(
            chunks.c.paper_id.in_(paper_ids),
            papers.c.deleted_at.is_(None),
            attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES),
        )
        .distinct()
    )
    return {int(row[0]) for row in conn.execute(stmt)}


def resolve_axis_corpus(conn: Connection, axis_id: int, tier: EligibilityTier, *, cutoff: float) -> list[int]:
    """The concrete eligible paper-id set for an axis Ask, resolved at execution time. `tier="assigned"` keeps
    manual + assigned members; `tier="all"` keeps every stored member (adds uncertain). Sorted for determinism;
    never widened beyond the axis's own members."""
    members = _member_rows(conn, axis_id)
    keep_uncertain = tier == "all"
    out = [pid for pid, conf in members.items() if keep_uncertain or classify_member(conf, cutoff) != "uncertain"]
    return sorted(out)
