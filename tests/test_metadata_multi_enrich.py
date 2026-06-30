"""inc 217 (SP1) — multi-pass, gap-filling metadata enrichment.

Hermetic: the cascade runs against STUB sources / injected fake clients (no live network). Covers the gap-fill
contract (fill only empty fields, never overwrite), DOI recovery via title-search (strong match adopts, weak/
year-mismatch/duplicate rejects), provenance preservation on hand-edited papers, the OpenAlex CSL mapper, and the
per-paper + library-wide endpoints.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.discovery.providers import Item
from app.backend.metadata.enrich_sources import EnrichmentRegistry
from app.backend.metadata.enrichment import enrich_paper_metadata_multi, gap_merge
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, get_paper
from integrations.crossref import CrossrefClient
from integrations.openalex.adapter import OpenAlexClient, _csl_from_work


class _StubSource:
    """An enrichment source that returns a fixed CSL fragment (no network)."""

    def __init__(self, name: str, fragment: dict | None) -> None:
        self.name = name
        self._fragment = fragment

    def fetch(self, conn, ref):
        return dict(self._fragment) if self._fragment else None


class _StubSearch:
    """A DOI-recovery search provider returning canned Items."""

    def __init__(self, items) -> None:
        self._items = list(items)

    def search(self, query, limit):
        return self._items


def _reg(*sources) -> EnrichmentRegistry:
    registry = EnrichmentRegistry()
    for source in sources:
        registry.register(source)
    return registry


def _paper(conn, *, title="Untitled", csl_json=None, **kw) -> int:
    return create_paper(conn, title=title, csl_json=csl_json if csl_json is not None else {"title": title}, **kw)


# ---- gap_merge (pure) ------------------------------------------------------


def test_gap_merge_fills_only_empty_keys():
    merged = gap_merge(
        {"title": "Kept", "abstract": "", "author": []},
        [{"title": "X", "abstract": "A", "type": "article-journal", "author": [{"literal": "Q"}]}],
    )
    assert merged["title"] == "Kept"  # populated → unchanged
    assert merged["abstract"] == "A"  # empty string → filled
    assert merged["type"] == "article-journal"  # absent → filled
    assert merged["author"] == [{"literal": "Q"}]  # empty list → filled
    # DOI is handled by the caller (the UNIQUE column + dedup guard), never merged here:
    assert gap_merge({}, [{"DOI": "10.1/x"}]) == {}


# ---- the orchestrator: gap-fill, cascade, provenance -----------------------


def test_cascade_fills_abstract_from_a_later_source(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(
            conn,
            title="Paper",
            doi="10.1/a",
            csl_json={"title": "Paper", "DOI": "10.1/a"},
            imported_source="pdf-scaffold",
        )
        registry = _reg(
            _StubSource("first", {"title": "Paper", "container-title": "Jrnl"}),  # no abstract
            _StubSource("second", {"abstract": "From the second source", "type": "article-journal"}),
        )
        result = enrich_paper_metadata_multi(conn, pid, registry=registry, search_provider=_StubSearch([]))
        paper = get_paper(conn, pid)
    engine.dispose()
    assert paper["abstract"] == "From the second source"  # filled by the 2nd source
    assert paper["venue"] == "Jrnl"
    assert paper["item_type"] == "article-journal"
    assert "abstract" in result.filled_fields and "venue" in result.filled_fields
    assert paper["imported_source"] == "crossref"  # a scaffold that got enriched


def test_gap_fill_never_overwrites_populated_fields(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(
            conn,
            title="Paper",
            abstract="Mine",
            venue="MyVenue",
            doi="10.1/a",
            csl_json={"title": "Paper", "abstract": "Mine", "container-title": "MyVenue", "DOI": "10.1/a"},
        )
        registry = _reg(_StubSource("s", {"abstract": "Other", "container-title": "OtherVenue"}))
        result = enrich_paper_metadata_multi(conn, pid, registry=registry, search_provider=_StubSearch([]))
        paper = get_paper(conn, pid)
    engine.dispose()
    assert paper["abstract"] == "Mine"  # unchanged
    assert paper["venue"] == "MyVenue"  # unchanged
    assert paper["csl_json"]["abstract"] == "Mine"
    assert "abstract" not in result.filled_fields and "venue" not in result.filled_fields


def test_doi_recovery_strong_match_adopts_weak_and_mismatch_reject(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        strong = _paper(conn, title="A Study of X", year=2020, imported_source="pdf-scaffold")
        r1 = enrich_paper_metadata_multi(
            conn,
            strong,
            registry=_reg(),
            search_provider=_StubSearch([Item(title="A study of X", doi="10.1/x", year=2020)]),
        )
        assert r1.doi == "10.1/x" and r1.doi_recovered and not r1.still_missing_doi
        assert get_paper(conn, strong)["doi"] == "10.1/x"

        weak = _paper(conn, title="A Study of X", year=2020, imported_source="pdf-scaffold")
        r2 = enrich_paper_metadata_multi(
            conn,
            weak,
            registry=_reg(),
            search_provider=_StubSearch([Item(title="Totally Unrelated Paper Title", doi="10.1/y", year=2020)]),
        )
        assert r2.doi is None and not r2.doi_recovered and r2.still_missing_doi
        assert get_paper(conn, weak)["doi"] is None

        yrmis = _paper(conn, title="A Study of X", year=2020, imported_source="pdf-scaffold")
        r3 = enrich_paper_metadata_multi(
            conn,
            yrmis,
            registry=_reg(),
            search_provider=_StubSearch([Item(title="A study of X", doi="10.1/z", year=1999)]),
        )
        assert r3.doi is None  # title matches but the year disagrees → not adopted
    engine.dispose()


def test_recovered_doi_colliding_with_another_paper_is_skipped(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, title="Owner", doi="10.1/x", csl_json={"title": "Owner", "DOI": "10.1/x"})
        mine = _paper(conn, title="A Study of X", year=2020, imported_source="pdf-scaffold")
        r = enrich_paper_metadata_multi(
            conn,
            mine,
            registry=_reg(),
            search_provider=_StubSearch([Item(title="A study of X", doi="10.1/x", year=2020)]),
        )
        assert r.doi is None and r.still_missing_doi  # belongs to another paper → left for dedup
        assert get_paper(conn, mine)["doi"] is None
    engine.dispose()


def test_user_edited_provenance_preserved_blanks_filled(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(
            conn,
            title="Hand",
            venue="Typed Venue",
            doi="10.1/a",
            csl_json={"title": "Hand", "container-title": "Typed Venue", "DOI": "10.1/a"},
            imported_source="user-edited",
        )
        registry = _reg(_StubSource("s", {"abstract": "Filled abstract", "container-title": "Other"}))
        enrich_paper_metadata_multi(conn, pid, registry=registry, search_provider=_StubSearch([]))
        paper = get_paper(conn, pid)
    engine.dispose()
    assert paper["abstract"] == "Filled abstract"  # blank filled
    assert paper["venue"] == "Typed Venue"  # typed value untouched
    assert paper["imported_source"] == "user-edited"  # provenance NOT downgraded


def test_scaffold_no_doi_no_recovery_marks_unresolved(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, title="Orphan", imported_source="pdf-scaffold")
        result = enrich_paper_metadata_multi(conn, pid, registry=_reg(), search_provider=_StubSearch([]))
        paper = get_paper(conn, pid)
    engine.dispose()
    assert result.still_missing_doi and paper["imported_source"] == "crossref-unresolved"


# ---- the OpenAlex CSL mapper -----------------------------------------------


def test_csl_from_work_maps_venue_abstract_type_pmid():
    frag = _csl_from_work(
        {
            "display_name": "W",
            "publication_year": 2021,
            "type": "article",
            "primary_location": {"source": {"display_name": "Nature"}},
            "abstract_inverted_index": {"Hello": [0], "world": [1]},
            "authorships": [{"author": {"display_name": "Jane Roe"}}],
            "ids": {"doi": "https://doi.org/10.1/W", "pmid": "https://pubmed.ncbi.nlm.nih.gov/777"},
        }
    )
    assert frag["container-title"] == "Nature"
    assert frag["abstract"] == "Hello world"
    assert frag["type"] == "article-journal"
    assert frag["DOI"] == "10.1/w" and frag["PMID"] == "777"
    assert frag["author"] == [{"literal": "Jane Roe"}]
    assert _csl_from_work(None) is None


# ---- endpoints -------------------------------------------------------------


def _crossref_fetcher(message_by_doi):
    def fake(doi, *, headers, timeout):
        if doi in message_by_doi:
            return 200, {"message": message_by_doi[doi]}
        return 404, {"status": "error"}

    return fake


_OFFLINE_OPENALEX = OpenAlexClient(fetcher=lambda path, **kw: (404, {"error": "offline"}))


def _inject_offline(client):
    """Make every source hermetic: a canned Crossref + an OpenAlex that 404s + a no-op title search."""
    client.app.state.openalex_client = _OFFLINE_OPENALEX
    client.app.state.enrich_search_provider = _StubSearch([])


def test_fill_metadata_endpoint_gap_fills_one_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(
            conn,
            title="Scaffold",
            doi="10.1/a",
            csl_json={"title": "Scaffold", "DOI": "10.1/a"},
            imported_source="pdf-scaffold",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.crossref_client = CrossrefClient(
        fetcher=_crossref_fetcher(
            {
                "10.1/a": {
                    "DOI": "10.1/a",
                    "type": "journal-article",
                    "title": ["Resolved"],
                    "container-title": ["J"],
                    "issued": {"date-parts": [[2020]]},
                    "abstract": "An abstract.",
                }
            }
        )
    )
    _inject_offline(client)
    body = client.post(f"/papers/{pid}/fill-metadata").json()
    assert "abstract" in body["filled_fields"] and "venue" in body["filled_fields"]
    assert body["paper"]["venue"] == "J" and body["paper"]["abstract"] == "An abstract."
    assert body["still_missing_doi"] is False


def _drive_enrich(client):
    jid = client.post("/library/enrich/refresh").json()["job_id"]
    data = {}
    for _ in range(30):
        data = client.get(f"/library/enrich/refresh/{jid}").json()
        if data["status"] in ("done", "error"):
            return data
    return data


def test_enrich_library_batch_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, title="A", doi="10.1/a", csl_json={"title": "A", "DOI": "10.1/a"}, imported_source="pdf-scaffold")
        _paper(conn, title="B", imported_source="pdf-scaffold")  # no DOI, no recovery
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.crossref_client = CrossrefClient(
        fetcher=_crossref_fetcher(
            {
                "10.1/a": {
                    "DOI": "10.1/a",
                    "type": "journal-article",
                    "title": ["A"],
                    "container-title": ["J"],
                    "issued": {"date-parts": [[2020]]},
                    "abstract": "abs",
                }
            }
        )
    )
    _inject_offline(client)
    done = _drive_enrich(client)
    assert done["status"] == "done"
    assert done["summary"]["papers"] == 2
    assert done["summary"]["fields_filled"] >= 2  # A gained abstract + venue
    assert done["summary"]["still_missing_doi"] == 1  # B never got a DOI


def test_enrich_refresh_status_404_for_unknown_job(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/library/enrich/refresh/nope").status_code == 404
