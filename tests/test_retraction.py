from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.acquisition.registry import PaperRef
from app.backend.api import create_app
from app.backend.metadata.enrich_sources import EnrichmentRegistry
from app.backend.methods.retraction import (
    RETRACTION_TAG_NAME,
    RETRACTION_TAG_SOURCE,
    RETRACTION_WATCH_CHECKER,
    SELF_CORRECTION_TAG_NAME,
    SELF_CORRECTION_TAG_SOURCE,
    RetractionChecker,
    RetractionSignal,
    apply_retraction,
    auto_check_retractions,
    detect_retraction,
    merge_signals,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import get_paper_findings
from app.backend.persistence.repository import create_paper
from app.backend.persistence.signals_repo import (
    count_retraction_flagged,
    get_retraction_status,
)
from app.backend.persistence.tags_repo import get_tags_for_paper
from integrations.crossref.adapter import CrossrefClient
from integrations.openalex.adapter import OpenAlexClient
from integrations.retraction_watch.adapter import RetractionWatchClient


def _paper(conn, *, doi=None, title="P") -> int:
    return create_paper(conn, title=title, csl_json={"title": title, "DOI": doi}, doi=doi)


# ---- merge_signals ---------------------------------------------------------


def test_merge_keeps_richest_detail_and_all_sources():
    crossref = RetractionSignal(source="crossref", status="retracted", date="2021-03-15", notice_doi="10.1/notice")
    openalex = RetractionSignal(source="openalex", status="retracted")  # thin corroboration, no notice
    merged = merge_signals([openalex, crossref])
    assert merged.status == "retracted"
    assert merged.notice_doi == "10.1/notice" and merged.date == "2021-03-15"
    assert merged.sources == ["crossref", "openalex"]  # sorted


def test_merge_escalates_status():
    merged = merge_signals(
        [RetractionSignal(source="a", status="correction"), RetractionSignal(source="b", status="retracted")]
    )
    assert merged.status == "retracted"  # retraction outranks correction


def test_merge_empty_is_none():
    assert merge_signals([]) is None
    assert merge_signals([None]) is None


# ---- detect_retraction (injected fake checkers) ----------------------------


def _checker(source, signal=None, *, raises=False):
    calls = []

    def fn(conn, paper):
        calls.append(paper)
        if raises:
            raise RuntimeError("source down")
        return signal

    c = RetractionChecker(source, fn)
    c.calls = calls  # type: ignore[attr-defined]
    return c


def test_detect_no_doi_is_unchecked_and_calls_nothing(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi=None)
        paper = {"id": pid, "doi": None, "csl_json": {}}
        checker = _checker("crossref", RetractionSignal(source="crossref", status="retracted"))
        outcome = detect_retraction(conn, paper, checkers=[checker])
    engine.dispose()
    assert outcome.status_kind == "unchecked"
    assert checker.calls == []  # no DOI → never hits a source


def test_detect_all_clean_is_none(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper = {"id": _paper(conn, doi="10.1/x"), "doi": "10.1/x", "csl_json": {}}
        outcome = detect_retraction(conn, paper, checkers=[_checker("crossref"), _checker("openalex")])
    engine.dispose()
    assert outcome.status_kind == "none" and outcome.merged is None
    assert outcome.sources_checked == ["crossref", "openalex"]


def test_detect_one_flag_is_retracted(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper = {"id": _paper(conn, doi="10.1/x"), "doi": "10.1/x", "csl_json": {}}
        flag = _checker("crossref", RetractionSignal(source="crossref", status="retracted", notice_doi="10.1/n"))
        outcome = detect_retraction(conn, paper, checkers=[flag, _checker("openalex")])
    engine.dispose()
    assert outcome.status_kind == "retracted"
    assert outcome.merged.notice_doi == "10.1/n"


def test_detect_skips_a_raising_checker(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper = {"id": _paper(conn, doi="10.1/x"), "doi": "10.1/x", "csl_json": {}}
        bad = _checker("crossref", raises=True)
        good = _checker("openalex", RetractionSignal(source="openalex", status="retracted"))
        outcome = detect_retraction(conn, paper, checkers=[bad, good])
    engine.dispose()
    assert outcome.status_kind == "retracted"  # the good source still flags
    assert outcome.sources_checked == ["openalex"]  # the raising source isn't counted as checked


# ---- apply_retraction (findings FACT + signal status) ----------------------


def test_apply_retracted_writes_fact_and_signal(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        flag = _checker("crossref", RetractionSignal(source="crossref", status="retracted", notice_doi="10.1/n"))
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[flag]))
        findings = get_paper_findings(conn, pid)
        status = get_retraction_status(conn, pid)
        flagged = count_retraction_flagged(conn)
    engine.dispose()
    assert len(findings["facts"]) == 1
    fact = findings["facts"][0]
    assert fact["payload"]["status"] == "retracted" and fact["payload"]["sources"] == ["crossref"]
    assert fact["payload"]["notice_url"] == "https://doi.org/10.1/n"
    assert status["status"] == "retracted" and flagged == 1


def test_apply_clean_writes_no_fact_and_none_signal(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[_checker("crossref")]))
        findings = get_paper_findings(conn, pid)
        status = get_retraction_status(conn, pid)
    engine.dispose()
    assert findings["facts"] == [] and status["status"] == "none"


def test_apply_unretraction_supersedes_fact(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        flag = _checker("crossref", RetractionSignal(source="crossref", status="retracted"))
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[flag]))
        assert len(get_paper_findings(conn, pid)["facts"]) == 1
        # the registry no longer flags it → re-apply clean
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[_checker("crossref")]))
        findings = get_paper_findings(conn, pid)
        status = get_retraction_status(conn, pid)
        flagged = count_retraction_flagged(conn)
    engine.dispose()
    assert findings["facts"] == []  # the FACT was superseded
    assert status["status"] == "none" and flagged == 0


