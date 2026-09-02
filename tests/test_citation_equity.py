"""inc 227 (backlog #25; reworked inc 229) — the structural citation-concentration analyzer: the OpenAlex parser
extension + field-sample fetch, the pure analyzer's 4 descriptive signals, the no-people-categorization guarantee,
and the async endpoint. Descriptive, never a score/verdict/accusation; the tool NEVER categorizes the people cited
(no gender/race/nationality — the geography "Global South" signal was removed inc 229, rejected on principle)."""

from __future__ import annotations

from pathlib import Path

from app.backend.methods.citation_equity import audit_reference_list
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from integrations.openalex.adapter import OpenAlexClient, _meta_from_work

# --- canned OpenAlex work objects -------------------------------------------


def _ref_work(
    wid, *, cited=10, venue="Nature", country="US", inst="MIT", authors=("X Y",), author_id=None, referenced_works=None
):
    work = {
        "id": f"https://openalex.org/{wid}",
        "cited_by_count": cited,
        "primary_location": {"source": {"display_name": venue, "issn_l": "1000-0001"}},
        "authorships": [
            {
                "author": {"display_name": a, **({"id": f"https://openalex.org/{author_id}"} if author_id else {})},
                "institutions": [{"display_name": inst, "country_code": country}],
            }
            for a in authors
        ],
    }
    if referenced_works is not None:  # inc 457: only set when a test needs this field paper self-citation-computable
        work["referenced_works"] = [f"https://openalex.org/{w}" for w in referenced_works]
    return work


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
    assert meta["institutions"] == ["Univ Lagos"]
    assert "country_codes" not in meta  # nationality is deliberately NOT extracted (inc 229)
    # a gap-finder-shape blob with none of the new structures → safe defaults, no crash
    bare = _meta_from_work({"id": "https://openalex.org/W9", "cited_by_count": 5})
    assert bare["venue"] is None and bare["institutions"] == []
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
        assert len(out) == 2 and out[1]["venue"] == "Nature"
        assert client.fetch_field_sample(conn, "X1") == []  # not ^T\d+$ → no request, []
        bad = OpenAlexClient(fetcher=lambda p, **k: (500, None))
        assert bad.fetch_field_sample(conn, "T999") == []  # non-200 → fail-closed
    engine.dispose()


# --- adapter: fetch_self_citation_hit_count (inc 456 self-citation field baseline) ------------------------------


def _count_fetcher(hits_by_chunk_key, *, calls=None):
    """A fake OpenAlex fetcher for the count-only `openalex_id:...,authorships.author.id:...` filter -- returns
    `{"meta": {"count": N}}` for a (sorted ref-ids, sorted author-ids) key registered in `hits_by_chunk_key`."""

    def fake(path, *, params, headers, timeout):
        filt = params.get("filter") or ""
        if calls is not None:
            calls.append(filt)
        if "openalex_id:" not in filt or "authorships.author.id:" not in filt:
            return (404, {"error": "unexpected filter"})
        ids_part, authors_part = filt.split(",authorships.author.id:")
        ids_key = tuple(sorted(ids_part[len("openalex_id:") :].split("|")))
        authors_key = tuple(sorted(authors_part.split("|")))
        key = (ids_key, authors_key)
        if key not in hits_by_chunk_key:
            return (404, {"error": "unregistered chunk"})
        return (200, {"meta": {"count": hits_by_chunk_key[key]}})

    return fake


