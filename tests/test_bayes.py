"""Tests for the Bayesian auditor (inc 241) — deterministic default-JZS Bayes-factor recomputation.
Hermetic (no network, no LLM). The JZS math is anchored to the published/pingouin value; extraction + the
reproduce-or-flag logic errs toward "reproduced" (the non-accusatory direction)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.bayes import _normalize_bf10, jzs_bf10, run_bayes
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper


def _chunk(text, page=1):
    return {"text": text, "page_start": page}


def test_jzs_two_sample_anchor():
    # pingouin bayesfactor_ttest(3.5, 20, 20) = 26.743 (two-sample: n_eff = 10, df = 38)
    assert abs(jzs_bf10(3.5, n=10, df=38) - 26.743) < 0.05


def test_jzs_monotone_sanity():
    assert jzs_bf10(0.1, n=30, df=29) < 1.0  # t ≈ 0 → favors the null
    assert jzs_bf10(5.0, n=30, df=29) > 100.0  # a large t → strong evidence for H1
    assert jzs_bf10(0.0, n=10, df=9) < 1.0
    assert jzs_bf10(2.0, n=10, df=-1) is None  # degenerate df → None, never a crash


def test_normalize_bf10():
    assert _normalize_bf10(None, 3.0) == 3.0  # bare "BF" assumed BF10
    assert _normalize_bf10("10", 3.0) == 3.0
    assert abs(_normalize_bf10("01", 4.0) - 0.25) < 1e-9  # BF01 inverted
    assert _normalize_bf10("10", 0.0) is None  # non-positive → skip


def test_reproduces_paired_ttest():
    # t(19) → paired candidate BF10 ≈ 2.845; a reported 2.9 reproduces (within a factor of ~2)
    rep = run_bayes([_chunk("A paired test, t(19) = 2.53, p = .02, BF10 = 2.9, was decisive.")])
    assert rep.checked == 1 and rep.not_reproduced == 0
    r = rep.results[0]
    assert r.consistency == "reproduced" and r.matched_design == "paired"
    assert r.reported_bf10 == 2.9 and r.page == 1


def test_reproduces_two_sample():
    # t(38) = 3.5 → two-sample candidate ≈ 26.74; a reported 26.7 reproduces
    rep = run_bayes([_chunk("Between groups, t(38) = 3.50, BF10 = 26.7.")])
    assert rep.results[0].consistency == "reproduced"


def test_flags_a_gross_mismatch():
    # a reported BF10 that matches neither the paired nor the two-sample reading is flagged
    rep = run_bayes([_chunk("t(19) = 2.53, BF10 = 500.")])
    assert rep.checked == 1 and rep.not_reproduced == 1
    r = rep.results[0]
    assert r.consistency == "not-reproduced" and r.matched_design is None


def test_scientific_notation_and_bf01():
    # BF10 in scientific form; and a BF01 (inverted to BF10) both parse
    rep = run_bayes([_chunk("Overwhelming, t(19) = 2.53, BF10 = 2.9e0.")])
    assert rep.results[0].reported_bf10 == 2.9
    rep2 = run_bayes([_chunk("t(19) = 2.53, BF01 = 0.34.")])  # → BF10 ≈ 2.94 → reproduces (paired ≈ 2.845)
    assert abs(rep2.results[0].reported_bf10 - 2.941) < 0.01
    assert rep2.results[0].consistency == "reproduced"


def test_bf_without_adjacent_t_is_not_checked():
    # a BF with no t-stat within the window is invisible (honest coverage — never guessed)
    assert run_bayes([_chunk("The evidence was strong (BF10 = 12.0).")]).checked == 0


def test_no_bayes_factors_text():
    assert run_bayes([_chunk("Prose about the design and sampling, with no statistics.")]).checked == 0


def test_bayes_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Bayes Paper", csl_json={"type": "article-journal", "title": "Bayes Paper"})
        att = create_attachment(
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
            attachment_id=att,
            text="The effect was reliable, t(19) = 2.53, p = .02, BF10 = 2.9.",
            page_start=4,
            page_end=4,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="x",
            extraction_version="1",
            chunking_strategy="s",
            chunk_version="v1",
            source_attachment_checksum="ck1",
        )
        empty_id = create_paper(conn, title="No Text", csl_json={"title": "No Text"})  # metadata-only

    client = TestClient(create_app(db_url=temp_db_url))
    data = client.get(f"/papers/{paper_id}/bayes").json()
    assert data["checked"] == 1 and data["not_reproduced"] == 0
    assert data["results"][0]["page"] == 4 and data["results"][0]["consistency"] == "reproduced"
    assert data["prior_scale"] == round((2**0.5) / 2, 4)

    assert client.get(f"/papers/{empty_id}/bayes").json() == {  # no chunks → honest empty, not an error
        "checked": 0,
        "not_reproduced": 0,
        "prior_scale": round((2**0.5) / 2, 4),
        "results": [],
    }
    assert client.get("/papers/999999/bayes").status_code == 404