def test_apply_unchecked_writes_unchecked_signal(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi=None)
        paper = {"id": pid, "doi": None, "csl_json": {}}
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[_checker("crossref")]))
        findings = get_paper_findings(conn, pid)
        status = get_retraction_status(conn, pid)
    engine.dispose()
    assert findings["facts"] == [] and status["status"] == "unchecked"


# ---- backlog #19: the system-fact tag stays in lockstep with the FACT/signal --------


def test_apply_retracted_creates_the_system_fact_tag(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        flag = _checker("crossref", RetractionSignal(source="crossref", status="retracted"))
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[flag]))
        tags = get_tags_for_paper(conn, pid)
    engine.dispose()
    assert len(tags) == 1
    assert tags[0]["name"] == RETRACTION_TAG_NAME
    assert tags[0]["import_source"] == RETRACTION_TAG_SOURCE == "system:retraction"


def test_apply_unretraction_removes_the_system_fact_tag(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        flag = _checker("crossref", RetractionSignal(source="crossref", status="retracted"))
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[flag]))
        assert len(get_tags_for_paper(conn, pid)) == 1
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[_checker("crossref")]))  # un-retracted
        tags = get_tags_for_paper(conn, pid)
    engine.dispose()
    assert tags == []


def test_apply_correction_gets_positive_system_fact_tag_but_not_retraction_tag(temp_db_url):
    # A correction is a separate positive fact, never part of count_retraction_flagged or the retraction filter.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        flag = _checker(
            "crossref", RetractionSignal(source="crossref", status="correction", notice_doi="10.1/correction")
        )
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[flag]))
        tags = get_tags_for_paper(conn, pid)
    engine.dispose()
    assert [(t["name"], t["import_source"]) for t in tags] == [(SELF_CORRECTION_TAG_NAME, SELF_CORRECTION_TAG_SOURCE)]


def test_apply_concern_or_clean_removes_positive_correction_tag(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        correction = _checker(
            "crossref", RetractionSignal(source="crossref", status="correction", notice_doi="10.1/correction")
        )
        concern = _checker("crossref", RetractionSignal(source="crossref", status="concern"))
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[correction]))
        assert [t["name"] for t in get_tags_for_paper(conn, pid)] == [SELF_CORRECTION_TAG_NAME]
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[concern]))
        concern_tags = get_tags_for_paper(conn, pid)
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[_checker("crossref")]))
        clean_tags = get_tags_for_paper(conn, pid)
    engine.dispose()
    assert concern_tags == []
    assert clean_tags == []


