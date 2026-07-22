"""Meta-analysis reporting auditor (backlog #36 consumer-side, inc 249).

Hermetic: a chunk is any object with `.text` + `.page_start`. Covers the gate (word + analytic cue), each of the 7
checks (present/not-found), the precondition scoping (search & selection → not-applicable for a within-study
mini-meta), the "not found ≠ missing" wording, the k>=10 caveat, the no-verdict/no-score contract, the identity
boundary (no statistical-computation import), inspectable evidence, and the read-only endpoint.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.metaanalysis import apply_meta_analysis, audit_meta_analysis
from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import get_paper_findings
from app.backend.persistence.repository import create_paper
from app.backend.persistence.signals_repo import count_meta_flagged, get_meta_summary


@dataclass
class _Chunk:
    text: str
    page_start: int | None = 1


def _audit(*texts):
    return audit_meta_analysis([_Chunk(t) for t in texts])


def _by_key(report, key):
    return next(c for c in report.checks if c.key == key)


# A realistic systematic-review meta-analysis paragraph exercising most cues.
_META_TEXT = (
    "We conducted a systematic review and meta-analysis. We searched PubMed, Embase, and Web of Science; "
    "inclusion criteria required randomized trials. Twelve included studies (k = 12) were pooled using a "
    "random-effects model (DerSimonian-Laird). Effect sizes were expressed as Hedges' g. Heterogeneity was "
    "assessed with I2 = 62% and tau-squared. Publication bias was examined with a funnel plot and Egger's test. "
    "A leave-one-out sensitivity analysis confirmed robustness."
)


def test_gate_off_for_non_meta_paper():
    r = _audit("We ran a randomized controlled trial of a new therapy in 40 patients.")
    assert r.is_meta_analysis is False
    assert r.checks == []


def test_gate_off_when_only_citing_a_meta_analysis():
    # mentions the word but no analytic cue → not itself a meta-analysis
    r = _audit("A recent meta-analysis by Smith et al. reported a benefit; our single trial extends it.")
    assert r.is_meta_analysis is False


def test_gate_on_and_all_present():
    r = _audit(_META_TEXT)
    assert r.is_meta_analysis is True
    for key in ("effect_size_metric", "model", "heterogeneity", "publication_bias", "sensitivity", "study_count"):
        assert _by_key(r, key).status == "present", key
    # search reporting present (databases + inclusion criteria named)
    assert _by_key(r, "search_selection").status == "present"


def test_each_check_not_found():
    # a meta-analysis paragraph that omits every reportable detail but still trips the gate
    bare = "We performed a meta-analysis and present the pooled effect in a forest plot."
    r = _audit(bare)
    assert r.is_meta_analysis is True
    for key in ("effect_size_metric", "model", "heterogeneity", "publication_bias", "sensitivity"):
        c = _by_key(r, key)
        assert c.status == "not-found", key
        assert "check the paper" in (c.note or "")
        assert "missing" not in (c.note or "").lower()


def test_publication_bias_note_has_k10_caveat():
    bare = "We performed a random-effects meta-analysis of Hedges' g."
    c = _by_key(_audit(bare), "publication_bias")
    assert c.status == "not-found"
    assert "10" in (c.note or "")  # the k >= 10 convention is mentioned, not a suppression


def test_search_selection_na_for_within_study_mini_meta():
    mini = (
        "We ran a random-effects internal meta-analysis of our 4 experiments, pooling the standardized mean "
        "difference across these 4 studies. Hedges' g was the effect-size metric."
    )
    c = _by_key(_audit(mini), "search_selection")
    assert c.status == "not-applicable"
    assert "systematic" in (c.note or "").lower()


def test_search_selection_not_found_when_systematic_but_unreported():
    r = _audit("We performed a random-effects meta-analysis of Hedges' g across the literature.")
    assert _by_key(r, "search_selection").status == "not-found"


def test_no_verdict_no_score():
    r = _audit(_META_TEXT)
    assert not hasattr(r, "score") and not hasattr(r, "grade")
    for c in r.checks:
        d = c.to_dict()
        assert "score" not in d and "grade" not in d
        assert c.status in ("present", "not-found", "not-applicable")


def test_no_statistical_computation_import():
    src = pathlib.Path("app/backend/methods/metaanalysis.py").read_text(encoding="utf-8")
    for banned in ("import numpy", "import scipy", "import statsmodels", "import sklearn", "import pandas"):
        assert banned not in src, f"identity boundary: {banned} must not appear"


def test_evidence_and_basis_on_present_row():
    c = _by_key(_audit(_META_TEXT), "heterogeneity")
    assert c.status == "present"
    assert c.evidence and c.basis and c.explainer
    assert c.page == 1


# --- the endpoint ------------------------------------------------------------


def test_endpoint_404_unknown(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers/99999/meta-analysis").status_code == 404


def test_endpoint_no_chunks_is_honest_empty(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="No text", csl_json={"title": "No text"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.get(f"/papers/{pid}/meta-analysis")
    assert r.status_code == 200
    body = r.json()
    assert body["is_meta_analysis"] is False and body["checks"] == []


# --- backlog #23: apply_meta_analysis (F4 persistence) + the F1 batch/chip ---

_INCOMPLETE_TEXT = "We performed a random-effects meta-analysis of Hedges' g across the literature."


def test_apply_meta_incomplete_stores_signal_and_candidate(temp_db_url):
    rep = _audit(_INCOMPLETE_TEXT)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_meta_analysis(conn, pid, rep)
        summary = get_meta_summary(conn, pid)
        findings = get_paper_findings(conn, pid)
        flagged = count_meta_flagged(conn)
    engine.dispose()
    assert summary["status"] == "incomplete"
    assert len(findings["candidates"]) == 1
    assert flagged == 1


def test_apply_meta_complete_stores_signal_no_candidate(temp_db_url):
    rep = _audit(_META_TEXT)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_meta_analysis(conn, pid, rep)
        summary = get_meta_summary(conn, pid)
        findings = get_paper_findings(conn, pid)
    engine.dispose()
    assert summary["status"] == "complete"
    assert findings["candidates"] == []


def test_apply_meta_not_meta_analysis_stores_nothing(temp_db_url):
    rep = audit_meta_analysis([_Chunk("We ran a randomized controlled trial of a new therapy in 40 patients.")])
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_meta_analysis(conn, pid, rep)
        summary = get_meta_summary(conn, pid)
    engine.dispose()
    assert summary is None


def test_apply_meta_reapply_is_idempotent(temp_db_url):
    rep = _audit(_INCOMPLETE_TEXT)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_meta_analysis(conn, pid, rep)
        apply_meta_analysis(conn, pid, rep)
        findings = get_paper_findings(conn, pid)
        flagged = count_meta_flagged(conn)
    engine.dispose()
    assert len(findings["candidates"]) == 1
    assert flagged == 1


def test_endpoint_persists_signal_on_ad_hoc_view(temp_db_url):
    # F4: simply viewing a paper's meta-analysis panel (the ad-hoc GET) persists — no batch run required first.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        _seed_chunks(conn, pid, _INCOMPLETE_TEXT)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    with make_engine(temp_db_url).connect() as conn:
        assert get_meta_summary(conn, pid) is None  # never viewed yet

    r = client.get(f"/papers/{pid}/meta-analysis")
    assert r.status_code == 200 and r.json()["is_meta_analysis"] is True

    with make_engine(temp_db_url).connect() as conn:
        assert get_meta_summary(conn, pid)["status"] == "incomplete"
    assert client.get(f"/papers/{pid}/findings").json()["candidates"]


def test_batch_run_summary_and_library_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
        _seed_chunks(conn, a, _INCOMPLETE_TEXT)
        b = create_paper(conn, title="B", csl_json={"title": "B"})
        _seed_chunks(conn, b, "We ran a randomized controlled trial of a new therapy in 40 patients.")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    run = client.post("/methods/meta-analysis/run")
    assert run.status_code == 202
    done = client.get(f"/methods/meta-analysis/run/{run.json()['job_id']}").json()
    assert done["status"] == "done"
    assert done["summary"]["total"] == 2 and done["summary"]["detected"] == 1 and done["summary"]["incomplete"] == 1

    assert client.get("/methods/meta-analysis/summary").json()["incomplete"] == 1
    ids = [p["id"] for p in client.get("/papers?signal=meta-incomplete").json()]
    assert a in ids and b not in ids


def _seed_chunks(conn, paper_id, *texts):
    from app.backend.persistence.repository import create_attachment, create_chunk

    checksum = f"meta-test-{paper_id}"
    aid = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum=checksum,
    )
    for text in texts:
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=aid,
            text=text,
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version=f"cv-{checksum}",
            source_attachment_checksum=checksum,
        )
