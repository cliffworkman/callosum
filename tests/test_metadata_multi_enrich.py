"""inc 217 (SP1) — multi-pass, gap-filling metadata enrichment.

Hermetic: the cascade runs against STUB sources / injected fake clients (no live network). Covers the gap-fill
contract (fill only empty fields, never overwrite), DOI recovery via title-search (strong match adopts, weak/
year-mismatch rejects), provenance preservation on hand-edited papers, the OpenAlex CSL mapper, and the
per-paper + library-wide endpoints.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.backend.api import create_app
from app.backend.api.routers.library_enrich import _enrich_progress_label
from app.backend.discovery.providers import Item
from app.backend.metadata.enrich_sources import (
    EnrichmentRegistry,
    EnrichRef,
    PubMedEnrichSource,
    build_default_enrich_registry,
)
from app.backend.metadata.enrichment import enrich_paper_metadata_multi, gap_merge
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, get_paper
from integrations.europepmc.adapter import EuropePmcClient
from integrations.openalex.adapter import _csl_from_work


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


def test_recovered_doi_already_on_another_paper_is_written_for_merge_workflow(temp_db_url):
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
        assert r.doi == "10.1/x" and r.doi_recovered and not r.still_missing_doi
        assert get_paper(conn, mine)["doi"] == "10.1/x"
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


# ---- SP2 sources: Europe PMC + PubMed --------------------------------------


def test_europepmc_lookup_metadata_maps_core_record(temp_db_url):
    engine = make_engine(temp_db_url)
    record = {
        "resultList": {
            "result": [
                {
                    "title": "EPMC title",
                    "authorList": {"author": [{"lastName": "Doe", "firstName": "Jane"}, {"fullName": "R. Roe"}]},
                    "journalInfo": {"journal": {"title": "EPMC Journal"}},
                    "pubYear": "2017",
                    "abstractText": "An EPMC abstract.",
                    "doi": "10.1/EPMC",
                    "pmid": "555",
                }
            ]
        }
    }
    with engine.begin() as conn:
        client = EuropePmcClient(fetcher=lambda q, **kw: (200, record))
        frag = client.lookup_metadata(conn, EnrichRef(doi="10.1/epmc").to_paper_ref())
    engine.dispose()
    assert frag["container-title"] == "EPMC Journal"
    assert frag["abstract"] == "An EPMC abstract."
    assert frag["author"] == [{"family": "Doe", "given": "Jane"}, {"literal": "R. Roe"}]
    assert frag["issued"] == {"date-parts": [[2017]]} and frag["PMID"] == "555" and frag["DOI"] == "10.1/epmc"


def test_pubmed_source_pmid_abstract_and_title_search(temp_db_url):
    engine = make_engine(temp_db_url)
    rec = {
        "uid": "999",
        "title": "A Study of X",
        "fulljournalname": "J Pub",
        "pubdate": "2016",
        "articleids": [{"idtype": "doi", "value": "10.1/pub"}],
    }
    src = PubMedEnrichSource(
        search=lambda q, n, **kw: [rec],
        abstract_fetcher=lambda pmids, **kw: {"999": "A PubMed abstract."},
    )
    with engine.begin() as conn:
        # PMID known → just the abstract
        assert src.fetch(conn, EnrichRef(pmid="999")) == {"abstract": "A PubMed abstract."}
        # title-search → matched record's metadata + abstract
        frag = src.fetch(conn, EnrichRef(title="A study of X"))
        assert frag["container-title"] == "J Pub" and frag["DOI"] == "10.1/pub"
        assert frag["PMID"] == "999" and frag["abstract"] == "A PubMed abstract."
        # title that doesn't match the returned record → nothing (no wrong-paper enrichment)
        miss = PubMedEnrichSource(search=lambda q, n, **kw: [rec], abstract_fetcher=lambda p, **k: {})
        assert miss.fetch(conn, EnrichRef(title="Totally Unrelated Title")) is None
    engine.dispose()


def test_default_registry_has_four_sources():
    assert [s.name for s in build_default_enrich_registry().sources] == ["crossref", "openalex", "europepmc", "pubmed"]


# ---- endpoints (hermetic via an injected stub registry — no live sources) --


def _stub_registry(fragment):
    return _reg(_StubSource("stub", fragment))


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
    client.app.state.enrich_registry = _stub_registry(
        {"title": "Resolved", "container-title": "J", "issued": {"date-parts": [[2020]]}, "abstract": "An abstract."}
    )
    client.app.state.enrich_search_provider = _StubSearch([])
    body = client.post(f"/papers/{pid}/fill-metadata").json()
    assert "abstract" in body["filled_fields"] and "venue" in body["filled_fields"]
    assert body["paper"]["venue"] == "J" and body["paper"]["abstract"] == "An abstract."
    assert body["still_missing_doi"] is False


def test_fill_metadata_endpoint_legacy_unique_doi_constraint_returns_409(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, title="Owner", doi="10.1/a", csl_json={"title": "Owner", "DOI": "10.1/a"})
        pid = _paper(conn, title="Scaffold", imported_source="pdf-scaffold")
        conn.execute(text("CREATE UNIQUE INDEX legacy_uq_papers_doi ON papers(doi)"))
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.enrich_registry = _stub_registry({"title": "Scaffold", "abstract": "A"})
    client.app.state.enrich_search_provider = _StubSearch([Item(title="Scaffold", doi="10.1/a", year=None)])

    response = client.post(f"/papers/{pid}/fill-metadata")

    assert response.status_code == 409
    assert "legacy unique DOI constraint" in response.json()["detail"]


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
    client.app.state.enrich_registry = _stub_registry(
        {"container-title": "J", "issued": {"date-parts": [[2020]]}, "abstract": "abs"}
    )
    client.app.state.enrich_search_provider = _StubSearch([])
    done = _drive_enrich(client)
    assert done["status"] == "done"
    assert done["summary"]["papers"] == 2
    assert done["summary"]["fields_filled"] >= 2  # A gained venue + abstract
    assert done["summary"]["still_missing_doi"] == 1  # B never got a DOI


def test_enrich_refresh_status_404_for_unknown_job(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/library/enrich/refresh/nope").status_code == 404


def test_enrich_progress_label_shows_title_and_falls_back():
    # #4: the enrich job's per-item progress label names the paper being enriched (like scan shows the filename).
    assert _enrich_progress_label("Anomalous faces and trust") == "Enriching Anomalous faces and trust"
    assert _enrich_progress_label(None) == "Enriching metadata"
    assert _enrich_progress_label("   ") == "Enriching metadata"
    long_label = _enrich_progress_label("T" * 100)
    assert long_label.startswith("Enriching ") and long_label.endswith("…")
    assert len(long_label) <= len("Enriching ") + 60


def test_enrich_commits_per_paper_partial_progress(temp_db_url, monkeypatch):
    """inc B: a failure enriching the 2nd paper leaves the 1st paper's enrichment committed and the job completes
    (per-paper commit + skip). Under the old single-transaction job, the 2nd's failure rolled back the 1st too and
    errored the whole run — so status 'done' + fields_filled>=2 can only hold with per-paper commits."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, title="A", doi="10.1/a", csl_json={"title": "A", "DOI": "10.1/a"}, imported_source="pdf-scaffold")
        _paper(conn, title="B", imported_source="pdf-scaffold")
    engine.dispose()

    from app.backend.api.routers import library_enrich as le

    real = le.enrich_paper_metadata_multi
    calls = {"n": 0}

    def flaky(conn, paper_id, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # papers processed id-ASC → the 2nd is paper B
            raise RuntimeError("boom enriching the 2nd paper")
        return real(conn, paper_id, **kwargs)

    monkeypatch.setattr(le, "enrich_paper_metadata_multi", flaky)
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.enrich_registry = _stub_registry(
        {"container-title": "J", "issued": {"date-parts": [[2020]]}, "abstract": "abs"}
    )
    client.app.state.enrich_search_provider = _StubSearch([])
    done = _drive_enrich(client)
    assert done["status"] == "done"  # per-paper skip → the run completes
    assert done["summary"]["fields_filled"] >= 2  # paper A enriched + committed before B failed


# ---- inc 306: imported keyword tags from the enrich sources -----------------


class _KeywordStubSource:
    """A source that advertises the inc-306 keyword capability (keyword_source + keywords) — no network."""

    def __init__(self, name: str, keyword_source: str, names: list[str]) -> None:
        self.name = name
        self.keyword_source = keyword_source
        self._names = list(names)

    def fetch(self, conn, ref):
        return None  # contributes no CSL, only keyword tags

    def keywords(self, conn, ref):
        return list(self._names)


def test_enrich_imports_source_keyword_tags(temp_db_url):
    from app.backend.persistence.tags_repo import get_tags_for_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(
            conn, title="P", doi="10.1/a", csl_json={"title": "P", "DOI": "10.1/a"}, imported_source="pdf-scaffold"
        )
        registry = _reg(
            _KeywordStubSource("openalex", "keyword:openalex", ["Facial Recognition", "Emotion Perception"]),
            _KeywordStubSource("pubmed", "keyword:pubmed", ["Face", "Emotions"]),
        )
        enrich_paper_metadata_multi(conn, pid, registry=registry, search_provider=_StubSearch([]))
        tags = {t["name"]: t["import_source"] for t in get_tags_for_paper(conn, pid)}
    assert tags["Facial Recognition"] == "keyword:openalex"
    assert tags["Emotion Perception"] == "keyword:openalex"
    assert tags["Face"] == "keyword:pubmed"
    assert tags["Emotions"] == "keyword:pubmed"


def test_enrich_keyword_tags_respect_suppression_and_are_idempotent(temp_db_url):
    from app.backend.persistence.tags_repo import get_tags_for_paper, remove_tag_from_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(
            conn, title="P", doi="10.1/a", csl_json={"title": "P", "DOI": "10.1/a"}, imported_source="pdf-scaffold"
        )
        registry = _reg(_KeywordStubSource("openalex", "keyword:openalex", ["Topic A", "Topic B"]))
        enrich_paper_metadata_multi(conn, pid, registry=registry, search_provider=_StubSearch([]))
        rows = {t["name"]: t["id"] for t in get_tags_for_paper(conn, pid)}
        remove_tag_from_paper(conn, pid, rows["Topic A"])  # deleting a keyword:* tag records an inc-143 suppression
        enrich_paper_metadata_multi(conn, pid, registry=registry, search_provider=_StubSearch([]))  # re-enrich
        names = [t["name"] for t in get_tags_for_paper(conn, pid)]
    assert "Topic A" not in names  # suppression held across re-enrich
    assert names.count("Topic B") == 1  # additive + idempotent (no duplicate)


def test_enrich_without_keyword_capable_source_adds_no_keyword_tags(temp_db_url):
    """The hermetic guarantee: a registry whose sources don't advertise `keyword_source` emits no keyword tags."""
    from app.backend.persistence.tags_repo import get_tags_for_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(
            conn, title="P", doi="10.1/a", csl_json={"title": "P", "DOI": "10.1/a"}, imported_source="pdf-scaffold"
        )
        enrich_paper_metadata_multi(
            conn, pid, registry=_reg(_StubSource("s", {"abstract": "x"})), search_provider=_StubSearch([])
        )
        keyword_tags = [
            t for t in get_tags_for_paper(conn, pid) if str(t["import_source"] or "").startswith("keyword:")
        ]
    assert keyword_tags == []


def test_import_registry_keyword_tags_applies_and_is_hermetic(temp_db_url):
    """inc 307: the extracted keyword importer applies a capable source's tags; an empty registry emits nothing."""
    from app.backend.metadata.enrichment import import_registry_keyword_tags
    from app.backend.persistence.tags_repo import get_tags_for_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, title="P", doi="10.1/a", csl_json={"title": "P", "DOI": "10.1/a"})
        ref = EnrichRef(doi="10.1/a", title="P")
        import_registry_keyword_tags(
            conn, pid, ref=ref, registry=_reg(_KeywordStubSource("oa", "keyword:openalex", ["Topic X"]))
        )
        import_registry_keyword_tags(conn, pid, ref=ref, registry=EnrichmentRegistry())  # empty → no-op, no network
        tags = {t["name"]: t["import_source"] for t in get_tags_for_paper(conn, pid)}
    assert tags == {"Topic X": "keyword:openalex"}