def test_apply_correction_without_openable_record_does_not_get_positive_badge_tag(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        correction = _checker("crossref", RetractionSignal(source="crossref", status="correction"))
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[correction]))
        findings = get_paper_findings(conn, pid)
        tags = get_tags_for_paper(conn, pid)
    engine.dispose()
    assert findings["facts"][0]["payload"]["status"] == "correction"
    assert tags == []  # the registry fact remains, but no evidence-linked positive badge is claimed
    listed = TestClient(create_app(db_url=temp_db_url)).get("/papers").json()
    assert next(p for p in listed if p["id"] == pid)["correction_evidence_linked"] is False


def test_apply_retraction_reapply_is_idempotent(temp_db_url):
    # Repeated batch runs (or the on-import hook re-firing) must not duplicate the tag link.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/x")
        paper = {"id": pid, "doi": "10.1/x", "csl_json": {}}
        flag = _checker("crossref", RetractionSignal(source="crossref", status="retracted"))
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[flag]))
        apply_retraction(conn, pid, detect_retraction(conn, paper, checkers=[flag]))
        tags = get_tags_for_paper(conn, pid)
    engine.dispose()
    assert len(tags) == 1


# ---- the source checkers (injected fake fetchers, no network) --------------


def test_crossref_lookup_parses_update_to_retraction(temp_db_url):
    body = {
        "message": {
            "update-to": [
                {
                    "type": "retraction",
                    "DOI": "10.1/Notice",
                    "label": "Retraction",
                    "updated": {"date-parts": [[2021, 3, 15]]},
                }
            ]
        }
    }

    def fake(doi, *, headers, timeout):
        return 200, body

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        raw = CrossrefClient(fetcher=fake).lookup_retraction(conn, "10.1/x")
    engine.dispose()
    assert raw["status"] == "retracted"
    assert raw["notice_doi"] == "10.1/notice" and raw["date"] == "2021-03-15"


def test_crossref_lookup_correction_and_none(temp_db_url):
    def fake_corr(doi, *, headers, timeout):
        return 200, {"message": {"update-to": [{"type": "correction", "DOI": "10.1/c"}]}}

    def fake_clean(doi, *, headers, timeout):
        return 200, {"message": {"title": ["A normal paper"]}}

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        corr = CrossrefClient(fetcher=fake_corr).lookup_retraction(conn, "10.1/a")
        clean = CrossrefClient(fetcher=fake_clean).lookup_retraction(conn, "10.1/b")
    engine.dispose()
    assert corr["status"] == "correction"
    assert clean is None


def test_openalex_lookup_is_retracted(temp_db_url):
    def fake_true(path, *, params, headers, timeout):
        return 200, {"id": "https://openalex.org/W1", "is_retracted": True}

    def fake_false(path, *, params, headers, timeout):
        return 200, {"id": "https://openalex.org/W2", "is_retracted": False}

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        flagged = OpenAlexClient(fetcher=fake_true).lookup_retraction(conn, PaperRef(doi="10.1/x"))
        clean = OpenAlexClient(fetcher=fake_false).lookup_retraction(conn, PaperRef(doi="10.1/y"))
    engine.dispose()
    assert flagged["status"] == "retracted"
    assert clean is None


# ---- endpoints + library filter (injected fake checkers, no network) --------


