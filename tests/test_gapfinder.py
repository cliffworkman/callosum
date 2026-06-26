"""inc 135 — literature gap-finder: OpenAlex referenced-works / work-meta + compute_gaps."""

from __future__ import annotations

from app.backend.acquisition.registry import PaperRef
from app.backend.clustering.gapfinder import GapCandidate, compute_gaps
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from integrations.openalex.adapter import OpenAlexClient


def _paper(conn, doi) -> int:
    return create_paper(conn, title=doi, csl_json={"title": doi, "DOI": doi}, doi=doi)


# ---- adapter: fetch_referenced_works + fetch_work_meta (fake fetcher) -------


def test_fetch_referenced_works(temp_db_url):
    def fake(path, *, params, headers, timeout):
        return 200, {
            "id": "https://openalex.org/W9",
            "referenced_works": ["https://openalex.org/W1", "https://openalex.org/W2", "junk"],
        }

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids = OpenAlexClient(fetcher=fake).fetch_referenced_works(conn, PaperRef(doi="10.1/x"))
    engine.dispose()
    assert ids == ["W1", "W2"]  # bare ids; the non-W junk is dropped


def test_fetch_referenced_works_no_field(temp_db_url):
    def fake(path, *, params, headers, timeout):
        return 200, {"id": "https://openalex.org/W9"}  # no referenced_works

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids = OpenAlexClient(fetcher=fake).fetch_referenced_works(conn, PaperRef(doi="10.1/y"))
    engine.dispose()
    assert ids == []


def test_fetch_work_meta(temp_db_url):
    def fake(path, *, params, headers, timeout):
        assert path == "/W1"
        return 200, {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.5/Imp",
            "title": "Important Work",
            "publication_year": 2010,
            "cited_by_count": 999,
            "authorships": [{"author": {"display_name": "A. Researcher"}}],
        }

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        meta = OpenAlexClient(fetcher=fake).fetch_work_meta(conn, "W1")
        bad = OpenAlexClient(fetcher=fake).fetch_work_meta(conn, "not-an-id")
    engine.dispose()
    assert meta["openalex_work_id"] == "W1" and meta["doi"] == "10.5/imp"  # normalized lower, prefix stripped
    assert meta["title"] == "Important Work" and meta["authors"] == ["A. Researcher"] and meta["year"] == 2010
    assert bad is None  # an invalid id is rejected without a fetch


# ---- compute_gaps (injected fake client, no network) -----------------------


class _FakeOA:
    def __init__(self, refs_by_doi, meta_by_id):
        self.refs_by_doi = refs_by_doi
        self.meta_by_id = meta_by_id

    def fetch_referenced_works(self, conn, ref):
        return self.refs_by_doi.get(ref.doi, [])

    def fetch_work_meta(self, conn, work_id):
        return self.meta_by_id.get(work_id)


def _meta(wid, doi, title="T", year=2010):
    return {"openalex_work_id": wid, "doi": doi, "title": title, "authors": ["A"], "year": year, "cited_by_count": 5}


def test_compute_gaps_surfaces_works_cited_by_many(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        p1 = _paper(conn, "10.1/p1")
        p2 = _paper(conn, "10.1/p2")
        _paper(conn, "10.1/p3")
        oa = _FakeOA(
            refs_by_doi={"10.1/p1": ["W1", "W2", "W1"], "10.1/p2": ["W1"], "10.1/p3": ["W3"]},  # W1 cited by p1,p2
            meta_by_id={
                "W1": _meta("W1", "10.9/w1", "Cited Often"),
                "W2": _meta("W2", "10.9/w2"),
                "W3": _meta("W3", "10.9/w3"),
            },
        )
        candidates, coverage = compute_gaps(conn, openalex_client=oa, dismissed=set(), min_citations=2)
    engine.dispose()
    del p1, p2
    assert [c.openalex_work_id for c in candidates] == ["W1"]  # only W1 is cited by >=2 papers
    assert candidates[0].cited_by_in_library == 2 and candidates[0].title == "Cited Often"
    assert isinstance(candidates[0], GapCandidate)
    assert coverage["checked"] == 3 and coverage["total"] == 3 and "coverage" in coverage["note"].lower()


def test_compute_gaps_excludes_in_library_and_dismissed(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, "10.1/p1")
        _paper(conn, "10.1/p2")
        _paper(conn, "10.9/w1")  # we ALREADY have W1's DOI → not a gap
        oa = _FakeOA(
            refs_by_doi={"10.1/p1": ["W1", "W2"], "10.1/p2": ["W1", "W2"]},  # W1, W2 both cited by 2
            meta_by_id={"W1": _meta("W1", "10.9/w1"), "W2": _meta("W2", "10.9/w2")},
        )
        all_cands, _ = compute_gaps(conn, openalex_client=oa, dismissed=set(), min_citations=2)
        dismissed_cands, _ = compute_gaps(conn, openalex_client=oa, dismissed={"W2"}, min_citations=2)
    engine.dispose()
    assert [c.openalex_work_id for c in all_cands] == ["W2"]  # W1 excluded (already in library)
    assert dismissed_cands == []  # W2 dismissed, W1 in library → nothing left
