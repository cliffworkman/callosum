"""Tests for My Publications (inc 78) — hermetic (injected fake author client / fetcher; no real network,
no model tokens)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.clustering.my_publications import (
    CONFIRMED_CONFIDENCE,
    build_dashboard,
    import_missing_work,
    maybe_add_to_my_publications,
    resolve_my_publications,
)
from app.backend.clustering.my_publications_domains import decompose_domains
from app.backend.persistence.database import make_engine
from app.backend.persistence.profile_repo import (
    dismiss_work,
    get_decisions,
    get_profile,
    set_decision,
    set_my_publications_dismissed,
    set_openalex_author_id,
    set_research_domains,
    set_starred,
    undismiss_work,
    upsert_profile,
)
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import axes, cluster_node_papers, cluster_nodes, papers
from integrations.api_cache import get_cached, put_cached
from integrations.openalex.author import (
    OPENALEX_WORKS_PROVIDER,
    AuthorWork,
    AuthorWorksResult,
    OpenAlexAuthorClient,
    OpenAlexAuthorUnavailable,
    ResolvedAuthor,
)


def _csl(title: str, doi: str | None = None) -> dict:
    out = {"id": doi or title, "type": "document", "title": title}
    if doi:
        out["DOI"] = doi
    return out


def _members(conn) -> dict[int, float | None]:
    axis_id = conn.execute(select(axes.c.id).where(axes.c.kind == "my_publications")).scalar()
    if axis_id is None:
        return {}
    node_id = conn.execute(select(cluster_nodes.c.id).where(cluster_nodes.c.axis_id == axis_id)).scalar()
    rows = conn.execute(
        select(cluster_node_papers.c.paper_id, cluster_node_papers.c.confidence).where(
            cluster_node_papers.c.cluster_node_id == node_id
        )
    )
    return {int(r[0]): r[1] for r in rows}


class _FakeAuthorClient:
    def __init__(self, author=None, works=None):
        self.author = author
        self.works = works or []

    def resolve_author(self, conn, *, orcid=None, name=None):
        return self.author

    def cached_author(self, conn, *, orcid=None, name=None):
        return self.author

    def fetch_author_works(self, conn, author_id, *, refresh=False):
        return self.works


class _IncompleteAuthorClient(_FakeAuthorClient):
    def fetch_author_works_result(self, conn, author_id, *, refresh=False):
        return AuthorWorksResult(tuple(self.works), complete=False)


class _FakeSummaryGen:
    def generate(self, *, documents):
        return f"Ada's work spans {len(documents)} publications on analytical engines."


class _UnresolvedResolution:
    resolved = False
    csl_json = None
    error = None


class _NoCrossref:
    """A Crossref client stub that never resolves — so import tests don't hit the network."""

    def resolve_doi(self, conn, doi):
        return _UnresolvedResolution()


class _ClusterModel:
    """A 3-D fake embedding model: 'alpha'/'beta' titles map to separated unit vectors so clustering yields
    two clean domains (inc 83 decomposition tests)."""

    name = "cluster-fake"
    version = "v1"
    dimension = 3
    normalization = "none"

    def encode_texts(self, texts):
        out = []
        for text in texts:
            low = (text or "").lower()
            out.append([1.0, 0.0, 0.0] if "alpha" in low else ([0.0, 1.0, 0.0] if "beta" in low else [0.0, 0.0, 1.0]))
        return out


_ADA = ResolvedAuthor(
    author_id="A1", display_name="Ada Lovelace", orcid="0000-0002-1825-0097", works_count=2, matched_by="orcid"
)

_ADA_STATS = ResolvedAuthor(
    author_id="A1",
    display_name="Ada Lovelace",
    orcid="0000-0002-1825-0097",
    works_count=4,
    matched_by="orcid",
    cited_by_count=120,
    h_index=5,
    i10_index=3,
    two_year_mean_citedness=2.5,
    affiliation="Analytical Engine Lab",
    counts_by_year=(
        {"year": 2019, "works_count": 1, "cited_by_count": 40},
        {"year": 2020, "works_count": 2, "cited_by_count": 80},
    ),
)


# --- resolver --------------------------------------------------------------------------------------------


