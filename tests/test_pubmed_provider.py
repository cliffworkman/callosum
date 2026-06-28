"""inc 186 — discovery SP1a: the PubMed (NCBI E-utilities) Search provider.

Hermetic — an injected fetcher replaces the esearch→esummary network calls. Public-metadata search — not the
Gemini gate. Maps esummary records → normalized Items; dedups across providers via run_search.
"""

from __future__ import annotations

from app.backend.discovery.providers import Item, SourceRegistry
from app.backend.discovery.pubmed_provider import PubMedSearchProvider, summary_to_item
from app.backend.discovery.search import run_search
from app.backend.persistence.database import make_engine

_REC = {
    "uid": "28182253",
    "title": "Attention Is All You Need.",
    "fulljournalname": "Advances in Neural Information Processing Systems",
    "source": "NeurIPS",
    "pubdate": "2017 Jun",
    "authors": [{"name": "Vaswani A"}, {"name": "Shazeer N"}],
    "articleids": [{"idtype": "pubmed", "value": "28182253"}, {"idtype": "doi", "value": "10.5555/Attn"}],
}


def test_summary_to_item_maps_fields():
    it = summary_to_item(_REC)
    assert it is not None
    assert it.pmid == "28182253" and it.doi == "10.5555/attn" and it.sources == ("pubmed",)  # doi lowercased
    assert it.title == "Attention Is All You Need" and it.journal.startswith("Advances")  # trailing "." stripped
    assert it.authors == ("Vaswani A", "Shazeer N") and it.year == 2017
    assert it.url == "https://pubmed.ncbi.nlm.nih.gov/28182253/"


def test_summary_to_item_doi_from_elocationid_and_drops_empty():
    it = summary_to_item({"uid": "9", "title": "", "elocationid": "doi: 10.1234/eloc"})
    assert it is not None and it.doi == "10.1234/eloc"  # no title but a DOI → kept; parsed from elocationid
    assert summary_to_item({"uid": "1", "title": "", "articleids": []}) is None  # no title and no DOI → dropped


def test_provider_uses_injected_fetcher():
    captured = {}

    def fake(query, retmax, *, email, timeout):
        captured["query"] = query
        captured["retmax"] = retmax
        return [_REC, {"uid": "2", "title": "Second", "articleids": [{"idtype": "doi", "value": "10.1/b"}]}]

    provider = PubMedSearchProvider(fetcher=fake, email="x@example.com")
    items = provider.search("transformers", 10)
    assert [i.pmid for i in items] == ["28182253", "2"] and captured["query"] == "transformers"
    assert provider.search("   ", 10) == []  # blank query → no fetch


def test_run_search_dedups_crossref_and_pubmed_on_doi(temp_db_url):
    # the SAME paper from Crossref (doi only) + PubMed (doi + pmid) → one item, both source labels
    crossref = type(
        "P",
        (),
        {
            "name": "crossref",
            "search": lambda self, q, n: [
                Item(title="Shared Paper", sources=("crossref",), doi="10.1/shared", journal="J")
            ],
        },
    )()
    pubmed = type(
        "P",
        (),
        {
            "name": "pubmed",
            "search": lambda self, q, n: [
                Item(title="Shared Paper", sources=("pubmed",), doi="10.1/shared", pmid="999")
            ],
        },
    )()
    reg = SourceRegistry().register(crossref).register(pubmed)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        items = run_search(conn, reg, "shared")
    engine.dispose()
    assert len(items) == 1
    assert items[0].sources == ("crossref", "pubmed") and items[0].pmid == "999"  # pmid filled from the pubmed copy
