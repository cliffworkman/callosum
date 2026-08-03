"""Deterministic WIP tool-run, finding, and validity contracts."""

from __future__ import annotations

from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.backend.api import create_app


def _poll(client: TestClient, job_id: str) -> None:
    for _ in range(30):
        result = client.get(f"/wip/scan/{job_id}").json()
        if result["status"] in {"done", "error"}:
            assert result["status"] == "done"
            return
    raise AssertionError("scan did not finish")


def _setup(client: TestClient, folder: Path) -> tuple[int, int, int]:
    root = client.post(
        "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
    ).json()
    scan = client.post(f"/wip/watch-roots/{root['id']}/scan").json()
    _poll(client, scan["job_id"])
    manuscript_id = client.get("/wip/manuscripts").json()[0]["id"]
    file_id = client.get(f"/wip/manuscripts/{manuscript_id}/files").json()[0]["id"]
    assert (
        client.patch(
            f"/wip/manuscripts/{manuscript_id}/files/{file_id}",
            json={"is_primary": True},
        ).status_code
        == 200
    )
    return root["id"], manuscript_id, file_id


def test_statcheck_run_is_snapshot_bound_reviewable_and_hash_invalidated(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text("Results: t(18) = 2.10, p = .90.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    root_id, manuscript_id, _ = _setup(client, folder)

    empty = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()
    assert empty["tools"][0]["id"] == "statcheck"
    assert empty["tools"][1]["id"] == "transparency"
    assert empty["tools"][2]["id"] == "lmm"
    assert empty["tools"][3]["id"] == "bayes"
    assert empty["tools"][4]["id"] == "meta-analysis"
    assert empty["runs"] == []
    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/statcheck", json={})
    assert run.status_code == 200
    payload = run.json()
    assert payload["tool_id"] == "statcheck"
    assert payload["tool_version"] == "2"
    assert payload["validity"] == "current-with-findings"
    assert "No surfaced inconsistency never means" in payload["coverage"]
    assert payload["structured_result_json"]["checked"] == 1
    first_run_id = payload["id"]
    finding = payload["findings"][0]
    assert finding["kind"] == "candidate"
    assert finding["quote"] == "t(18) = 2.10, p = .90"
    assert finding["coordinate_precision"] is None

    reviewed = client.patch(f"/wip/findings/{finding['id']}", json={"disposition": "resolved"})
    assert reviewed.status_code == 200
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] == "current"

    draft.write_text("Results changed: t(18) = 2.10, p = .04.", encoding="utf-8")
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    _poll(client, scan["job_id"])
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] == "potentially-stale"

    rerun = client.post(f"/wip/manuscripts/{manuscript_id}/checks/statcheck", json={})
    assert rerun.status_code == 200
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] in {"current", "current-with-findings"}
    assert next(item for item in runs if item["id"] == first_run_id)["validity"] == "stale"


