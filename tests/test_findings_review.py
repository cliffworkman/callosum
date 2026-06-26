"""inc 133 — statcheck emits CANDIDATE findings + the unified needs-review filter."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import (
    get_paper_findings,
    set_review_state,
    upsert_findings,
)
from app.backend.persistence.repository import (
    create_attachment,
    create_chunk,
    create_paper,
    list_papers,
)


def _stat_paper(conn, title, checksum, text) -> int:
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
        page_start=3,
        page_end=3,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="x",
        extraction_version="1",
        chunking_strategy="s",
        chunk_version="v1",
        source_attachment_checksum=checksum,
    )
    return pid


# ---- the needs-review filter (pure) ----------------------------------------


def test_needs_review_filter_returns_only_unreviewed_candidates(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
        b = create_paper(conn, title="B", csl_json={"title": "B"})
        c = create_paper(conn, title="C", csl_json={"title": "C"})
        upsert_findings(conn, a, "statcheck", [{"kind": "candidate", "payload": {"desc": "review me"}}])
        upsert_findings(
            conn, b, "retraction", [{"kind": "fact", "payload": {"status": "retracted"}}]
        )  # fact, not reviewable
        upsert_findings(conn, c, "statcheck", [{"kind": "candidate", "payload": {"desc": "then reviewed"}}])
        c_cand_id = get_paper_findings(conn, c)["candidates"][0]["id"]
        set_review_state(conn, c_cand_id, "noted")  # C reviewed → out of the queue
        ids = {r["id"] for r in list_papers(conn, finding="needs-review")}
        unknown = {r["id"] for r in list_papers(conn, finding="bogus")}  # unknown → no filter
    engine.dispose()
    assert ids == {a}  # only A: B is a fact (not a candidate), C is reviewed
    assert {a, b, c} <= unknown


# ---- statcheck batch emits candidates --------------------------------------


def test_statcheck_batch_emits_candidate_and_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        bad = _stat_paper(conn, "Bad Stats", "b", "We found t(28) = 1.5, p = .04.")  # a decision error → flagged
        good = _stat_paper(conn, "Good Stats", "g", "We found t(28) = 2.10, p = .04.")  # consistent
    client = TestClient(create_app(db_url=temp_db_url))
    started = client.post("/methods/statcheck/run")
    job_id = started.json()["job_id"]
    for _ in range(30):
        if client.get(f"/methods/statcheck/run/{job_id}").json()["status"] in ("done", "error"):
            break

    with engine.begin() as conn:
        bad_findings = get_paper_findings(conn, bad)
        good_findings = get_paper_findings(conn, good)
    engine.dispose()

    assert len(bad_findings["candidates"]) == 1
    cand = bad_findings["candidates"][0]
    assert cand["source"] == "statcheck" and cand["review_state"] == "unreviewed"
    assert "inconsistenc" in cand["payload"]["desc"] and cand["payload"]["decision_errors"] == 1
    assert cand["payload"]["page"] == 3  # the flagged result's page → "show in paper"
    assert good_findings["candidates"] == []  # a consistent paper gets no statcheck finding

    # the unified needs-review filter narrows to the flagged paper
    review = client.get("/papers", params={"finding": "needs-review"}).json()
    assert [p["title"] for p in review] == ["Bad Stats"]


def test_statcheck_candidate_preserved_when_reviewed_then_rerun(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        bad = _stat_paper(conn, "Bad Stats", "b", "We found t(28) = 1.5, p = .04.")
    client = TestClient(create_app(db_url=temp_db_url))

    def run_batch():
        jid = client.post("/methods/statcheck/run").json()["job_id"]
        for _ in range(30):
            if client.get(f"/methods/statcheck/run/{jid}").json()["status"] in ("done", "error"):
                return

    run_batch()
    with engine.begin() as conn:
        cand_id = get_paper_findings(conn, bad)["candidates"][0]["id"]
        set_review_state(conn, cand_id, "noted")  # the user triages it
    run_batch()  # re-run with the same result
    with engine.begin() as conn:
        cands = get_paper_findings(conn, bad)["candidates"]
    engine.dispose()
    assert len(cands) == 1 and cands[0]["id"] == cand_id and cands[0]["review_state"] == "noted"
