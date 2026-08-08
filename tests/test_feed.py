"""inc 187 — literature Feed (backlog #28 SP2): subscriptions + polling + read/starred store + the bioRxiv source.

Hermetic — a fake FeedSource (and the bioRxiv source's injected collection fetcher) replace the network. Pull-only,
opt-in; public-metadata polling — not the Gemini gate.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.discovery.biorxiv_source import BioRxivFeedSource, record_to_entry
from app.backend.discovery.feed import (
    FeedEntry,
    FeedRegistry,
    build_default_feed_registry,
    feed_view,
    refresh_subscriptions,
)
from app.backend.persistence import feed_repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper


class _FakeSource:
    kind = "test_source"

    def __init__(self, entries, *, boom=False):
        self.entries = entries
        self.boom = boom

    def fetch(self, value, *, limit):
        if self.boom:
            raise RuntimeError("source down")
        return self.entries[:limit]


# ---- feed_repo: subscriptions + items + state ------------------------------


def test_feed_repo_subscriptions_items_and_state(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        s = feed_repo.add_subscription(conn, kind="biorxiv_category", value="neuroscience", label="Neuro")
        again = feed_repo.add_subscription(conn, kind="biorxiv_category", value="neuroscience")  # get-or-create
        assert again["id"] == s["id"]
        sid = int(s["id"])
        n1 = feed_repo.upsert_items(
            conn, sid, [{"dedup_key": "doi:1", "title": "A"}, {"dedup_key": "doi:2", "title": "B"}]
        )
        n2 = feed_repo.upsert_items(conn, sid, [{"dedup_key": "doi:1", "title": "A"}])  # dup → 0 new
        assert n1 == 2 and n2 == 0 and feed_repo.unread_count(conn) == 2
        items = feed_repo.list_items(conn, subscription_id=sid)
        iid = int(items[0]["id"])
        feed_repo.set_item_state(conn, iid, is_read=True, is_starred=True)
        assert feed_repo.unread_count(conn) == 1
        assert len(feed_repo.list_items(conn, unread_only=True)) == 1
        assert len(feed_repo.list_items(conn, starred_only=True)) == 1
        feed_repo.upsert_items(conn, sid, [{"dedup_key": items[0]["dedup_key"], "title": "A"}])  # re-poll
        assert feed_repo.unread_count(conn) == 1  # read state preserved across a re-poll
        assert feed_repo.mark_all_read(conn) == 1 and feed_repo.unread_count(conn) == 0
        feed_repo.remove_subscription(conn, sid)
        assert feed_repo.list_items(conn, subscription_id=sid) == []  # FK cascade dropped the items
    engine.dispose()


# ---- bioRxiv source: record mapping + category filter + dedup --------------


def test_biorxiv_record_to_entry_maps_fields():
    rec = {
        "doi": "10.1101/2025.12.27.696608",
        "title": "Connections of early visual areas",
        "authors": "Wang, Q.; Kaas, J. H.; Stepniewska, I.",
        "date": "2025-12-29",
        "category": "neuroscience",
        "abstract": "Body text.",
    }
    e = record_to_entry(rec)
    assert e is not None and e.doi == "10.1101/2025.12.27.696608" and e.journal == "bioRxiv" and e.year == 2025
    assert e.authors == ("Wang, Q.", "Kaas, J. H.", "Stepniewska, I.")
    assert e.dedup_key == "doi:10.1101/2025.12.27.696608"
    assert e.url == "https://www.biorxiv.org/content/10.1101/2025.12.27.696608v1"
    assert record_to_entry({"title": "", "doi": ""}) is None  # no title and no doi → dropped


def test_biorxiv_fetch_filters_category_and_dedups():
    rec = {"doi": "10.1101/a", "title": "A", "authors": "X Y", "date": "2025-12-29", "category": "neuroscience"}

    def fake(window_days, max_pages, *, timeout):
        return [rec, {**rec, "category": "genetics"}, {**rec}]  # one off-category + a dup of the first

    src = BioRxivFeedSource(fetcher=fake)
    items = src.fetch("neuroscience", limit=10)
    assert [i.doi for i in items] == ["10.1101/a"]  # genetics filtered out; the duplicate collapsed
    assert src.fetch("", limit=10) == []  # blank category → no fetch


def test_default_feed_registry_registers_sources():
    reg = build_default_feed_registry()
    # inc 295: journal-by-title is registered FIRST → it's the Follow picker's default; journal-by-ISSN dropped.
    assert reg.kinds == ["journal", "biorxiv_category", "medrxiv_category", "pubmed_query"]
    meta = {m["kind"]: m for m in reg.source_meta}
    assert meta["journal"]["label"] == "Journal"
    assert meta["biorxiv_category"]["label"] == "bioRxiv category" and meta["biorxiv_category"]["suggestions"]
    assert meta["medrxiv_category"]["label"] == "medRxiv category" and meta["medrxiv_category"]["suggestions"]
    assert meta["pubmed_query"]["label"] == "PubMed search"
    assert all(m["user_addable"] for m in reg.source_meta)  # the 4 built-ins are all directly Follow-able


# ---- followed-author Feed source (inc 455) ----------------------------------


def test_default_feed_registry_with_engine_registers_followed_author_source():
    from app.backend.persistence.database import make_engine as _make_engine

    engine = _make_engine("sqlite:///:memory:")
    reg = build_default_feed_registry(engine=engine)
    assert reg.kinds == ["journal", "biorxiv_category", "medrxiv_category", "pubmed_query", "followed_author"]
    meta = {m["kind"]: m for m in reg.source_meta}
    assert meta["followed_author"]["label"] == "Followed author"
    assert meta["followed_author"]["user_addable"] is False  # never offered in the generic "Add source" picker
    engine.dispose()


class _FakeAuthorClient:
    def __init__(self, works_by_author):
        self.works_by_author = works_by_author

    def with_cache_engine(self, _engine):
        return self

    def fetch_author_works(self, conn, author_id, *, refresh=False):
        return self.works_by_author.get(author_id, [])


def test_followed_author_source_maps_skips_no_doi_and_caps_limit(temp_db_url):
    from app.backend.discovery.followed_author_feed_source import FollowedAuthorFeedSource
    from integrations.openalex import AuthorWork

    engine = make_engine(temp_db_url)
    works = [
        AuthorWork(doi="10.9/newer", title="Newer", year=2025, cited_by_count=0, openalex_work_id="W1"),
        AuthorWork(doi=None, title="No DOI", year=2026, cited_by_count=0, openalex_work_id="W2"),
        AuthorWork(doi="10.9/older", title="Older", year=2020, cited_by_count=0, openalex_work_id="W3"),
    ]
    src = FollowedAuthorFeedSource(engine=engine, author_client=_FakeAuthorClient({"A1": works}))
    entries = src.fetch("A1", limit=1)
    assert [e.doi for e in entries] == ["10.9/newer"]  # no-DOI skipped, newest-first, capped to limit
    assert entries[0].posted_date == "2025"  # a bare year, not left NULL -- feed_repo sorts by posted_date DESC
    assert src.fetch("", limit=10) == []
    engine.dispose()


def test_followed_author_source_prefers_real_publication_date_over_bare_year(temp_db_url):
    """inc 458 (backlog #28): when OpenAlex supplies a real `publication_date`, Feed uses it (day-level precision)
    instead of falling back to a bare "YYYY" -- a work dated later in the same year now sorts ahead of an earlier
    same-year work, which a bare-year-only posted_date couldn't distinguish."""
    from app.backend.discovery.followed_author_feed_source import FollowedAuthorFeedSource
    from integrations.openalex import AuthorWork

    engine = make_engine(temp_db_url)
    works = [
        AuthorWork(doi="10.9/dated", title="Dated", year=2026, cited_by_count=0, publication_date="2026-03-14"),
        AuthorWork(doi="10.9/undated", title="Undated", year=2026, cited_by_count=0),  # pre-458 cache: no date
    ]
    src = FollowedAuthorFeedSource(engine=engine, author_client=_FakeAuthorClient({"A1": works}))
    entries = {e.doi: e for e in src.fetch("A1", limit=10)}
    assert entries["10.9/dated"].posted_date == "2026-03-14"  # real date used verbatim
    assert entries["10.9/undated"].posted_date == "2026"  # falls back to the bare year, unchanged
    engine.dispose()


def test_followed_author_source_items_sort_correctly_alongside_dated_sources(temp_db_url):
    """Regression: a NULL posted_date sorts LAST under feed_repo.list_items's `posted_date DESC` ordering
    (SQLite treats NULL as smallest) -- so a followed author's newest work would silently sink to the bottom of
    the feed regardless of recency unless posted_date is set to at least a bare year."""
    from app.backend.discovery.followed_author_feed_source import FollowedAuthorFeedSource
    from integrations.openalex import AuthorWork

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        feed_repo.add_subscription(conn, kind="test_source", value="dated")
        feed_repo.add_subscription(conn, kind="followed_author", value="A1", label="A")
        dated_source = _FakeSource(
            [FeedEntry(dedup_key="doi:old", title="Old dated item", doi="10.1/old", posted_date="2024-01-01")]
        )
        src = FollowedAuthorFeedSource(
            engine=engine,
            author_client=_FakeAuthorClient(
                {"A1": [AuthorWork(doi="10.9/new", title="New followed-author work", year=2026, cited_by_count=0)]}
            ),
        )
        reg = FeedRegistry().register(dated_source).register(src)
        refresh_subscriptions(conn, reg)
        titles = [v["title"] for v in feed_view(conn)]
        assert titles[0] == "New followed-author work"  # 2026 sorts before the 2024-01-01 dated item, not after
    engine.dispose()


def test_refresh_subscriptions_dispatches_to_followed_author_source(temp_db_url):
    from integrations.openalex import AuthorWork

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        feed_repo.add_subscription(conn, kind="followed_author", value="A1", label="A. Researcher")
        reg = FeedRegistry().register(
            _wrap_source(
                "followed_author",
                _FakeAuthorClient({"A1": [AuthorWork(doi="10.9/x", title="X", year=2024, cited_by_count=0)]}),
                engine,
            )
        )
        counts = refresh_subscriptions(conn, reg)
        assert counts == {"subscriptions": 1, "new_items": 1}
        items = [v["doi"] for v in feed_view(conn)]
        assert items == ["10.9/x"]
    engine.dispose()


def _wrap_source(kind, author_client, engine):
    from app.backend.discovery.followed_author_feed_source import FollowedAuthorFeedSource

    src = FollowedAuthorFeedSource(engine=engine, author_client=author_client)
    assert src.kind == kind
    return src


def test_medrxiv_source_uses_the_medrxiv_server():
    from app.backend.discovery.biorxiv_source import BioRxivFeedSource

    captured = {}

    def fake(window_days, max_pages, *, timeout):
        captured["called"] = True
        return [
            {
                "doi": "10.1101/m",
                "title": "A medRxiv preprint",
                "date": "2026-06-20",
                "category": "epidemiology",
                "server": "medrxiv",
            }
        ]

    src = BioRxivFeedSource(server="medrxiv", fetcher=fake)
    assert src.kind == "medrxiv_category" and src.label == "medRxiv category" and src.server == "medrxiv"
    items = src.fetch("epidemiology", limit=10)
    assert [i.doi for i in items] == ["10.1101/m"] and captured["called"]
    assert items[0].journal == "medRxiv" and "medrxiv.org" in items[0].url  # server-aware label + URL


# ---- journal-by-title Feed source (inc 295) --------------------------------


def test_journal_title_record_and_fetch():
    from app.backend.discovery.journal_title_source import JournalTitleFeedSource, record_to_feed_entry

    msg = {
        "DOI": "10.1038/AbC",
        "title": ["A Nature Paper"],
        "container-title": ["Nature"],
        "author": [{"family": "Curie", "given": "Marie"}],
        "issued": {"date-parts": [[2026, 6, 7]]},
        "published": {"date-parts": [[2026, 6, 9]]},
        "URL": "https://doi.org/10.1038/abc",
    }
    e = record_to_feed_entry(msg)
    assert e is not None and e.doi == "10.1038/abc" and e.journal == "Nature" and e.posted_date == "2026-06-09"
    assert e.dedup_key == "doi:10.1038/abc"

    captured = {}

    def fake_lookup(title, *, mailto, timeout):
        captured["title"] = title
        return "1476-4687"  # resolve the journal title → its ISSN

    def fake_works(params, *, mailto, timeout):
        captured["params"] = params
        return [msg, {**msg, "DOI": "10.1038/b", "title": ["Second"]}]

    src = JournalTitleFeedSource(works_fetcher=fake_works, issn_lookup=fake_lookup, mailto="x@example.com")
    items = src.fetch("Nature", limit=10)
    assert [i.doi for i in items] == ["10.1038/abc", "10.1038/b"]
    assert captured["title"] == "Nature" and captured["params"]["filter"] == "issn:1476-4687"  # exact ISSN path

    # no ISSN match → fuzzy container-title works query
    src2 = JournalTitleFeedSource(works_fetcher=fake_works, issn_lookup=lambda *a, **k: None, mailto="x@example.com")
    src2.fetch("Some Journal", limit=5)
    assert captured["params"].get("query.container-title") == "Some Journal"

    assert src.fetch("", limit=10) == []  # blank title → no fetch (validated before the request)


# ---- PubMed-keyword Feed source (SP2c, inc 189) ----------------------------


def test_pubmed_feed_record_and_fetch_sorted_by_date():
    from app.backend.discovery.pubmed_provider import PubMedKeywordFeedSource, record_to_feed_entry

    rec = {
        "uid": "42",
        "title": "A Recent Paper.",
        "fulljournalname": "J. Recent",
        "sortpubdate": "2026/06/20 00:00",
        "authors": [{"name": "Smith J"}],
        "articleids": [{"idtype": "doi", "value": "10.1/x"}],
    }
    e = record_to_feed_entry(rec)
    assert e.doi == "10.1/x" and e.posted_date == "2026/06/20" and e.dedup_key == "doi:10.1/x"
    assert e.journal == "J. Recent" and e.url == "https://pubmed.ncbi.nlm.nih.gov/42/"
    assert record_to_feed_entry({"uid": "1", "title": "", "articleids": []}) is None  # no title + no doi → dropped

    captured = {}

    def fake(query, retmax, *, email, timeout, sort):
        captured["sort"] = sort
        return [rec, {**rec, "uid": "43", "articleids": [{"idtype": "doi", "value": "10.1/y"}]}]

    src = PubMedKeywordFeedSource(fetcher=fake, abstract_fetcher=lambda pmids, *, email, timeout: {})
    items = src.fetch("crispr", limit=10)
    assert [i.doi for i in items] == ["10.1/x", "10.1/y"] and captured["sort"] == "date"  # newest-first poll
    assert src.fetch("   ", limit=10) == []  # blank query → no fetch


def test_pubmed_efetch_abstracts_parse_and_enrich():
    from app.backend.discovery.pubmed_provider import PubMedKeywordFeedSource, _parse_abstracts

    xml = (
        "<x><PubmedArticle><MedlineCitation><PMID Version='1'>42</PMID>"
        "<Abstract><AbstractText Label='BACKGROUND'>First &amp; <i>part</i>.</AbstractText>"
        "<AbstractText Label='RESULTS'>Second part.</AbstractText></Abstract></MedlineCitation></PubmedArticle>"
        "<PubmedArticle><MedlineCitation><PMID>43</PMID></MedlineCitation></PubmedArticle></x>"  # no abstract
    )
    parsed = _parse_abstracts(xml)
    assert parsed == {"42": "First & part. Second part."}  # joined, entity-unescaped, inline tags stripped; 43 absent

    rec = {"uid": "42", "title": "Has Abstract", "articleids": [{"idtype": "doi", "value": "10.1/a"}]}

    def fake(query, retmax, *, email, timeout, sort):
        return [rec]

    src = PubMedKeywordFeedSource(
        fetcher=fake, abstract_fetcher=lambda pmids, *, email, timeout: {"42": "The fetched abstract."}
    )
    items = src.fetch("q", limit=10)
    assert items[0].abstract == "The fetched abstract."  # efetch enriched the entry

    # a failing efetch never sinks the poll (abstracts are a nicety)
    def boom(pmids, *, email, timeout):
        raise RuntimeError("efetch down")

    src2 = PubMedKeywordFeedSource(fetcher=fake, abstract_fetcher=boom)
    assert src2.fetch("q", limit=10)[0].doi == "10.1/a"


# ---- the refresh + read service -------------------------------------------


def test_refresh_upserts_and_view_marks_in_library(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(conn, title="Owned", csl_json={"title": "Owned", "DOI": "10.1/owned"}, doi="10.1/owned")
        feed_repo.add_subscription(conn, kind="test_source", value="x")
        reg = FeedRegistry().register(
            _FakeSource(
                [
                    FeedEntry(dedup_key="doi:10.1/owned", title="Owned", doi="10.1/owned"),
                    FeedEntry(dedup_key="doi:10.1/new", title="New One", doi="10.1/new"),
                ]
            )
        )
        counts = refresh_subscriptions(conn, reg)
        assert counts == {"subscriptions": 1, "new_items": 2}
        assert refresh_subscriptions(conn, reg)["new_items"] == 0  # re-poll adds nothing
        by_doi = {v["doi"]: v for v in feed_view(conn)}
        assert by_doi["10.1/owned"]["in_library"] is True and by_doi["10.1/new"]["in_library"] is False
    engine.dispose()


def test_refresh_skips_a_failing_source(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        feed_repo.add_subscription(conn, kind="test_source", value="x")
        reg = FeedRegistry().register(_FakeSource([], boom=True))
        assert refresh_subscriptions(conn, reg)["new_items"] == 0  # a raising source is skipped, not fatal
    engine.dispose()


# ---- endpoints (injected fake registry) -----------------------------------


def _client(temp_db_url, entries):
    return TestClient(create_app(db_url=temp_db_url, feed_registry=FeedRegistry().register(_FakeSource(entries))))


def test_feed_endpoints(temp_db_url):
    entries = [
        FeedEntry(dedup_key="doi:10.1/a", title="A", doi="10.1/a"),
        FeedEntry(dedup_key="doi:10.1/b", title="B", doi="10.1/b"),
    ]
    client = _client(temp_db_url, entries)

    assert client.post("/feed/subscriptions", json={"kind": "bogus", "value": "x"}).status_code == 422
    r = client.post("/feed/subscriptions", json={"kind": "test_source", "value": "x", "label": "X"})
    assert r.status_code == 200
    sid = r.json()["id"]
    listing = client.get("/feed/subscriptions").json()
    assert listing["kinds"] == ["test_source"]
    assert listing["source_meta"] == [
        {"kind": "test_source", "label": "test_source", "placeholder": "", "suggestions": [], "user_addable": True}
    ]

    jid = client.post("/feed/refresh").json()["job_id"]
    data = {}
    for _ in range(30):
        data = client.get(f"/feed/refresh/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    assert data["status"] == "done" and data["result"]["new_items"] == 2

    body = client.get("/feed").json()
    assert len(body["items"]) == 2 and body["unread_count"] == 2
    iid = body["items"][0]["id"]
    assert client.post(f"/feed/items/{iid}/state", json={"is_read": True}).status_code == 200
    assert client.get("/feed", params={"unread": True}).json()["unread_count"] == 1
    assert client.post("/feed/mark-read", json={}).json()["marked"] == 1
    assert client.get("/feed", params={"unread": True}).json()["unread_count"] == 0

    assert client.delete(f"/feed/subscriptions/{sid}").status_code == 204
    assert client.get("/feed").json()["items"] == []  # cascade removed the items


def test_unfollowing_a_followed_author_subscription_from_feed_also_unfollows_it(temp_db_url):
    """inc 455: unfollowing via Feed's own subscription chip must mean the same thing as unfollowing via the
    Followed Authors tab -- both directions of the sync."""
    from integrations.openalex import ResolvedAuthor

    class _Client:
        def with_cache_engine(self, _engine):
            return self

        def resolve_author(self, conn, *, orcid=None, name=None):
            return ResolvedAuthor(
                author_id="A1", display_name="A. Researcher", orcid=None, works_count=1, matched_by="name"
            )

        def fetch_author_works(self, conn, author_id, *, refresh=False):
            return []

    app = create_app(db_url=temp_db_url, openalex_author_client=_Client())
    client = TestClient(app)
    client.post("/followed-authors", json={"name": "A. Researcher"})
    subs = client.get("/feed/subscriptions").json()["subscriptions"]
    sub = next(s for s in subs if s["kind"] == "followed_author")

    assert client.delete(f"/feed/subscriptions/{sub['id']}").status_code == 204
    assert client.get("/followed-authors").json() == []  # the reverse sync removed the followed_authors row too


def test_library_journals_endpoint(temp_db_url):
    # inc 295: the Feed "Suggest" journals + typeahead read the library's own venues (local, no egress).
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(conn, title="A", csl_json={"title": "A"}, venue="Nature")
        create_paper(conn, title="B", csl_json={"title": "B"}, venue="Nature")
        create_paper(conn, title="C", csl_json={"title": "C"}, venue="Cell")
        create_paper(conn, title="D", csl_json={"title": "D"})  # no venue → excluded
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    journals = client.get("/feed/library-journals").json()["journals"]
    assert journals == [{"journal": "Nature", "count": 2}, {"journal": "Cell", "count": 1}]  # most-frequent first
