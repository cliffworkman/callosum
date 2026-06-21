"""Tests for statcheck (inc 95) — deterministic NHST p-value recomputation. Hermetic (no network, no LLM).
The crux is correctness: a correctly-rounded / one-tailed result must NOT be flagged (no false positives)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.methods.statcheck import recompute_p, run_statcheck
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper, list_papers
from app.backend.persistence.schema import open_science_signals
from app.backend.persistence.signals_repo import get_statcheck_summary, store_statcheck


def _chunk(text, page=1):
    return {"text": text, "page_start": page}


def test_consistent_t():
    rep = run_statcheck([_chunk("There was a significant effect, t(28) = 2.10, p = .04, overall.")])
    assert rep.checked == 1
    r = rep.results[0]
    assert r.test_type == "t" and r.consistency == "consistent"
    assert abs(r.computed_p - 0.045) < 0.01  # ~.0448


def test_inconsistent_same_significance():
    # computed ~.045 (significant); reported .001 (also significant) → value wrong, decision unchanged
    rep = run_statcheck([_chunk("t(28) = 2.10, p = .001")])
    assert rep.results[0].consistency == "inconsistent"
    assert rep.inconsistent == 1 and rep.decision_errors == 0


def test_decision_error():
    # t = 1.5 → computed ~.14 (non-significant), but reported p = .04 (significant) → the decision flips
    rep = run_statcheck([_chunk("t(28) = 1.5, p = .04")])
    assert rep.results[0].consistency == "decision-error"
    assert rep.decision_errors == 1 and rep.inconsistent == 0


def test_correct_rounding_not_flagged():
    # the recomputation must account for the stat's rounding — a correctly-rounded p is consistent
    assert run_statcheck([_chunk("t(28) = 2.10, p = .045")]).results[0].consistency == "consistent"


def test_one_tailed_not_flagged():
    # one-tailed p ~ .022 — a two-tailed-only check would false-flag; the one-tailed reading is consistent
    assert run_statcheck([_chunk("t(28) = 2.10, p = .02")]).results[0].consistency == "consistent"


def test_all_forms_detected():
    text = "F(2, 45) = 3.10, p = .05; r(30) = .42, p = .02; χ2(1) = 5.20, p = .02; z = 2.10, p = .04"
    rep = run_statcheck([_chunk(text)])
    assert {r.test_type for r in rep.results} == {"F", "r", "chi2", "z"}


def test_no_statistics_text():
    rep = run_statcheck([_chunk("Prose about treatment and weighting, with no inline statistics at all.")])
    assert rep.checked == 0 and rep.results == []


def test_page_provenance_from_chunk():
    rep = run_statcheck([_chunk("introduction prose", 1), _chunk("Results: t(10) = 2.0, p = .07.", 5)])
    assert rep.checked == 1 and rep.results[0].page == 5


def test_recompute_p_known_values():
    assert abs(recompute_p("t", 2.048, 28, None) - 0.05) < 0.01  # critical t(28) ≈ 2.048 → p ≈ .05
    assert abs(recompute_p("z", 1.96, 0, None) - 0.05) < 0.005  # z = 1.96 → p ≈ .05
    assert recompute_p("r", 1.5, 10, None) is None  # |r| ≥ 1 is degenerate → None, not a crash


def test_statcheck_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Stats Paper", csl_json={"type": "article-journal", "title": "Stats Paper"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            checksum="ck1",
            content_type="application/pdf",
        )
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="In the results, t(28) = 1.5, p = .04 and t(28) = 2.10, p = .04.",
            page_start=3,
            page_end=3,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="x",
            extraction_version="1",
            chunking_strategy="s",
            chunk_version="v1",
            source_attachment_checksum="ck1",
        )
        empty_id = create_paper(conn, title="No Text", csl_json={"title": "No Text"})  # metadata-only

    client = TestClient(create_app(db_url=temp_db_url))
    data = client.get(f"/papers/{paper_id}/statcheck").json()
    assert data["checked"] == 2 and data["decision_errors"] == 1  # the t=1.5/p=.04 flips significance
    assert all(r["page"] == 3 for r in data["results"])  # page provenance from the chunk

    assert client.get(f"/papers/{empty_id}/statcheck").json() == {  # no chunks → honest empty, not an error
        "checked": 0,
        "inconsistent": 0,
        "decision_errors": 0,
        "results": [],
    }
    assert client.get("/papers/999999/statcheck").status_code == 404


def _stat_chunk(conn, title, checksum, text):
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


def test_store_statcheck_upserts(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        store_statcheck(conn, pid, checked=5, inconsistent=2, decision_errors=1)
        assert get_statcheck_summary(conn, pid)["status"] == "inconsistent"
        store_statcheck(conn, pid, checked=5, inconsistent=0, decision_errors=0)  # re-run, now clean
        assert get_statcheck_summary(conn, pid)["status"] == "consistent"  # status flips
        rows = list(conn.execute(select(open_science_signals).where(open_science_signals.c.paper_id == pid)))
        assert len(rows) == 1  # OR REPLACE → exactly one row, never a duplicate


def test_list_papers_signal_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        good = create_paper(conn, title="Good", csl_json={"title": "Good"})
        bad = create_paper(conn, title="Bad", csl_json={"title": "Bad"})
        store_statcheck(conn, good, checked=3, inconsistent=0, decision_errors=0)
        store_statcheck(conn, bad, checked=3, inconsistent=1, decision_errors=0)
        assert [r["id"] for r in list_papers(conn, signal="statcheck-inconsistent")] == [bad]
        assert {r["id"] for r in list_papers(conn, signal="bogus")} == {good, bad}  # unknown → ignored (no filter)


def test_statcheck_batch_run_then_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _stat_chunk(conn, "Bad Stats", "b", "We found t(28) = 1.5, p = .04.")  # decision error
        _stat_chunk(conn, "Good Stats", "g", "We found t(28) = 2.10, p = .04.")  # consistent
        create_paper(conn, title="No Stats", csl_json={"title": "No Stats"})  # metadata-only → not flagged
    client = TestClient(create_app(db_url=temp_db_url))
    started = client.post("/methods/statcheck/run")
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/methods/statcheck/run/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result
    assert result["summary"] == {"total": 3, "checked": 2, "flagged": 1}
    flagged = client.get("/papers", params={"signal": "statcheck-inconsistent"}).json()
    assert [p["title"] for p in flagged] == ["Bad Stats"]  # only the inconsistent paper, never a rank
    assert client.get("/methods/statcheck/summary").json()["flagged"] == 1  # drives the library "N flagged" chip
    assert client.get("/methods/statcheck/run/nope").status_code == 404
