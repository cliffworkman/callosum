"""Transparency persistence producer (backlog #44 inc 1b, inc 251).

Hermetic (a throwaway DB + a real paper row for the FK + fake chunks): a present disclosure → a findings-FACT + a
`detected` status; a not-found → NO fact + `not-detected`; an n/a → NO fact + `not-applicable`; re-run idempotence
(a now-absent disclosure supersedes its FACT + flips its status); the review-queue count; and the A-A pin (no FACT is
ever written for a non-present disclosure — silence≠certificate).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.backend.methods.transparency_findings import persist_transparency
from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import get_paper_findings
from app.backend.persistence.repository import create_paper
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
