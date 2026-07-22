"""Tests for the Bayesian auditor (inc 241) — deterministic default-JZS Bayes-factor recomputation.
Hermetic (no network, no LLM). The JZS math is anchored to the published/pingouin value; extraction + the
reproduce-or-flag logic errs toward "reproduced" (the non-accusatory direction)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.bayes import (
    BayesCompleteness,
    BayesReport,
    BayesResult,
    CompletenessItem,
    _normalize_bf10,
    apply_bayes,
    audit_completeness,
    corr_bf10,
    jzs_bf10,
    run_bayes,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import get_paper_findings
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.signals_repo import count_bayes_flagged, get_bayes_summary


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


# ── SP3 (inc 243): Pearson-correlation Bayes factors ──


def test_corr_bf10_anchor():
    # verified against pingouin bayesfactor_pearson: (0.6, 20) = 10.634, (0.5, 30) = 9.904, (0.0, 40) = 0.197
    assert abs(corr_bf10(0.6, 20) - 10.6336) < 0.01
    assert abs(corr_bf10(0.5, 30) - 9.90396) < 0.01
    assert abs(corr_bf10(0.0, 40) - 0.196932) < 0.001
    assert corr_bf10(1.5, 30) is None  # |r| > 1 → None
    assert corr_bf10(0.4, 2) is None  # n < 3 → None (df < 1)


def test_reproduces_correlation():
    # r(58) → n = 60; corr_bf10(.42, 60) ≈ 37.39; a reported 37.4 reproduces (single, unambiguous recompute)
    rep = run_bayes([_chunk("There was a correlation, r(58) = .42, p < .001, BF10 = 37.4.")])
    assert rep.checked == 1 and rep.not_reproduced == 0
    r = rep.results[0]
    assert r.consistency == "reproduced" and r.matched_design == "correlation"
    assert abs(r.computed_correlation - 37.39) < 0.1
    assert r.computed_paired is None and r.computed_two_sample is None


def test_flags_a_correlation_mismatch():
    # a reported correlation BF that doesn't reproduce under the default prior is flagged
    rep = run_bayes([_chunk("r(58) = .42, BF10 = 900.")])
    assert rep.checked == 1 and rep.not_reproduced == 1
    assert rep.results[0].consistency == "not-reproduced" and rep.results[0].matched_design is None


def test_correlation_leading_dot_and_negative():
    # a leading-dot r value parses; a negative r reproduces the same (BF uses r²)
    rep = run_bayes([_chunk("A negative association, r(58) = -.42, BF10 = 37.4.")])
    assert rep.results[0].consistency == "reproduced" and rep.results[0].matched_design == "correlation"


def test_nearest_statistic_wins_correlation_over_t():
    # a t-stat far away, an r-stat adjacent to the BF → the correlation recompute is used, not the t-test
    text = "t(30) = 1.1 " + ("x" * 90) + " and here r(58) = .42, BF10 = 37.4"
    rep = run_bayes([_chunk(text)])
    assert rep.results[0].matched_design == "correlation"


# ── SP2: the Tier-2 completeness/coherence checklist ──


def _items(comp):
    return {i.key: i for i in comp.items}


def test_completeness_gated_on_bayesian():
    # a non-Bayesian paper is not audited (else every paper "fails" the checklist)
    comp = audit_completeness([_chunk("An OLS regression, F(2, 45) = 3.1, p = .05, with robust standard errors.")])
    assert comp.is_bayesian is False and comp.items == []


def test_completeness_closed_form_bf():
    # a closed-form default-BF paper: prior stated (Cauchy), convergence N/A (no chains), no sensitivity analysis
    comp = audit_completeness([_chunk("A Bayesian t-test with a Cauchy prior (scale 0.707); t(19) = 2.5, BF10 = 3.4.")])
    assert comp.is_bayesian is True
    items = _items(comp)
    assert items["prior"].status == "present" and items["prior"].evidence
    assert items["convergence"].status == "not-applicable"  # no MCMC → not "missing"
    assert items["sensitivity"].status == "not-found"


def test_completeness_mcmc_convergence_coherence_flag():
    # an MCMC paper reporting a breaching R-hat → a coherence flag (not "missing"), with the value + convention noted
    comp = audit_completeness(
        [
            _chunk(
                "A brms model (MCMC) with a normal prior. R-hat = 1.21 for all parameters. A prior sensitivity analysis "
                "confirmed robustness of the results to the prior."
            )
        ]
    )
    items = _items(comp)
    assert items["prior"].status == "present"
    assert items["convergence"].status == "coherence-flag" and "1.21" in items["convergence"].note
    assert items["sensitivity"].status == "present"


def test_completeness_default_prior_underspecified():
    # "default priors" with no scale is present-but-under-specified (the BARG point), not simply absent
    comp = audit_completeness([_chunk("We ran a Bayesian ANOVA in JASP with the default priors; BF10 = 8.")])
    prior = _items(comp)["prior"]
    assert prior.status == "present" and "under-specified" in prior.note


def test_completeness_mcmc_diagnostics_present_no_breach():
    # an MCMC paper reporting good diagnostics → present, no flag
    comp = audit_completeness(
        [
            _chunk(
                "We used Stan (posterior sampling). R-hat = 1.00 and the effective sample size exceeded 2000 for all "
                "parameters, with a weakly-informative prior."
            )
        ]
    )
    assert _items(comp)["convergence"].status == "present"


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
    # SP2: the paper (an inline BF10 present) is detectably Bayesian → the checklist runs
    assert data["completeness"]["is_bayesian"] is True
    assert {i["key"] for i in data["completeness"]["items"]} == {"prior", "convergence", "sensitivity"}
    assert data["completeness"]["advisories"] == []  # SP4: none for a clean paper

    empty = client.get(f"/papers/{empty_id}/bayes").json()  # no chunks → honest empty, not an error
    assert empty["checked"] == 0 and empty["results"] == []
    assert empty["completeness"] == {"is_bayesian": False, "items": [], "advisories": []}
    assert client.get("/papers/999999/bayes").status_code == 404


# ── SP4 (inc 244): Tier-3 textual-coherence advisory prompts ──


def _advkeys(comp):
    return {a.key for a in comp.advisories}


def test_advisory_credible_vs_confidence():
    # a Bayesian paper that mentions "confidence interval" but never "credible interval" → an advisory prompt
    comp = audit_completeness([_chunk("A Bayesian t-test (BF10 = 3). We report the 95% confidence interval [.1, .5].")])
    assert "credible-confidence" in _advkeys(comp)
    note = next(a for a in comp.advisories if a.key == "credible-confidence")
    assert "credible interval" in note.note and note.evidence


def test_advisory_credible_suppressed_when_both_present():
    # if the paper distinguishes them (says "credible interval" too), no advisory — conservative, prefer false negatives
    comp = audit_completeness(
        [_chunk("A Bayesian analysis (posterior). We report a 95% credible interval and a confidence interval.")]
    )
    assert "credible-confidence" not in _advkeys(comp)


def test_advisory_bf_direction():
    # a BF01 near a claim of support for the alternative → an advisory (BF01 favors the null)
    comp = audit_completeness(
        [_chunk("The Bayesian t-test gave BF01 = 6.2, which supported the alternative hypothesis.")]
    )
    assert "bf-direction" in _advkeys(comp)


def test_advisory_none_for_clean_bayesian():
    comp = audit_completeness([_chunk("A Bayesian t-test with a Cauchy prior, t(19) = 2.5, BF10 = 3.")])
    assert comp.advisories == []


def test_advisory_none_for_non_bayesian():
    # advisories run only on a Bayesian paper — a non-Bayesian paper mentioning a confidence interval is untouched
    comp = audit_completeness([_chunk("An OLS regression; we report the 95% confidence interval.")])
    assert comp.is_bayesian is False and comp.advisories == []


# --- backlog #23: apply_bayes combines two independent signals (F4 persistence) + the F1 batch/chip ---


def _clean_item(key):
    return CompletenessItem(key, key, "present", "evidence", 1, None)


def _gap_item(key):
    return CompletenessItem(key, key, "not-found", None, None, None)


def test_apply_bayes_flags_on_bf_mismatch_alone(temp_db_url):
    report = BayesReport(
        checked=1,
        not_reproduced=1,
        results=[BayesResult("t(19)=2.5, BF=500", 500.0, 1.2, 0.9, None, "not-reproduced", None, 1)],
    )
    completeness = BayesCompleteness(
        is_bayesian=True,
        items=[_clean_item("prior"), _clean_item("convergence"), _clean_item("sensitivity")],
        advisories=[],
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_bayes(conn, pid, report, completeness)
        summary = get_bayes_summary(conn, pid)
        findings = get_paper_findings(conn, pid)
    engine.dispose()
    assert summary["status"] == "flagged"
    assert len(findings["candidates"]) == 1
    assert "didn't reproduce" in findings["candidates"][0]["payload"]["desc"]


def test_apply_bayes_flags_on_completeness_gap_alone(temp_db_url):
    report = BayesReport(
        checked=1,
        not_reproduced=0,
        results=[BayesResult("t(19)=2.5, BF=3", 3.0, 3.1, None, None, "reproduced", "paired", 1)],
    )
    completeness = BayesCompleteness(
        is_bayesian=True,
        items=[_gap_item("prior"), _clean_item("convergence"), _clean_item("sensitivity")],
        advisories=[],
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_bayes(conn, pid, report, completeness)
        summary = get_bayes_summary(conn, pid)
        findings = get_paper_findings(conn, pid)
    engine.dispose()
    assert summary["status"] == "flagged"
    assert len(findings["candidates"]) == 1
    assert "not detected" in findings["candidates"][0]["payload"]["desc"]


def test_apply_bayes_clean_stores_signal_no_candidate(temp_db_url):
    report = BayesReport(
        checked=1,
        not_reproduced=0,
        results=[BayesResult("t(19)=2.5, BF=3", 3.0, 3.1, None, None, "reproduced", "paired", 1)],
    )
    completeness = BayesCompleteness(
        is_bayesian=True,
        items=[_clean_item("prior"), _clean_item("convergence"), _clean_item("sensitivity")],
        advisories=[],
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_bayes(conn, pid, report, completeness)
        summary = get_bayes_summary(conn, pid)
        findings = get_paper_findings(conn, pid)
    engine.dispose()
    assert summary["status"] == "clean"
    assert findings["candidates"] == []


def test_apply_bayes_not_bayesian_stores_nothing(temp_db_url):
    report = BayesReport(checked=0, not_reproduced=0, results=[])
    completeness = BayesCompleteness(is_bayesian=False, items=[], advisories=[])
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_bayes(conn, pid, report, completeness)
        summary = get_bayes_summary(conn, pid)
    engine.dispose()
    assert summary is None


def test_apply_bayes_reapply_is_idempotent(temp_db_url):
    report = BayesReport(checked=1, not_reproduced=1, results=[])
    completeness = BayesCompleteness(is_bayesian=True, items=[_gap_item("prior")], advisories=[])
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        apply_bayes(conn, pid, report, completeness)
        apply_bayes(conn, pid, report, completeness)
        findings = get_paper_findings(conn, pid)
        flagged = count_bayes_flagged(conn)
    engine.dispose()
    assert len(findings["candidates"]) == 1
    assert flagged == 1


def _seed_chunk_text(conn, paper_id, text):
    aid = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum=f"bayes-test-{paper_id}",
    )
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
        chunk_version=f"cv-{paper_id}",
        source_attachment_checksum=f"bayes-test-{paper_id}",
    )


def test_endpoint_persists_signal_on_ad_hoc_view(temp_db_url):
    # F4: simply viewing a paper's Bayes panel (the ad-hoc GET) persists — no batch run required first.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        _seed_chunk_text(conn, pid, "t(19) = 2.53, BF10 = 500.")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    with make_engine(temp_db_url).connect() as conn:
        assert get_bayes_summary(conn, pid) is None  # never viewed yet

    r = client.get(f"/papers/{pid}/bayes")
    assert r.status_code == 200 and r.json()["completeness"]["is_bayesian"] is True

    with make_engine(temp_db_url).connect() as conn:
        assert get_bayes_summary(conn, pid)["status"] == "flagged"
    assert client.get(f"/papers/{pid}/findings").json()["candidates"]


def test_batch_run_summary_and_library_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="A", csl_json={"title": "A"})
        _seed_chunk_text(conn, a, "t(19) = 2.53, BF10 = 500.")
        b = create_paper(conn, title="B", csl_json={"title": "B"})
        _seed_chunk_text(conn, b, "An OLS regression; we report the 95% confidence interval.")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    run = client.post("/methods/bayes/run")
    assert run.status_code == 202
    done = client.get(f"/methods/bayes/run/{run.json()['job_id']}").json()
    assert done["status"] == "done"
    assert done["summary"]["total"] == 2 and done["summary"]["detected"] == 1 and done["summary"]["flagged"] == 1

    assert client.get("/methods/bayes/summary").json()["flagged"] == 1
    ids = [p["id"] for p in client.get("/papers?signal=bayes-flagged").json()]
    assert a in ids and b not in ids
