"""Followed authors — a lightweight gap-finder source (backlog #29, inc 454).

Sibling to `gapfinder.py`'s backward/forward directions, not a third value on them: `GapCandidate` has no room
for author provenance and no per-author refresh scope. A followed author's works come from an explicit
subscription (not derived from the user's own library the way backward/forward's citation graph is), so ranking
by axis relevance would need genuinely new embedding-similarity machinery that doesn't exist for this purpose —
deliberately deferred (see `FOLLOWED_AUTHOR_NOTE`), not silently dropped. This module is a flat, deduped-against-
library candidate list per followed author, capped and cached, exactly the honesty posture the rest of gap-finder
already uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection

from app.backend.persistence.repository import find_existing_paper_by_identity

FOLLOWED_AUTHOR_MAX_CANDIDATES = 50

FOLLOWED_AUTHOR_NOTE = (
    "Based on this author's works recorded in OpenAlex — name/ORCID matching and OpenAlex's own indexing are "
    "both partial, so this isn't necessarily every work they've published. Not filtered or ranked by relevance "
    "to your research axes (that machinery doesn't exist for this source yet) — only deduplicated against your "
    "library."
)


@dataclass(frozen=True)
class FollowedAuthorCandidate:
    author_id: str
    author_display_name: str
    openalex_work_id: str | None
    doi: str
    title: str | None
    year: int | None
    cited_by_count: int


def compute_followed_author_candidates(
    conn: Connection,
    *,
    author_client: Any,
    author_id: str,
    author_display_name: str,
    dismissed: set[str],
    max_candidates: int = FOLLOWED_AUTHOR_MAX_CANDIDATES,
) -> tuple[list[FollowedAuthorCandidate], dict]:
    """One followed author's works absent from the library, newest first. Always forces a live refresh
    (`refresh=True`) — this is ONLY ever called from the refresh job; an ordinary read goes through
    `followed_author_repo.read_followed_author_candidates` instead (zero egress). Returns (candidates, coverage)
    where coverage = {works_checked, note}."""
    works = author_client.fetch_author_works(conn, author_id, refresh=True)
    ranked = sorted(works, key=lambda w: (-(w.year or 0), w.title or ""))
    candidates: list[FollowedAuthorCandidate] = []
    for work in ranked:
        doi = work.doi
        if not doi:  # mirrors gapfinder.py's own bar — no-DOI works can't be deduped/imported, so skip them
            continue
        if doi in dismissed or (work.openalex_work_id and work.openalex_work_id in dismissed):
            continue
        if find_existing_paper_by_identity(conn, doi=doi) is not None:  # already in the library -> not a gap
            continue
        candidates.append(
            FollowedAuthorCandidate(
                author_id=author_id,
                author_display_name=author_display_name,
                openalex_work_id=work.openalex_work_id,
                doi=doi,
                title=work.title,
                year=work.year,
                cited_by_count=work.cited_by_count,
            )
        )
        if len(candidates) >= max_candidates:
            break
    return candidates, {"works_checked": len(works), "note": FOLLOWED_AUTHOR_NOTE}
