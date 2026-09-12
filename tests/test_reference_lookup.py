"""Reader "Find referenced paper…" resolver + endpoint (hermetic — the release gate).

All Crossref access is injected (a fake DOI client + a fake bibliographic search), so these run with no
network. One real-Crossref smoke lives at the bottom, marked skip-by-default (developer/manual, non-gating).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.backend.api import create_app
from app.backend.discovery.providers import Item
from app.backend.metadata import reference_resolver as rr
from app.backend.metadata.reference_resolver import normalize_reference_text, resolve_reference
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper

# --- fakes ------------------------------------------------------------------------------------------------


class _FakeResolution:
    def __init__(self, resolved: bool, csl_json: dict | None = None) -> None:
        self.resolved = resolved
        self.csl_json = csl_json


class _FakeCrossref:
    """Stands in for CrossrefClient.resolve_doi (DOI path). Records the DOI it was asked to resolve."""

    def __init__(self, csl: dict | None, *, resolved: bool = True) -> None:
        self._csl = csl
        self._resolved = resolved
        self.asked: list[str] = []

    def resolve_doi(self, conn, doi):  # noqa: ANN001 — test double
        self.asked.append(doi)
        return _FakeResolution(self._resolved, self._csl)


_CSL = {
    "title": "Predictive Coding in the Human Brain",
    "DOI": "10.1234/abc",
    "container-title": "Nature Neuroscience",
    "issued": {"date-parts": [[2019]]},
    "author": [{"family": "Smith", "given": "Jane"}, {"family": "Doe", "given": "John"}],
}


def _bib(items):
    """A fake bib_search(text) -> list[Item] that ignores the query and returns fixed items."""
    return lambda _q: list(items)


def _conn(temp_db_url: str):
    return make_engine(temp_db_url).begin()


# --- normalization (pure, amendment 4) --------------------------------------------------------------------


def test_normalize_collapses_whitespace_newlines_and_trailing_punctuation():
    raw = "  Smith,  J.,\n  &  Doe,  J.\r\n (2019).  Predictive coding.  Nature.  "
    assert normalize_reference_text(raw) == "Smith, J., & Doe, J. (2019). Predictive coding. Nature"


def test_normalize_applies_nfkc_and_a_hard_size_bound():
    assert normalize_reference_text("ﬁle") == "file"  # NFKC ligature fold
    assert normalize_reference_text(None) == "" and normalize_reference_text("   ") == ""
    assert len(normalize_reference_text("x " * 5000)) <= rr.MAX_REFERENCE_LEN


# --- DOI path (identifier_match) --------------------------------------------------------------------------


def test_doi_in_selection_is_an_identifier_match(temp_db_url):
    crossref = _FakeCrossref(_CSL)
    with _conn(temp_db_url) as conn:
        res = resolve_reference(
            conn,
            "As shown by Smith et al. (2019), https://doi.org/10.1234/abc, this holds.",
            crossref_client=crossref,
            bib_search=_bib([]),  # must NOT be consulted on a clean DOI hit
        )
    assert crossref.asked == ["10.1234/abc"]
    assert res.classification == "identifier_match"
    assert len(res.candidates) == 1
    c = res.candidates[0]
    assert c.doi == "10.1234/abc" and c.year == 2019 and c.venue == "Nature Neuroscience"
    assert c.authors[0].startswith("Smith") and c.url == "https://doi.org/10.1234/abc"


def test_unresolvable_doi_falls_through_to_bibliographic(temp_db_url):
    crossref = _FakeCrossref(None, resolved=False)
    hit = Item("Predictive Coding in the Human Brain", doi="10.1234/abc", authors=("Smith, Jane",), year=2019)
    with _conn(temp_db_url) as conn:
        res = resolve_reference(
            conn,
            "Smith 2019 predictive coding brain https://doi.org/10.1234/abc",
            crossref_client=crossref,
            bib_search=_bib([hit]),
        )
    assert res.classification == "one_candidate" and res.candidates[0].doi == "10.1234/abc"


# --- bibliographic path (one / multiple / none) -----------------------------------------------------------


def test_full_bibliography_string_resolves_to_one_candidate(temp_db_url):
    hit = Item(
        "Predictive Coding in the Human Brain",
        doi="10.1234/abc",
        authors=("Smith, Jane",),
        year=2019,
        journal="Nature Neuroscience",
    )
    with _conn(temp_db_url) as conn:
        res = resolve_reference(
            conn,
            "Smith, J. (2019). Predictive coding in the human brain. Nature Neuroscience, 22(4), 1-10.",
            crossref_client=None,
            bib_search=_bib([hit]),
        )
    assert res.classification == "one_candidate"
    assert res.candidates[0].title == "Predictive Coding in the Human Brain"


def test_author_year_selection_resolves_via_author_and_year_agreement(temp_db_url):
    # Selection carries no title tokens — only author+year agreement can carry it (and must).
    good = Item("A Totally Different Title", doi="10.1/good", authors=("Smith, Jane",), year=2019)
    with _conn(temp_db_url) as conn:
        res = resolve_reference(conn, "Smith et al. (2019)", crossref_client=None, bib_search=_bib([good]))
    assert res.classification == "one_candidate" and res.candidates[0].doi == "10.1/good"


def test_ambiguous_reference_returns_multiple_and_never_auto_picks(temp_db_url):
    a = Item("Predictive coding accounts of perception", doi="10.1/a", authors=("Smith, Jane",), year=2019)
    b = Item("Predictive coding and the brain", doi="10.1/b", authors=("Smith, John",), year=2019)
    with _conn(temp_db_url) as conn:
        res = resolve_reference(conn, "Smith 2019 predictive coding", crossref_client=None, bib_search=_bib([a, b]))
    assert res.classification == "multiple_candidates"
    assert {c.doi for c in res.candidates} == {"10.1/a", "10.1/b"}  # both surfaced, none chosen


def test_unresolvable_reference_returns_none(temp_db_url):
    with _conn(temp_db_url) as conn:
        res = resolve_reference(conn, "Some obscure reference", crossref_client=None, bib_search=_bib([]))
    assert res.classification == "none" and res.candidates == [] and res.error is None


def test_ordinary_prose_is_gated_out_to_none(temp_db_url):
    # Crossref will return SOMETHING for any query; the agreement gate must suppress unrelated hits.
    unrelated = Item("Quantum chromodynamics on the lattice", doi="10.1/qcd", authors=("Zhao, Li",), year=1998)
    with _conn(temp_db_url) as conn:
        res = resolve_reference(
            conn,
            "In this section we describe how participants completed the questionnaire.",
            crossref_client=None,
            bib_search=_bib([unrelated]),
        )
    assert res.classification == "none"


# --- dedup / in_library -----------------------------------------------------------------------------------


def test_already_in_library_is_marked_with_existing_id(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Owned", csl_json={"title": "Owned", "DOI": "10.1234/abc"}, doi="10.1234/abc")
    with engine.begin() as conn:
        res = resolve_reference(
            conn, "see https://doi.org/10.1234/abc", crossref_client=_FakeCrossref(_CSL), bib_search=_bib([])
        )
    engine.dispose()
    assert res.classification == "identifier_match"
    assert res.candidates[0].in_library is True and res.candidates[0].existing_paper_id == pid


# --- failure handling (amendment 10): human-readable error, zero mutation ---------------------------------


def test_crossref_failure_returns_error_and_creates_nothing(temp_db_url):
    def _boom(_q):
        raise RuntimeError("connection reset")

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        before = conn.execute(text("select count(*) from papers")).scalar()
    with engine.begin() as conn:
        res = resolve_reference(conn, "Smith 2019 predictive coding", crossref_client=None, bib_search=_boom)
    with engine.begin() as conn:
        after = conn.execute(text("select count(*) from papers")).scalar()
    engine.dispose()
    assert res.classification == "none" and res.error is not None
    assert "Crossref" in res.error and after == before  # zero mutation


def test_resolution_snapshots_the_text_it_was_given(temp_db_url):
    # The resolver is a pure function of the passed text — a later selection change cannot affect an
    # in-flight call. (The modal additionally snapshots the text at click time; see 30h_reference_finder.jsx.)
    captured: list[str] = []

    def _capture(q):
        captured.append(q)
        return []

    with _conn(temp_db_url) as conn:
        resolve_reference(conn, "  Smith,\n 2019 \n", crossref_client=None, bib_search=_capture)
    assert captured == ["Smith, 2019"]  # normalized snapshot, not the raw live selection


# --- endpoint ---------------------------------------------------------------------------------------------


def test_endpoint_resolves_a_doi_selection(temp_db_url):
    app = create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(_CSL))
    with TestClient(app) as client:
        r = client.post("/references/resolve", json={"text": "ref: https://doi.org/10.1234/abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["classification"] == "identifier_match"
    assert body["candidates"][0]["doi"] == "10.1234/abc"
    assert "abstract" not in body["candidates"][0]  # minimal candidate contract (amendment 5)


def test_endpoint_bibliographic_path_via_monkeypatch(temp_db_url, monkeypatch):
    hit = Item("Predictive Coding in the Human Brain", doi="10.9/x", authors=("Smith, Jane",), year=2019)
    monkeypatch.setattr(rr, "bibliographic_search", lambda q, limit=5: [hit])
    app = create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(None, resolved=False))
    with TestClient(app) as client:
        r = client.post(
            "/references/resolve",
            json={"text": "Smith, J. (2019). Predictive coding in the human brain. Nature Neuroscience."},
        )
    assert r.status_code == 200 and r.json()["classification"] == "one_candidate"


def test_endpoint_rejects_empty_and_oversized_input(temp_db_url):
    app = create_app(db_url=temp_db_url)
    with TestClient(app) as client:
        assert client.post("/references/resolve", json={"text": ""}).status_code == 422
        assert client.post("/references/resolve", json={"text": "x" * (rr.MAX_REFERENCE_LEN + 1)}).status_code == 422


# --- developer/manual smoke (non-gating) ------------------------------------------------------------------


@pytest.mark.skip(reason="developer/manual: hits the real Crossref API; hermetic tests are the release gate")
def test_real_crossref_bibliographic_smoke():  # pragma: no cover
    from app.backend.discovery.crossref_provider import bibliographic_search

    items = bibliographic_search(
        "Friston, K. (2010). The free-energy principle: a unified brain theory? Nature Reviews Neuroscience.",
        limit=3,
    )
    assert any("free-energy" in (it.title or "").lower() or "free energy" in (it.title or "").lower() for it in items)
