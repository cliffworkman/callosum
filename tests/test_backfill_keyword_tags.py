from __future__ import annotations

from sqlalchemy import insert

from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, get_paper
from app.backend.persistence.schema import external_api_cache
from app.backend.persistence.tags_repo import get_tags_for_paper
from integrations.crossref import CrossrefClient
from tools.backfill_keyword_tags import backfill_keyword_tags


class _FakeFetcher:
    def __init__(self, body: dict) -> None:
        self.body = body

    def __call__(self, doi: str, *, headers: dict, timeout: float):
        return 200, self.body


def _seed_cache(conn, doi: str, subjects: list[str]) -> None:
    conn.execute(
        insert(external_api_cache).values(
            provider="crossref",
            cache_key=doi,
            request_json={"doi": doi},
            status_code=200,
            response_json={"message": {"DOI": doi, "title": ["Cached"], "subject": subjects}},
        )
    )


def test_backfill_tags_from_cache_without_fetching(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Cached Paper", doi="10.5/cache", csl_json={"title": "Cached Paper"})
        _seed_cache(conn, "10.5/cache", ["Genetics", "Cell Biology"])

    def _boom(doi, *, headers, timeout):  # must not be reached on a cache hit
        raise AssertionError("backfill fetched the network despite a cached response")

    stats = backfill_keyword_tags(engine, CrossrefClient(fetcher=_boom))
    with engine.begin() as conn:
        assert {r["name"] for r in get_tags_for_paper(conn, pid)} == {"Genetics", "Cell Biology"}
    assert stats["from_cache"] == 1 and stats["from_network"] == 0 and stats["tagged"] == 1
    engine.dispose()


def test_backfill_fetches_uncached_is_idempotent_and_metadata_safe(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(
            conn,
            title="Original Title",
            doi="10.6/fetch",
            first_author_family_name="Orig",
            csl_json={"title": "Original Title"},
        )
    client = CrossrefClient(
        fetcher=_FakeFetcher({"message": {"DOI": "10.6/fetch", "title": ["Crossref Title"], "subject": ["Optics"]}})
    )

    stats1 = backfill_keyword_tags(engine, client)
    with engine.begin() as conn:
        assert {r["name"] for r in get_tags_for_paper(conn, pid)} == {"Optics"}
        assert get_paper(conn, pid)["title"] == "Original Title"  # tag-only: backfill never clobbers metadata
    assert stats1["from_network"] == 1 and stats1["tagged"] == 1

    stats2 = backfill_keyword_tags(engine, client)  # re-run → now a cache hit, no dupes
    with engine.begin() as conn:
        assert [r["name"] for r in get_tags_for_paper(conn, pid)] == ["Optics"]
    assert stats2["from_cache"] == 1
    engine.dispose()
