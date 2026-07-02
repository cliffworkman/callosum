"""LMM-reporting completeness auditor (backlog #23, inc 247).

Hermetic: a chunk is any object with `.text` + `.page_start`. Covers the gate, each of the 7 checks
(present/not-found), the precondition scoping (ICC + missing-data → not-applicable when their precondition fails),
the "not found ≠ missing" wording, inspectable evidence, the identity boundary (no model-fitting import), and the
read-only endpoint.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.lmm import audit_lmm
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper


@dataclass
class _Chunk:
    text: str
    page_start: int | None = 1


def _audit(*texts):
    return audit_lmm([_Chunk(t) for t in texts])


# --- the pure auditor --------------------------------------------------------


def test_gate_off_for_non_lmm():
    rep = audit_lmm([_Chunk("We ran an ordinary least-squares regression of y on x.")])
    assert rep.is_lmm is False and rep.checks == []


def test_gate_on_and_random_effects_present():
    rep = _audit("We fit a linear mixed model with lmer: y ~ x + (1 | subject).")
    assert rep.is_lmm is True
    by = {c.key: c for c in rep.checks}
    assert by["random_effects"].status == "present" and by["random_effects"].evidence
    assert "Barr" in by["random_effects"].basis
    assert by["random_effects"].explainer  # the always-on literacy note is present


def test_df_and_convergence_and_estimation_present():
    rep = _audit(
        "A linear mixed-effects model (lme4) was fit by REML. Denominator df used the "
        "Kenward-Roger approximation. The model converged with no singular fit."
    )
    by = {c.key: c for c in rep.checks}
    assert by["df_method"].status == "present"
    assert by["convergence"].status == "present"
    assert by["estimation"].status == "present"


def test_missing_items_say_check_the_paper():
    rep = _audit("We fit a mixed-effects model of reaction time with random intercepts for subject.")
    by = {c.key: c for c in rep.checks}
    assert by["df_method"].status == "not-found"
    assert "check the paper" in (by["df_method"].note or "").lower()
    assert "missing" not in (by["df_method"].note or "").lower()  # never worded "missing"


def test_icc_not_applicable_without_clustering_claim():
    rep = _audit("A linear mixed model with a by-subject random intercept (repeated measures).")
    by = {c.key: c for c in rep.checks}
    assert by["icc"].status == "not-applicable" and "clustering" in (by["icc"].note or "").lower()


def test_icc_not_found_when_clustering_claimed_but_absent():
    rep = _audit("A multilevel model of students nested within schools; a random intercept per school.")
    by = {c.key: c for c in rep.checks}
    assert by["icc"].status == "not-found"


def test_missing_data_not_applicable_without_longitudinal_dropout():
    rep = _audit("A linear mixed model on a single cross-sectional dataset (one measurement per person).")
    by = {c.key: c for c in rep.checks}
    assert by["missing_data"].status == "not-applicable"


def test_missing_data_flagged_on_longitudinal_dropout_without_sensitivity():
    rep = _audit(
        "A longitudinal mixed-effects model over four repeated-measures visits. 22% of "
        "participants showed attrition by the final assessment."
    )
    by = {c.key: c for c in rep.checks}
    assert by["missing_data"].status == "not-found"
    assert "sensitivity" in (by["missing_data"].note or "").lower()
    assert "not a claim the analysis is wrong" in (by["missing_data"].note or "").lower()


def test_missing_data_present_when_sensitivity_reported():
    rep = _audit(
        "A longitudinal mixed model with dropout. We assessed robustness with a "
        "reference-based controlled-imputation sensitivity analysis."
    )
    by = {c.key: c for c in rep.checks}
    assert by["missing_data"].status == "present"


def test_r2_present():
    rep = _audit("A mixed model; marginal and conditional R2 were computed following Nakagawa.")
    by = {c.key: c for c in rep.checks}
    assert by["r2"].status == "present"


def test_no_status_is_a_verdict_or_score():
    # FLAG-not-ADJUDICATE: only present / not-found / not-applicable ever appear; no report-level aggregate/score.
    rep = _audit("A linear mixed model with (1 | subject), fit by REML; Satterthwaite df; converged.")
    assert all(c.status in ("present", "not-found", "not-applicable") for c in rep.checks)
    assert not hasattr(rep, "score") and not hasattr(rep, "grade")


def test_no_model_fitting_import():
    # The identity boundary: the module reads text and never fits a model.
    src = pathlib.Path("app/backend/methods/lmm.py").read_text(encoding="utf-8")
    for banned in ("import lme4", "import mice", "statsmodels", "scipy.optimize", "import numpy"):
        assert banned not in src, f"identity boundary: {banned} must not appear (reads text, never fits a model)"


# --- the endpoint ------------------------------------------------------------


def test_endpoint_404_unknown(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers/99999/lmm").status_code == 404


def test_endpoint_no_chunks_is_honest_empty(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="No text", csl_json={"title": "No text"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.get(f"/papers/{pid}/lmm")
    assert r.status_code == 200
    body = r.json()
    assert body["is_lmm"] is False and body["checks"] == []