def test_retraction_endpoints_and_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, doi="10.1/retracted", title="A")
        b = _paper(conn, doi="10.1/clean", title="B")
        c = _paper(conn, doi="10.1/corrected", title="C")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    def fake(conn, paper):  # deterministic, offline
        if paper["doi"] == "10.1/retracted":
            return RetractionSignal(source="crossref", status="retracted", notice_doi="10.1/n")
        if paper["doi"] == "10.1/corrected":
            return RetractionSignal(source="crossref", status="correction", notice_doi="10.1/c")
        return None

    client.app.state.retraction_checkers = [RetractionChecker("crossref", fake)]

    # per-paper status before any run → never checked
    pre = client.get(f"/papers/{a}/retraction").json()
    assert pre["status"] == "unchecked" and pre["checked"] is False

    # library-wide batch
    run = client.post("/methods/retraction/run")
    assert run.status_code == 202
    done = client.get(f"/methods/retraction/run/{run.json()['job_id']}").json()
    assert done["status"] == "done"
    assert done["summary"]["flagged"] == 1 and done["summary"]["corrections"] == 1

    # A flagged retracted, B honestly checked-clean
    assert client.get(f"/papers/{a}/retraction").json()["status"] == "retracted"
    assert client.get(f"/papers/{b}/retraction").json() == {
        "paper_id": b,
        "status": "none",
        "checked": True,
        "sources": ["crossref"],
        "checked_at": client.get(f"/papers/{b}/retraction").json()["checked_at"],
    }

    # the chip count + the library "Retracted" filter
    assert client.get("/methods/retraction/summary").json()["retracted"] == 1
    papers = client.get("/papers").json()
    assert next(p for p in papers if p["id"] == a)["retraction_status"] == "retracted"
    assert next(p for p in papers if p["id"] == b)["retraction_status"] == "none"
    assert next(p for p in papers if p["id"] == c)["correction_evidence_linked"] is True
    assert client.get(f"/papers/{a}").json()["retraction_status"] == "retracted"
    ids = [p["id"] for p in client.get("/papers?signal=retraction-retracted").json()]
    assert a in ids and b not in ids

    # A carries the retraction FACT
    facts = client.get(f"/papers/{a}/findings").json()["facts"]
    assert any(f["payload"]["status"] == "retracted" for f in facts)
    correction_facts = client.get(f"/papers/{c}/findings").json()["facts"]
    assert any(
        f["payload"]["status"] == "correction" and f["payload"]["notice_url"] == "https://doi.org/10.1/c"
        for f in correction_facts
    )
    correction_tags = client.get(f"/papers/{c}").json()["tags"]
    assert any(tag["name"] == SELF_CORRECTION_TAG_NAME for tag in correction_tags)

    assert client.get("/papers/999999/retraction").status_code == 404


def test_retraction_run_refreshes_rw_database_before_check(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, doi="10.1/orig", title="A")
    engine.dispose()

    csv = (
        "RecordID,Title,OriginalPaperDOI,RetractionDOI,RetractionNature,RetractionDate,Reason,URLS\n"
        "1,Bad Paper,10.1/orig,10.1/notice,Retraction,2021-03-15,+Data issue,https://x\n"
    )

    def fake(url, *, timeout, max_bytes):
        return csv

    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.retraction_watch_client = RetractionWatchClient(fetcher=fake, mailto="x@y.z")
    client.app.state.retraction_checkers = [RETRACTION_WATCH_CHECKER]

    run = client.post("/methods/retraction/run")
    assert run.status_code == 202
    done = client.get(f"/methods/retraction/run/{run.json()['job_id']}").json()
    assert done["status"] == "done"
    assert done["detail"] is None
    assert done["summary"]["database_records"] == 1
    assert done["summary"]["flagged"] == 1
    assert client.get("/methods/retraction/database").json()["count"] == 1
    assert client.get(f"/papers/{a}/retraction").json()["sources"] == ["retraction-watch"]
    assert client.get(f"/papers/{a}").json()["retraction_status"] == "retracted"


# ---- on-import auto-check (inc 134) -----------------------------------------


def test_auto_check_retractions_best_effort(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, doi="10.1/retracted", title="A")
        b = _paper(conn, doi="10.1/clean", title="B")

        def fake(conn, paper):
            return RetractionSignal(source="crossref", status="retracted") if paper["doi"] == "10.1/retracted" else None

        n = auto_check_retractions(
            conn, [a, b, 999999], checkers=[RetractionChecker("crossref", fake)]
        )  # 999999 missing → skipped
        a_findings = get_paper_findings(conn, a)
        b_status = get_retraction_status(conn, b)
    engine.dispose()
    assert n == 1  # only A flagged; the missing id is swallowed, B is clean
    assert len(a_findings["facts"]) == 1 and a_findings["facts"][0]["payload"]["status"] == "retracted"
    assert b_status["status"] == "none"  # B was checked-clean (silence != clean)


def test_citation_import_auto_checks_retraction(temp_db_url):
    import json as _json

    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.retraction_checkers = [
        RetractionChecker(
            "crossref",
            lambda c, p: RetractionSignal(source="crossref", status="retracted", notice_doi="10.1/n")
            if p["doi"] == "10.1/retracted"
            else None,
        )
    ]
    csl = [{"DOI": "10.1/retracted", "title": "Imported Paper", "type": "article-journal"}]
    started = client.post("/library/import", json={"content": _json.dumps(csl), "format": "csl-json"})
    assert started.status_code == 202
    jid = started.json()["job_id"]
    for _ in range(30):
        if client.get(f"/library/import/{jid}").json()["status"] in ("done", "error"):
            break
    pid = next(p["id"] for p in client.get("/papers").json() if p["title"] == "Imported Paper")
    facts = client.get(f"/papers/{pid}/findings").json()["facts"]
    assert any(f["payload"]["status"] == "retracted" for f in facts)  # flagged on import, no manual batch


