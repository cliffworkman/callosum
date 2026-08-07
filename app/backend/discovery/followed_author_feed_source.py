"""Followed-author Feed source (backlog #29, inc 455): a followed author's own works flow into the chronological
Feed too, not just the dedicated "what am I missing" gap list (inc 454, `clustering/followed_authors.py`).
Reuses the already-audited `OpenAlexAuthorClient` -- no new host/dependency.

Deliberately does NOT dedupe against the library at write time -- unlike `compute_followed_author_candidates`,
whose whole point IS library-dedup for the gap list. This mirrors Feed's own established convention (journal /
bioRxiv / PubMed all store everything polled and compute `in_library` at READ time via `feed_view`) -- importing
a paper is reflected without a re-poll, and Feed keeps its full chronological history regardless of library state.

`FeedSource.fetch(value, *, limit)` receives no DB connection (every other source is a stateless HTTP wrapper),
but `OpenAlexAuthorClient.fetch_author_works` needs one for its cache read -- so this source holds its own
`Engine` (injected at construction, from `app.py`) and opens a short-lived connection internally.
"""

from __future__ import annotations

from sqlalchemy import Engine

from app.backend.discovery.feed import FeedEntry
from integrations.openalex import AuthorWork, OpenAlexAuthorClient


class FollowedAuthorFeedSource:
    kind = "followed_author"
    label = "Followed author"
    placeholder = ""
    suggestions: list[str] = []
    user_addable = False  # the Followed Authors tab's resolve flow is the only sanctioned way to follow an author

    def __init__(self, engine: Engine, author_client: OpenAlexAuthorClient) -> None:
        self.engine = engine
        # self-committing cache writes (the inc-454 pattern) so the plain read connection below never blocks on
        # a write lock held by a concurrent Feed refresh's own transaction.
        self.author_client = (
            author_client.with_cache_engine(engine) if hasattr(author_client, "with_cache_engine") else author_client
        )

    def fetch(self, value: str, *, limit: int) -> list[FeedEntry]:
        author_id = (value or "").strip()
        if not author_id:
            return []
        with self.engine.connect() as conn:
            works = self.author_client.fetch_author_works(conn, author_id, refresh=True)
        ranked = sorted(works, key=lambda w: (-(w.year or 0), w.title or ""))
        out: list[FeedEntry] = []
        for work in ranked:
            entry = _to_entry(work)
            if entry is None:
                continue
            out.append(entry)
            if len(out) >= max(limit, 1):
                break
        return out


def _to_entry(work: AuthorWork) -> FeedEntry | None:
    if not work.doi:  # mirrors compute_followed_author_candidates' own bar -- no DOI, no stable dedup_key
        return None
    return FeedEntry(
        dedup_key=f"doi:{work.doi}",
        title=work.title or work.doi,
        doi=work.doi,
        year=work.year,
        # OpenAlex's authored-works listing only gives a coarse year, never a full date -- but feed_repo.list_items
        # sorts by `posted_date DESC` and SQLite treats NULL as smallest, so leaving this unset would sink every
        # followed-author item to the bottom regardless of recency. A bare "YYYY" still sorts correctly against
        # full "YYYY-MM-DD" strings from other sources (a shorter string that's a prefix of a longer one compares
        # as "less than" it), just without day-level precision within the same year.
        posted_date=str(work.year) if work.year else None,
    )
