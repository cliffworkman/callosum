from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.pcurve import ALPHA, MIN_RELIABLE, compute_pcurve, run_pcurve
from app.backend.methods.statcheck import StatResult
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper


def _sr(p: float, page: int | None = 1) -> StatResult:
    return StatResult(
        raw=f"t(30) = 2.5, p = {p}",
        test_type="t",
        reported_p=f"p = {p}",
        computed_p=p,
        consistency="consistent",
        page=page,
    )


def test_right_skewed_set_is_significant() -> None:
    # Many very-small p-values → strong right skew → evidential value (Z < 0, right_skew_p < .05).
    out = compute_pcurve([0.001, 0.002, 0.005, 0.008, 0.01, 0.012])
    assert out["k_significant"] == 6
    assert out["right_skew_z"] is not None and out["right_skew_z"] < 0
    assert out["right_skew_p"] < ALPHA


def test_flat_uniform_set_is_not_significant() -> None:
    # p-values spread evenly across (0, .05) → flat → no evidential value (right_skew_p ≈ .5, not < .05).
    out = compute_pcurve([0.005, 0.015, 0.025, 0.035, 0.045])
    assert out["right_skew_p"] > ALPHA


def test_left_skewed_set_is_not_significant() -> None:
    # p-values clustered just under .05 → left skew → definitely not right-skewed.
    out = compute_pcurve([0.046, 0.047, 0.048, 0.049, 0.0495])
    assert out["right_skew_p"] > ALPHA


def test_k_zero_is_honest_empty() -> None:
    out = compute_pcurve([])
    assert out["k_significant"] == 0
    assert out["bins"] == []
    assert out["right_skew_z"] is None
    assert out["right_skew_p"] is None
    assert out["low_power"] is True


def test_excludes_nonsignificant_and_nonpositive() -> None:
    # Only .03 and .01 are 0 < p < .05; .06/.05/0/-.1 are excluded.
    out = compute_pcurve([0.06, 0.05, 0.0, -0.1, 0.03, 0.01])
    assert out["k_significant"] == 2


def test_low_power_flag_below_minimum() -> None:
    out = compute_pcurve([0.01, 0.02, 0.03])
    assert out["k_significant"] == 3
    assert out["low_power"] is True
    assert MIN_RELIABLE == 5


def test_bins_are_percentages_summing_to_100() -> None:
    # p ≤ .01 → bin0; (.01,.02] → bin1; … ; (.04,.05) → bin4.
    out = compute_pcurve([0.005, 0.008, 0.015, 0.025, 0.035, 0.045])
    assert len(out["bins"]) == 5
    assert abs(sum(out["bins"]) - 100.0) < 0.5
    assert out["bins"][0] > 0  # two values ≤ .01


def test_run_pcurve_over_statresults() -> None:
    # Two papers; significant tests are filtered + carried with provenance (paper_id, page, p, raw).
    per_paper = [
        (101, [_sr(0.001, page=3), _sr(0.20, page=4)]),  # .20 excluded (≥ .05)
        (102, [_sr(0.004, page=2), _sr(0.01, page=5), _sr(0.03, page=6)]),
    ]
    result = run_pcurve(per_paper)
    assert result.n_papers == 2
    assert result.k_total_extracted == 5
    assert result.k_significant == 4  # all but the .20
    assert {t.paper_id for t in result.included_tests} == {101, 102}
    assert all(0 < t.p < ALPHA for t in result.included_tests)
    assert result.note  # a non-empty coverage note


def test_run_pcurve_empty_selection_is_honest() -> None:
    result = run_pcurve([(1, [_sr(0.20)])])  # one paper, no significant test
    assert result.k_significant == 0
    assert result.bins == []
    assert "No significant" in result.note


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


def test_pcurve_endpoint_over_a_selection(temp_db_url) -> None:
    # Strongly- (but not extremely-) significant t/F results: their recomputed p is small but stays > 0 after
    # statcheck's 4-decimal rounding (p < ~.00005 would round to 0.0 and be conservatively excluded), and the
    # small p-values are strongly right-skewed → evidential value.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _seed_stats_paper(conn, "A", "cka", "Results: t(30) = 3.8, p < .001 and t(40) = 3.6, p < .001.")
        b = _seed_stats_paper(conn, "B", "ckb", "We found t(50) = 3.4, p = .001, t(25) = 3.5, p < .01, and F(1, 60) = 14.0, p < .001.")
    client = TestClient(create_app(db_url=temp_db_url))

    started = client.post("/methods/pcurve/run", json={"paper_ids": [a, b]})
    assert started.status_code == 202
    result = client.get(f"/methods/pcurve/run/{started.json()['job_id']}").json()

    assert result["status"] == "done"
    r = result["result"]
    assert r["n_papers"] == 2
    assert r["k_significant"] >= 3  # the strongly-significant tests
    assert r["right_skew_p"] < ALPHA  # strong right skew → evidential value
    assert {t["paper_id"] for t in r["included_tests"]} == {a, b}
    assert len(r["bins"]) == 5

    assert client.post("/methods/pcurve/run", json={"paper_ids": []}).status_code == 422
    assert client.get("/methods/pcurve/run/nope").status_code == 404