# ---- on-enrich / on-acquire auto-check (inc 224 — the remaining DOI-bearing paths) ----


class _GracefulCrossref:  # a hermetic Crossref fetcher: always a clean 404 miss, never networks
    def __call__(self, doi, *, headers, timeout):
        return 404, {"status": "error"}


def _flag_checker():  # a fake retraction checker that flags one DOI, offline
    return RetractionChecker(
        "crossref",
        lambda c, p: RetractionSignal(source="crossref", status="retracted", notice_doi="10.1/n")
        if p["doi"] == "10.1/retracted"
        else None,
    )


def test_reresolve_auto_checks_retraction(temp_db_url):
    # inc 224: re-resolving a paper's DOI auto-checks retraction (the on-import hook). The graceful Crossref miss
    # keeps the paper's existing DOI; the fake retraction checker keys off that DOI → the FACT lands.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, doi="10.1/retracted", title="A")
        b = _paper(conn, doi="10.1/clean", title="B")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=CrossrefClient(fetcher=_GracefulCrossref())))
    client.app.state.retraction_checkers = [_flag_checker()]

    assert client.post(f"/papers/{a}/re-resolve").status_code == 200
    assert client.post(f"/papers/{b}/re-resolve").status_code == 200
    a_facts = client.get(f"/papers/{a}/findings").json()["facts"]
    assert any(f["payload"]["status"] == "retracted" for f in a_facts)  # flagged on re-resolve
    assert client.get(f"/papers/{b}/findings").json()["facts"] == []  # clean DOI → no FACT


def test_fill_metadata_auto_checks_retraction(temp_db_url):
    # inc 224: gap-fill ("Fill missing fields") auto-checks retraction. An empty enrich registry keeps it hermetic
    # (no source fetch); the seeded DOI drives the fake checker.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, doi="10.1/retracted", title="A")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.enrich_registry = EnrichmentRegistry()  # no sources → no network
    client.app.state.retraction_checkers = [_flag_checker()]

    assert client.post(f"/papers/{a}/fill-metadata").status_code == 200
    facts = client.get(f"/papers/{a}/findings").json()["facts"]
    assert any(f["payload"]["status"] == "retracted" for f in facts)


def test_oa_acquire_auto_checks_retraction(temp_db_url, monkeypatch, tmp_path):
    # inc 224: an OA-acquired paper (just Crossref-enriched) auto-checks retraction. Hermetic: a fake resolver +
    # a fake download (a real minimal PDF) + a graceful Crossref + the fake checker — no network.
    import fitz

    import app.backend.api.routers.acquisition as acq
    from app.backend.acquisition.registry import OaLocation

    monkeypatch.setenv("CALLOSUM_LIBRARY_DIR", str(tmp_path / "lib"))
    doc = fitz.open()
    doc.new_page()
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(doc.tobytes())
    doc.close()

    class _Reg:
        def resolve(self, conn, ref):
            return OaLocation(pdf_url="https://e.org/x.pdf", oa_color="gold", version="vor", source="openalex")

    monkeypatch.setattr(acq, "build_default_registry", lambda **kw: _Reg())
    monkeypatch.setattr(acq, "download_oa_pdf", lambda location: str(pdf))

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, doi="10.1/retracted", title="Acq")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=CrossrefClient(fetcher=_GracefulCrossref())))
    client.app.state.retraction_checkers = [_flag_checker()]

    started = client.post(f"/papers/{pid}/acquire-oa")
    assert started.status_code in (200, 202)
    jid = started.json()["job_id"]
    for _ in range(30):
        if client.get(f"/papers/acquire-oa/{jid}").json()["status"] in ("done", "error"):
            break
    assert client.get(f"/papers/acquire-oa/{jid}").json()["status"] == "done"
    facts = client.get(f"/papers/{pid}/findings").json()["facts"]
    assert any(f["payload"]["status"] == "retracted" for f in facts)  # flagged after OA acquire