def test_self_citation_hit_count_counts_and_validates_ids(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = OpenAlexClient(fetcher=_count_fetcher({(("W1", "W2"), ("A1",)): 1}))
        # "bad"/"A9x" dropped by validation before the request is ever built
        n = client.fetch_self_citation_hit_count(conn, ref_ids=["W1", "W2", "bad"], author_ids=["A1", "A9x"])
        assert n == 1
        assert client.fetch_self_citation_hit_count(conn, ref_ids=[], author_ids=["A1"]) is None  # no refs
        assert client.fetch_self_citation_hit_count(conn, ref_ids=["W1"], author_ids=[]) is None  # no authors
    engine.dispose()


def test_self_citation_hit_count_chunks_over_50_refs_and_sums(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        # fetch_self_citation_hit_count sorts+dedupes the FULL ref-id set before chunking (string-lexicographic,
        # not numeric) -- derive the expected chunk boundaries the same way, rather than pre-guessing them.
        all_refs = sorted({f"W{i}" for i in range(60)})
        chunk_a = tuple(all_refs[:50])
        chunk_b = tuple(all_refs[50:])
        calls: list[str] = []
        client = OpenAlexClient(fetcher=_count_fetcher({(chunk_a, ("A1",)): 3, (chunk_b, ("A1",)): 2}, calls=calls))
        n = client.fetch_self_citation_hit_count(conn, ref_ids=[f"W{i}" for i in range(60)], author_ids=["A1"])
        assert n == 5 and len(calls) == 2  # two chunks (≤MAX_BYIDS each), summed
    engine.dispose()


def test_self_citation_hit_count_fail_closed_never_a_silent_partial_zero(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        bad = OpenAlexClient(fetcher=lambda p, **k: (500, None))
        assert bad.fetch_self_citation_hit_count(conn, ref_ids=["W1"], author_ids=["A1"]) is None
        # one good chunk + one failing chunk → the whole result is None, never a silently-undercounted partial sum
        all_refs = sorted({f"W{i}" for i in range(51)})
        chunk_a = tuple(all_refs[:50])  # the second chunk (all_refs[50:]) is deliberately left unregistered
        mixed = OpenAlexClient(fetcher=_count_fetcher({(chunk_a, ("A1",)): 3}))
        n = mixed.fetch_self_citation_hit_count(conn, ref_ids=[f"W{i}" for i in range(51)], author_ids=["A1"])
        assert n is None  # the unregistered second chunk → fails closed, not a silent "3"
    engine.dispose()


def test_self_citation_hit_count_caches(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        calls: list[str] = []
        client = OpenAlexClient(fetcher=_count_fetcher({(("W1",), ("A1",)): 1}, calls=calls))
        client.fetch_self_citation_hit_count(conn, ref_ids=["W1"], author_ids=["A1"])
        client.fetch_self_citation_hit_count(conn, ref_ids=["W1"], author_ids=["A1"])
        assert len(calls) == 1  # the second call hit the cache, no second request
    engine.dispose()


# --- analyzer: the 4 descriptive signals ------------------------------------


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


def test_self_citation_field_baseline_present_and_absent():
    """inc 457: field_pct now carries a real self-citation field baseline when the caller (the router) computed
    one; still an honest None (not a guessed 0) when it couldn't."""
    refs = [{"title": "Mine", "year": 2020, "authors": ["Pat Doe"]}]
    with_baseline = audit_reference_list(
        refs=refs,
        focal_author_families={"doe"},
        field=None,
        field_topic=None,
        references_total=1,
        self_citation_field_baseline=0.16,
        self_citation_field_baseline_n=147,
    )
    sc = _by_key(with_baseline)["self_citation"]
    assert sc.field_pct == 0.16
    assert "147 papers checked" in sc.summary and "16%" in sc.summary

    without_baseline = audit_reference_list(
        refs=refs, focal_author_families={"doe"}, field=None, field_topic=None, references_total=1
    )
    sc2 = _by_key(without_baseline)["self_citation"]
    assert sc2.field_pct is None
    assert "No field baseline could be computed" in sc2.summary


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
    assert v.list_pct == 1.0 and "3 references" not in v.coverage.text and "venue data" in v.coverage.text
    inst = _by_key(rep)["institution"]
    assert inst.list_pct is not None and "affiliation data" in inst.coverage.text


def test_low_coverage_flag_when_a_signal_resolves_under_half():
    """A signal computed over <50% of the references is SHOWN but flagged low-confidence (honesty #4/#6) — never
    hidden, and never presented next to the field baseline as if equally reliable (the inc-227 experience-pass gap)."""
    # 3 refs resolved (all with institution data) out of 10 listed → institution coverage = 3/10 = 0.3 → low.
    refs = [{"institutions": ["MIT"], "authors": [], "cited_by_count": 1} for _ in range(3)]
    rep = audit_reference_list(refs=refs, focal_author_families=set(), field=[], field_topic=None, references_total=10)
    inst = _by_key(rep)["institution"]
    assert inst.coverage.fraction is not None and inst.coverage.fraction < 0.5  # 3 of 10
    assert inst.coverage.low is True
    d = inst.to_dict()
    assert d["low_coverage"] is True and d["coverage_fraction"] == inst.coverage.fraction  # flows through the payload

    # A fully-resolved signal (all references resolved with data) is NOT flagged.
    full = [{"institutions": ["MIT"], "authors": [], "cited_by_count": 1} for _ in range(4)]
    rep2 = audit_reference_list(refs=full, focal_author_families=set(), field=[], field_topic=None, references_total=4)
    inst2 = _by_key(rep2)["institution"]
    assert inst2.coverage.fraction == 1.0 and inst2.coverage.low is False and inst2.to_dict()["low_coverage"] is False


def test_no_people_categorization_in_core():
    """The load-bearing guarantee (inc 229): the analyzer NEVER categorizes the people cited. Behaviorally —
    injecting gender/race/sex/nationality fields into the inputs changes NOTHING in the output (they are never
    read); and no signal or basis line names an identity attribute."""
    refs = [{"venue": "Nature", "institutions": ["MIT"], "authors": ["A B"], "cited_by_count": 5}]
    base = audit_reference_list(refs=refs, focal_author_families=set(), field=[], field_topic=None, references_total=1)
    poisoned = [{**refs[0], "gender": "f", "author_race": "x", "sex": "m", "country_codes": ["NG"]}]
    withjunk = audit_reference_list(
        refs=poisoned, focal_author_families=set(), field=[], field_topic=None, references_total=1
    )
    assert base.to_dict() == withjunk.to_dict()  # gender/race/sex/nationality are ignored entirely
    blob = str(base.to_dict()).lower()
    assert all(w not in blob for w in ("male", "female", "race", "global south", "country"))


def test_analyzer_source_has_no_people_categorization():
    """A static guard: the analyzer never reads a gender/race/sex/nationality key, and carries no Global-North/South
    classification — categorizing the people cited is rejected on principle (inc 229), not just unimplemented."""
    src = Path("app/backend/methods/citation_equity.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines() if not line.strip().startswith("#"))
    for forbidden in (
        '.get("gender"',
        '.get("sex"',
        '.get("race"',
        '["gender"]',
        '["sex"]',
        '["race"]',
        "country_code",
        "GLOBAL_NORTH",
        "global_south",
    ):
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
    assert keys == {"self_citation", "matthew", "venue", "institution"}  # no geography — people are never categorized
    by_key = {s["key"]: s for s in rep["signals"]}
    assert by_key["self_citation"]["list_pct"] == 0.5  # W1 (Pat Doe) is a self-cite, W2 is not
    # the default _ref_work field papers carry no author_id/referenced_works -- none are baseline-computable,
    # so field_pct stays an honest None rather than crashing or fabricating a rate
    assert by_key["self_citation"]["field_pct"] is None


def test_run_404_and_422(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        no_doi = _seed(conn, "No DOI", None)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/methods/citation-equity/run", json={"paper_id": 99999}).status_code == 404
    assert client.post("/methods/citation-equity/run", json={"paper_id": no_doi}).status_code == 422


def test_run_reports_openalex_outage_instead_of_publishing_empty_audit(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Focal", "10.1/f")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=lambda *a, **k: (503, {"error": "unavailable"}))

    done = _drive(client, pid)

    assert done["status"] == "error"
    assert "unavailable" in done["detail"].lower()


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
    assert len(rep["signals"]) == 4  # the own-shape signals still computed
    assert {s["key"]: s for s in rep["signals"]}["matthew"]["field_pct"] is None


def test_status_404_for_unknown_job(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/methods/citation-equity/run/nope").status_code == 404


# --- P2 item #18 (backlog #33/#34, inc 463): POST /methods/citation-equity/check-selected -- the LibreOffice
# adapter's "Citation coverage audit..." command's backend. Synchronous (no job/poll), scoped to a caller-named
# paper_ids list rather than a paper's own OpenAlex reference graph or a WIP manuscript's wip_references. ------


def test_check_selected_produces_report(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        p1 = _seed(conn, "Cited One", "10.1/c1")
        p2 = _seed(conn, "Cited Two", "10.1/c2")
    engine.dispose()
    works_by_doi = {
        "10.1/c1": _ref_work("W1", cited=900, venue="Nature", country="US"),
        "10.1/c2": _ref_work("W2", cited=4, venue="Cell", country="NG", inst="Univ Lagos"),
    }
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher(works_by_doi, {}, []))

    resp = client.post("/methods/citation-equity/check-selected", json={"paper_ids": [p1, p2]})
    assert resp.status_code == 200
    rep = resp.json()
    assert rep["references_total"] == 2 and rep["references_resolved"] == 2
    # honest degraded path: no stored author identity, no field-topic comparison for a live Writer document
    assert rep["field_topic"] is None and rep["field_sample_size"] == 0
    keys = {s["key"] for s in rep["signals"]}
    assert keys == {"self_citation", "matthew", "venue", "institution"}
    by_key = {s["key"]: s for s in rep["signals"]}
    assert by_key["self_citation"]["field_pct"] is None
    assert by_key["matthew"]["field_pct"] is None


def test_check_selected_skips_missing_and_unresolvable_papers(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        p1 = _seed(conn, "Resolvable", "10.1/ok")
        p2 = _seed(conn, "Unresolvable DOI", "10.1/missing-from-openalex")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher({"10.1/ok": _ref_work("W1")}, {}, []))

    not_in_library = 999999
    resp = client.post("/methods/citation-equity/check-selected", json={"paper_ids": [p1, p2, not_in_library]})
    assert resp.status_code == 200
    rep = resp.json()
    # 3 requested; p2's DOI 404s at OpenAlex, not_in_library isn't even in the DB -- both skipped, never fatal
    assert rep["references_total"] == 3 and rep["references_resolved"] == 1


def test_check_selected_rejects_empty_and_over_cap_input(temp_db_url):
    from app.backend.api.routers.citation_equity import MAX_EQUITY_CHECK_SELECTED

    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/methods/citation-equity/check-selected", json={"paper_ids": []}).status_code == 422
    too_many = list(range(1, MAX_EQUITY_CHECK_SELECTED + 2))
    assert client.post("/methods/citation-equity/check-selected", json={"paper_ids": too_many}).status_code == 422


def test_check_selected_returns_503_when_openalex_is_unavailable(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Selected", "10.1/selected")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=lambda *a, **k: (503, {"error": "unavailable"}))

    response = client.post("/methods/citation-equity/check-selected", json={"paper_ids": [pid]})

    assert response.status_code == 503
    assert response.json()["detail"] == "OpenAlex metadata is temporarily unavailable."


# --- inc 457: the self-citation field baseline's dual cap (target N=40, max checks=100) -----------------------


def _fetcher_with_self_citation(works_by_doi, works_by_id, field_results, hits_by_ref_and_author, *, calls):
    """Extends `_fetcher`'s dispatch with the count-only `openalex_id:...,authorships.author.id:...` filter
    (inc 456's primitive) -- `hits_by_ref_and_author` maps a single ref id -> hit count; an unregistered ref id
    yields a 404 (fetch_self_citation_hit_count -> None), simulating a field paper whose count can't be resolved."""

    def fake(path, *, params, headers, timeout):
        filt = params.get("filter") or ""
        if "authorships.author.id:" in filt:
            calls.append(filt)
            ref_id = filt.split("openalex_id:")[1].split(",authorships.author.id:")[0]
            if ref_id not in hits_by_ref_and_author:
                return (404, {"error": "unregistered"})
            return (200, {"meta": {"count": hits_by_ref_and_author[ref_id]}})
        if path.startswith("/doi:"):
            doi = path[len("/doi:") :]
            return (200, works_by_doi[doi]) if doi in works_by_doi else (404, {"error": "nf"})
        if path.startswith("/W"):
            wid = path[1:]
            return (200, works_by_id[wid]) if wid in works_by_id else (404, {"error": "nf"})
        if path == "" and "primary_topic.id:" in filt:
            return (200, {"results": field_results})
        return (404, {"error": "nf"})

    return fake


def test_self_citation_baseline_stops_at_target_n_even_with_more_computable_papers(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Focal", "10.1/f2", authors=[{"family": "Doe", "given": "Pat"}])
    engine.dispose()
    works_by_doi = {"10.1/f2": _focal_work("10.1/f2", ["W1"])}
    works_by_id = {"W1": _ref_work("W1", authors=("Pat Doe",))}
    # 50 field papers, ALL computable (author_id + a single referenced_work each) -- more than the target N=40
    field = [
        _ref_work(f"WF{i}", author_id=f"A{i}", referenced_works=[f"W900{i}"], authors=(f"Person {i}",))
        for i in range(50)
    ]
    hits = {f"W900{i}": 1 for i in range(50)}  # every field paper "self-cites" its own single reference
    calls: list[str] = []
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(
        fetcher=_fetcher_with_self_citation(works_by_doi, works_by_id, field, hits, calls=calls)
    )

    done = _drive(client, pid)
    assert done["status"] == "done"
    sc = {s["key"]: s for s in done["report"]["signals"]}["self_citation"]
    assert sc["field_pct"] == 1.0
    assert "40 papers checked" in sc["summary"]  # stopped at the target N, not all 50 available
    assert len(calls) == 40  # only 40 self-citation-count requests were made, not 50


def test_self_citation_baseline_stops_at_max_checks_when_coverage_is_low(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Focal", "10.1/f3", authors=[{"family": "Doe", "given": "Pat"}])
    engine.dispose()
    works_by_doi = {"10.1/f3": _focal_work("10.1/f3", ["W1"])}
    works_by_id = {"W1": _ref_work("W1", authors=("Pat Doe",))}
    # 110 "eligible" field papers (each has author_id + one referenced_work), but only 3 of the first 100 ever
    # resolve a real count -- simulating a low-coverage field where most count queries fail/miss.
    field = [
        _ref_work(f"WF{i}", author_id=f"A{i}", referenced_works=[f"W9{i}"], authors=(f"Person {i}",))
        for i in range(110)
    ]
    hits = {"W92": 1, "W910": 0, "W950": 1}  # only these 3 (all within the first 100) resolve
    calls: list[str] = []
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(
        fetcher=_fetcher_with_self_citation(works_by_doi, works_by_id, field, hits, calls=calls)
    )

    done = _drive(client, pid)
    assert done["status"] == "done"
    sc = {s["key"]: s for s in done["report"]["signals"]}["self_citation"]
    assert sc["field_pct"] is not None  # 2 of 3 resolved counts were nonzero -- a real, if thin, baseline
    assert "3 papers checked" in sc["summary"]  # only the 3 that actually resolved count toward the total
    assert len(calls) == 100  # the max-checks cap fired -- the 10 papers after WF99 were never queried
