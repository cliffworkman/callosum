"""GitHub #77: Discover Search providers for arXiv / Europe PMC / PsyArXiv (the sources with a real free-text
search API). Hermetic — injected fetchers, no network. One real-API smoke per provider is skip-by-default.

Confirms: the default registry exposes all five search sources (so the data-driven dropdown shows them); each
new provider maps its source records into the canonical ``Item``; and ``run_search`` fans out across them and
dedups cross-provider duplicates through the existing ``Item.dedup_key`` policy (provider is never a ranking).
"""

from __future__ import annotations

from app.backend.discovery.preprint_search import (
    ArxivSearchProvider,
    EuropePmcSearchProvider,
    PsyArxivSearchProvider,
)
from app.backend.discovery.providers import SourceRegistry, build_default_registry
from app.backend.discovery.search import run_search
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper

_ARXIV_XML = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2601.12345v1</id>
    <title>Predictive Coding, Revisited</title>
    <published>2026-01-15T00:00:00Z</published>
    <summary>An arXiv abstract.</summary>
    <author><name>Ada Lovelace</name></author>
  </entry>
</feed>"""

# An arXiv entry that DID carry a published DOI — used to prove cross-provider dedup against Europe PMC.
_ARXIV_XML_WITH_DOI = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2601.99999v1</id>
    <title>Shared Work</title>
    <published>2026-02-01T00:00:00Z</published>
    <summary>Shared abstract.</summary>
    <author><name>Grace Hopper</name></author>
    <arxiv:doi>10.1/shared</arxiv:doi>
  </entry>
</feed>"""

_EPMC_REC = {
    "doi": "10.1/epmc",
    "title": "A Europe PMC Result",
    "authorString": "Curie, Marie",
    "journalInfo": {"journal": {"title": "Journal of Things"}},
    "pubYear": "2025",
    "firstPublicationDate": "2025-01-01",
    "abstractText": "An abstract.",
    "source": "MED",
    "id": "12345",
}

_PSY_REC = {
    "attributes": {"title": "A PsyArXiv Preprint", "doi": None, "date_published": "2024-03-01", "description": "abs"},
    "links": {"self": "https://api.osf.io/v2/preprints/abc123/"},
    "embeds": {},
}


def _arxiv(xml):
    return ArxivSearchProvider(fetcher=lambda q, rows, *, timeout: xml)


def test_default_registry_exposes_all_five_search_sources():
    reg = build_default_registry()
    assert reg.kinds == ["crossref", "pubmed", "arxiv", "europepmc", "psyarxiv"]
    labels = {m["kind"]: m["label"] for m in reg.source_meta}
    assert labels["arxiv"] == "arXiv" and labels["europepmc"] == "Europe PMC" and labels["psyarxiv"] == "PsyArXiv"


def test_arxiv_search_maps_atom_entry_to_item():
    items = _arxiv(_ARXIV_XML).search("predictive coding", 10)
    assert len(items) == 1
    it = items[0]
    assert it.title == "Predictive Coding, Revisited" and it.journal == "arXiv" and "arxiv.org/abs/2601.12345" in it.url
    assert it.sources == ("arxiv",) and it.doi is None  # a DOI-less preprint dedups by title


def test_europepmc_search_maps_record_to_item():
    prov = EuropePmcSearchProvider(fetcher=lambda q, rows, *, timeout: [_EPMC_REC])
    items = prov.search("hippocampus", 10)
    assert len(items) == 1 and items[0].doi == "10.1/epmc" and items[0].sources == ("europepmc",)
    assert items[0].journal == "Journal of Things" and items[0].year == 2025


def test_psyarxiv_search_maps_record_to_item():
    prov = PsyArxivSearchProvider(fetcher=lambda q, rows, *, timeout: [_PSY_REC])
    items = prov.search("working memory", 10)
    assert len(items) == 1 and items[0].title == "A PsyArXiv Preprint" and items[0].sources == ("psyarxiv",)
    assert "osf.io/abc123" in items[0].url  # DOI-less → OSF guid identity/url


def test_empty_query_returns_no_results():
    assert _arxiv(_ARXIV_XML).search("   ", 10) == []
    assert EuropePmcSearchProvider(fetcher=lambda q, rows, *, timeout: [_EPMC_REC]).search("", 10) == []


def test_run_search_fans_out_and_dedups_cross_provider(temp_db_url):
    # arXiv (with DOI 10.1/shared) + Europe PMC (a different DOI) both queried under "All sources".
    reg = (
        SourceRegistry()
        .register(_arxiv(_ARXIV_XML_WITH_DOI))
        .register(EuropePmcSearchProvider(fetcher=lambda q, rows, *, timeout: [_EPMC_REC]))
        .register(PsyArxivSearchProvider(fetcher=lambda q, rows, *, timeout: [_PSY_REC]))
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        items = run_search(conn, reg, "q")
    engine.dispose()
    by_doi = {i.doi: i for i in items}
    assert {"arxiv", "europepmc", "psyarxiv"}.issubset({s for i in items for s in i.sources})
    assert "10.1/shared" in by_doi and "10.1/epmc" in by_doi  # distinct DOIs → distinct rows (no false merge)


def test_run_search_merges_the_same_doi_from_two_providers(temp_db_url):
    # arXiv AND Europe PMC both return DOI 10.1/shared → one deduped row carrying BOTH source labels.
    shared_epmc = {**_EPMC_REC, "doi": "10.1/shared", "title": "Shared Work"}
    reg = (
        SourceRegistry()
        .register(_arxiv(_ARXIV_XML_WITH_DOI))
        .register(EuropePmcSearchProvider(fetcher=lambda q, rows, *, timeout: [shared_epmc]))
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        items = run_search(conn, reg, "q")
    engine.dispose()
    shared = [i for i in items if i.doi == "10.1/shared"]
    assert len(shared) == 1 and set(shared[0].sources) == {"arxiv", "europepmc"}


def test_run_search_marks_in_library(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(conn, title="Owned", csl_json={"title": "Owned", "DOI": "10.1/epmc"}, doi="10.1/epmc")
    reg = SourceRegistry().register(EuropePmcSearchProvider(fetcher=lambda q, rows, *, timeout: [_EPMC_REC]))
    with engine.begin() as conn:
        items = run_search(conn, reg, "q")
    engine.dispose()
    assert items and items[0].in_library is True