def test_resolver_confirms_doi_and_flags_name_candidate(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        confirmed = create_paper(
            conn, title="Note on the Engine", csl_json=_csl("Note on the Engine", "10.1/engine"), doi="10.1/engine"
        )
        candidate = create_paper(
            conn, title="Untitled Memoir", csl_json=_csl("Untitled Memoir"), first_author_family_name="Lovelace"
        )
        other = create_paper(
            conn,
            title="Banana",
            csl_json=_csl("Banana", "10.9/banana"),
            doi="10.9/banana",
            first_author_family_name="Turing",
        )
    client = _FakeAuthorClient(
        author=_ADA, works=[AuthorWork(doi="10.1/engine", title="Note on the Engine", year=1843)]
    )

    with engine.begin() as conn:
        summary = resolve_my_publications(conn, author_client=client, force=True)
        members = _members(conn)

    assert summary["status"] == "ok" and summary["in_library"] == 1
    assert members.get(confirmed) == 0.95  # DOI-confirmed → assigned
    assert members.get(candidate) == 0.25  # name-only → uncertain candidate
    assert other not in members


def test_resolver_honors_decisions(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        confirmed = create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/engine"), doi="10.1/engine")
        candidate = create_paper(conn, title="Memoir", csl_json=_csl("Memoir"), first_author_family_name="Lovelace")
        set_decision(conn, candidate, "rejected")
        set_decision(conn, confirmed, "confirmed")
    client = _FakeAuthorClient(author=_ADA, works=[AuthorWork(doi="10.1/engine", title="Engine", year=1843)])

    with engine.begin() as conn:
        resolve_my_publications(conn, author_client=client, force=True)
        members = _members(conn)

    assert candidate not in members  # rejected → never proposed
    assert confirmed in members and members[confirmed] is None  # confirmed → manual (NULL)


def test_resolver_no_identity(temp_db_url):
    with make_engine(temp_db_url).begin() as conn:
        summary = resolve_my_publications(conn, author_client=_FakeAuthorClient(author=None), force=True)
    assert summary["status"] == "no-identity"


def test_resolver_no_match(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Nobody Real", name_variants=[], orcid=None)
        summary = resolve_my_publications(conn, author_client=_FakeAuthorClient(author=None), force=True)
    assert summary["status"] == "no-match" and summary["name"] == "Nobody Real"


def test_resolver_respects_dismissed_until_forced(temp_db_url):
    engine = make_engine(temp_db_url)
    client = _FakeAuthorClient(author=_ADA, works=[])
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        set_my_publications_dismissed(conn, True)
        assert resolve_my_publications(conn, author_client=client, force=False)["status"] == "dismissed"
        assert resolve_my_publications(conn, author_client=client, force=True)["status"] == "ok"  # force bypasses


def test_incomplete_author_refresh_preserves_existing_memberships(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        kept = create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/engine"), doi="10.1/engine")
        resolve_my_publications(
            conn,
            author_client=_FakeAuthorClient(
                author=_ADA, works=[AuthorWork(doi="10.1/engine", title="Engine", year=1843)]
            ),
            force=True,
        )
        before = _members(conn)
        result = resolve_my_publications(
            conn,
            author_client=_IncompleteAuthorClient(
                author=_ADA, works=[AuthorWork(doi="10.1/partial", title="Partial", year=1844)]
            ),
            force=True,
        )
        after = _members(conn)
    assert result["status"] == "refresh-incomplete"
    assert before == after and after[kept] == CONFIRMED_CONFIDENCE


# --- import hook -----------------------------------------------------------------------------------------


def test_import_hook_adds_cached_work(temp_db_url):
    engine = make_engine(temp_db_url)
    client = _FakeAuthorClient(author=_ADA, works=[AuthorWork(doi="10.1/old", title="Old", year=2019)])
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        resolve_my_publications(conn, author_client=client, force=True)  # creates the axis + sets the author id
        # the fake client doesn't write the works cache the way the real one does — simulate it:
        put_cached(
            conn,
            OPENALEX_WORKS_PROVIDER,
            "A1",
            request_json={},
            response_json={"works": [{"doi": "10.1/new", "title": "New", "year": 2020}]},
            status_code=200,
        )
        new_pid = create_paper(conn, title="New", csl_json=_csl("New", "10.1/new"), doi="10.1/new")
        maybe_add_to_my_publications(conn, new_pid)
        members = _members(conn)
    assert members.get(new_pid) == 0.95


def test_import_hook_noop_without_profile(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="X", csl_json=_csl("X", "10.1/x"), doi="10.1/x")
        maybe_add_to_my_publications(conn, pid)  # no profile → no-op (no error, no axis created)
        assert conn.execute(select(axes.c.id).where(axes.c.kind == "my_publications")).first() is None


# --- OpenAlex author client ------------------------------------------------------------------------------


class _AuthorFetcher:
    def __init__(self, by_fragment):
        self.by_fragment = by_fragment
        self.calls = []

    def __call__(self, url, *, params, headers, timeout):
        self.calls.append((url, params))
        for fragment, resp in self.by_fragment.items():
            if fragment in url:
                return resp
        return 404, None


def test_author_client_resolves_by_orcid(temp_db_url):
    body = {
        "id": "https://openalex.org/A1",
        "display_name": "Ada",
        "orcid": "https://orcid.org/0000-x",
        "works_count": 3,
    }
    client = OpenAlexAuthorClient(fetcher=_AuthorFetcher({"/authors/orcid:": (200, body)}))
    with make_engine(temp_db_url).begin() as conn:
        author = client.resolve_author(conn, orcid="0000-x")
    assert (
        author.author_id == "A1"
        and author.matched_by == "orcid"
        and author.orcid == "0000-x"
        and author.works_count == 3
    )


def test_author_client_resolves_by_name(temp_db_url):
    body = {"results": [{"id": "https://openalex.org/A2", "display_name": "Ada L", "works_count": 1}]}
    client = OpenAlexAuthorClient(fetcher=_AuthorFetcher({"/authors": (200, body)}))
    with make_engine(temp_db_url).begin() as conn:
        author = client.resolve_author(conn, name="Ada L")
    assert author.author_id == "A2" and author.matched_by == "name"


def test_author_client_falls_back_to_name_when_orcid_unlinked(temp_db_url):
    """A real, common gap (not a Callosum bug): OpenAlex's own author record can lack the ORCID link even
    though the ORCID itself is correct (the OpenAlex profile predates or was never merged with it) — the
    orcid-keyed lookup 404s, but a name search still finds the same person. Falling back keeps this an
    honest, lower-confidence match (``matched_by="name"``), not a silent no-match."""
    name_body = {"results": [{"id": "https://openalex.org/A9", "display_name": "Isabella Bobrow", "works_count": 14}]}
    fetcher = _AuthorFetcher({"/authors/orcid:": (404, None), "/authors": (200, name_body)})
    client = OpenAlexAuthorClient(fetcher=fetcher)
    with make_engine(temp_db_url).begin() as conn:
        author = client.resolve_author(conn, orcid="0009-0008-6787-5123", name="Isabella Bobrow")
    assert author is not None and author.author_id == "A9" and author.matched_by == "name"
    assert len(fetcher.calls) == 2  # both the orcid attempt and the name fallback actually ran


def test_author_client_orcid_success_never_tries_name_fallback(temp_db_url):
    body = {"id": "https://openalex.org/A1", "display_name": "Ada", "orcid": "https://orcid.org/0000-x"}
    fetcher = _AuthorFetcher({"/authors/orcid:": (200, body), "/authors": (200, {"results": []})})
    client = OpenAlexAuthorClient(fetcher=fetcher)
    with make_engine(temp_db_url).begin() as conn:
        author = client.resolve_author(conn, orcid="0000-x", name="Someone Else")
    assert author.matched_by == "orcid" and len(fetcher.calls) == 1  # never reaches the name search


def test_author_client_works_mapping_and_cache(temp_db_url):
    body = {
        "results": [
            {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/A", "title": "A", "publication_year": 2020}
        ],
        "meta": {"next_cursor": None},
    }
    fetcher = _AuthorFetcher({"/works": (200, body)})
    client = OpenAlexAuthorClient(fetcher=fetcher)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        works = client.fetch_author_works(conn, "A1")
    assert len(works) == 1 and works[0].doi == "10.1/a" and works[0].year == 2020  # normalized, prefix stripped
    calls_before = len(fetcher.calls)
    with engine.begin() as conn:
        works2 = client.fetch_author_works(conn, "A1")
    assert len(works2) == 1 and len(fetcher.calls) == calls_before  # served from cache


def test_author_client_works_publication_date_parsed_validated_and_cached(temp_db_url):
    """inc 458 (backlog #28): OpenAlex's real `publication_date` (day precision) is extracted, validated at the
    untrusted-input boundary (rule #4 -- a malformed value never reaches Feed's posted_date ordering), and
    survives a cache round-trip (fetch_author_works's cache-read branch reconstructs it, not just year/doi/title)."""
    body = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.1/A",
                "title": "A",
                "publication_year": 2020,
                "publication_date": "2020-06-15",
            },
            {
                "id": "https://openalex.org/W2",
                "doi": "https://doi.org/10.1/B",
                "title": "B",
                "publication_year": 2021,
                "publication_date": "not-a-date",  # malformed -- dropped, not trusted verbatim
            },
        ],
        "meta": {"next_cursor": None},
    }
    fetcher = _AuthorFetcher({"/works": (200, body)})
    client = OpenAlexAuthorClient(fetcher=fetcher)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        works = client.fetch_author_works(conn, "A1")
    by_doi = {w.doi: w for w in works}
    assert by_doi["10.1/a"].publication_date == "2020-06-15"
    assert by_doi["10.1/b"].publication_date is None  # malformed value validated away, not passed through

    with engine.begin() as conn:  # a fresh connection -- proves the cache-read branch, not just the live fetch
        cached_works = client.fetch_author_works(conn, "A1")
    assert {w.doi: w.publication_date for w in cached_works} == {"10.1/a": "2020-06-15", "10.1/b": None}


def test_author_client_exact_orcid_failure_does_not_fall_back_to_name(temp_db_url):
    class _Boom:
        def __init__(self):
            self.calls = []

        def __call__(self, url, *, params, headers, timeout):
            self.calls.append(url)
            raise RuntimeError("network down")

    fetcher = _Boom()
    client = OpenAlexAuthorClient(fetcher=fetcher)
    with make_engine(temp_db_url).begin() as conn:
        with pytest.raises(OpenAlexAuthorUnavailable):
            client.resolve_author(conn, orcid="0000-x", name="Another Person")
    assert len(fetcher.calls) == 1


def test_author_client_retries_after_a_transient_fetch_failure(temp_db_url):
    """Backlog #61: a transient fetch failure (network/decode error, not a real "no such author" answer) must
    NOT permanently poison that name/ORCID's resolution -- the next attempt should retry, not replay the same
    cached error forever."""

    class _FlakyThenGood:
        def __init__(self):
            self.calls = 0

        def __call__(self, url, *, params, headers, timeout):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient decode error")
            return 200, {"id": "https://openalex.org/A1", "display_name": "Ada", "orcid": "https://orcid.org/0000-x"}

    fetcher = _FlakyThenGood()
    client = OpenAlexAuthorClient(fetcher=fetcher)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        with pytest.raises(OpenAlexAuthorUnavailable):
            client.resolve_author(conn, orcid="0000-x")
    with engine.begin() as conn:
        author = client.resolve_author(conn, orcid="0000-x")  # second attempt: retries rather than replaying
    assert author is not None and author.author_id == "A1" and fetcher.calls == 2


def test_author_client_partial_page_failure_is_incomplete_and_not_cached(temp_db_url):
    class _PageThenFailure:
        def __init__(self):
            self.calls = 0

        def __call__(self, url, *, params, headers, timeout):
            self.calls += 1
            if self.calls == 1:
                return 200, {
                    "results": [{"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/a"}],
                    "meta": {"next_cursor": "page-2"},
                }
            return 503, {"error": "unavailable"}

    fetcher = _PageThenFailure()
    client = OpenAlexAuthorClient(fetcher=fetcher)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = client.fetch_author_works_result(conn, "A1", refresh=True)
        assert not result.complete and [work.doi for work in result.works] == ["10.1/a"]
    with engine.begin() as conn:
        assert get_cached(conn, OPENALEX_WORKS_PROVIDER, "A1") is None


# --- endpoints -------------------------------------------------------------------------------------------


def test_profile_endpoints(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/my-publications/profile").json()["display_name"] is None
    r = client.put(
        "/my-publications/profile", json={"display_name": "Ada", "name_variants": ["A L"], "orcid": "0000-x"}
    )
    assert r.status_code == 200 and r.json()["display_name"] == "Ada" and r.json()["name_variants"] == ["A L"]
    assert client.get("/my-publications/profile").json()["orcid"] == "0000-x"


def test_decide_endpoint_records_and_422(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="X", csl_json=_csl("X", "10.1/x"), doi="10.1/x")
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/my-publications/decide", json={"paper_id": pid, "decision": "rejected"}).status_code == 204
    with engine.begin() as conn:
        assert pid in get_decisions(conn)["rejected"]
    assert client.post("/my-publications/decide", json={"paper_id": 999999, "decision": "rejected"}).status_code == 404


def test_delete_dismisses_keeps_profile(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    client.put("/my-publications/profile", json={"display_name": "Ada"})
    assert client.delete("/my-publications").status_code == 204
    with make_engine(temp_db_url).begin() as conn:
        profile = get_profile(conn)
    assert profile["my_publications_dismissed"] == 1 and profile["display_name"] == "Ada"  # profile survives


# --- dashboard (inc 81) ----------------------------------------------------------------------------------


def test_author_client_parses_stats_and_counts_by_year(temp_db_url):
    body = {
        "id": "https://openalex.org/A1",
        "display_name": "Ada",
        "orcid": "https://orcid.org/0000-x",
        "works_count": 3,
        "cited_by_count": 99,
        "summary_stats": {"h_index": 7, "i10_index": 4, "2yr_mean_citedness": 3.5},
        "last_known_institutions": [{"display_name": "Analytical Engine Lab"}],
        "counts_by_year": [{"year": 2021, "works_count": 1, "cited_by_count": 10}],
    }
    client = OpenAlexAuthorClient(fetcher=_AuthorFetcher({"/authors/orcid:": (200, body)}))
    with make_engine(temp_db_url).begin() as conn:
        author = client.resolve_author(conn, orcid="0000-x")
    assert author.cited_by_count == 99 and author.h_index == 7 and author.i10_index == 4
    assert author.counts_by_year == ({"year": 2021, "works_count": 1, "cited_by_count": 10},)
    assert author.two_year_mean_citedness == 3.5 and author.affiliation == "Analytical Engine Lab"


def test_cached_author_reads_cache_without_fetching(temp_db_url):
    body = {
        "id": "https://openalex.org/A1",
        "display_name": "Ada",
        "orcid": "https://orcid.org/0000-x",
        "cited_by_count": 5,
    }
    fetcher = _AuthorFetcher({"/authors/orcid:": (200, body)})
    client = OpenAlexAuthorClient(fetcher=fetcher)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert client.cached_author(conn, orcid="0000-x") is None  # cold cache → None, and...
    assert fetcher.calls == []  # ...never fetches
    with engine.begin() as conn:
        client.resolve_author(conn, orcid="0000-x")  # warm the cache
    calls = len(fetcher.calls)
    with engine.begin() as conn:
        author = client.cached_author(conn, orcid="0000-x")
    assert author is not None and author.cited_by_count == 5 and len(fetcher.calls) == calls  # served from cache


def test_cached_author_finds_a_prior_name_fallback_match(temp_db_url):
    """cached_author must mirror resolve_author's orcid-then-name fallback order — otherwise a name-fallback
    match resolved once would silently vanish (report not-resolved) on every later cache-only dashboard read,
    even though the underlying OpenAlex data hasn't changed."""
    name_body = {"results": [{"id": "https://openalex.org/A9", "display_name": "Isabella Bobrow"}]}
    fetcher = _AuthorFetcher({"/authors/orcid:": (404, None), "/authors": (200, name_body)})
    client = OpenAlexAuthorClient(fetcher=fetcher)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client.resolve_author(conn, orcid="0009-0008-6787-5123", name="Isabella Bobrow")  # warms both cache keys
    calls = len(fetcher.calls)
    with engine.begin() as conn:
        author = client.cached_author(conn, orcid="0009-0008-6787-5123", name="Isabella Bobrow")
    assert author is not None and author.author_id == "A9" and author.matched_by == "name"
    assert len(fetcher.calls) == calls  # served entirely from cache, no new fetch


def test_dashboard_ok_returns_metrics_and_pubs_by_year(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        set_openalex_author_id(conn, "A1")
        create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/engine"), doi="10.1/engine")
    works = [
        AuthorWork(doi="10.1/engine", title="Engine", year=2019),
        AuthorWork(doi="10.2/x", title="X", year=2020),
        AuthorWork(doi="10.3/y", title="Y", year=2020),
    ]
    with engine.begin() as conn:
        dash = build_dashboard(conn, author_client=_FakeAuthorClient(author=_ADA_STATS, works=works))
    assert dash["status"] == "ok"
    assert dash["metrics"] == {"works_count": 4, "cited_by_count": 120, "h_index": 5, "i10_index": 3}
    assert dash["pubs_by_year"] == [{"year": 2019, "count": 1}, {"year": 2020, "count": 2}]
    assert dash["indexed_works"] == 4 and dash["in_library"] == 1 and dash["gap"] == 3
    assert dash["openalex_extra"] == {
        "two_year_mean_citedness": 2.5,
        "affiliation": "Analytical Engine Lab",
        "openalex_author_id": "A1",
    }
    assert dash["starred_count"] == 0


def test_dashboard_exposes_domain_paper_ids_and_starred(temp_db_url):  # SP2 T1
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        set_openalex_author_id(conn, "A1")
        pid = create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/engine"), doi="10.1/engine")
        set_research_domains(conn, [{"label": "Engines", "terms": ["engine"], "paper_ids": [int(pid)]}])
        set_starred(conn, int(pid), True)
    works = [AuthorWork(doi="10.1/engine", title="Engine", year=1843, cited_by_count=5)]
    with engine.begin() as conn:
        dash = build_dashboard(conn, author_client=_FakeAuthorClient(author=_ADA_STATS, works=works))
    assert dash["domains"][0]["paper_ids"] == [int(pid)]
    assert dash["starred_ids"] == [int(pid)]


def test_work_from_obj_captures_openalex_work_id():  # SP3 T1
    from integrations.openalex.author import _work_from_obj

    w = _work_from_obj(
        {
            "id": "https://openalex.org/W9",
            "doi": "https://doi.org/10.1/x",
            "title": "X",
            "publication_year": 2020,
            "cited_by_count": 3,
        }
    )
    assert w.openalex_work_id == "W9" and w.cited_by_count == 3


def test_dashboard_paper_citations(temp_db_url):  # SP3 T1 (#14)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada", name_variants=[], orcid="0000-x")
        set_openalex_author_id(conn, "A1")
        pid = create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/engine"), doi="10.1/engine")
    works = [AuthorWork(doi="10.1/engine", title="Engine", year=1843, cited_by_count=42, openalex_work_id="W9")]
    with engine.begin() as conn:
        dash = build_dashboard(conn, author_client=_FakeAuthorClient(author=_ADA_STATS, works=works))
    assert dash["paper_citations"][str(pid)] == {"cited_by_count": 42, "openalex_work_id": "W9"}


def test_fetch_citing_works_caches_and_endpoint(temp_db_url):  # SP3 T2 (#14)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(conn, title="Citer In Lib", csl_json=_csl("Citer In Lib", "10.2/inlib"), doi="10.2/inlib")
    captured = {"filter": None, "calls": 0}

    def fetcher(url, params=None, headers=None, timeout=None):
        captured["filter"] = (params or {}).get("filter")
        captured["calls"] += 1
        return (
            200,
            {
                "results": [
                    {
                        "id": "https://openalex.org/W100",
                        "doi": "https://doi.org/10.2/inlib",
                        "title": "Citer In Lib",
                        "publication_year": 2022,
                        "cited_by_count": 1,
                        "authorships": [{"author": {"display_name": "Jo Citer"}}],
                    },
                    {
                        "id": "https://openalex.org/W101",
                        "doi": "https://doi.org/10.3/new",
                        "title": "New Citer",
                        "publication_year": 2023,
                        "cited_by_count": 0,
                        "authorships": [],
                    },
                ],
                "meta": {"next_cursor": None},
            },
        )

    client = OpenAlexAuthorClient(fetcher=fetcher)
    with engine.begin() as conn:
        works, capped = client.fetch_citing_works(conn, "W9")
    assert (
        captured["filter"] == "cites:W9" and len(works) == 2 and works[0].authors == ("Jo Citer",) and capped is False
    )
    before = captured["calls"]
    with engine.begin() as conn:
        client.fetch_citing_works(conn, "W9")  # served from cache
    assert captured["calls"] == before
    # bad work id → no fetch, empty
    with engine.begin() as conn:
        assert client.fetch_citing_works(conn, "not-a-work") == ([], False)

    app = create_app(db_url=temp_db_url, openalex_author_client=client)
    body = TestClient(app).get("/my-publications/citing/W9").json()
    assert body["total"] == 2 and body["capped"] is False
    inlib = {w["doi"]: w["in_library"] for w in body["works"]}
    assert inlib["10.2/inlib"] is True and inlib["10.3/new"] is False


def test_import_citing_work(temp_db_url):  # SP3 T3 (#14)
    from app.backend.clustering.my_publications import import_citing_work
    from app.backend.persistence.repository import get_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        r1 = import_citing_work(conn, doi="10.3/new", title="A Citer", crossref_client=_NoCrossref())
        assert r1["status"] == "imported"
        pid = r1["paper_id"]
        assert pid not in _members(conn)  # a citing paper is NOT added to My Publications
        assert get_paper(conn, pid)["doi"] == "10.3/new"  # created (enrich may relabel imported_source on no-resolve)
        assert import_citing_work(conn, doi="10.3/new", crossref_client=_NoCrossref())["status"] == "exists"  # dedup
        assert import_citing_work(conn, doi="  ", crossref_client=_NoCrossref())["status"] == "invalid"
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_NoCrossref()))
    r = client.post("/my-publications/citing/import", json={"doi": "10.4/another", "title": "Another"})
    assert r.status_code == 200 and r.json()["status"] == "imported"


def test_clusters_response_carries_domain_for_my_pubs(temp_db_url):  # SP2 T1 (#16)
    app = _resolved_member_app(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = int(conn.execute(select(papers.c.id).where(papers.c.doi == "10.1/engine")).scalar())
        set_research_domains(conn, [{"label": "Engines", "terms": ["engine"], "paper_ids": [pid]}])
        axis_id = int(conn.execute(select(axes.c.id).where(axes.c.kind == "my_publications")).scalar())
    r = TestClient(app).get(f"/axes/{axis_id}/clusters")
    assert r.status_code == 200
    paps = [p for node in r.json() for p in node["papers"]]
    assert any(p.get("domain") == "Engines" for p in paps)


def test_rename_domain_endpoint(temp_db_url):  # SP2 T2 (#15)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada", name_variants=[], orcid="0000-x")
        pid = create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/e"), doi="10.1/e")
        set_research_domains(conn, [{"label": "Auto", "terms": ["x"], "paper_ids": [int(pid)]}])
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/my-publications/domains/rename", json={"paper_ids": [pid], "label": "  "}).status_code == 422
    assert client.post("/my-publications/domains/rename", json={"paper_ids": [99999], "label": "X"}).status_code == 422
    assert (
        client.post("/my-publications/domains/rename", json={"paper_ids": [pid], "label": "My Domain"}).status_code
        == 204
    )
    with engine.begin() as conn:
        d = get_profile(conn)["research_domains"][0]
    assert d["label"] == "My Domain" and d["custom"] is True


def test_reapply_custom_labels_by_overlap():  # SP2 T2 (#15 — re-decompose preserves custom names)
    from app.backend.clustering.my_publications_domains import _reapply_custom_labels

    domains = [
        {"label": "Auto A", "terms": [], "paper_ids": [1, 2, 3]},
        {"label": "Auto B", "terms": [], "paper_ids": [4, 5]},
    ]
    old = [
        {"label": "My Custom", "paper_ids": [1, 2, 3, 9], "custom": True},  # 3/4 Jaccard vs [1,2,3] ≥ 0.5
        {"label": "Not Custom", "paper_ids": [4, 5], "custom": False},  # not custom → not carried
    ]
    _reapply_custom_labels(domains, old)
    assert domains[0]["label"] == "My Custom" and domains[0]["custom"] is True
    assert domains[1]["label"] == "Auto B" and "custom" not in domains[1]


def test_dashboard_not_resolved_and_no_identity(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:  # blank profile → no-identity
        assert build_dashboard(conn, author_client=_FakeAuthorClient(author=_ADA_STATS))["status"] == "no-identity"
    with engine.begin() as conn:  # identity but never resolved (no author id) → not-resolved
        upsert_profile(conn, display_name="Ada", name_variants=[], orcid=None)
        assert build_dashboard(conn, author_client=_FakeAuthorClient(author=_ADA_STATS))["status"] == "not-resolved"


def test_dashboard_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        set_openalex_author_id(conn, "A1")
    fake = _FakeAuthorClient(author=_ADA_STATS, works=[AuthorWork(doi="10.1/a", title="A", year=2020)])
    client = TestClient(create_app(db_url=temp_db_url, openalex_author_client=fake))
    r = client.get("/my-publications/dashboard")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["metrics"]["h_index"] == 5


def _resolved_member_app(temp_db_url, **overrides):
    """A create_app whose My Publications axis already has one confirmed member (so summary generation has input)."""
    engine = make_engine(temp_db_url)
    fake = _FakeAuthorClient(author=_ADA_STATS, works=[AuthorWork(doi="10.1/engine", title="Engine", year=1843)])
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/engine"), doi="10.1/engine")
        resolve_my_publications(conn, author_client=fake, force=True)  # creates the axis + the member + author id
    return create_app(
        db_url=temp_db_url, openalex_author_client=fake, research_summary_generator=_FakeSummaryGen(), **overrides
    )


def test_summary_generate_and_persist(temp_db_url):  # conftest sets CALLOSUM_ALLOW_DATA_EGRESS=1 by default
    client = TestClient(_resolved_member_app(temp_db_url))
    r = client.post("/my-publications/summary/generate", json={})
    assert r.status_code == 200 and "publications" in r.json()["summary"]  # generated from the member doc(s)
    assert client.put("/my-publications/summary", json={"summary": "My edited summary."}).status_code == 200
    assert client.get("/my-publications/dashboard").json()["research_summary"] == "My edited summary."


def test_summary_generate_egress_off_returns_503(temp_db_url, monkeypatch):
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    client = TestClient(_resolved_member_app(temp_db_url))
    assert client.post("/my-publications/summary/generate", json={}).status_code == 503


def test_summary_generate_no_members_returns_422(temp_db_url):
    # Profile set + author id, but no My Publications axis members yet → nothing to summarize.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        set_openalex_author_id(conn, "A1")
    client = TestClient(create_app(db_url=temp_db_url, research_summary_generator=_FakeSummaryGen()))
    assert client.post("/my-publications/summary/generate", json={}).status_code == 422


# --- domain decomposition (inc 83) -----------------------------------------------------------------------


def _seed_confirmed_corpus(conn):
    """4 alpha/beta confirmed papers + 1 name-only candidate; returns ({a1,a2,b1,b2}, candidate_id, works)."""
    upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
    ids = {}
    for key, title in [
        ("a1", "Alpha study one"),
        ("a2", "Alpha study two"),
        ("b1", "Beta study one"),
        ("b2", "Beta study two"),
    ]:
        ids[key] = create_paper(conn, title=title, csl_json=_csl(title, f"10.1/{key}"), doi=f"10.1/{key}")
    cand = create_paper(conn, title="Gamma memoir", csl_json=_csl("Gamma memoir"), first_author_family_name="Lovelace")
    works = [
        AuthorWork(doi="10.1/a1", title="a1", year=2019, cited_by_count=10),
        AuthorWork(doi="10.1/a2", title="a2", year=2020, cited_by_count=5),
        AuthorWork(doi="10.1/b1", title="b1", year=2019, cited_by_count=100),
        AuthorWork(doi="10.1/b2", title="b2", year=2021, cited_by_count=50),
    ]
    return ids, cand, works


def test_author_work_cited_by_count_and_refresh(temp_db_url):
    body = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.1/a",
                "title": "A",
                "publication_year": 2020,
                "cited_by_count": 42,
            }
        ],
        "meta": {"next_cursor": None},
    }
    fetcher = _AuthorFetcher({"/works": (200, body)})
    client = OpenAlexAuthorClient(fetcher=fetcher)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert client.fetch_author_works(conn, "A1")[0].cited_by_count == 42  # parsed from the live fetch
    calls = len(fetcher.calls)
    with engine.begin() as conn:
        client.fetch_author_works(conn, "A1")  # cache hit
    assert len(fetcher.calls) == calls
    with engine.begin() as conn:
        client.fetch_author_works(conn, "A1", refresh=True)  # bypasses + re-fetches
    assert len(fetcher.calls) > calls


def test_decompose_domains_clusters_confirmed_members(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids, cand, works = _seed_confirmed_corpus(conn)
    fake = _FakeAuthorClient(author=_ADA_STATS, works=works)
    with engine.begin() as conn:
        resolve_my_publications(conn, author_client=fake, force=True)  # a*/b* confirmed; gamma → 0.25 candidate
        result = decompose_domains(conn, model=_ClusterModel(), author_client=fake)
        domains = get_profile(conn)["research_domains"]
    assert result["status"] == "ok" and result["domain_count"] == 2
    groups = sorted(sorted(d["paper_ids"]) for d in domains)
    assert groups == sorted([sorted([ids["a1"], ids["a2"]]), sorted([ids["b1"], ids["b2"]])])  # alpha / beta split
    assert all(d["terms"] for d in domains)  # each domain has c-TF-IDF terms
    assert cand not in {pid for d in domains for pid in d["paper_ids"]}  # the unconfirmed candidate is excluded


def test_decompose_too_few(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        create_paper(conn, title="Alpha", csl_json=_csl("Alpha", "10.1/a1"), doi="10.1/a1")
    fake = _FakeAuthorClient(
        author=_ADA_STATS, works=[AuthorWork(doi="10.1/a1", title="a", year=2020, cited_by_count=1)]
    )
    with engine.begin() as conn:
        resolve_my_publications(conn, author_client=fake, force=True)
        assert decompose_domains(conn, model=_ClusterModel(), author_client=fake)["status"] == "too-few"


def test_dashboard_includes_domains_sorted_by_citations(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _, _, works = _seed_confirmed_corpus(conn)
    fake = _FakeAuthorClient(author=_ADA_STATS, works=works)
    with engine.begin() as conn:
        resolve_my_publications(conn, author_client=fake, force=True)
        decompose_domains(conn, model=_ClusterModel(), author_client=fake)
        persisted = get_profile(conn)["research_domains"]
        set_research_domains(
            conn,
            [*persisted, {"label": "Deleted-paper domain", "terms": ["stale"], "paper_ids": [999999]}],
        )
        dash = build_dashboard(conn, author_client=fake)
    domains = dash["domains"]
    assert len(domains) == 2
    assert domains[0]["citation_count"] == 150 and domains[1]["citation_count"] == 15  # beta first (impact order)
    assert domains[0]["paper_count"] == 2
    assert all(domain["key"].startswith("domain:") for domain in domains)


def test_domains_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _, _, works = _seed_confirmed_corpus(conn)
    fake = _FakeAuthorClient(author=_ADA_STATS, works=works)
    with engine.begin() as conn:
        resolve_my_publications(conn, author_client=fake, force=True)
    client = TestClient(create_app(db_url=temp_db_url, openalex_author_client=fake, embedding_model=_ClusterModel()))
    started = client.post("/my-publications/domains", json={})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(20):
        result = client.get(f"/my-publications/domains/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done" and result["result_status"] == "ok" and result["domain_count"] == 2
    assert len(client.get("/my-publications/dashboard").json()["domains"]) == 2


# --- starring + scoped summary (inc 84) ------------------------------------------------------------------


def test_star_toggles_and_clusters_reflect_it(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        p1 = create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/engine"), doi="10.1/engine")
    fake = _FakeAuthorClient(
        author=_ADA_STATS, works=[AuthorWork(doi="10.1/engine", title="Engine", year=1843, cited_by_count=3)]
    )
    with engine.begin() as conn:
        resolve_my_publications(conn, author_client=fake, force=True)
    client = TestClient(create_app(db_url=temp_db_url, openalex_author_client=fake))
    assert client.post("/my-publications/star", json={"paper_id": p1, "starred": True}).status_code == 204
    axis = next(a for a in client.get("/axes").json() if a["kind"] == "my_publications")
    papers = [p for node in client.get(f"/axes/{axis['id']}/clusters").json() for p in node["papers"]]
    assert any(p["id"] == p1 and p["starred"] for p in papers)  # starred surfaces on the my-pubs clusters
    assert client.post("/my-publications/star", json={"paper_id": p1, "starred": False}).status_code == 204
    papers2 = [p for node in client.get(f"/axes/{axis['id']}/clusters").json() for p in node["papers"]]
    assert all(not p["starred"] for p in papers2)


def test_generate_summary_scoped_to_starred(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        p1 = create_paper(conn, title="Engine", csl_json=_csl("Engine", "10.1/engine"), doi="10.1/engine")
        create_paper(conn, title="Other", csl_json=_csl("Other", "10.1/other"), doi="10.1/other")
    works = [
        AuthorWork(doi="10.1/engine", title="Engine", year=1843, cited_by_count=1),
        AuthorWork(doi="10.1/other", title="Other", year=1844, cited_by_count=1),
    ]
    fake = _FakeAuthorClient(author=_ADA_STATS, works=works)
    with engine.begin() as conn:
        resolve_my_publications(conn, author_client=fake, force=True)  # 2 confirmed members
    client = TestClient(
        create_app(db_url=temp_db_url, openalex_author_client=fake, research_summary_generator=_FakeSummaryGen())
    )
    assert (
        client.post("/my-publications/summary/generate", json={"starred_only": True}).status_code == 422
    )  # none starred
    client.post("/my-publications/star", json={"paper_id": p1, "starred": True})
    starred = client.post("/my-publications/summary/generate", json={"starred_only": True})
    assert starred.status_code == 200 and "1 publications" in starred.json()["summary"]  # scoped to the 1 starred
    full = client.post("/my-publications/summary/generate", json={"starred_only": False})
    assert "2 publications" in full.json()["summary"]  # all members


# --- missing-works review + import (inc 85) --------------------------------------------------------------


def test_missing_works_excludes_matched_and_dismissed(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        set_openalex_author_id(conn, "A1")
        create_paper(conn, title="In Library", csl_json=_csl("In Library", "10.1/inlib"), doi="10.1/inlib")
    works = [
        AuthorWork(doi="10.1/inlib", title="In Library", year=2019, cited_by_count=1),
        AuthorWork(doi="10.1/miss-a", title="Missing A", year=2020, cited_by_count=5),
        AuthorWork(doi="10.1/miss-b", title="Missing B", year=2021, cited_by_count=80),
    ]
    fake = _FakeAuthorClient(author=_ADA_STATS, works=works)
    with engine.begin() as conn:
        mw = build_dashboard(conn, author_client=fake)["missing_works"]
    assert [w["doi"] for w in mw] == ["10.1/miss-b", "10.1/miss-a"]  # matched excluded; sorted by citations
    with engine.begin() as conn:
        dismiss_work(conn, "10.1/MISS-B")  # normalized (case-insensitive)
        mw2 = build_dashboard(conn, author_client=fake)["missing_works"]
    assert [w["doi"] for w in mw2] == ["10.1/miss-a"]  # the dismissed work is gone


def test_import_missing_work_adds_to_library_and_mypubs(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        create_paper(conn, title="Have", csl_json=_csl("Have", "10.1/have"), doi="10.1/have")
    works = [
        AuthorWork(doi="10.1/have", title="Have", year=2019, cited_by_count=1),
        AuthorWork(doi="10.1/want", title="Want", year=2020, cited_by_count=9),
    ]
    fake = _FakeAuthorClient(author=_ADA_STATS, works=works)
    with engine.begin() as conn:
        resolve_my_publications(conn, author_client=fake, force=True)  # have → member; want → missing
        result = import_missing_work(conn, doi="10.1/want", author_client=fake, crossref_client=_NoCrossref())
        members = _members(conn)
        mw = build_dashboard(conn, author_client=fake)["missing_works"]
    assert result["status"] == "imported"
    assert members.get(result["paper_id"]) == 0.95  # the imported work joins My Pubs as a confirmed member
    assert "10.1/want" not in {w["doi"] for w in mw}  # now in the library → no longer missing
    with engine.begin() as conn:  # idempotent
        again = import_missing_work(conn, doi="10.1/want", author_client=fake, crossref_client=_NoCrossref())
    assert again["status"] == "exists" and again["paper_id"] == result["paper_id"]


def test_import_rejects_non_author_doi_and_dismiss_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        set_openalex_author_id(conn, "A1")
    fake = _FakeAuthorClient(
        author=_ADA_STATS, works=[AuthorWork(doi="10.1/mine", title="Mine", year=2020, cited_by_count=1)]
    )
    client = TestClient(create_app(db_url=temp_db_url, openalex_author_client=fake, crossref_client=_NoCrossref()))
    # a DOI not among the author's works is refused (no arbitrary minting)
    assert client.post("/my-publications/works/import", json={"doi": "10.1/not-mine"}).status_code == 422
    # the dismiss endpoint is local + always 204
    assert client.post("/my-publications/works/dismiss", json={"doi": "10.1/mine"}).status_code == 204


def test_undismiss_returns_work_to_missing_queue(temp_db_url):
    # A dismissed missing work can be undone (inc 91, mirror of inc-67): it surfaces in dismissed_works, and
    # un-dismissing moves it back to missing_works.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        upsert_profile(conn, display_name="Ada Lovelace", name_variants=[], orcid="0000-0002-1825-0097")
        set_openalex_author_id(conn, "A1")
    fake = _FakeAuthorClient(
        author=_ADA_STATS, works=[AuthorWork(doi="10.1/miss", title="Missing", year=2020, cited_by_count=3)]
    )
    with engine.begin() as conn:
        assert [w["doi"] for w in build_dashboard(conn, author_client=fake)["missing_works"]] == ["10.1/miss"]
        dismiss_work(conn, "10.1/miss")
        dash = build_dashboard(conn, author_client=fake)
    assert dash["missing_works"] == []  # dismissed → out of the queue
    assert [w["doi"] for w in dash["dismissed_works"]] == ["10.1/miss"]  # …and visible as "previously dismissed"
    with engine.begin() as conn:
        undismiss_work(conn, "10.1/MISS")  # case-insensitive
        dash2 = build_dashboard(conn, author_client=fake)
    assert [w["doi"] for w in dash2["missing_works"]] == ["10.1/miss"]  # back in the queue
    assert dash2["dismissed_works"] == []

    # the undismiss endpoint is local + always 204 (idempotent)
    client = TestClient(create_app(db_url=temp_db_url, openalex_author_client=fake))
    assert client.post("/my-publications/works/undismiss", json={"doi": "10.1/miss"}).status_code == 204


def test_research_summary_prompt_bounds_documents_tighter_for_managed_local_than_cloud() -> None:
    """60 docs x 600-char abstracts is up to 36,000 chars of abstracts alone; measured real worst-case input
    was 56,397 chars -- well past the managed Local AI preview's ~10,240-token budget."""
    from integrations.gemini.research_summary import _prompt

    documents = [{"title": f"Paper {i}", "abstract": "x" * 600} for i in range(60)]

    cloud_prompt = _prompt(documents, provider="gemini")
    managed_prompt = _prompt(documents, provider="managed_local")

    assert len(managed_prompt) < len(cloud_prompt)
    assert "Paper 0" in managed_prompt and "Paper 59" not in managed_prompt  # fewer docs sent, not truncated mid-list
