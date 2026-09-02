"""Followed-author Feed source (backlog #29, inc 455): a followed author's own works flow into the chronological
Feed. Reuses the already-audited `OpenAlexAuthorClient` -- no new host/dependency.

Deliberately does NOT dedupe against the library at write time -- Feed's own established convention (journal /
bioRxiv / PubMed all store everything polled and compute `in_library` at READ time via `feed_view`) -- importing
a paper is reflected without a re-poll, and Feed keeps its full chronological history regardless of library state.
(The standalone Followed Authors tab's separate library-deduped gap list was retired 2026-08-27, consolidating
this feature into Feed alone.)

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
            if hasattr(self.author_client, "fetch_author_works_result"):
                result = self.author_client.fetch_author_works_result(conn, author_id, refresh=True)
                if not result.complete:
                    raise RuntimeError("OpenAlex author-work refresh was incomplete")
                works = list(result.works)
            else:
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
    if not work.doi:  # no DOI, no stable dedup_key
        return None
    return FeedEntry(
        dedup_key=f"doi:{work.doi}",
        title=work.title or work.doi,
        doi=work.doi,
        year=work.year,
        # inc 458 (backlog #28): OpenAlex's Work object DOES carry a real "YYYY-MM-DD" (`publication_date`), now
        # fetched + validated in `_work_from_obj`/`_normalize_publication_date` -- prefer it for day-level Feed
        # sort precision. Pre-458 cached works (or a work OpenAlex itself never dated precisely) fall back to the
        # bare year: feed_repo.list_items sorts by `posted_date DESC` and SQLite treats NULL as smallest, so
        # leaving this unset would sink the item to the bottom regardless of recency, and a bare "YYYY" still
        # sorts correctly against full "YYYY-MM-DD" strings from other sources (a shorter string that's a prefix
        # of a longer one compares as "less than" it) -- just without day-level precision within the same year.
        posted_date=work.publication_date or (str(work.year) if work.year else None),
    )
