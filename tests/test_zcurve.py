from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.statcheck import StatResult
from app.backend.methods.zcurve import MIN_RELIABLE_N, A, _power_two_sided, fit_zcurve, run_zcurve
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper


def _sr(p: float, page: int | None = 1) -> StatResult:
    return StatResult(
        raw=f"t(30) = 2.5, p = {p}",
        context=f"The analysis returned t(30) = 2.5, p = {p}.",
        test_type="t",
        reported_p=f"p = {p}",
        computed_p=p,
        consistency="consistent",
        page=page,
    )


def test_power_formula_matches_reference_component_powers() -> None:
    # z_to_power at the 7 fixed component means, verified against the reference zcurve R package's own
    # documented component powers (.05, .17, .85, .98, .999, .99997 for mu = 0, 1, 3, 4, 5, 6).
    got = _power_two_sided(np.array([0.0, 1.0, 3.0, 4.0, 5.0, 6.0]))
    assert abs(got[0] - 0.05) < 0.001
    assert abs(got[1] - 0.17) < 0.005
    assert abs(got[2] - 0.85) < 0.005
    assert abs(got[3] - 0.98) < 0.005
    assert abs(got[4] - 0.999) < 0.001
    assert abs(got[5] - 0.99997) < 0.0001


def test_fit_zcurve_recovers_homogeneous_high_power() -> None:
    # A homogeneous population (every conducted test has the same noncentrality) is the easy case: EDR and ERR
    # should both land close to that population's true two-sided power.
    rng = np.random.default_rng(42)
    true_mu = 4.0
    true_power = float(_power_two_sided(np.array([true_mu]))[0])
    raw_z = np.abs(rng.normal(loc=true_mu, scale=1.0, size=600))
    sig_z = raw_z[raw_z >= A]

    fit = fit_zcurve(sig_z.tolist(), bootstrap=50, rng=rng)
    assert fit is not None
    assert abs(fit.edr - true_power) < 0.05
    assert abs(fit.err - true_power) < 0.05
    assert fit.edr_ci is not None and fit.edr_ci[0] <= true_power <= fit.edr_ci[1]


def test_fit_zcurve_none_when_no_significant_values() -> None:
    assert fit_zcurve([]) is None


def test_run_zcurve_over_statresults() -> None:
    per_paper = [
        (101, [_sr(0.001, page=3), _sr(0.20, page=4)]),  # .20 excluded (>= .05)
        (102, [_sr(0.004, page=2), _sr(0.01, page=5), _sr(0.03, page=6)]),
    ]
    result = run_zcurve(per_paper, bootstrap=20)
    assert result.n_papers == 2
    assert result.k_total_extracted == 5
    assert result.k_significant == 4  # all but the .20
    assert {t.paper_id for t in result.included_tests} == {101, 102}
    assert all(0 < t.p < 0.05 for t in result.included_tests)
    assert all(t.z >= A for t in result.included_tests)
    assert result.odr == 4 / 5
    assert result.note  # a non-empty coverage note
    assert result.low_reliability is True  # 4 << MIN_RELIABLE_N


def test_run_zcurve_empty_selection_is_honest() -> None:
    result = run_zcurve([(1, [_sr(0.20)])])  # one paper, no significant test
    assert result.k_significant == 0
    assert result.edr is None
    assert result.err is None
    assert "No significant" in result.note


def test_low_reliability_threshold_is_300() -> None:
    assert MIN_RELIABLE_N == 300


def _seed_stats_paper(conn, title: str, checksum: str, text: str) -> int:
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
        page_start=2,
        page_end=2,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="x",
        extraction_version="1",
        chunking_strategy="s",
        chunk_version="v1",
        source_attachment_checksum=checksum,
    )
    return pid


def test_zcurve_endpoint_over_a_selection(temp_db_url) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _seed_stats_paper(conn, "A", "cka", "Results: t(30) = 3.8, p < .001 and t(40) = 3.6, p < .001.")
        b = _seed_stats_paper(
            conn, "B", "ckb", "We found t(50) = 3.4, p = .001, t(25) = 3.5, p < .01, and F(1, 60) = 14.0, p < .001."
        )
    client = TestClient(create_app(db_url=temp_db_url))

    started = client.post("/methods/zcurve/run", json={"paper_ids": [a, b]})
    assert started.status_code == 202
    result = client.get(f"/methods/zcurve/run/{started.json()['job_id']}").json()

    assert result["status"] == "done"
    r = result["result"]
    assert r["n_papers"] == 2
    assert r["k_significant"] >= 3  # the strongly-significant tests
    assert r["edr"] is not None and 0 <= r["edr"] <= 1
    assert r["err"] is not None and 0 <= r["err"] <= 1
    assert r["low_reliability"] is True  # far below MIN_RELIABLE_N at this scale
    assert {t["paper_id"] for t in r["included_tests"]} == {a, b}

    assert client.post("/methods/zcurve/run", json={"paper_ids": []}).status_code == 422
    assert client.get("/methods/zcurve/run/nope").status_code == 404
