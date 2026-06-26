from __future__ import annotations

from app.backend.acquisition.registry import PaperRef
from app.backend.methods.retraction import (
    RetractionChecker,
    RetractionSignal,
    apply_retraction,
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
from integrations.crossref.adapter import CrossrefClient
from integrations.openalex.adapter import OpenAlexClient


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
