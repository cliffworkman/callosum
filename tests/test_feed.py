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
    assert reg.kinds == ["biorxiv_category", "pubmed_query", "journal_issn"]  # SP2c: PubMed + journal join bioRxiv
    meta = {m["kind"]: m for m in reg.source_meta}
    assert meta["biorxiv_category"]["label"] == "bioRxiv category" and meta["biorxiv_category"]["suggestions"]
    assert meta["pubmed_query"]["label"] == "PubMed search"
    assert meta["journal_issn"]["label"] == "Journal (ISSN)"


# ---- journal-by-ISSN Feed source (SP2c-2, inc 190) -------------------------


def test_journal_issn_record_and_fetch():
    from app.backend.discovery.journal_issn_source import JournalIssnFeedSource, record_to_feed_entry

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

    def fake(issn, rows, *, mailto, timeout):
        captured["issn"] = issn
        return [msg, {**msg, "DOI": "10.1038/b", "title": ["Second"]}]

    src = JournalIssnFeedSource(fetcher=fake, mailto="x@example.com")
    items = src.fetch("1476-4687", limit=10)
    assert [i.doi for i in items] == ["10.1038/abc", "10.1038/b"] and captured["issn"] == "1476-4687"
    assert src.fetch("not-an-issn", limit=10) == []  # invalid ISSN → no fetch (validated before the request)


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

    src = PubMedKeywordFeedSource(fetcher=fake)
    items = src.fetch("crispr", limit=10)
    assert [i.doi for i in items] == ["10.1/x", "10.1/y"] and captured["sort"] == "date"  # newest-first poll
    assert src.fetch("   ", limit=10) == []  # blank query → no fetch


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
        {"kind": "test_source", "label": "test_source", "placeholder": "", "suggestions": []}
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
