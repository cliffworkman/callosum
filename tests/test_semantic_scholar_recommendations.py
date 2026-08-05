"""inc 449 (backlog #30 Track C) — Semantic Scholar's recommendations API as a third beyond-library citation-
suggestion source. Client-level tests only (parse / cache / fail-closed / DOI-validate / fixed-fetch-cap); the
endpoint-level integration lives in tests/test_citations_suggest.py, mirroring how citation-context's own client
tests (test_citation_context.py) and endpoint tests are split. Hermetic: an injected fake recommendations fetcher
— no network."""

from __future__ import annotations

from app.backend.persistence.database import make_engine
from integrations.semantic_scholar.adapter import (
    MAX_S2_RECOMMENDATIONS_FETCH,
    S2_RECOMMENDATIONS_BASE_URL,
    SemanticScholarClient,
)


def _recommended(title, *, doi=None, pmid=None, year=2023, venue="Journal of Testing", abstract="An abstract."):
    ext = {}
    if doi:
        ext["DOI"] = doi
    if pmid:
        ext["PubMed"] = pmid
    return {
        "title": title,
        "abstract": abstract,
        "year": year,
        "venue": venue,
        "url": f"https://www.semanticscholar.org/paper/{title}",
        "authors": [{"authorId": "1", "name": "A Author"}, {"authorId": "2", "name": "B Author"}],
        "externalIds": ext,
    }


def test_client_parses_and_caps_recommendations(temp_db_url):
    body = {
        "recommendedPapers": [
            _recommended("Recommended One", doi="10.1/rec-one", pmid="12345"),
            _recommended("Recommended Two"),
        ]
    }

    calls = {"n": 0}

    def fetcher(path, *, params, headers, timeout):
        calls["n"] += 1
        return 200, body

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = SemanticScholarClient(recommendations_fetcher=fetcher)
        out = client.fetch_recommendations(conn, "10.1/focal", limit=5)
        assert [p.title for p in out] == ["Recommended One", "Recommended Two"]
        assert out[0].doi == "10.1/rec-one"
        assert out[0].pmid == "12345"
        assert out[0].authors == ["A Author", "B Author"]
        assert out[1].doi is None and out[1].pmid is None

        # a second call is served from cache (the fetcher would bump `calls["n"]` again if it ran)
        client.fetch_recommendations(conn, "10.1/focal", limit=5)
        assert calls["n"] == 1
    engine.dispose()


def test_authors_capped_at_six(temp_db_url):
    many_authors = [{"authorId": str(i), "name": f"Author {i}"} for i in range(10)]
    body = {"recommendedPapers": [{"title": "Many Authors", "authors": many_authors, "externalIds": {}}]}

    def fetcher(path, *, params, headers, timeout):
        return 200, body

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = SemanticScholarClient(recommendations_fetcher=fetcher)
        out = client.fetch_recommendations(conn, "10.1/focal")
        assert len(out[0].authors) == 6
    engine.dispose()


def test_client_validates_doi_and_fails_closed(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        # a non-DOI id → no request is made at all
        client = SemanticScholarClient(
            recommendations_fetcher=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not fetch"))
        )
        assert client.fetch_recommendations(conn, "not-a-doi") == []

        # a transient failure → [] and NOT cached (a retry can still succeed)
        state = {"fail": True}

        def flaky(path, *, params, headers, timeout):
            if state["fail"]:
                raise ConnectionError("boom")
            return 200, {"recommendedPapers": [_recommended("Recovered")]}

        client2 = SemanticScholarClient(recommendations_fetcher=flaky)
        assert client2.fetch_recommendations(conn, "10.1/retry") == []
        state["fail"] = False
        out = client2.fetch_recommendations(conn, "10.1/retry")
        assert [p.title for p in out] == ["Recovered"]
    engine.dispose()


def test_client_404_not_cached(temp_db_url):
    calls = {"n": 0}

    def fetcher(path, *, params, headers, timeout):
        calls["n"] += 1
        return 404, None

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = SemanticScholarClient(recommendations_fetcher=fetcher)
        assert client.fetch_recommendations(conn, "10.1/unknown") == []
        assert client.fetch_recommendations(conn, "10.1/unknown") == []
        assert calls["n"] == 2  # not cached — a 404 stays retryable, matching _fetch_edge's existing posture
    engine.dispose()


def test_fetch_uses_fixed_cap_independent_of_requested_limit(temp_db_url):
    seen_params = {}
    body = {"recommendedPapers": [_recommended(f"Paper {i}") for i in range(12)]}

    def fetcher(path, *, params, headers, timeout):
        seen_params.update(params)
        return 200, body

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = SemanticScholarClient(recommendations_fetcher=fetcher)
        out = client.fetch_recommendations(conn, "10.1/focal", limit=3)
        assert seen_params["limit"] == str(MAX_S2_RECOMMENDATIONS_FETCH)  # always the fixed fetch cap
        assert len(out) == 3  # sliced to the caller's requested limit
    engine.dispose()


def test_request_path_and_base_url(temp_db_url):
    captured = {}

    def fetcher(path, *, params, headers, timeout):
        captured["path"] = path
        return 200, {"recommendedPapers": []}

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = SemanticScholarClient(recommendations_fetcher=fetcher)
        client.fetch_recommendations(conn, "10.1/focal")
        assert captured["path"] == "/papers/forpaper/DOI:10.1%2Ffocal"
    engine.dispose()
    # this proves it targets recommendations/v1, not the graph/v1 base the citation-context client uses
    assert S2_RECOMMENDATIONS_BASE_URL == "https://api.semanticscholar.org/recommendations/v1"


def test_api_key_header_sent_when_resolved(temp_db_url, monkeypatch):
    monkeypatch.delenv("CALLOSUM_S2_API_KEY", raising=False)
    captured = {}

    def fetcher(path, *, params, headers, timeout):
        captured["headers"] = headers
        return 200, {"recommendedPapers": []}

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = SemanticScholarClient(recommendations_fetcher=fetcher, api_key="test-key")
        client.fetch_recommendations(conn, "10.1/focal")
        assert captured["headers"] == {"x-api-key": "test-key"}
    engine.dispose()
