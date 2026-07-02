"""Transparency persistence producer (backlog #44 inc 1b, inc 251).

Hermetic (a throwaway DB + a real paper row for the FK + fake chunks): a present disclosure → a findings-FACT + a
`detected` status; a not-found → NO fact + `not-detected`; an n/a → NO fact + `not-applicable`; re-run idempotence
(a now-absent disclosure supersedes its FACT + flips its status); the review-queue count; and the A-A pin (no FACT is
ever written for a non-present disclosure — silence≠certificate).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.methods.transparency_findings import persist_transparency
from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import get_paper_findings
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import open_science_signals
from app.backend.persistence.signals_repo import count_transparency_review


@dataclass
class _Chunk:
    text: str
    page_start: int | None = 1


_OPEN_TEXT = (
    "Data availability: all data are openly available at https://osf.io/ab12c/. Analysis code is available at "
    "https://github.com/lab/study. Conflict of interest: the authors declare no competing interests. Funding: this "
    "work was funded by NIH grant R01-12345. We conducted a laboratory experiment on memory with 40 undergraduates."
)
_BARE_TEXT = "We conducted a survey of 200 participants and report descriptive statistics."


def _statuses(conn, pid):
    rows = conn.execute(
        select(open_science_signals.c.source, open_science_signals.c.status).where(
            open_science_signals.c.paper_id == pid,
            open_science_signals.c.signal_type == "transparency",
        )
    ).all()
    return {src: st for src, st in rows}


def _fact_keys(conn, pid):
    facts = get_paper_findings(conn, pid)["facts"]
    return {f["payload"]["key"] for f in facts if f["source"] == "transparency"}


def test_present_disclosures_become_facts_and_detected_status(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Open paper", csl_json={"title": "Open paper"})
        summary = persist_transparency(conn, pid, [_Chunk(_OPEN_TEXT)])
        assert summary == {"present": 4, "checks": 7}
        keys = _fact_keys(conn, pid)
        assert keys == {"data_availability", "code_availability", "conflict_of_interest", "funding"}
        st = _statuses(conn, pid)
        assert st["data_availability"] == "detected" and st["code_availability"] == "detected"
        assert st["preregistration"] == "not-detected"  # no prereg in the text
        assert st["registration"] == "not-applicable"  # non-trial design
        assert st["upon_request"] == "not-applicable"  # phrase absent
    engine.dispose()


def test_bare_paper_writes_no_absence_facts(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Bare paper", csl_json={"title": "Bare paper"})
        persist_transparency(conn, pid, [_Chunk(_BARE_TEXT)])
        # THE A-A PIN: an absence is never a FACT.
        assert _fact_keys(conn, pid) == set()
        st = _statuses(conn, pid)
        assert st["data_availability"] == "not-detected" and st["code_availability"] == "not-detected"
        # 7 status rows written even when nothing is disclosed
        assert len(st) == 7
    engine.dispose()


def test_rerun_supersedes_a_now_absent_disclosure(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Paper", csl_json={"title": "Paper"})
        persist_transparency(conn, pid, [_Chunk(_OPEN_TEXT)])
        assert "data_availability" in _fact_keys(conn, pid)
        # re-run over text with no disclosures — the stale FACT is superseded, the status flips
        persist_transparency(conn, pid, [_Chunk(_BARE_TEXT)])
        assert _fact_keys(conn, pid) == set()
        assert _statuses(conn, pid)["data_availability"] == "not-detected"
    engine.dispose()


def test_rerun_idempotent_no_churn(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Paper", csl_json={"title": "Paper"})
        persist_transparency(conn, pid, [_Chunk(_OPEN_TEXT)])
        first = _fact_keys(conn, pid)
        persist_transparency(conn, pid, [_Chunk(_OPEN_TEXT)])
        assert _fact_keys(conn, pid) == first  # same content_keys → unchanged
        # one status row per disclosure (no duplication on the unique constraint)
        assert len(_statuses(conn, pid)) == 7
    engine.dispose()


def test_count_transparency_review(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        open_pid = create_paper(conn, title="Open", csl_json={"title": "Open"})
        bare_pid = create_paper(conn, title="Bare", csl_json={"title": "Bare"})
        persist_transparency(conn, open_pid, [_Chunk(_OPEN_TEXT)])
        persist_transparency(conn, bare_pid, [_Chunk(_BARE_TEXT)])
        # only the bare paper has data-availability not-detected
        assert count_transparency_review(conn, "data_availability") == 1
        # both papers lack a preregistration disclosure
        assert count_transparency_review(conn, "preregistration") == 2
        # registration is n/a for both (non-trial) → not in the not-detected queue
        assert count_transparency_review(conn, "registration") == 0
    engine.dispose()


def test_facts_are_facts_only(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Open", csl_json={"title": "Open"})
        persist_transparency(conn, pid, [_Chunk(_OPEN_TEXT)])
        found = get_paper_findings(conn, pid)
        assert found["candidates"] == []  # transparency emits no candidates
        for f in found["facts"]:
            assert f["kind"] == "fact" and f["review_state"] is None
    engine.dispose()


# --- the batch endpoint + the review-queue filters -----------------------------------------------------------------


def _chunk_paper(conn, title, checksum, text):
    pid = create_paper(conn, title=title, csl_json={"title": title})
    att = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="managed",
        availability="available",
        checksum=checksum,
        content_type="application/pdf",
    )
    create_chunk(
        conn,
        paper_id=pid,
        attachment_id=att,
        text=text,
        page_start=1,
        page_end=1,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="x",
        extraction_version="1",
        chunking_strategy="s",
        chunk_version="v1",
        source_attachment_checksum=checksum,
    )
    return pid


_UPON_REQUEST_TEXT = "Data are available from the corresponding author upon reasonable request."
_TRIAL_TEXT = "We ran a randomized controlled trial comparing two treatments in 120 patients."


def _run_batch(client):
    started = client.post("/methods/transparency/run")
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/methods/transparency/run/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result
    return result


def test_batch_run_persists_then_review_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _chunk_paper(conn, "Open paper", "op", _OPEN_TEXT)  # data + code + COI + funding
        _chunk_paper(conn, "Bare paper", "ba", _BARE_TEXT)  # nothing disclosed
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    result = _run_batch(client)
    assert result["summary"] == {"total": 2, "with_disclosures": 1}

    # the review queue: only the bare paper lacks a data-availability disclosure (the open one is excluded)
    q = client.get("/papers", params={"signal": "transparency-data-not-detected"}).json()
    assert [p["title"] for p in q] == ["Bare paper"]
    # the summary drives the chip
    assert client.get("/methods/transparency/summary").json()["data_not_detected"] == 1
    # both papers lack preregistration → both in that review queue
    prereg = client.get("/papers", params={"signal": "transparency-preregistration-not-detected"}).json()
    assert {p["title"] for p in prereg} == {"Open paper", "Bare paper"}
    assert client.get("/methods/transparency/run/nope").status_code == 404


def test_registration_filter_excludes_non_trial_and_upon_request_is_present(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _chunk_paper(conn, "Non-trial", "nt", _BARE_TEXT)  # registration n/a (non-trial)
        _chunk_paper(conn, "Unregistered trial", "ut", _TRIAL_TEXT)  # registration not-detected (a trial, no reg)
        _chunk_paper(conn, "Upon-request paper", "ur", _UPON_REQUEST_TEXT)  # upon_request present
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    _run_batch(client)

    # registration review queue = only the trial that didn't register (the non-trial paper's n/a is excluded)
    reg = client.get("/papers", params={"signal": "transparency-registration-not-detected"}).json()
    assert [p["title"] for p in reg] == ["Unregistered trial"]
    # upon_request filter is the PRESENT case (a weaker-openness prompt), not a "not detected" queue
    ur = client.get("/papers", params={"signal": "transparency-upon-request"}).json()
    assert [p["title"] for p in ur] == ["Upon-request paper"]
