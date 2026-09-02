"""inc 210 (A2) — library-wide per-paper OpenAlex citation counts: the fetch, the store/projection, the
explicit Most-cited sort, and the async refresh endpoint. Verbatim count, attributed; never a silent rank."""

from __future__ import annotations

from app.backend.acquisition.registry import PaperRef
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import (
    create_paper,
    list_live_papers_with_doi,
    list_papers,
    upsert_citation_count,
)
from integrations.openalex.adapter import OpenAlexClient


def _paper(conn, title, doi=None) -> int:
    return create_paper(conn, title=title, csl_json={"title": title, "DOI": doi}, doi=doi)


def _fetcher(count_by_doi):
    """A fake OpenAlex fetcher: /doi:<doi> → a work dict carrying cited_by_count (or a 404 if unknown)."""

    def fake(path, *, params, headers, timeout):
        doi = path[len("/doi:") :] if path.startswith("/doi:") else None
        if doi in count_by_doi:
            return 200, {"id": "https://openalex.org/W1", "cited_by_count": count_by_doi[doi]}
        return 404, {"error": "not found"}

    return fake


# ---- adapter: fetch_cited_by_count -----------------------------------------


def test_fetch_cited_by_count_verbatim_zero_kept_and_missing_is_none(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = OpenAlexClient(fetcher=_fetcher({"10.1/a": 42, "10.1/zero": 0}))
        assert client.fetch_cited_by_count(conn, PaperRef(doi="10.1/a")) == 42
        assert client.fetch_cited_by_count(conn, PaperRef(doi="10.1/zero")) == 0  # 0 is a real count, kept
        assert client.fetch_cited_by_count(conn, PaperRef(doi="10.1/unknown")) is None  # 404 → None

        # work resolves but the field is absent → None (not 0): silence is not "zero citations"
        no_field = OpenAlexClient(fetcher=lambda p, **k: (200, {"id": "https://openalex.org/W9"}))
        assert no_field.fetch_cited_by_count(conn, PaperRef(doi="10.1/b")) is None
    engine.dispose()


def test_citation_refresh_bypasses_cached_work_and_replaces_it(temp_db_url):
    counts = iter((4, 9))

    def fetcher(path, *, params, headers, timeout):
        return 200, {"id": "https://openalex.org/W1", "cited_by_count": next(counts)}

    client = OpenAlexClient(fetcher=fetcher)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert client.fetch_cited_by_count(conn, PaperRef(doi="10.1/a")) == 4
    with engine.begin() as conn:
        assert client.fetch_cited_by_count(conn, PaperRef(doi="10.1/a")) == 4
        assert client.fetch_cited_by_count(conn, PaperRef(doi="10.1/a"), refresh=True) == 9
    engine.dispose()


# ---- store + list projection + Most-cited sort -----------------------------


def test_upsert_projection_and_most_cited_sort(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        low = _paper(conn, "Low", "10.1/low")
        none = _paper(conn, "Uncounted", "10.1/none")  # never fetched
        high = _paper(conn, "High", "10.1/high")
        upsert_citation_count(conn, low, 5)
        upsert_citation_count(conn, high, 30)

        by_id = {r["id"]: r for r in list_papers(conn)}
        assert by_id[high]["cited_by_count"] == 30 and by_id[high]["cited_by_as_of"] is not None
        assert by_id[low]["cited_by_count"] == 5
        assert by_id[none]["cited_by_count"] is None and by_id[none]["cited_by_as_of"] is None  # honest "—"

        # explicit "Most cited" sort: counted papers desc, the uncounted one last
        order = [r["id"] for r in list_papers(conn, sort="citations_desc")]
        assert order == [high, low, none]

        # re-fetch replaces (idempotent OR-REPLACE)
        upsert_citation_count(conn, low, 7)
        assert {r["id"]: r["cited_by_count"] for r in list_papers(conn)}[low] == 7
    engine.dispose()


def test_list_live_papers_with_doi_only(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        with_doi = _paper(conn, "Has DOI", "10.1/x")
        _paper(conn, "No DOI", None)  # excluded — DOI is the reliable identifier
        rows = list_live_papers_with_doi(conn)
    engine.dispose()
    assert [r["id"] for r in rows] == [with_doi]


# ---- the async refresh endpoint --------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.backend.api import create_app  # noqa: E402


def _drive_refresh(client):
    jid = client.post("/papers/citation-counts/refresh").json()["job_id"]
    data = {}
    for _ in range(30):
        data = client.get(f"/papers/citation-counts/refresh/{jid}").json()
        if data["status"] in ("done", "error"):
            return data
    return data


def test_refresh_stores_counts_and_shows_on_list(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        p1 = _paper(conn, "Cited", "10.1/c1")
        p2 = _paper(conn, "Uncited match", "10.1/c2")
        miss = _paper(conn, "No OpenAlex record", "10.1/miss")  # has a DOI but OpenAlex 404s
        _paper(conn, "No DOI", None)  # not fetched at all
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher({"10.1/c1": 12, "10.1/c2": 0}))

    done = _drive_refresh(client)
    assert done["status"] == "done"
    assert done["summary"]["total"] == 3  # the 3 DOI papers (no-DOI excluded)
    assert done["summary"]["updated"] == 2  # c1 + c2 (miss 404 → not stored)

    by_id = {p["id"]: p for p in client.get("/papers").json()}
    assert by_id[p1]["cited_by_count"] == 12 and by_id[p1]["cited_by_as_of"] is not None
    assert by_id[p2]["cited_by_count"] == 0  # a real zero, shown
    assert by_id[miss]["cited_by_count"] is None  # 404 → honest "—", never 0


def test_refresh_status_404_for_unknown_job(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers/citation-counts/refresh/nope").status_code == 404