def test_statcheck_no_findings_states_coverage_not_cleanliness(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("No inline tests in this draft.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/statcheck", json={}).json()
    assert run["validity"] == "current"
    assert run["findings"] == []
    assert run["structured_result_json"]["checked"] == 0
    assert "No surfaced inconsistency never means the manuscript is clean." in run["coverage"]


def test_transparency_run_is_snapshot_bound_and_persists_positive_facts_only(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text(
        "Data are available at https://osf.io/abcd. Analysis code is available on GitHub. "
        "The authors declare no conflicts of interest. This work was funded by the NSF. "
        "The analysis plan was preregistered at AsPredicted.",
        encoding="utf-8",
    )
    client = TestClient(create_app(db_url=temp_db_url))
    root_id, manuscript_id, _ = _setup(client, folder)

    response = client.post(f"/wip/manuscripts/{manuscript_id}/checks/transparency", json={})

    assert response.status_code == 200
    run = response.json()
    assert run["tool_id"] == "transparency"
    assert run["tool_version"] == "1"
    assert run["validity"] == "current"
    assert "no result is a transparency score or judgment" in run["coverage"]
    result = run["structured_result_json"]
    assert len(result["checks"]) == 7
    assert result["present"] >= 5
    assert len(run["findings"]) == result["present"]
    assert all(finding["kind"] == "fact" for finding in run["findings"])
    assert all(finding["disposition"] is None for finding in run["findings"])
    assert all(finding["quote"] for finding in run["findings"])
    assert all(finding["coordinate_precision"] is None for finding in run["findings"])
    assert not any("not-detected" in finding["finding_type"] for finding in run["findings"])

    fact_id = run["findings"][0]["id"]
    rejected_review = client.patch(f"/wip/findings/{fact_id}", json={"disposition": "resolved"})
    assert rejected_review.status_code == 422
    assert rejected_review.json()["detail"] == "Only candidate findings have a review disposition"

    draft.write_text("The manuscript text changed completely.", encoding="utf-8")
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    _poll(client, scan["job_id"])
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] == "potentially-stale"


def test_transparency_no_detections_retains_coverage_without_negative_findings(
    temp_db_url: str, tmp_path: Path
) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("A short manuscript introduction.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/transparency", json={}).json()

    assert run["validity"] == "current"
    assert run["findings"] == []
    assert run["structured_result_json"]["present"] == 0
    statuses = {check["key"]: check["status"] for check in run["structured_result_json"]["checks"]}
    assert statuses["data_availability"] == "not-found"
    assert statuses["registration"] == "not-applicable"
    assert "'Not detected' never means absent" in run["coverage"]


def test_transparency_preserves_region_page_only_for_pdf_sources(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Data are available in the OSF repository.")
    document.save(draft)
    document.close()
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/transparency", json={}).json()

    data_check = next(check for check in run["structured_result_json"]["checks"] if check["key"] == "data_availability")
    data_fact = next(finding for finding in run["findings"] if finding["finding_type"].startswith("transparency-data"))
    assert data_check["page"] == 1
    assert data_check["coordinate_precision"] == "region"
    assert data_fact["coordinate_precision"] == "region"


def test_transparency_rejects_missing_manuscript_and_missing_primary_file(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    missing = client.post("/wip/manuscripts/999/checks/transparency", json={})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "WIP manuscript not found"
    missing_lmm = client.post("/wip/manuscripts/999/checks/lmm", json={})
    assert missing_lmm.status_code == 404
    assert missing_lmm.json()["detail"] == "WIP manuscript not found"
    missing_bayes = client.post("/wip/manuscripts/999/checks/bayes", json={})
    assert missing_bayes.status_code == 404
    assert missing_bayes.json()["detail"] == "WIP manuscript not found"
    missing_meta = client.post("/wip/manuscripts/999/checks/meta-analysis", json={})
    assert missing_meta.status_code == 404
    assert missing_meta.json()["detail"] == "WIP manuscript not found"

    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("Data are available in a repository.", encoding="utf-8")
    root = client.post(
        "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
    ).json()
    scan = client.post(f"/wip/watch-roots/{root['id']}/scan").json()
    _poll(client, scan["job_id"])
    manuscript_id = client.get("/wip/manuscripts").json()[0]["id"]

    no_primary = client.post(f"/wip/manuscripts/{manuscript_id}/checks/transparency", json={})
    assert no_primary.status_code == 422
    assert no_primary.json()["detail"] == "Select a primary manuscript file before creating a checkpoint"
    no_primary_lmm = client.post(f"/wip/manuscripts/{manuscript_id}/checks/lmm", json={})
    assert no_primary_lmm.status_code == 422
    assert no_primary_lmm.json()["detail"] == "Select a primary manuscript file before creating a checkpoint"
    no_primary_bayes = client.post(f"/wip/manuscripts/{manuscript_id}/checks/bayes", json={})
    assert no_primary_bayes.status_code == 422
    assert no_primary_bayes.json()["detail"] == "Select a primary manuscript file before creating a checkpoint"
    no_primary_meta = client.post(f"/wip/manuscripts/{manuscript_id}/checks/meta-analysis", json={})
    assert no_primary_meta.status_code == 422
    assert no_primary_meta.json()["detail"] == "Select a primary manuscript file before creating a checkpoint"


def test_lmm_run_is_snapshot_bound_and_persists_review_candidates(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text(
        "We fit a linear mixed-effects model with a random intercept for participant using REML. "
        "The model converged without a singular fit.",
        encoding="utf-8",
    )
    client = TestClient(create_app(db_url=temp_db_url))
    root_id, manuscript_id, _ = _setup(client, folder)

    response = client.post(f"/wip/manuscripts/{manuscript_id}/checks/lmm", json={})

    assert response.status_code == 200
    run = response.json()
    assert run["tool_id"] == "lmm"
    assert run["tool_version"] == "1"
    assert run["validity"] == "current-with-findings"
    assert "never runs a model" in run["coverage"]
    result = run["structured_result_json"]
    assert result["is_lmm"] is True
    assert len(result["checks"]) == 7
    assert result["present"] >= 3
    assert result["not_found"] >= 1
    assert len(run["findings"]) == result["not_found"]
    assert all(finding["kind"] == "candidate" for finding in run["findings"])
    assert all(finding["disposition"] == "open" for finding in run["findings"])
    assert all(finding["quote"] is None for finding in run["findings"])
    assert all(finding["finding_type"].endswith("-not-detected") for finding in run["findings"])
    assert all("not detected" in finding["context"].lower() for finding in run["findings"])
    assert all(check["coordinate_precision"] is None for check in result["checks"])

    for finding in run["findings"]:
        reviewed = client.patch(f"/wip/findings/{finding['id']}", json={"disposition": "resolved"})
        assert reviewed.status_code == 200
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] == "current"

    draft.write_text("We now report a different analysis.", encoding="utf-8")
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    _poll(client, scan["job_id"])
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] == "potentially-stale"


def test_lmm_gate_off_records_honest_receipt_without_findings(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("We ran an ordinary least-squares regression.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/lmm", json={}).json()

    assert run["validity"] == "current"
    assert run["findings"] == []
    assert run["structured_result_json"] == {
        "is_lmm": False,
        "present": 0,
        "not_found": 0,
        "not_applicable": 0,
        "checks": [],
    }
    assert "no checklist was applied" in run["result_summary"]
    assert "not proof of omission" in run["coverage"]


def test_lmm_preserves_region_page_only_for_pdf_evidence(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "A linear mixed model used a random intercept for participant and REML estimation.")
    document.save(draft)
    document.close()
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/lmm", json={}).json()

    random_check = next(check for check in run["structured_result_json"]["checks"] if check["key"] == "random_effects")
    assert random_check["status"] == "present"
    assert random_check["page"] == 1
    assert random_check["coordinate_precision"] == "region"


def test_bayes_run_persists_assumptions_receipt_and_conservative_candidates(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text(
        "We ran a Bayesian t-test with a Cauchy prior. The result was t(19) = 2.53, BF10 = 500. "
        "Posterior samples came from MCMC; R-hat = 1.21. We report a 95% confidence interval.",
        encoding="utf-8",
    )
    client = TestClient(create_app(db_url=temp_db_url))
    root_id, manuscript_id, _ = _setup(client, folder)

    response = client.post(f"/wip/manuscripts/{manuscript_id}/checks/bayes", json={})

    assert response.status_code == 200
    run = response.json()
    assert run["tool_id"] == "bayes"
    assert run["tool_version"] == "1"
    assert run["validity"] == "current-with-findings"
    assert "never fits a model or produces a correctness verdict or score" in run["coverage"]
    assert run["parameters_json"] == {
        "jzs_prior_scale": 0.7071,
        "correlation_prior_kappa": 1.0,
        "log10_tolerance": 0.3,
    }
    result = run["structured_result_json"]
    assert result["checked"] == 1
    assert result["not_reproduced"] == 1
    assert result["prior_scale"] == 0.7071
    assert result["results"][0]["consistency"] == "not-reproduced"
    assert result["results"][0]["coordinate_precision"] is None
    completeness = result["completeness"]
    assert completeness["is_bayesian"] is True
    assert {item["key"] for item in completeness["items"]} == {"prior", "convergence", "sensitivity"}
    assert next(item for item in completeness["items"] if item["key"] == "convergence")["status"] == "coherence-flag"
    assert {item["key"] for item in completeness["advisories"]} == {"credible-confidence"}

    # One BF mismatch + convergence coherence prompt + sensitivity miss + terminology advisory. Every row remains
    # reporter-reviewable info, never an objective severity or a claimed error.
    assert len(run["findings"]) == 4
    assert all(finding["kind"] == "candidate" for finding in run["findings"])
    assert all(finding["severity"] == "info" for finding in run["findings"])
    assert all(finding["disposition"] == "open" for finding in run["findings"])
    assert all(finding["coordinate_precision"] is None for finding in run["findings"])
    finding_types = {finding["finding_type"] for finding in run["findings"]}
    assert finding_types == {
        "bayes-factor-not-reproduced",
        "bayes-convergence-coherence-flag",
        "bayes-sensitivity-not-found",
        "bayes-advisory-credible-confidence",
    }
    mismatch = next(finding for finding in run["findings"] if finding["finding_type"] == "bayes-factor-not-reproduced")
    assert mismatch["quote"] == "t(19) = 2.53, BF10 = 500"
    assert mismatch["details_json"]["jzs_prior_scale"] == 0.7071
    assert "commonly explains a mismatch" in mismatch["context"]

    for finding in run["findings"]:
        assert client.patch(f"/wip/findings/{finding['id']}", json={"disposition": "resolved"}).status_code == 200
    assert client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"][0]["validity"] == "current"

    draft.write_text("The Bayesian analysis changed.", encoding="utf-8")
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    _poll(client, scan["job_id"])
    assert client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"][0]["validity"] == "potentially-stale"


def test_bayes_gate_off_records_receipt_without_findings(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("We ran an ordinary least-squares regression.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/bayes", json={}).json()

    assert run["validity"] == "current"
    assert run["findings"] == []
    assert run["structured_result_json"]["checked"] == 0
    assert run["structured_result_json"]["results"] == []
    assert run["structured_result_json"]["completeness"] == {
        "is_bayesian": False,
        "items": [],
        "advisories": [],
    }
    assert "no checklist was applied" in run["result_summary"]
    assert "not detected' never proves omission" in run["coverage"]


def test_bayes_pdf_correlation_match_retains_real_region_without_finding(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "A Bayesian correlation gave r(58) = .42, BF10 = 37.4 using a Cauchy prior.")
    document.save(draft)
    document.close()
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/bayes", json={}).json()

    result = run["structured_result_json"]
    bf = result["results"][0]
    assert bf["consistency"] == "reproduced"
    assert bf["matched_design"] == "correlation"
    assert bf["page"] == 1
    assert bf["coordinate_precision"] == "region"
    assert not any(finding["finding_type"] == "bayes-factor-not-reproduced" for finding in run["findings"])


def test_meta_analysis_run_is_snapshot_bound_and_persists_not_found_candidates(
    temp_db_url: str, tmp_path: Path
) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text(
        "We performed a random-effects meta-analysis of Hedges' g across the literature.",
        encoding="utf-8",
    )
    client = TestClient(create_app(db_url=temp_db_url))
    root_id, manuscript_id, _ = _setup(client, folder)

    response = client.post(f"/wip/manuscripts/{manuscript_id}/checks/meta-analysis", json={})

    assert response.status_code == 200
    run = response.json()
    assert run["tool_id"] == "meta-analysis"
    assert run["tool_version"] == "1"
    assert run["parameters_json"] == {}
    assert run["validity"] == "current-with-findings"
    assert "never pools, models, recomputes, scores, or judges" in run["coverage"]
    result = run["structured_result_json"]
    assert result["is_meta_analysis"] is True
    assert len(result["checks"]) == 7
    assert result["present"] == 2
    assert result["not_found"] == 5
    assert result["not_applicable"] == 0
    assert len(run["findings"]) == result["not_found"]
    missing_keys = {check["key"] for check in result["checks"] if check["status"] == "not-found"}
    assert {finding["finding_type"] for finding in run["findings"]} == {
        f"meta-analysis-{key}-not-detected" for key in missing_keys
    }
    assert all(finding["kind"] == "candidate" for finding in run["findings"])
    assert all(finding["severity"] == "info" for finding in run["findings"])
    assert all(finding["disposition"] == "open" for finding in run["findings"])
    assert all(finding["quote"] is None for finding in run["findings"])
    assert all(finding["coordinate_precision"] is None for finding in run["findings"])
    assert all(check["coordinate_precision"] is None for check in result["checks"])

    for finding in run["findings"]:
        assert client.patch(f"/wip/findings/{finding['id']}", json={"disposition": "resolved"}).status_code == 200
    assert client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"][0]["validity"] == "current"

    draft.write_text("The synthesis changed.", encoding="utf-8")
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    _poll(client, scan["job_id"])
    assert client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"][0]["validity"] == "potentially-stale"


def test_meta_analysis_gate_off_records_receipt_without_findings(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("We ran a randomized controlled trial.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/meta-analysis", json={}).json()

    assert run["validity"] == "current"
    assert run["findings"] == []
    assert run["structured_result_json"] == {
        "is_meta_analysis": False,
        "present": 0,
        "not_found": 0,
        "not_applicable": 0,
        "checks": [],
    }
    assert "no checklist was applied" in run["result_summary"]
    assert "'not detected' is never proof of omission" in run["coverage"]


def test_meta_analysis_pdf_retains_real_region_for_present_evidence(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "We performed a random-effects meta-analysis of Hedges' g. Heterogeneity I2 = 10%.")
    document.save(draft)
    document.close()
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/meta-analysis", json={}).json()

    result = run["structured_result_json"]
    effect = next(check for check in result["checks"] if check["key"] == "effect_size_metric")
    assert effect["status"] == "present"
    assert effect["page"] == 1
    assert effect["coordinate_precision"] == "region"


def test_wip_check_routes_remain_local_only(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    headers = {"host": "example.com"}
    assert client.get("/wip/manuscripts/1/checks", headers=headers).status_code == 403
    assert client.post("/wip/manuscripts/1/checks/statcheck", headers=headers).status_code == 403
    assert client.post("/wip/manuscripts/1/checks/transparency", headers=headers).status_code == 403
    assert client.post("/wip/manuscripts/1/checks/lmm", headers=headers).status_code == 403
    assert client.post("/wip/manuscripts/1/checks/bayes", headers=headers).status_code == 403
    assert client.post("/wip/manuscripts/1/checks/meta-analysis", headers=headers).status_code == 403
    assert client.patch("/wip/findings/1", headers=headers, json={"disposition": "resolved"}).status_code == 403
