"""inc 135 — literature gap-finder (backward); inc 137 — forward + axis-scoped + persistent cache."""

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


# ---- adapter: fetch_work_id + fetch_citing_works (inc 137 forward) ----------


def test_fetch_work_id(temp_db_url):
    def fake(path, *, params, headers, timeout):
        return 200, {"id": "https://openalex.org/W42", "doi": "https://doi.org/10.1/z"}

    def fake_empty(path, *, params, headers, timeout):
        return 200, {}  # no id

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        wid = OpenAlexClient(fetcher=fake).fetch_work_id(conn, PaperRef(doi="10.1/z"))
        none = OpenAlexClient(fetcher=fake_empty).fetch_work_id(conn, PaperRef(doi="10.1/none"))
    engine.dispose()
    assert wid == "W42"  # bare id, prefix stripped
    assert none is None


def test_fetch_citing_works(temp_db_url):
    def fake(path, *, params, headers, timeout):
        assert "cites:W42" in params["filter"]
        return 200, {
            "results": [
                {
                    "id": "https://openalex.org/W101",
                    "doi": "https://doi.org/10.9/C1",
                    "title": "Citer One",
                    "publication_year": 2020,
                    "authorships": [{"author": {"display_name": "B. Author"}}],
                },
                {"id": None, "title": "no id, dropped"},
            ]
        }

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        citing = OpenAlexClient(fetcher=fake).fetch_citing_works(conn, "W42")
        bad = OpenAlexClient(fetcher=fake).fetch_citing_works(conn, "not-an-id")
    engine.dispose()
    assert [c["openalex_work_id"] for c in citing] == ["W101"]  # the no-id work is dropped
    assert citing[0]["doi"] == "10.9/c1" and citing[0]["authors"] == ["B. Author"] and citing[0]["year"] == 2020
    assert bad == []  # an invalid id is rejected without a fetch


# ---- compute_gaps (injected fake client, no network) -----------------------


class _FakeOA:
    def __init__(self, refs_by_doi=None, meta_by_id=None, workid_by_doi=None, citing_by_workid=None):
        self.refs_by_doi = refs_by_doi or {}
        self.meta_by_id = meta_by_id or {}
        self.workid_by_doi = workid_by_doi or {}
        self.citing_by_workid = citing_by_workid or {}

    def fetch_referenced_works(self, conn, ref):
        return self.refs_by_doi.get(ref.doi, [])

    def fetch_work_meta(self, conn, work_id):
        return self.meta_by_id.get(work_id)

    def fetch_work_id(self, conn, ref):
        return self.workid_by_doi.get(ref.doi)

    def fetch_citing_works(self, conn, work_id):
        return self.citing_by_workid.get(work_id, [])


def _meta(wid, doi, title="T", year=2010):
    return {"openalex_work_id": wid, "doi": doi, "title": title, "authors": ["A"], "year": year, "cited_by_count": 5}


def test_compute_gaps_surfaces_works_cited_by_many(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, "10.1/p1")
        _paper(conn, "10.1/p2")
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


def test_compute_gaps_forward_surfaces_works_that_cite_many(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, "10.1/p1")
        _paper(conn, "10.1/p2")
        _paper(conn, "10.1/p3")
        oa = _FakeOA(
            workid_by_doi={"10.1/p1": "W101", "10.1/p2": "W102", "10.1/p3": "W103"},
            citing_by_workid={
                "W101": [_meta("WC1", "10.9/c1", "Cites Two")],  # WC1 cites p1
                "W102": [_meta("WC1", "10.9/c1", "Cites Two")],  # WC1 cites p2 → 2
                "W103": [_meta("WC2", "10.9/c2")],  # WC2 cites only p3
            },
        )
        candidates, coverage = compute_gaps(
            conn, openalex_client=oa, dismissed=set(), direction="forward", min_citations=2
        )
    engine.dispose()
    assert [c.openalex_work_id for c in candidates] == ["WC1"]  # only WC1 cites >=2 of our papers
    assert candidates[0].cited_by_in_library == 2 and candidates[0].title == "Cites Two"
    assert "cites" in coverage["note"].lower()  # direction-specific note


def test_compute_gaps_axis_scoped_restricts_to_members(temp_db_url):
    from app.backend.clustering.axis_assignments import add_manual_assignment
    from app.backend.clustering.axis_scoring import create_axis

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        p1 = _paper(conn, "10.1/p1")
        p2 = _paper(conn, "10.1/p2")
        _paper(conn, "10.1/p3")  # NOT in the axis
        axis_id = create_axis(conn, label="Topic")
        add_manual_assignment(conn, axis_id=axis_id, paper_id=p1)
        add_manual_assignment(conn, axis_id=axis_id, paper_id=p2)
        oa = _FakeOA(
            refs_by_doi={"10.1/p1": ["W1"], "10.1/p2": ["W1"], "10.1/p3": ["W1"]},  # all 3 cite W1
            meta_by_id={"W1": _meta("W1", "10.9/w1")},
        )
        scoped, cov = compute_gaps(conn, openalex_client=oa, dismissed=set(), axis_id=axis_id, min_citations=2)
        allcands, allcov = compute_gaps(conn, openalex_client=oa, dismissed=set(), min_citations=2)
    engine.dispose()
    assert scoped[0].cited_by_in_library == 2 and cov["checked"] == 2 and cov["total"] == 2  # only p1,p2 scanned
    assert allcands[0].cited_by_in_library == 3 and allcov["checked"] == 3  # whole library: p1,p2,p3


# ---- gap_repo persistent cache (inc 137) -----------------------------------

