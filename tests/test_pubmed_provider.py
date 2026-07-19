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


# --- MeSH extraction (inc 306 — the keyword:pubmed tag source) ---------------

_MESH_XML = (
    "<PubmedArticleSet><PubmedArticle><MedlineCitation>"
    '<PMID Version="1">12345</PMID>'
    "<MeshHeadingList>"
    '<MeshHeading><DescriptorName UI="D005145" MajorTopicYN="Y">Face</DescriptorName></MeshHeading>'
    # descriptor N but a MAJOR qualifier → the heading is major (Emotions/physiology is a primary point)
    '<MeshHeading><DescriptorName UI="D004644" MajorTopicYN="N">Emotions</DescriptorName>'
    '<QualifierName MajorTopicYN="Y">physiology</QualifierName></MeshHeading>'
    # a generic check-tag, all N → dropped once any major heading exists
    '<MeshHeading><DescriptorName UI="D006801" MajorTopicYN="N">Humans</DescriptorName></MeshHeading>'
    "</MeshHeadingList></MedlineCitation></PubmedArticle></PubmedArticleSet>"
)


def test_parse_mesh_prefers_major_headings_and_drops_check_tags():
    from app.backend.discovery.pubmed_provider import _parse_mesh

    assert _parse_mesh(_MESH_XML) == {"12345": ["Face", "Emotions"]}  # "Humans" (all-N check-tag) dropped


def test_parse_mesh_falls_back_to_all_when_none_major():
    from app.backend.discovery.pubmed_provider import _parse_mesh

    xml = (
        "<PubmedArticle><PMID>1</PMID><MeshHeadingList>"
        '<MeshHeading><DescriptorName MajorTopicYN="N">Alpha</DescriptorName></MeshHeading>'
        '<MeshHeading><DescriptorName MajorTopicYN="N">Beta</DescriptorName></MeshHeading>'
        "</MeshHeadingList></PubmedArticle>"
    )
    assert _parse_mesh(xml) == {"1": ["Alpha", "Beta"]}


def test_parse_mesh_without_meshlist_or_pmid_is_empty():
    from app.backend.discovery.pubmed_provider import _parse_mesh

    assert _parse_mesh("<PubmedArticle><PMID>999</PMID></PubmedArticle>") == {}  # no MeshHeadingList
    no_pmid = (
        "<PubmedArticle><MeshHeadingList>"
        "<MeshHeading><DescriptorName>X</DescriptorName></MeshHeading>"
        "</MeshHeadingList></PubmedArticle>"
    )
    assert _parse_mesh(no_pmid) == {}  # no PMID
    assert _parse_mesh("not xml at all") == {}


def test_fetch_mesh_terms_no_call_when_no_valid_pmids(monkeypatch):
    from app.backend.discovery import pubmed_provider as pp

    def _boom(*a, **k):
        raise AssertionError("must not fetch when there are no valid PMIDs")

    monkeypatch.setattr(pp.httpx, "get", _boom)
    assert pp.fetch_mesh_terms(["abc", ""], email=None, timeout=1.0) == {}


def test_fetch_mesh_terms_non_200_is_fail_closed(monkeypatch):
    from app.backend.discovery import pubmed_provider as pp

    class _Resp:
        status_code = 500
        text = ""

    monkeypatch.setattr(pp.httpx, "get", lambda *a, **k: _Resp())
    assert pp.fetch_mesh_terms(["12345"], email=None, timeout=1.0) == {}


def test_fetch_mesh_terms_parses_200_response(monkeypatch):
    from app.backend.discovery import pubmed_provider as pp

    class _Resp:
        status_code = 200
        text = _MESH_XML

    monkeypatch.setattr(pp.httpx, "get", lambda *a, **k: _Resp())
    assert pp.fetch_mesh_terms(["12345"], email="x@example.org", timeout=1.0) == {"12345": ["Face", "Emotions"]}
