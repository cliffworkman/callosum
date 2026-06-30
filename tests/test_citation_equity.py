"""inc 227 (backlog #25) — the identity-agnostic structural citation-equity audit: the OpenAlex parser extension
+ field-sample fetch, the pure analyzer's 5 descriptive signals, the no-identity-inference guarantee, and the async
endpoint. Descriptive, never a score/verdict/accusation; the gender module is deferred + absent."""

from __future__ import annotations

from pathlib import Path

from app.backend.methods.citation_equity import GLOBAL_NORTH, audit_reference_list
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from integrations.openalex.adapter import OpenAlexClient, _meta_from_work

# --- canned OpenAlex work objects -------------------------------------------


def _ref_work(wid, *, cited=10, venue="Nature", country="US", inst="MIT", authors=("X Y",)):
    return {
        "id": f"https://openalex.org/{wid}",
        "cited_by_count": cited,
        "primary_location": {"source": {"display_name": venue, "issn_l": "1000-0001"}},
        "authorships": [
            {"author": {"display_name": a}, "institutions": [{"display_name": inst, "country_code": country}]}
            for a in authors
        ],
    }


def _focal_work(doi, ref_ids, *, topic=("T100", "Genetics")):
    return {
        "id": "https://openalex.org/W0",
        "doi": f"https://doi.org/{doi}",
        "cited_by_count": 3,
        "referenced_works": [f"https://openalex.org/{w}" for w in ref_ids],
        "primary_topic": {"id": f"https://openalex.org/{topic[0]}", "display_name": topic[1]} if topic else None,
        "authorships": [{"author": {"display_name": "Pat Doe"}}],
    }


def _fetcher(works_by_doi, works_by_id, field_results):
    def fake(path, *, params, headers, timeout):
        if path.startswith("/doi:"):
            doi = path[len("/doi:") :]
            return (200, works_by_doi[doi]) if doi in works_by_doi else (404, {"error": "nf"})
        if path.startswith("/W"):
            wid = path[1:]
            return (200, works_by_id[wid]) if wid in works_by_id else (404, {"error": "nf"})
        if path == "" and "primary_topic.id:" in (params.get("filter") or ""):
            return (200, {"results": field_results})
        return (404, {"error": "nf"})

    return fake


# --- adapter: the additive _meta_from_work fields + fetch_field_sample -------


def test_meta_from_work_parses_new_fields():
    meta = _meta_from_work(_ref_work("W7", cited=42, venue="Cell", country="ng", inst="Univ Lagos"))
    assert meta["cited_by_count"] == 42
    assert meta["venue"] == "Cell" and meta["issn"] == "1000-0001"
    assert meta["country_codes"] == ["NG"]  # upper-cased
    assert meta["institutions"] == ["Univ Lagos"]
    # a gap-finder-shape blob with none of the new structures → safe defaults, no crash
    bare = _meta_from_work({"id": "https://openalex.org/W9", "cited_by_count": 5})
    assert bare["venue"] is None and bare["country_codes"] == [] and bare["institutions"] == []
    assert bare["primary_topic"] is None


def test_meta_from_work_validates_primary_topic():
    ok = _meta_from_work({"id": "x", "primary_topic": {"id": "https://openalex.org/T42", "display_name": "Stats"}})
    assert ok["primary_topic"] == {"id": "T42", "display_name": "Stats"}
    bad = _meta_from_work({"id": "x", "primary_topic": {"id": "https://openalex.org/Cnope"}})
    assert bad["primary_topic"] is None  # not a ^T\d+$ id → dropped


