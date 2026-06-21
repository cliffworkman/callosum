"""Tests for My Publications (inc 78) — hermetic (injected fake author client / fetcher; no real network,
no model tokens)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.clustering.my_publications import (
    build_dashboard,
    maybe_add_to_my_publications,
    resolve_my_publications,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.profile_repo import (
    get_decisions,
    get_profile,
    set_decision,
    set_my_publications_dismissed,
    set_openalex_author_id,
    upsert_profile,
)
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import axes, cluster_node_papers, cluster_nodes
from integrations.api_cache import put_cached
from integrations.openalex.author import OPENALEX_WORKS_PROVIDER, AuthorWork, OpenAlexAuthorClient, ResolvedAuthor


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

    def fetch_author_works(self, conn, author_id):
        return self.works


class _FakeSummaryGen:
    def generate(self, *, documents):
        return f"Ada's work spans {len(documents)} publications on analytical engines."


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


def test_author_client_fails_closed(temp_db_url):
    class _Boom:
        def __call__(self, url, *, params, headers, timeout):
            raise RuntimeError("network down")

    client = OpenAlexAuthorClient(fetcher=_Boom())
    with make_engine(temp_db_url).begin() as conn:
        assert client.resolve_author(conn, orcid="0000-x") is None  # never raises


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
        "summary_stats": {"h_index": 7, "i10_index": 4},
        "counts_by_year": [{"year": 2021, "works_count": 1, "cited_by_count": 10}],
    }
    client = OpenAlexAuthorClient(fetcher=_AuthorFetcher({"/authors/orcid:": (200, body)}))
    with make_engine(temp_db_url).begin() as conn:
        author = client.resolve_author(conn, orcid="0000-x")
    assert author.cited_by_count == 99 and author.h_index == 7 and author.i10_index == 4
    assert author.counts_by_year == ({"year": 2021, "works_count": 1, "cited_by_count": 10},)


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
