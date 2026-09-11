"""Add-by-DOI (backlog #58): the canonical DOI normalizer, the shared add primitive, and the Library
endpoint. Hermetic — an injected fake Crossref client, no network."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.metadata.doi import normalize_doi
from app.backend.metadata.doi_add import add_paper_by_doi
from app.backend.persistence.database import make_engine


class _FakeCrossref:
    """create_app(crossref_client=...) seam — resolves a fixed CSL record (or refuses)."""

    def __init__(self, *, resolved: bool, csl: dict | None = None):
        self._resolved = resolved
        self._csl = csl or {}

    def resolve_doi(self, conn, doi):
        from integrations.crossref.adapter import CrossrefResolution

        return CrossrefResolution(doi=doi, resolved=self._resolved, csl_json=self._csl if self._resolved else None)


def test_normalize_doi_accepts_the_common_forms():
    assert normalize_doi("10.1037/A0033242") == "10.1037/a0033242"
    assert normalize_doi("doi:10.1037/a0033242") == "10.1037/a0033242"
    assert normalize_doi("https://doi.org/10.1037/a0033242") == "10.1037/a0033242"
    assert normalize_doi("http://dx.doi.org/10.1/x") == "10.1/x"
    assert normalize_doi("  10.1/x/  ") == "10.1/x"


def test_normalize_doi_rejects_non_dois():
    for bad in ("", None, "   ", "not-a-doi", "https://example.com/foo", "10-no-slash"):
        assert normalize_doi(bad) is None


# --- the shared add primitive ---------------------------------------------------------------------------


def test_add_paper_by_doi_creates_from_resolved_metadata(temp_db_url: str):
    engine = make_engine(temp_db_url)
    csl = {"title": "A Real Paper", "type": "article-journal", "issued": {"date-parts": [[2020]]}}
    with engine.begin() as conn:
        result = add_paper_by_doi(
            conn,
            "https://doi.org/10.1/real",
            crossref_client=_FakeCrossref(resolved=True, csl=csl),
            imported_source="doi-import",
        )
    assert result.status == "created" and result.paper_id is not None
    assert result.doi == "10.1/real" and result.title == "A Real Paper"


def test_add_paper_by_doi_surfaces_existing_not_duplicate(temp_db_url: str):
    engine = make_engine(temp_db_url)
    csl = {"title": "Dup Paper", "type": "article-journal"}
    with engine.begin() as conn:
        first = add_paper_by_doi(
            conn, "10.5/dup", crossref_client=_FakeCrossref(resolved=True, csl=csl), imported_source="doi-import"
        )
    with engine.begin() as conn:
        again = add_paper_by_doi(
            conn, "DOI:10.5/DUP", crossref_client=_FakeCrossref(resolved=True, csl=csl), imported_source="doi-import"
        )
    assert first.status == "created"
    assert again.status == "existing" and again.paper_id == first.paper_id  # same record, no duplicate


def test_add_paper_by_doi_unresolvable_creates_nothing(temp_db_url: str):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = add_paper_by_doi(
            conn, "10.999/nope", crossref_client=_FakeCrossref(resolved=False), imported_source="doi-import"
        )
    assert result.status == "unresolved" and result.paper_id is None


def test_add_paper_by_doi_invalid_input(temp_db_url: str):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = add_paper_by_doi(
            conn,
            "not-a-doi",
            crossref_client=_FakeCrossref(resolved=True, csl={"title": "x"}),
            imported_source="doi-import",
        )
    assert result.status == "invalid" and result.paper_id is None


# --- the Library endpoint --------------------------------------------------------------------------------


def test_endpoint_creates_and_starts_a_distinct_oa_job(temp_db_url: str):
    csl = {"title": "Endpoint Paper", "type": "article-journal"}
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=True, csl=csl)))
    r = client.post("/papers/by-doi", json={"doi": "https://doi.org/10.1/endpoint", "acquire_oa": True})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "created" and body["paper_id"] is not None and body["doi"] == "10.1/endpoint"
    # OA acquisition is a SEPARATE job (distinct from the metadata import) the UI polls on its own.
    assert body["acquire_job_id"] is not None
    assert client.get(f"/papers/acquire-oa/{body['acquire_job_id']}").status_code == 200


def test_endpoint_no_oa_job_when_not_requested(temp_db_url: str):
    csl = {"title": "No OA", "type": "article-journal"}
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=True, csl=csl)))
    body = client.post("/papers/by-doi", json={"doi": "10.1/nooa", "acquire_oa": False}).json()
    assert body["status"] == "created" and body["acquire_job_id"] is None


def test_endpoint_existing_is_surfaced_without_oa_job(temp_db_url: str):
    csl = {"title": "Existing", "type": "article-journal"}
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=True, csl=csl)))
    first = client.post("/papers/by-doi", json={"doi": "10.1/exists", "acquire_oa": False}).json()
    again = client.post("/papers/by-doi", json={"doi": "10.1/exists", "acquire_oa": True}).json()
    assert again["status"] == "existing" and again["paper_id"] == first["paper_id"]
    assert again["acquire_job_id"] is None  # an already-present paper is surfaced, not re-acquired


@pytest.mark.parametrize("bad", ["not-a-doi", "https://example.com/x"])
def test_endpoint_invalid_doi_is_422_and_creates_nothing(temp_db_url: str, bad: str):
    client = TestClient(
        create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=True, csl={"title": "x"}))
    )
    assert client.post("/papers/by-doi", json={"doi": bad}).status_code == 422


def test_endpoint_unresolvable_doi_is_422(temp_db_url: str):
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=False)))
    assert client.post("/papers/by-doi", json={"doi": "10.999/nope"}).status_code == 422
