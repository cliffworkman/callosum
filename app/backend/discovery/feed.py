"""The literature Feed engine (backlog #28 SP2, inc 187): a FeedSource registry + the refresh/read service.

Pull-only, opt-in, source-level — there is no auto-subscribe and no push; the user follows a source, then a refresh
polls it. A FeedSource maps a subscription (kind + value) to recent items. Adding a source = `register()` one
FeedSource — no endpoint/UI edit (mirrors the Search SourceRegistry + the acquisition-resolver registry).

`feed_view` computes `in_library` at read time (like the Search tab), so importing a paper is reflected without a
re-poll. Save reuses the Search `save_item` path (metadata-only, deduped, no PDF).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import Connection

from app.backend.persistence import feed_repo
from app.backend.persistence.repository import find_existing_paper_by_identity


@dataclass(frozen=True)
class FeedEntry:
    """A normalized item polled from a feed source (the subset the Feed stores)."""

    dedup_key: str
    title: str
    doi: str | None = None
    authors: tuple[str, ...] = ()
    journal: str | None = None
    year: int | None = None
    url: str | None = None
    abstract: str | None = None
    posted_date: str | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "dedup_key": self.dedup_key,
            "title": self.title,
            "doi": self.doi,
            "authors": list(self.authors),
            "journal": self.journal,
            "year": self.year,
            "url": self.url,
            "abstract": self.abstract,
            "posted_date": self.posted_date,
        }


@runtime_checkable
class FeedSource(Protocol):
    kind: str
    # Optional display metadata the Follow UI renders (a data-driven picker → adding a source needs no frontend edit):
    label: str  # e.g. "bioRxiv category"
    placeholder: str  # e.g. "neuroscience"
    suggestions: list[str]  # optional datalist values (e.g. the bioRxiv categories)

    def fetch(self, value: str, *, limit: int) -> list[FeedEntry]: ...


class FeedRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, FeedSource] = {}

    def register(self, source: FeedSource) -> "FeedRegistry":
        self._sources[source.kind] = source
        return self

    def get(self, kind: str) -> FeedSource | None:
        return self._sources.get(kind)

    @property
    def kinds(self) -> list[str]:
        return list(self._sources)

    @property
    def source_meta(self) -> list[dict[str, Any]]:
        """Per-kind display metadata for the Follow UI (a source without metadata still works — defaults applied)."""
        return [
            {
                "kind": s.kind,
                "label": getattr(s, "label", s.kind),
                "placeholder": getattr(s, "placeholder", ""),
                "suggestions": list(getattr(s, "suggestions", []) or []),
            }
            for s in self._sources.values()
        ]


def build_default_feed_registry() -> FeedRegistry:
    """The shipped feed sources: bioRxiv-by-category (SP2a) + PubMed-keyword + journal-by-ISSN (SP2c). Adding a source
    is one `register()`, no endpoint/UI edit (the Follow picker is data-driven from `source_meta`)."""
    from app.backend.discovery.biorxiv_source import BioRxivFeedSource
    from app.backend.discovery.journal_issn_source import JournalIssnFeedSource
    from app.backend.discovery.pubmed_provider import PubMedKeywordFeedSource

    return (
        FeedRegistry()
        .register(BioRxivFeedSource(server="biorxiv"))
        .register(BioRxivFeedSource(server="medrxiv"))
        .register(PubMedKeywordFeedSource())
        .register(JournalIssnFeedSource())
    )


def refresh_subscriptions(conn: Connection, registry: FeedRegistry, *, limit_per: int = 40) -> dict[str, Any]:
    """Poll every subscription via its source, upsert new items (re-polls don't reset read state). A source that
    raises is skipped (one bad source/subscription never aborts the run). Returns counts."""
    subs = feed_repo.list_subscriptions(conn)
    total_new = 0
    polled = 0
    for sub in subs:
        source = registry.get(str(sub["kind"]))
        if source is None:
            continue
        try:
            entries = source.fetch(str(sub["value"]), limit=limit_per)
        except Exception:  # noqa: BLE001 — one bad source/subscription must not sink the rest
            entries = []
        new = feed_repo.upsert_items(conn, int(sub["id"]), [e.to_row() for e in entries])
        feed_repo.touch_subscription(conn, int(sub["id"]))
        total_new += new
        polled += 1
    return {"subscriptions": polled, "new_items": total_new}


def _first_family(authors: list[str]) -> str | None:
    if not authors:
        return None
    # "Wang, Q." → "Wang"; "Smith J" → "Smith"
    first = authors[0]
    return (first.split(",")[0].strip() or first.split(" ")[0].strip()) or None


def feed_view(
    conn: Connection,
    *,
    unread_only: bool = False,
    starred_only: bool = False,
    subscription_id: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List stored items + compute `in_library` at read time (dedup vs the live library), so a saved item is
    reflected without a re-poll."""
    rows = feed_repo.list_items(
        conn, unread_only=unread_only, starred_only=starred_only, subscription_id=subscription_id, limit=limit
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        authors = list(r["authors"] or [])
        existing = find_existing_paper_by_identity(
            conn, doi=r["doi"], title=r["title"], year=r["year"], first_author_family_name=_first_family(authors)
        )
        out.append(
            {
                "id": int(r["id"]),
                "subscription_id": int(r["subscription_id"]),
                "title": r["title"],
                "doi": r["doi"],
                "authors": authors,
                "journal": r["journal"],
                "year": r["year"],
                "url": r["url"],
                "abstract": r["abstract"],
                "posted_date": r["posted_date"],
                "is_read": bool(r["is_read"]),
                "is_starred": bool(r["is_starred"]),
                "in_library": existing is not None,
            }
        )
    return out
