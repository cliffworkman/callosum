"""Tests for citation-file import (inc 93) — hermetic (hand-rolled parsers; injected fake embedding model; no
network). The inverse of inc-70 export."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.metadata.citation_import import (
    csl_record_to_paper_fields,
    detect_format,
    import_citations,
    parse_bibtex,
    parse_csl_json,
    parse_ris,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper

_BIBTEX = """
@article{doe2020,
  author = {Doe, Jane and Smith, John},
  title = {{A Grand Study}},
  journal = {Journal of Things},
  year = {2020},
  volume = {12},
  number = {3},
  pages = {100--120},
  doi = {10.1/abc},
}

@book{org2019,
  author = {{World Health Organization}},
  title = {Big Report},
  year = {2019},
}

@comment{ this should be ignored }
@article{junk2021}
"""

_RIS = """TY  - JOUR
AU  - Doe, Jane
AU  - Smith, John
TI  - A Grand Study
PY  - 2020
T2  - Journal of Things
VL  - 12
IS  - 3
SP  - 100
EP  - 120
DO  - 10.1/abc
ER  -

TY  - BOOK
TI  - Big Report
PY  - 2019
ER  -
"""

_CSL_JSON = """[
  {"type": "article-journal", "title": "A Grand Study", "DOI": "10.1/abc",
   "author": [{"family": "Doe", "given": "Jane"}], "issued": {"date-parts": [[2020]]}},
  {"title": "No Type But Has Title"}
]"""


def test_parse_bibtex():
    recs, skipped = parse_bibtex(_BIBTEX)
    assert len(recs) == 2  # @comment ignored; the title-less @article{junk2021} dropped
    assert skipped == 1  # the dropped @article{junk2021} is now reported (inc 173), not silent
    first = recs[0]
    assert first["type"] == "article-journal"
    assert first["title"] == "A Grand Study"  # case-protection braces stripped
    assert first["author"] == [{"family": "Doe", "given": "Jane"}, {"family": "Smith", "given": "John"}]
    assert first["container-title"] == "Journal of Things"
    assert first["issued"] == {"date-parts": [[2020]]}
    assert first["volume"] == "12" and first["issue"] == "3" and first["page"] == "100-120"
    assert first["DOI"] == "10.1/abc" and first["id"] == "doe2020"
    assert recs[1]["type"] == "book"
    assert recs[1]["author"] == [{"literal": "World Health Organization"}]  # braced group → organisation literal


def test_parse_ris():
    recs, skipped = parse_ris(_RIS)
    assert len(recs) == 2 and skipped == 0
    first = recs[0]
    assert first["type"] == "article-journal"
    assert [a["family"] for a in first["author"]] == ["Doe", "Smith"]
    assert first["issued"] == {"date-parts": [[2020]]} and first["page"] == "100-120"
    assert first["DOI"] == "10.1/abc"
    assert recs[1]["type"] == "book" and recs[1]["title"] == "Big Report"


def test_parse_csl_json():
    recs, skipped = parse_csl_json(_CSL_JSON)
    assert len(recs) == 2 and skipped == 0  # both have a title (or DOI)
    assert recs[0]["DOI"] == "10.1/abc"
    # a malformed array (a non-dict + a dict with neither title nor DOI) is reported, not silently dropped
    kept, dropped = parse_csl_json('[{"author":[]}, 42, {"title":"Keep me"}]')
    assert len(kept) == 1 and dropped == 2


def test_detect_format():
    assert detect_format(_BIBTEX) == "bibtex"
    assert detect_format(_RIS) == "ris"
    assert detect_format(_CSL_JSON) == "csl-json"
    assert detect_format("just some prose, no structure") is None
    assert detect_format("") is None


def test_csl_record_to_paper_fields():
    recs, _ = parse_bibtex(_BIBTEX)
    fields = csl_record_to_paper_fields(recs[0])
    assert fields["title"] == "A Grand Study"
    assert fields["year"] == 2020
    assert fields["doi"] == "10.1/abc"
    assert fields["venue"] == "Journal of Things"
    assert fields["item_type"] == "article-journal"  # CSL type → the inc-91 Type facet labels it "Journal article"
    assert fields["first_author_family_name"] == "Doe"
    assert fields["citation_key"] == "doe2020"


def test_import_citations_creates_dedups_and_isolates(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = import_citations(conn, _BIBTEX, "bibtex")
    assert len(result["created"]) == 2 and result["duplicate"] == 0 and result["failed"] == 0
    assert result["skipped"] == 1  # the title-less @article{junk2021} reported at parse, not silently dropped
    assert result["format"] == "bibtex"
    # re-importing the same file → both dedup (DOI for the article; title+year+author for the book)
    with engine.begin() as conn:
        again = import_citations(conn, _BIBTEX, "bibtex")
    assert again["created"] == [] and again["duplicate"] == 2
    # the created papers carry the CSL item type (verified via the inc-91 Type facet)
    client = TestClient(create_app(db_url=temp_db_url))
    assert len(client.get("/papers").json()) == 2
    assert len(client.get("/papers", params={"item_type": "article-journal"}).json()) == 1
    assert len(client.get("/papers", params={"item_type": "book"}).json()) == 1


def test_import_roundtrips_exported_csl_json(temp_db_url):
    # export → import is lossless + deduped: a callosum CSL-JSON export re-imports as duplicates, not copies.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(
            conn,
            title="Roundtrip",
            doi="10.9/rt",
            item_type="article-journal",
            csl_json={"type": "article-journal", "title": "Roundtrip", "DOI": "10.9/rt"},
        )
    client = TestClient(create_app(db_url=temp_db_url))
    exported = client.post("/papers/export", json={"paper_ids": [1], "format": "csl-json"}).text
    with engine.begin() as conn:
        result = import_citations(conn, exported, "csl-json")
    assert result["created"] == [] and result["duplicate"] == 1  # same DOI → deduped, no copy


def test_import_endpoint_processes_file(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel()))
    started = client.post("/library/import", json={"content": _RIS, "format": "auto"})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/library/import/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result
    assert result["summary"]["imported"] == 2 and result["summary"]["format"] == "ris"
    # the imported papers are in the library and filterable by the inc-91 Type facet
    assert len(client.get("/papers").json()) == 2
    assert len(client.get("/papers", params={"item_type": "article-journal"}).json()) == 1


def test_import_endpoint_unrecognized_content(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel()))
    started = client.post("/library/import", json={"content": "not a citation file at all"})
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/library/import/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done"
    assert result["summary"]["imported"] == 0 and result["summary"]["format"] is None  # nothing created, reported


class _FakeModel:
    name = "fake-import"
    version = "v1"
    dimension = 4
    normalization = "none"

    def encode_texts(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]