def test_fetch_field_sample_validates_id_and_fail_closed(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = OpenAlexClient(fetcher=_fetcher({}, {}, [_ref_work("W1"), _ref_work("W2", country="NG")]))
        out = client.fetch_field_sample(conn, "T100", size=10)
        assert len(out) == 2 and out[1]["country_codes"] == ["NG"]
        assert client.fetch_field_sample(conn, "X1") == []  # not ^T\d+$ → no request, []
        bad = OpenAlexClient(fetcher=lambda p, **k: (500, None))
        assert bad.fetch_field_sample(conn, "T999") == []  # non-200 → fail-closed
    engine.dispose()


# --- analyzer: the 5 descriptive signals ------------------------------------


def _by_key(report):
    return {s.key: s for s in report.signals}


def test_self_citation_by_author_overlap():
    refs = [
        {"title": "Mine", "year": 2020, "authors": ["Pat Doe", "A B"]},
        {"title": "Theirs", "year": 2019, "authors": ["C D"]},
    ]
    rep = audit_reference_list(
        refs=refs, focal_author_families={"doe"}, field=None, field_topic=None, references_total=2
    )
    sc = _by_key(rep)["self_citation"]
    assert sc.list_pct == 0.5 and sc.field_pct is None
    assert any("Mine" in b for b in sc.basis)
    # no author names → not computed (never a guessed 0)
    rep2 = audit_reference_list(
        refs=refs, focal_author_families=set(), field=None, field_topic=None, references_total=2
    )
    assert _by_key(rep2)["self_citation"].list_pct is None


def test_matthew_top_decile_vs_field():
    refs = [{"cited_by_count": c, "authors": []} for c in (2, 5, 900)]
    field = [{"cited_by_count": c} for c in range(0, 100)]  # p90 threshold = 90 → only the 900-ref is above
    rep = audit_reference_list(
        refs=refs,
        focal_author_families=set(),
        field=field,
        field_topic={"id": "T1", "display_name": "X"},
        references_total=3,
    )
    m = _by_key(rep)["matthew"]
    assert m.list_pct is not None and round(m.list_pct, 3) == round(1 / 3, 3)  # 1 of 3 above the field's top decile
    assert m.field_pct == 0.10
    # no field → list_pct None, the median shown descriptively (never a "vs field" claim without a baseline)
    rep2 = audit_reference_list(
        refs=refs, focal_author_families=set(), field=None, field_topic=None, references_total=3
    )
    m2 = _by_key(rep2)["matthew"]
    assert m2.list_pct is None and "Median" in m2.summary


def test_venue_and_institution_concentration():
    refs = [
        {"venue": "Nature", "institutions": ["MIT"], "authors": [], "cited_by_count": 1},
        {"venue": "Nature", "institutions": ["MIT"], "authors": [], "cited_by_count": 1},
        {"venue": "Cell", "institutions": ["Oxford"], "authors": [], "cited_by_count": 1},
        {"authors": [], "cited_by_count": 1},  # no venue / no institution → counted in coverage, not the share
    ]
    rep = audit_reference_list(refs=refs, focal_author_families=set(), field=[], field_topic=None, references_total=4)
    v = _by_key(rep)["venue"]
    assert v.list_pct == 1.0 and "3 references" not in v.coverage and "venue data" in v.coverage  # 3 of 4 had a venue
    inst = _by_key(rep)["institution"]
    assert inst.list_pct is not None and "affiliation data" in inst.coverage


def test_geography_global_south_share_and_coverage():
    assert "NG" not in GLOBAL_NORTH and "US" in GLOBAL_NORTH
    refs = [
        {"country_codes": ["US"], "authors": [], "cited_by_count": 1},
        {"country_codes": ["NG"], "authors": [], "cited_by_count": 1},
        {"country_codes": ["US", "CN"], "authors": [], "cited_by_count": 1},  # has a non-North author → counts
        {"authors": [], "cited_by_count": 1},  # no country → unknown, NOT assumed domestic
    ]
    rep = audit_reference_list(refs=refs, focal_author_families=set(), field=[], field_topic=None, references_total=4)
    g = _by_key(rep)["geography"]
    assert round(g.list_pct, 3) == round(2 / 3, 3)  # 2 of the 3 with country data have a Global-South author
    assert "shown as unknown" in g.coverage  # the 1 unknown is reported, not assumed
    assert any(b.startswith("NG") or b.startswith("US") or b.startswith("CN") for b in g.basis)  # country breakdown


def test_no_identity_inference_in_core():
    """The acceptance criterion: no gender/race code path. Behaviorally — injecting an author 'gender' field into
    the inputs changes NOTHING in the output (the analyzer never reads it); and the report carries no per-author
    identity label."""
    refs = [{"venue": "Nature", "country_codes": ["NG"], "authors": ["A B"], "cited_by_count": 5}]
    base = audit_reference_list(refs=refs, focal_author_families=set(), field=[], field_topic=None, references_total=1)
    poisoned = [{**refs[0], "gender": "f", "author_race": "x", "sex": "m"}]
    withjunk = audit_reference_list(
        refs=poisoned, focal_author_families=set(), field=[], field_topic=None, references_total=1
    )
    assert base.to_dict() == withjunk.to_dict()  # identity fields are ignored entirely
    # no signal or basis line names a gender/race attribute
    blob = str(base.to_dict()).lower()
    assert "male" not in blob and "female" not in blob and "race" not in blob


def test_analyzer_source_has_no_gender_keying():
    """A static guard: the analyzer never reads a gender/race/sex key from its inputs."""
    src = Path("app/backend/methods/citation_equity.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines() if not line.strip().startswith("#"))
    for forbidden in ('.get("gender"', '.get("sex"', '.get("race"', '["gender"]', '["sex"]', '["race"]'):
        assert forbidden not in code


# --- the async endpoint ------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.backend.api import create_app  # noqa: E402


def _seed(conn, title, doi, authors=None):
    csl = {"title": title, "DOI": doi}
    if authors:
        csl["author"] = authors
    return create_paper(conn, title=title, csl_json=csl, doi=doi)


def _drive(client, paper_id):
    r = client.post("/methods/citation-equity/run", json={"paper_id": paper_id})
    if r.status_code != 202:
        return r
    jid = r.json()["job_id"]
    data = {}
    for _ in range(40):
        data = client.get(f"/methods/citation-equity/run/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    return data


def test_run_produces_report(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Focal", "10.1/f", authors=[{"family": "Doe", "given": "Pat"}])
    engine.dispose()
    works_by_doi = {"10.1/f": _focal_work("10.1/f", ["W1", "W2"])}
    works_by_id = {
        "W1": _ref_work("W1", cited=900, venue="Nature", country="US", authors=("Pat Doe",)),  # a self-cite
        "W2": _ref_work("W2", cited=4, venue="Cell", country="NG", inst="Univ Lagos", authors=("Amara Okafor",)),
    }
    field = [_ref_work(f"WF{i}", cited=i, venue="Nature", country="US") for i in range(20)]
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher(works_by_doi, works_by_id, field))

    done = _drive(client, pid)
    assert done["status"] == "done"
    rep = done["report"]
    assert rep["references_total"] == 2 and rep["references_resolved"] == 2
    assert rep["field_topic"]["display_name"] == "Genetics" and rep["field_sample_size"] == 20
    keys = {s["key"] for s in rep["signals"]}
    assert keys == {"self_citation", "matthew", "venue", "institution", "geography"}
    by_key = {s["key"]: s for s in rep["signals"]}
    assert by_key["self_citation"]["list_pct"] == 0.5  # W1 (Pat Doe) is a self-cite, W2 is not
    assert by_key["geography"]["list_pct"] == 0.5  # 1 of 2 (NG) outside the high-income economies


def test_run_404_and_422(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        no_doi = _seed(conn, "No DOI", None)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/methods/citation-equity/run", json={"paper_id": 99999}).status_code == 404
    assert client.post("/methods/citation-equity/run", json={"paper_id": no_doi}).status_code == 422


def test_run_no_referenced_works_is_graceful(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Bare", "10.1/bare")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(
        fetcher=_fetcher({"10.1/bare": _focal_work("10.1/bare", [])}, {}, [])
    )
    done = _drive(client, pid)
    assert done["status"] == "done" and done["report"]["references_total"] == 0


def test_run_field_absent_is_own_shape(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "NoTopic", "10.1/nt")
    engine.dispose()
    works_by_doi = {"10.1/nt": _focal_work("10.1/nt", ["W1"], topic=None)}  # no primary_topic → no field baseline
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher(works_by_doi, {"W1": _ref_work("W1")}, []))
    done = _drive(client, pid)
    assert done["status"] == "done"
    rep = done["report"]
    assert rep["field_topic"] is None and rep["field_sample_size"] == 0
    assert len(rep["signals"]) == 5  # the own-shape signals still computed
    assert {s["key"]: s for s in rep["signals"]}["matthew"]["field_pct"] is None


def test_status_404_for_unknown_job(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/methods/citation-equity/run/nope").status_code == 404