from app.backend.persistence.gap_repo import read_gap_candidates, replace_gap_candidates  # noqa: E402


def test_gap_repo_replace_and_read_isolated_by_scope(temp_db_url):
    c_back = [GapCandidate("W1", "10/a", "Back", ["A"], 2010, 5)]
    c_fwd = [GapCandidate("W2", "10/b", "Fwd", ["B"], 2011, 3)]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        replace_gap_candidates(conn, "backward", None, c_back, computed_at="2026-06-26T00:00:00Z")
        replace_gap_candidates(conn, "forward", None, c_fwd, computed_at="2026-06-26T01:00:00Z")
        back_rows, back_at = read_gap_candidates(conn, "backward", None)
        fwd_rows, _ = read_gap_candidates(conn, "forward", None)
        empty_rows, empty_at = read_gap_candidates(conn, "backward", 7)  # an axis scope never written
        replace_gap_candidates(conn, "backward", None, [], computed_at="2026-06-26T02:00:00Z")  # re-refresh = replace
        after_rows, after_at = read_gap_candidates(conn, "backward", None)
    engine.dispose()
    assert len(back_rows) == 1 and back_rows[0]["openalex_work_id"] == "W1" and back_at == "2026-06-26T00:00:00Z"
    assert len(fwd_rows) == 1 and fwd_rows[0]["openalex_work_id"] == "W2"  # forward untouched by backward refresh
    assert empty_rows == [] and empty_at is None
    assert after_rows == [] and after_at is None  # backward replaced with the empty set


# ---- endpoints (injected fake client) --------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.backend.api import create_app  # noqa: E402
from app.backend.persistence.profile_repo import dismiss_gap, dismissed_gaps  # noqa: E402


def test_dismiss_gap_round_trip_without_a_profile(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert dismissed_gaps(conn) == set()  # no profile yet
        dismiss_gap(conn, "W7")  # inserts a minimal profile row
        dismiss_gap(conn, "10.9/x")
        keys = dismissed_gaps(conn)
    engine.dispose()
    assert keys == {"W7", "10.9/x"}


def _drive_refresh(client, direction="backward", axis_id=None):
    body = {"direction": direction}
    if axis_id is not None:
        body["axis_id"] = axis_id
    jid = client.post("/gaps/refresh", json=body).json()["job_id"]
    data = {}
    for _ in range(30):
        data = client.get(f"/gaps/refresh/{jid}").json()
        if data["status"] in ("done", "error"):
            return data
    return data


def test_gap_refresh_then_get_filters_dismissed_and_in_library(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:  # 4 papers; W1 cited by all 4, W2 by 3 (router default min=3)
        for d in ("10.1/p1", "10.1/p2", "10.1/p3", "10.1/p4"):
            _paper(conn, d)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = _FakeOA(
        refs_by_doi={"10.1/p1": ["W1", "W2"], "10.1/p2": ["W1", "W2"], "10.1/p3": ["W1", "W2"], "10.1/p4": ["W1"]},
        meta_by_id={"W1": _meta("W1", "10.9/w1", "Most"), "W2": _meta("W2", "10.9/w2", "Two")},
    )

    g0 = client.get("/gaps", params={"direction": "backward"}).json()
    assert g0["candidates"] == [] and g0["computed_at"] is None  # nothing cached yet

    done = _drive_refresh(client)
    assert done["status"] == "done" and done["result"]["checked"] == 4 and done["result"]["count"] == 2

    g1 = client.get("/gaps", params={"direction": "backward"}).json()
    assert [c["openalex_work_id"] for c in g1["candidates"]] == ["W1", "W2"]  # W1 (4) before W2 (3)
    assert g1["candidates"][0]["cited_by_in_library"] == 4 and g1["computed_at"] is not None

    # dismiss W2 → GET drops it (read-time filter, no recompute)
    assert client.post("/gaps/dismiss", json={"openalex_work_id": "W2", "doi": "10.9/w2"}).status_code == 204
    after_dismiss = client.get("/gaps", params={"direction": "backward"}).json()["candidates"]
    assert [c["openalex_work_id"] for c in after_dismiss] == ["W1"]

    # add W1 → GET drops it (now in library)
    add = client.post("/gaps/add", json={"doi": "10.9/w1", "openalex_work_id": "W1", "title": "Most"})
    assert add.status_code == 200 and add.json()["status"] == "imported"
    assert client.get("/gaps", params={"direction": "backward"}).json()["candidates"] == []


def test_gap_refresh_forward_direction_is_independent(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        for d in ("10.1/p1", "10.1/p2", "10.1/p3"):
            _paper(conn, d)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = _FakeOA(
        workid_by_doi={"10.1/p1": "W101", "10.1/p2": "W102", "10.1/p3": "W103"},
        citing_by_workid={
            "W101": [_meta("WC1", "10.9/c1", "Cites All Three")],
            "W102": [_meta("WC1", "10.9/c1", "Cites All Three")],
            "W103": [_meta("WC1", "10.9/c1", "Cites All Three")],
        },
    )
    done = _drive_refresh(client, direction="forward")
    assert done["status"] == "done" and done["result"]["count"] == 1

    fwd = client.get("/gaps", params={"direction": "forward"}).json()
    assert [c["openalex_work_id"] for c in fwd["candidates"]] == ["WC1"]
    assert fwd["candidates"][0]["cited_by_in_library"] == 3
    # the backward scope is a separate cache row → still empty (the directions don't bleed)
    assert client.get("/gaps", params={"direction": "backward"}).json()["candidates"] == []
