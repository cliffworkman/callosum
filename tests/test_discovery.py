"""inc 183 — literature discovery (Search tab): the SourceProvider registry + Item dedup + the 2 endpoints.

Hermetic — the Crossref provider uses an injected fetcher (no network), and the endpoint tests inject a fake
registry via ``create_app(discovery_registry=...)``. Public-metadata search — NOT the Gemini egress gate.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.discovery.crossref_provider import CrossrefSearchProvider, message_to_item
from app.backend.discovery.providers import Item, SourceRegistry, build_default_registry
from app.backend.discovery.search import DISCOVERY_SOURCE, run_search, save_item
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, find_existing_paper_by_identity

# ---- Item: dedup key precedence + cross-provider merge ----------------------


def test_item_dedup_key_precedence():
    assert Item("T", doi="10.1/X").dedup_key == "doi:10.1/x"  # DOI wins, lowercased
    assert Item("T", pmid="123").dedup_key == "pmid:123"  # PMID next
    assert Item("A Study  Of: Things").dedup_key == "title:a study of things"  # else normalized title


def test_item_merged_with_unions_sources_and_fills_blanks():
    a = Item("T", sources=("crossref",), doi="10.1/x", year=2020)
    b = Item("T", sources=("pubmed",), doi="10.1/x", abstract="full", year=2021)
    merged = a.merged_with(b)
    assert merged.sources == ("crossref", "pubmed")  # unioned, order preserved
    assert merged.abstract == "full"  # blank filled from the other
    assert merged.year == 2020  # the first non-blank wins (a's)


# ---- Crossref provider: message → Item mapping -----------------------------


def test_message_to_item_maps_fields_and_strips_jats():
    item = message_to_item(
        {
            "DOI": "10.5/AbC",
            "title": ["A Discovery Paper"],
            "abstract": "<jats:p>Body text here.</jats:p>",
            "author": [{"family": "Curie", "given": "Marie"}, {"family": "Lovelace", "given": "Ada"}],
            "container-title": ["Journal of Things"],
            "issued": {"date-parts": [[2019, 4]]},
            "URL": "https://doi.org/10.5/abc",
        }
    )
    assert item is not None
    assert item.doi == "10.5/abc" and item.sources == ("crossref",)  # DOI lowercased
    assert item.title == "A Discovery Paper" and item.journal == "Journal of Things" and item.year == 2019
    assert item.authors == ("Curie, Marie", "Lovelace, Ada")
    assert item.abstract == "Body text here."  # JATS stripped


def test_message_to_item_drops_entries_with_no_title_and_no_doi():
    assert message_to_item({"author": [{"family": "Nobody"}]}) is None
    assert message_to_item({"DOI": "10.1/only-doi"}) is not None  # a DOI alone is enough


def test_crossref_provider_uses_injected_fetcher():
    captured = {}

    def fake(query, rows, *, headers, timeout):
        captured["query"] = query
        captured["rows"] = rows
        return [{"DOI": "10.1/a", "title": ["First"]}, {"DOI": "10.1/b", "title": ["Second"]}]

    provider = CrossrefSearchProvider(fetcher=fake, mailto="x@example.com")
    items = provider.search("faces", 10)
    assert [i.doi for i in items] == ["10.1/a", "10.1/b"] and captured["query"] == "faces"
    assert provider.search("   ", 10) == []  # blank query → no fetch


# ---- registry: fan-out + one bad source doesn't sink the others ------------


class _FakeProvider:
    def __init__(self, name, items):
        self.name = name
        self._items = items

    def search(self, query, limit):
        # A real provider labels its own results; stamp the name when an item left sources blank.
        from dataclasses import replace

        return [it if it.sources else replace(it, sources=(self.name,)) for it in self._items]


class _BoomProvider:
    name = "boom"

    def search(self, query, limit):
        raise RuntimeError("provider down")


def test_registry_search_all_skips_a_failing_provider():
    reg = SourceRegistry().register(_BoomProvider()).register(_FakeProvider("good", [Item("Survivor")]))
    out = reg.search_all("q", 10)
    assert [i.title for i in out] == ["Survivor"]  # the boom provider was swallowed


def test_build_default_registry_registers_crossref_and_pubmed():
    reg = build_default_registry()
    assert [p.name for p in reg.providers] == ["crossref", "pubmed"]  # adding a source = one register() (SP1a)
    assert reg.source_meta == [{"kind": "crossref", "label": "Crossref"}, {"kind": "pubmed", "label": "PubMed"}]


# ---- run_search: cross-provider dedup + in_library marking -----------------


def test_run_search_dedups_across_providers_and_unions_sources(temp_db_url):
    p1 = _FakeProvider("crossref", [Item("Paper A", sources=("crossref",), doi="10.1/dup")])
    p2 = _FakeProvider("pubmed", [Item("Paper A", sources=("pubmed",), doi="10.1/dup", abstract="from pubmed")])
    reg = SourceRegistry().register(p1).register(p2)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        items = run_search(conn, reg, "paper a")
    engine.dispose()
    assert len(items) == 1  # one DOI → one row
    assert items[0].sources == ("crossref", "pubmed") and items[0].abstract == "from pubmed"


def test_run_search_can_query_one_named_source(temp_db_url):
    reg = (
        SourceRegistry()
        .register(_FakeProvider("crossref", [Item("Crossref Paper", sources=("crossref",), doi="10.1/c")]))
        .register(_FakeProvider("pubmed", [Item("PubMed Paper", sources=("pubmed",), doi="10.1/p")]))
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        items = run_search(conn, reg, "paper", source="pubmed")
    engine.dispose()
    assert [item.title for item in items] == ["PubMed Paper"]


def test_run_search_rejects_unknown_source(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        try:
            run_search(conn, SourceRegistry(), "paper", source="missing")
        except ValueError as exc:
            assert "Unknown discovery source: missing" in str(exc)
        else:  # pragma: no cover - defensive clarity
            raise AssertionError("unknown source should fail closed")
    engine.dispose()


def test_run_search_marks_in_library(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(conn, title="Owned", csl_json={"title": "Owned", "DOI": "10.1/owned"}, doi="10.1/owned")
    reg = SourceRegistry().register(
        _FakeProvider(
            "crossref",
            [Item("Owned", doi="10.1/owned"), Item("New Paper", doi="10.1/new")],
        )
    )
    with engine.begin() as conn:
        items = run_search(conn, reg, "q")
    engine.dispose()
    by_doi = {i.doi: i for i in items}
    assert by_doi["10.1/owned"].in_library is True and by_doi["10.1/new"].in_library is False


# ---- save_item: dedup-aware metadata-only create ---------------------------


def test_save_item_creates_metadata_only_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = save_item(
            conn,
            title="Saved Paper",
            doi="10.7/saved",
            abstract="An abstract.",
            authors=["Curie, Marie"],
            journal="J. Saves",
            year=2021,
            url="https://doi.org/10.7/saved",
        )
        row = find_existing_paper_by_identity(conn, doi="10.7/saved")
    engine.dispose()
    assert result["created"] is True and result["paper_id"] > 0
    assert row is not None and row[1]["imported_source"] == DISCOVERY_SOURCE


def test_save_item_dedups_against_an_existing_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        existing = create_paper(
            conn, title="Already Here", csl_json={"title": "Already Here", "DOI": "10.1/here"}, doi="10.1/here"
        )
        result = save_item(conn, title="Already Here", doi="10.1/here")
    engine.dispose()
    assert result == {"paper_id": existing, "created": False}  # deduped, no second row


# ---- endpoints (injected fake registry) ------------------------------------


def _client(temp_db_url, registry):
    return TestClient(create_app(db_url=temp_db_url, discovery_registry=registry))


def test_search_endpoint_shape(temp_db_url):
    reg = SourceRegistry().register(
        _FakeProvider("crossref", [Item("Endpoint Paper", sources=("crossref",), doi="10.1/e", year=2022)])
    )
    client = _client(temp_db_url, reg)
    body = client.get("/discovery/search", params={"q": "endpoint"}).json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["doi"] == "10.1/e" and item["dedup_key"] == "doi:10.1/e" and item["in_library"] is False
    assert item["sources"] == ["crossref"] and item["year"] == 2022


def test_sources_endpoint_returns_search_provider_metadata(temp_db_url):
    reg = SourceRegistry().register(_FakeProvider("crossref", [])).register(_FakeProvider("pubmed", []))
    client = _client(temp_db_url, reg)
    assert client.get("/discovery/sources").json() == {
        "sources": [{"kind": "crossref", "label": "crossref"}, {"kind": "pubmed", "label": "pubmed"}]
    }


def test_search_endpoint_can_restrict_to_one_source(temp_db_url):
    reg = (
        SourceRegistry()
        .register(_FakeProvider("crossref", [Item("Crossref Paper", sources=("crossref",), doi="10.1/c")]))
        .register(_FakeProvider("pubmed", [Item("PubMed Paper", sources=("pubmed",), doi="10.1/p")]))
    )
    client = _client(temp_db_url, reg)
    body = client.get("/discovery/search", params={"q": "paper", "source": "pubmed"}).json()
    assert [item["title"] for item in body["items"]] == ["PubMed Paper"]


def test_search_endpoint_rejects_unknown_source(temp_db_url):
    client = _client(temp_db_url, SourceRegistry())
    r = client.get("/discovery/search", params={"q": "paper", "source": "missing"})
    assert r.status_code == 422 and "Unknown discovery source" in r.json()["detail"]


def test_search_endpoint_rejects_blank_query(temp_db_url):
    client = _client(temp_db_url, SourceRegistry())
    assert client.get("/discovery/search", params={"q": ""}).status_code == 422


def test_save_endpoint_creates_then_search_marks_in_library(temp_db_url):
    reg = SourceRegistry().register(_FakeProvider("crossref", [Item("Cycle Paper", doi="10.1/cycle")]))
    client = _client(temp_db_url, reg)

    before = client.get("/discovery/search", params={"q": "cycle"}).json()["items"][0]
    assert before["in_library"] is False

    saved = client.post("/discovery/save", json={"title": "Cycle Paper", "doi": "10.1/cycle"})
    assert saved.status_code == 200 and saved.json()["created"] is True

    after = client.get("/discovery/search", params={"q": "cycle"}).json()["items"][0]
    assert after["in_library"] is True  # the saved paper now dedups against the library


def test_registry_accepts_a_new_provider_with_no_endpoint_edit(temp_db_url):
    """The 'add a source = register one provider' guarantee: a brand-new provider flows through the same endpoint."""
    reg = SourceRegistry().register(_FakeProvider("brandnew", [Item("From a New Source", doi="10.1/fresh")]))
    client = _client(temp_db_url, reg)
    body = client.get("/discovery/search", params={"q": "anything"}).json()
    assert body["items"][0]["sources"] == ["brandnew"]
