from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import (
    findings_overview,
    get_finding_dict,
    get_paper_findings,
    set_review_state,
    upsert_findings,
)
from app.backend.persistence.repository import create_paper


def _paper(conn, title="P") -> int:
    return create_paper(conn, title=title, csl_json={"title": title})


FACT = {"kind": "fact", "payload": {"label": "retracted (demo)"}}
CAND = {"kind": "candidate", "tier": "primary", "payload": {"desc": "reported t(28)=2.10, p=.02", "page": 4}}


def test_upsert_inserts_fact_and_candidate(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn)
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        data = get_paper_findings(conn, pid)
    engine.dispose()
    assert len(data["facts"]) == 1 and data["facts"][0]["review_state"] is None
    assert len(data["candidates"]) == 1 and data["candidates"][0]["review_state"] == "unreviewed"
    assert data["candidates"][0]["tier"] == "primary"


def test_upsert_is_idempotent_and_preserves_reviews(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn)
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        cand_id = get_paper_findings(conn, pid)["candidates"][0]["id"]
        assert set_review_state(conn, cand_id, "confirmed") == "ok"
        upsert_findings(conn, pid, "demo", [FACT, CAND])  # re-run with the SAME findings
        data = get_paper_findings(conn, pid)
    engine.dispose()
    assert len(data["candidates"]) == 1  # no duplicate
    assert data["candidates"][0]["id"] == cand_id  # same row
    assert data["candidates"][0]["review_state"] == "confirmed"  # review preserved across the re-run


def test_changed_payload_supersedes_old(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn)
        upsert_findings(conn, pid, "demo", [CAND])
        assert get_paper_findings(conn, pid)["candidates"][0]["payload"]["desc"].startswith("reported")
        changed = {"kind": "candidate", "tier": "primary", "payload": {"desc": "different", "page": 9}}
        upsert_findings(conn, pid, "demo", [changed])  # the old content_key is gone
        data = get_paper_findings(conn, pid)
    engine.dispose()
    assert len(data["candidates"]) == 1  # old superseded (deleted), one fresh
    # (SQLite may reuse the deleted rowid, so don't assert id inequality — assert the payload is the NEW one.)
    assert data["candidates"][0]["payload"]["desc"] == "different"
    assert data["candidates"][0]["review_state"] == "unreviewed"


def test_set_review_state_rules(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn)
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        fact_id = get_paper_findings(conn, pid)["facts"][0]["id"]
        cand_id = get_paper_findings(conn, pid)["candidates"][0]["id"]
        assert set_review_state(conn, fact_id, "confirmed") == "not-candidate"  # facts aren't reviewable
        assert set_review_state(conn, cand_id, "bogus") == "bad-state"
        assert set_review_state(conn, cand_id, "accepted") == "needs-reason"
        assert set_review_state(conn, cand_id, "accepted", "real but minor") == "ok"
        assert set_review_state(conn, 999999, "noted") == "not-found"
        d = get_finding_dict(conn, cand_id)
    engine.dispose()
    assert d["review_state"] == "accepted" and d["review_reason"] == "real but minor"


def test_findings_overview_counts(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "A")
        b = _paper(conn, "B")
        upsert_findings(conn, a, "demo", [FACT, CAND])  # 1 unreviewed, has fact
        upsert_findings(conn, b, "demo", [FACT])  # 0 unreviewed, has fact
        ov = {o["paper_id"]: o for o in findings_overview(conn)}
    engine.dispose()
    assert ov[a]["unreviewed_count"] == 1 and ov[a]["has_facts"] is True
    assert ov[b]["unreviewed_count"] == 0 and ov[b]["has_facts"] is True


def test_findings_endpoints(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Endpoint")
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        cand_id = get_paper_findings(conn, pid)["candidates"][0]["id"]
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    got = client.get(f"/papers/{pid}/findings").json()
    assert len(got["facts"]) == 1 and len(got["candidates"]) == 1
    assert client.get("/papers/999999/findings").status_code == 404

    ov = {o["paper_id"]: o for o in client.get("/findings/overview").json()}
    assert ov[pid]["unreviewed_count"] == 1 and ov[pid]["has_facts"] is True

    # accepted needs a reason; a valid review drops the count
    assert client.post(f"/findings/{cand_id}/review", json={"state": "accepted"}).status_code == 422
    ok = client.post(f"/findings/{cand_id}/review", json={"state": "accepted", "reason": "minor"})
    assert ok.status_code == 200 and ok.json()["review_state"] == "accepted"
    assert {o["paper_id"]: o for o in client.get("/findings/overview").json()}[pid]["unreviewed_count"] == 0
    assert client.post("/findings/999999/review", json={"state": "noted"}).status_code == 404


def test_get_paper_findings_source_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Multi-source")
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        other_cand = {"kind": "candidate", "tier": "speculative", "payload": {"desc": "other-source candidate"}}
        upsert_findings(conn, pid, "analytic-flexibility", [other_cand])

        unfiltered = get_paper_findings(conn, pid)
        af_only = get_paper_findings(conn, pid, source="analytic-flexibility")
        demo_only = get_paper_findings(conn, pid, source="demo")
    engine.dispose()

    assert len(unfiltered["facts"]) == 1 and len(unfiltered["candidates"]) == 2  # both sources, unfiltered
    assert len(af_only["facts"]) == 0 and len(af_only["candidates"]) == 1
    assert af_only["candidates"][0]["source"] == "analytic-flexibility"
    assert len(demo_only["facts"]) == 1 and len(demo_only["candidates"]) == 1
    assert demo_only["candidates"][0]["source"] == "demo"


def test_findings_endpoint_source_query_param(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Endpoint source filter")
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        other_cand = {"kind": "candidate", "tier": "speculative", "payload": {"desc": "other-source candidate"}}
        upsert_findings(conn, pid, "analytic-flexibility", [other_cand])
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    # No source param: unchanged, backward-compatible behavior -- both sources' candidates come back.
    got = client.get(f"/papers/{pid}/findings").json()
    assert len(got["facts"]) == 1 and len(got["candidates"]) == 2

    filtered = client.get(f"/papers/{pid}/findings", params={"source": "analytic-flexibility"}).json()
    assert len(filtered["facts"]) == 0 and len(filtered["candidates"]) == 1
    assert filtered["candidates"][0]["payload"]["desc"] == "other-source candidate"
