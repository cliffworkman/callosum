"""Followed authors — the follow/unfollow primitive + a library-frequency suggestion list (backlog #29, inc 454;
consolidated into Discover -> Feed 2026-08-27, dropping the standalone tab's gap-candidate view).

`suggest_authors_to_follow` is Feed's Suggest-modal "Author" tab data source: a plain, inspectable tally of how
often each author recurs across the user's own library, excluding the user and anyone already followed — never
an opaque score or a recommendation of a person (mirrors my_publications.py's "authors citing your work" posture).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, or_, select

from app.backend.clustering.my_publications import CONFIRMED_CONFIDENCE, MY_PUBLICATIONS_KIND
from app.backend.persistence.followed_author_repo import list_followed_authors
from app.backend.persistence.profile_repo import get_profile
from app.backend.persistence.schema import axes, cluster_node_papers, cluster_nodes, papers

# Real CSL-JSON author data sometimes carries a literal placeholder instead of an actual name -- an
# "et al." artifact from whatever upstream metadata source produced it, not something callosum invents.
# Excluded a priori; never surfaced as if it were a real recurring co-author.
_NON_NAME_AUTHOR_TOKENS = {"others", "et al", "et al.", "and others", "anonymous"}


def suggest_authors_to_follow(
    conn: Connection,
    *,
    limit: int = 20,
    axis_id: int | None = None,
    exclude_coauthors: bool = False,
) -> list[dict[str, Any]]:
    """Authors ranked by paper count across the live library, excluding the user's own name (last-name-token
    match against the user's profile, the `_family_tokens` convention also used in my_publications.py and
    citation_equity.py), anyone already followed, and known non-name placeholder strings. Case-insensitive
    dedup; displays the original casing. ``axis_id`` restricts the scanned papers to that axis's members (the
    same `cluster_node_papers`/`cluster_nodes` subquery gap-finder uses). ``exclude_coauthors`` additionally
    drops anyone who appears as an author on a confirmed/manual My-Publications paper (a real co-author),
    matched on the full name rather than the looser last-name-only self-match above."""
    profile = get_profile(conn) or {}
    self_tokens = _self_family_tokens(profile)
    followed = {row["display_name"].strip().lower() for row in list_followed_authors(conn)}
    coauthors = _coauthor_names(conn) if exclude_coauthors else set()

    stmt = select(papers.c.id, papers.c.csl_json).where(papers.c.deleted_at.is_(None), papers.c.csl_json.is_not(None))
    if axis_id is not None:
        axis_members = (
            select(cluster_node_papers.c.paper_id)
            .join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
            .where(cluster_nodes.c.axis_id == axis_id)
        )
        stmt = stmt.where(papers.c.id.in_(axis_members))
    rows = conn.execute(stmt)

    counts: dict[str, int] = {}
    displays: dict[str, str] = {}
    paper_ids: dict[str, list[int]] = {}
    for paper_id, csl_json in rows:
        for name in _authors_from_csl(csl_json):
            key = name.strip().lower()
            if not key or key in followed or key in _NON_NAME_AUTHOR_TOKENS or key in coauthors:
                continue
            last = key.split()[-1] if key.split() else key
            if last in self_tokens:
                continue
            counts[key] = counts.get(key, 0) + 1
            displays.setdefault(key, name.strip())
            paper_ids.setdefault(key, []).append(int(paper_id))

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], displays[kv[0]]))[:limit]
    return [{"name": displays[key], "paper_count": count, "paper_ids": paper_ids[key]} for key, count in ranked]


def _coauthor_names(conn: Connection) -> set[str]:
    """Full lower-cased author names appearing on any confirmed (DOI-matched, confidence >= CONFIRMED_CONFIDENCE)
    or manual (confidence NULL) My-Publications paper -- i.e. a paper the user has actually verified is their
    own. Deliberately excludes the 0.25-confidence name-only candidate tier, which hasn't been confirmed as the
    user's own work yet. Matches on the FULL name (not last-name-only, unlike the self-exclusion above) so an
    unrelated author who merely shares a surname with a real co-author isn't over-excluded."""
    axis_id = conn.execute(select(axes.c.id).where(axes.c.kind == MY_PUBLICATIONS_KIND).limit(1)).scalar_one_or_none()
    if axis_id is None:
        return set()
    node_id = conn.execute(
        select(cluster_nodes.c.id)
        .where(cluster_nodes.c.axis_id == int(axis_id), cluster_nodes.c.parent_id.is_(None))
        .limit(1)
    ).scalar_one_or_none()
    if node_id is None:
        return set()
    rows = conn.execute(
        select(papers.c.csl_json)
        .select_from(cluster_node_papers.join(papers, papers.c.id == cluster_node_papers.c.paper_id))
        .where(
            cluster_node_papers.c.cluster_node_id == int(node_id),
            papers.c.deleted_at.is_(None),
            papers.c.csl_json.is_not(None),
            or_(cluster_node_papers.c.confidence.is_(None), cluster_node_papers.c.confidence >= CONFIRMED_CONFIDENCE),
        )
    )
    names: set[str] = set()
    for (csl_json,) in rows:
        for name in _authors_from_csl(csl_json):
            key = name.strip().lower()
            if key:
                names.add(key)
    return names


def _self_family_tokens(profile: dict[str, Any]) -> set[str]:
    """Last-name tokens from the user's own display name + variants — a local copy of the `_family_tokens`
    convention (`my_publications.py`), not a cross-module import of that module's private helper."""
    names = [profile.get("display_name") or ""] + list(profile.get("name_variants") or [])
    tokens: set[str] = set()
    for name in names:
        parts = str(name).strip().split()
        if parts:
            tokens.add(parts[-1].lower())
    return tokens


def _authors_from_csl(csl_json: Any) -> list[str]:
    """Extract a paper's author display strings from its CSL-JSON `author` array — the same small pattern
    already duplicated in `routers/papers.py`, `clustering/duplicate_detection.py`,
    `metadata/citation_export.py`, and `methods/reference_integrity.py`; a local copy here rather than a
    cross-module import (rule #7 — no drive-by refactor of those four)."""
    out: list[str] = []
    for author in (csl_json or {}).get("author") or []:
        literal, family, given = author.get("literal"), author.get("family"), author.get("given")
        if literal:
            out.append(str(literal))
        elif family and given:
            out.append(f"{given} {family}")
        elif family:
            out.append(str(family))
    return out
