"""Followed authors — the follow/unfollow primitive + a library-frequency suggestion list (backlog #29, inc 454;
consolidated into Discover -> Feed 2026-08-27, dropping the standalone tab's gap-candidate view).

`suggest_authors_to_follow` is Feed's Suggest-modal "Author" tab data source: a plain, inspectable tally of how
often each author recurs across the user's own library, excluding the user and anyone already followed — never
an opaque score or a recommendation of a person (mirrors my_publications.py's "authors citing your work" posture).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, select

from app.backend.persistence.followed_author_repo import list_followed_authors
from app.backend.persistence.profile_repo import get_profile
from app.backend.persistence.schema import papers


def suggest_authors_to_follow(conn: Connection, *, limit: int = 20) -> list[dict[str, Any]]:
    """Authors ranked by paper count across the live library, excluding the user's own name (last-name-token
    match against the user's profile, the `_family_tokens` convention also used in my_publications.py and
    citation_equity.py) and anyone already followed. Case-insensitive dedup; displays the original casing."""
    profile = get_profile(conn) or {}
    self_tokens = _self_family_tokens(profile)
    followed = {row["display_name"].strip().lower() for row in list_followed_authors(conn)}

    rows = conn.execute(select(papers.c.csl_json).where(papers.c.deleted_at.is_(None), papers.c.csl_json.is_not(None)))
    counts: dict[str, int] = {}
    displays: dict[str, str] = {}
    for (csl_json,) in rows:
        for name in _authors_from_csl(csl_json):
            key = name.strip().lower()
            if not key or key in followed:
                continue
            last = key.split()[-1] if key.split() else key
            if last in self_tokens:
                continue
            counts[key] = counts.get(key, 0) + 1
            displays.setdefault(key, name.strip())

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], displays[kv[0]]))[:limit]
    return [{"name": displays[key], "paper_count": count} for key, count in ranked]


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
