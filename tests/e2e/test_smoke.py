"""Committed browser smoke test for the assembled frontend (CI's frontend gate).

Opt-in: the module is skipped unless ``CALLOSUM_RUN_E2E=1`` is set, so the default offline ``pytest``
run stays deterministic and dependency-light. CI sets the flag (after ``playwright install chromium``)
to exercise it. It spins up the real ``app.backend.api.app:app`` against a freshly migrated + seeded
temp database, loads ``/`` in headless Chromium, and asserts the React app mounts, the key surfaces
render, and there are **zero** console / page errors — the property the ephemeral ``.local/*_e2e``
manual checks used to verify by hand.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

if not os.environ.get("CALLOSUM_RUN_E2E"):
    pytest.skip("set CALLOSUM_RUN_E2E=1 to run the browser e2e smoke", allow_module_level=True)

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import sync_playwright  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.backend.api.startup import PROJECT_ROOT  # noqa: E402
from tests.api_helpers import _seed_library  # noqa: E402


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("e2e") / "e2e.sqlite"
    db_url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
    _seed_library(db_url)

    # Isolate app-settings.json and pre-complete onboarding (inc 416): without this, a CI
    # runner with no prior ~/.callosum/app-settings.json shows the first-run wizard overlay,
    # which blocks every pre-existing smoke test's clicks on the app underneath.
    settings_path = tmp_path_factory.mktemp("e2e") / "app-settings.json"
    settings_path.write_text('{"onboarding_completed": true, "onboarding_version": 2}', encoding="utf-8")

    port = _free_port()
    env = {
        **os.environ,
        "CALLOSUM_DB_URL": db_url,
        "CALLOSUM_SETTINGS_PATH": str(settings_path),
        "PYTHONPATH": str(PROJECT_ROOT),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.backend.api.app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base, proc)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _wait_for_health(base: str, proc: subprocess.Popen) -> None:
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"uvicorn exited early ({proc.returncode})")
        try:
            if httpx.get(base + "/health", timeout=1.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("uvicorn did not become healthy within 30s")


def test_frontend_mounts_without_console_errors(server: str):
    errors: list[str] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # browser binary missing despite the package being installed
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server, wait_until="load")
        # React mounts after the precompiled app script runs (inc 102) — wait for #root to populate.
        page.wait_for_function(
            "() => { const r = document.getElementById('root'); return !!r && r.children.length > 0; }",
            timeout=30000,
        )
        body_text = page.inner_text("body")
        browser.close()

    assert "Callosum" in body_text  # the brand wordmark rendered
    assert errors == [], f"unexpected console/page errors: {errors}"


def test_reading_mode_keeps_center_visible_and_does_not_persist_panel_collapse(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page()
        page.goto(server, wait_until="load")
        page.locator(".frame-reading").click()

        assert page.locator(".app").evaluate("el => el.classList.contains('reading')")
        assert page.locator(".lib-frame").bounding_box()["width"] > 300
        assert page.locator(".frame-reading").inner_text() == "⤢ Exit"
        assert page.evaluate("localStorage.getItem('callosum.leftOpen')") != "0"
        assert page.evaluate("localStorage.getItem('callosum.rightOpen')") != "0"
        assert page.evaluate("localStorage.getItem('callosum.readingMode')") is None
        browser.close()


def test_wip_checklists_are_snapshot_bound_local_and_visible_in_both_surfaces(server: str, tmp_path):
    _run_wip_checklists_e2e(server, tmp_path)


def test_feedback_dialog_end_to_end_states(server: str):
    """A bounded browser flow with a mock local relay: bug retry, feature success, disabled state, and focus."""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")

        capability = {
            "enabled": True,
            "schema_version": 1,
            "report_id": "fb_1234567890abcdef1234567890abcdef",
            "app_version": "0.3.8",
            "operating_system": "Windows 11",
            "installation_type": "tauri",
        }
        page = browser.new_page()
        errors = _mount_app(page, server)
        page.route("**/feedback/capability", lambda route: route.fulfill(json=capability))
        attempts: list[dict] = []
        pending: list[object] = []

        def submit_bug(route):
            attempts.append(route.request.post_data_json)
            if len(attempts) == 1:
                pending.append(route)
            else:
                route.fulfill(
                    status=201, json={"ok": True, "report_id": capability["report_id"], "status": "published"}
                )

        page.route("**/feedback/reports", submit_bug)
        launcher = page.get_by_role("button", name="Feedback").first
        launcher.click()
        dialog = page.get_by_role("dialog", name="Report a bug or request a feature")
        assert dialog.get_attribute("aria-modal") == "true"
        page.get_by_label("Title").fill("PDF viewer stays blank")
        page.get_by_label("Brief description").fill("The PDF tab opens but no page is rendered.")
        page.get_by_label("What happened").fill("The viewer remains blank after reopening the tab.")
        page.get_by_label("What you expected").fill("The previously selected PDF should render normally.")
        page.get_by_label("Reproduction steps").fill("Open a manuscript\nOpen a PDF\nClose and reopen the PDF")
        preview = json.loads(page.locator(".feedback-preview pre").inner_text())
        assert preview["report_type"] == "bug"
        assert preview["report_id"] == capability["report_id"]
        assert preview["app_version"] == "0.3.8"
        assert {"pdf_contents", "logs", "local_paths", "library_contents"}.isdisjoint(preview)

        submit = page.get_by_role("button", name="Submit report")
        submit.click()
        page.wait_for_function("() => document.querySelector('.feedback-actions button[type=submit]')?.disabled")
        assert len(attempts) == 1
        pending[0].fulfill(
            status=503,
            json={
                "ok": False,
                "report_id": capability["report_id"],
                "error": {"code": "feedback_service_unavailable", "message": "Feedback service unavailable."},
            },
        )
        page.get_by_text("Feedback service unavailable.").wait_for()
        assert page.get_by_label("Title").input_value() == "PDF viewer stays blank"
        page.get_by_role("button", name="Retry submission").click()
        page.get_by_text("Submitted successfully.").wait_for()
        assert len(attempts) == 2
        assert attempts[0] == attempts[1]
        errors = [error for error in errors if "status of 503" not in error]
        assert errors == []

        feature = browser.new_page()
        feature_errors = _mount_app(feature, server)
        feature.route("**/feedback/capability", lambda route: route.fulfill(json=capability))
        submitted_features: list[dict] = []

        def submit_feature(route):
            submitted_features.append(route.request.post_data_json)
            route.fulfill(status=201, json={"ok": True, "report_id": capability["report_id"], "status": "published"})

        feature.route("**/feedback/reports", submit_feature)
        feature_launcher = feature.get_by_role("button", name="Feedback").first
        feature_launcher.click()
        feature.get_by_label("Feature request").check()
        feature.get_by_role("button", name="Submit report").click()
        feature.get_by_text("Please add a title").wait_for()
        feature.get_by_label("Title").fill("Add a compact reading timer")
        feature.get_by_label("Brief description").fill("An optional timer would support focused reading sessions.")
        feature.get_by_label("Requested capability").fill("Provide an optional timer in the PDF reader.")
        feature.get_by_label("Problem or workflow").fill("I currently leave Callosum to time focused reading sessions.")
        feature.get_by_label("Why this matters").fill("It would keep focused reading work in one place.")
        feature.get_by_role("button", name="Submit report").click()
        feature.get_by_text("Submitted successfully.").wait_for()
        assert submitted_features[0]["report_type"] == "feature"
        assert "actual_behavior" not in submitted_features[0]
        feature.keyboard.press("Escape")
        assert feature.get_by_role("dialog").count() == 0
        assert feature_launcher.evaluate("el => el === document.activeElement")
        assert feature_errors == []

        disabled = browser.new_page()
        disabled_errors = _mount_app(disabled, server)
        disabled.route("**/feedback/capability", lambda route: route.fulfill(json={**capability, "enabled": False}))
        disabled_launcher = disabled.get_by_role("button", name="Feedback").first
        disabled_launcher.click()
        disabled.get_by_text("Feedback submission is unavailable").wait_for()
        assert disabled.get_by_role("button", name="Submit report").is_disabled()
        disabled.keyboard.press("Escape")
        assert disabled.get_by_role("dialog").count() == 0
        assert disabled_launcher.evaluate("el => el === document.activeElement")
        assert disabled_errors == []
        browser.close()


def _mount_app(page, server: str) -> list[str]:
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server, wait_until="domcontentloaded")
    page.wait_for_function(
        "() => { const r = document.getElementById('root'); return !!r && r.children.length > 0; }",
        timeout=30000,
    )
    return errors


def test_missing_pdf_explains_the_cause_and_opens_recovery(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.route(
            "**/papers/*/pdf",
            lambda route: route.fulfill(
                status=404,
                json={"detail": "PDF not available locally for this paper"},
                headers={
                    "X-Callosum-Error-Code": "PDF_LIBRARY_FOLDER_MISSING",
                    "X-Callosum-Attachment-Id": "123",
                    "X-Callosum-Storage-Mode": "managed",
                    "X-Callosum-Attachment-Availability": "available",
                    "X-Callosum-App-Version": "0.5.6",
                },
            ),
        )
        errors = _mount_app(page, server)

        page.locator(".paper").first.dblclick()
        page.get_by_text("Callosum's library folder is unavailable", exact=True).wait_for()
        assert page.get_by_role("button", name="Retry", exact=True).is_visible()
        assert page.get_by_role("button", name="Copy diagnostics", exact=True).is_visible()
        page.get_by_role("button", name="Find or Reconnect PDF", exact=True).click()
        page.get_by_text("Watched folders", exact=True).wait_for()
        assert page.get_by_role("button", name="Browse…", exact=True).is_visible()

        errors = [message for message in errors if "status of 404" not in message]
        assert errors == []
        browser.close()


def _run_wip_checklists_e2e(server: str, tmp_path):
    folder = tmp_path / "WIP Checklist Draft"
    folder.mkdir()
    (folder / "draft.md").write_text(
        "Data are available at https://osf.io/abcd. The authors declare no conflicts of interest. "
        "This project received no funding. We fit a linear mixed-effects model with a random intercept for "
        "participant using REML. The model converged without a singular fit. We also ran a Bayesian t-test with a "
        "Cauchy prior: t(19) = 2.53, BF10 = 500. We report a 95% confidence interval. We also performed a "
        "random-effects meta-analysis of Hedges' g across the literature.",
        encoding="utf-8",
    )
    root = httpx.post(
        server + "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
        timeout=30,
    ).json()
    scan = httpx.post(server + f"/wip/watch-roots/{root['id']}/scan", timeout=30).json()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status = httpx.get(server + f"/wip/scan/{scan['job_id']}", timeout=30).json()
        if status["status"] in {"done", "error"}:
            assert status["status"] == "done", status
            break
        time.sleep(0.1)
    else:
        raise AssertionError("WIP scan did not finish")
    manuscript = next(
        item
        for item in httpx.get(server + "/wip/manuscripts", timeout=30).json()
        if item["display_title"] == folder.name
    )
    primary = httpx.get(server + f"/wip/manuscripts/{manuscript['id']}/files", timeout=30).json()[0]
    selected = httpx.patch(
        server + f"/wip/manuscripts/{manuscript['id']}/files/{primary['id']}",
        json={"is_primary": True},
        timeout=30,
    )
    assert selected.status_code == 200
    transparency_response = httpx.post(
        server + f"/wip/manuscripts/{manuscript['id']}/checks/transparency",
        json={},
        timeout=30,
    )
    assert transparency_response.status_code == 200
    lmm_response = httpx.post(
        server + f"/wip/manuscripts/{manuscript['id']}/checks/lmm",
        json={},
        timeout=30,
    )
    assert lmm_response.status_code == 200
    assert lmm_response.json()["structured_result_json"]["is_lmm"] is True
    bayes_response = httpx.post(
        server + f"/wip/manuscripts/{manuscript['id']}/checks/bayes",
        json={},
        timeout=30,
    )
    assert bayes_response.status_code == 200
    assert bayes_response.json()["structured_result_json"]["completeness"]["is_bayesian"] is True
    meta_response = httpx.post(
        server + f"/wip/manuscripts/{manuscript['id']}/checks/meta-analysis",
        json={},
        timeout=30,
    )
    assert meta_response.status_code == 200
    assert meta_response.json()["structured_result_json"]["is_meta_analysis"] is True
    critical_start = httpx.post(
        server + f"/wip/manuscripts/{manuscript['id']}/critical-read",
        json={},
        timeout=30,
    )
    assert critical_start.status_code == 202
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        critical_job = httpx.get(server + f"/wip/critical-read/{critical_start.json()['job_id']}", timeout=30).json()
        if critical_job["status"] in {"done", "error"}:
            assert critical_job["status"] == "done", critical_job
            assert critical_job["run"]["structured_result_json"]["retrieval"]["status"] == "empty-library-corpus"
            break
        time.sleep(0.1)
    else:
        raise AssertionError("WIP critical read did not finish")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(90000)
        errors = _mount_app(page, server)
        outbound: list[str] = []
        page.on("request", lambda request: outbound.append(request.url) if not request.url.startswith(server) else None)

        page.get_by_role("button", name="WIP", exact=True).click()
        # Opening WIP deliberately starts its launch/focus rescan. Let that bounded
        # writer finish before exercising a check run so this scenario tests the
        # checklist workflow rather than racing two unrelated SQLite writes.
        page.get_by_role("button", name="Rescan", exact=True).wait_for()
        card = page.get_by_role("button", name=f"WIP manuscript: {folder.name}")
        card.dblclick()
        page.locator(".acc-header", has_text="Checklists").click()
        transparency_tab = page.get_by_role("tab", name="Transparency signals", exact=True)
        transparency_tab.click()
        page.locator(".detail-statcheck .wip-transparency-result:visible").wait_for()

        page.get_by_role("button", name="Checks", exact=True).click()
        wip_checks = page.locator(".wip-work-view:visible")
        wip_run = wip_checks.locator(".wip-tool-run").filter(has_text="Transparency")
        wip_run.wait_for()
        assert wip_run.count() == 1
        assert wip_run.locator("select").count() == 0
        assert "snapshot" in wip_run.inner_text()
        assert "not detected" in wip_run.inner_text().lower()

        lmm_button = wip_checks.get_by_role("button", name="Audit LMM Reporting", exact=True)
        lmm_button.wait_for()
        lmm_run = wip_checks.locator(".wip-tool-run").filter(has_text="Mixed-model reporting")
        lmm_run.wait_for()
        assert lmm_run.count() == 1
        assert lmm_run.locator("select").count() >= 1
        assert "not proof of omission" in lmm_run.inner_text()

        bayes_run = wip_checks.locator(".wip-tool-run").filter(has_text="Bayesian reporting")
        bayes_run.wait_for()
        assert bayes_run.count() == 1
        assert bayes_run.locator("select").count() >= 1
        assert "default-prior assumptions" in bayes_run.inner_text()

        meta_run = wip_checks.locator(".wip-tool-run").filter(has_text="Meta-analysis reporting")
        meta_run.wait_for()
        assert meta_run.count() == 1
        assert meta_run.locator("select").count() >= 1
        assert "never proof of omission" in meta_run.inner_text()

        transparency_tab.click()
        active_checklist = page.locator(".detail-statcheck .wip-transparency-result:visible")
        active_checklist.wait_for()
        assert active_checklist.get_by_text("Data availability", exact=True).count() == 1
        assert active_checklist.get_by_text("not detected", exact=True).count() >= 1
        assert (
            active_checklist.get_by_text("Detected rows are retained as evidence-backed facts.", exact=False).count()
            == 1
        )
        checklist_run = active_checklist.locator(
            "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' wip-tool-run ')][1]"
        )
        assert "transparency score or judgment" in checklist_run.inner_text()

        lmm_tab = page.get_by_role("tab", name="Mixed-model reporting", exact=True)
        lmm_tab.click()
        lmm_result = page.locator(".detail-statcheck .wip-lmm-result:visible")
        lmm_result.wait_for()
        assert lmm_result.get_by_text("Random-effects structure", exact=True).count() == 1
        assert lmm_result.get_by_text("not found", exact=True).count() >= 1
        assert "never a verdict, never a score, never an accusation" in lmm_result.inner_text().lower()
        assert "reviewable candidate" in lmm_result.inner_text()

        bayes_tab = page.get_by_role("tab", name="Bayesian statistics", exact=True)
        bayes_tab.click()
        bayes_result = page.locator(".detail-statcheck .wip-bayes-result:visible")
        bayes_result.wait_for()
        assert "500" in bayes_result.inner_text()
        assert "couldn't reproduce" in bayes_result.inner_text()
        assert bayes_result.get_by_text("Prior stated (family/scale)", exact=True).count() == 1
        assert "expert judgment" in bayes_result.inner_text().lower()
        assert "never an error verdict" in bayes_result.inner_text().lower()
        meta_tab = page.get_by_role("tab", name="Meta-analysis reporting", exact=True)
        meta_tab.click()
        meta_result = page.locator(".detail-statcheck .wip-meta-analysis-result:visible")
        meta_result.wait_for()
        assert meta_result.get_by_text("Effect-size metric", exact=True).count() == 1
        assert meta_result.get_by_text("not found", exact=True).count() >= 1
        assert "never proof of omission" in meta_result.inner_text().lower()
        assert "reviewable info candidate" in meta_result.inner_text().lower()

        page.get_by_role("tab", name="Synthesize", exact=True).click()
        page.get_by_role("tab", name="Critique", exact=True).click()
        critique = page.locator(".wip-critical-result:visible")
        critique.wait_for()
        page.get_by_role("button", name="Run local critical read again", exact=True).wait_for()
        assert "No matching-model article-fulltext embeddings" in critique.inner_text()
        assert "current receipt" in critique.inner_text().lower()
        assert "transient and never stored" in critique.inner_text()
        assert "does not decide which claim is correct" in critique.inner_text()
        assert (
            page.get_by_text("separate exact transmission preview and explicit consent design", exact=False).count()
            == 1
        )
        page.set_viewport_size({"width": 375, "height": 812})
        _assert_no_document_horizontal_overflow(page, "WIP critical read / mobile")
        _assert_tool_panes_do_not_overflow(page, "WIP critical read / mobile")
        assert outbound == []
        assert errors == []
        browser.close()


def _assert_no_document_horizontal_overflow(page, label: str) -> None:
    overflow = page.evaluate(
        """() => ({
            width: window.innerWidth,
            scrollWidth: document.documentElement.scrollWidth,
            bodyScrollWidth: document.body.scrollWidth
        })"""
    )
    max_scroll = max(overflow["scrollWidth"], overflow["bodyScrollWidth"])
    assert max_scroll <= overflow["width"] + 2, f"{label}: document overflows horizontally: {overflow}"


def _assert_tool_panes_do_not_overflow(page, label: str) -> None:
    panes = page.locator(".pane-sidebar:visible, .pane-detail:visible, .acc-section.open .acc-body:visible")
    measurements = panes.evaluate_all(
        """els => els.map((el, i) => ({
            index: i,
            className: el.className,
            clientWidth: el.clientWidth,
            scrollWidth: el.scrollWidth,
            clientHeight: el.clientHeight,
            scrollHeight: el.scrollHeight
        }))"""
    )
    offenders = [m for m in measurements if m["clientWidth"] > 0 and m["scrollWidth"] > m["clientWidth"] + 2]
    assert offenders == [], f"{label}: visible tool pane horizontal overflow: {offenders}"


def _assert_accordion_headers_visible(page, pane_selector: str, label: str) -> None:
    headers = page.locator(f"{pane_selector} .acc-header:visible")
    count = headers.count()
    assert count > 0, f"{label}: no visible accordion headers in {pane_selector}"
    viewport = page.viewport_size or {"width": 0, "height": 0}
    hidden: list[dict[str, object]] = []
    for i in range(count):
        header = headers.nth(i)
        box = header.bounding_box()
        if not box or box["y"] + box["height"] < 0 or box["y"] > viewport["height"]:
            hidden.append({"index": i, "text": header.inner_text(), "box": box})
    assert hidden == [], f"{label}: accordion headers left viewport: {hidden}"


def _walk_accordion_sections(page, pane_selector: str, label: str) -> None:
    headers = page.locator(f"{pane_selector} .acc-header:visible")
    count = headers.count()
    for i in range(count):
        header = headers.nth(i)
        section_label = header.inner_text().strip().replace("\n", " ")
        header.click()
        page.wait_for_timeout(120)
        assert header.get_attribute("aria-expanded") == "true", f"{label}: {section_label} did not open"
        _assert_accordion_headers_visible(page, pane_selector, f"{label} / {section_label}")
        _assert_tool_panes_do_not_overflow(page, f"{label} / {section_label}")


def test_my_publications_grounded_prospection_reveals_source_evidence(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page()
        page.route(
            "**/my-publications/dashboard",
            lambda route: route.fulfill(
                json={
                    "status": "ok",
                    "name": "Ada Lovelace",
                    "as_of": "2026-07-25T12:00:00",
                    "metrics": {"works_count": 4, "cited_by_count": 12, "h_index": 2, "i10_index": 1},
                    "pubs_by_year": [],
                    "counts_by_year": [],
                    "indexed_works": 4,
                    "in_library": 4,
                    "gap": 0,
                    "research_summary": None,
                    "domains": [
                        {
                            "key": "domain:aaaaaaaaaaaaaaaaaaaa",
                            "label": "Domain A",
                            "terms": ["alpha"],
                            "paper_count": 2,
                            "citation_count": 10,
                            "paper_years": [2022, 2023],
                            "paper_ids": [1, 2],
                        },
                        {
                            "key": "domain:bbbbbbbbbbbbbbbbbbbb",
                            "label": "Domain B",
                            "terms": ["beta"],
                            "paper_count": 2,
                            "citation_count": 2,
                            "paper_years": [2020, 2021],
                            "paper_ids": [3, 4],
                        },
                    ],
                    "missing_works": [],
                    "dismissed_works": [],
                    "openalex_extra": None,
                    "starred_count": 0,
                    "starred_ids": [],
                    "paper_citations": {},
                }
            ),
        )
        page.route(
            "**/my-publications/citation-gaps*",
            lambda route: route.fulfill(
                json={
                    "computed_at": "2026-07-25T12:30:00+00:00",
                    "coverage": {
                        "checked": 2 if "domain_key=" in route.request.url else 4,
                        "with_doi": 2 if "domain_key=" in route.request.url else 4,
                        "total": 2 if "domain_key=" in route.request.url else 4,
                        "library_total": 4,
                        "shared_anchor_count": 1,
                        "publication_cap_reached": False,
                        "scope_kind": "domains" if "domain_key=" in route.request.url else "all",
                        "domain_count": 1 if "domain_key=" in route.request.url else 0,
                        "domain_labels": ["Domain A"] if "domain_key=" in route.request.url else [],
                        "note": "OpenAlex coverage is partial.",
                    },
                    "scope": {
                        "kind": "domains" if "domain_key=" in route.request.url else "all",
                        "domain_keys": (["domain:aaaaaaaaaaaaaaaaaaaa"] if "domain_key=" in route.request.url else []),
                        "domain_labels": ["Domain A"] if "domain_key=" in route.request.url else [],
                    },
                    "candidates": [
                        {
                            "openalex_work_id": "W301",
                            "doi": "10.3/gap",
                            "title": (
                                "A domain-scoped neighboring work"
                                if "domain_key=" in route.request.url
                                else "A grounded neighboring work"
                            ),
                            "authors": ["Grace Hopper"],
                            "year": 2025,
                            "shared_reference_count": 1,
                            "source_publication_count": 2,
                            "evidence": [
                                {
                                    "reference_openalex_work_id": "W201",
                                    "reference_title": "The shared reference",
                                    "reference_doi": "10.2/reference",
                                    "source_papers": [
                                        {"paper_id": 1, "title": "Own publication A"},
                                        {"paper_id": 2, "title": "Own publication B"},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ),
        )
        page.route(
            "**/my-publications/emerging-citing-topics*",
            lambda route: route.fulfill(
                json={
                    "computed_at": "2026-07-26T12:30:00+00:00",
                    "coverage": {
                        "checked": 2 if "domain_key=" in route.request.url else 4,
                        "with_doi": 2 if "domain_key=" in route.request.url else 4,
                        "total": 2 if "domain_key=" in route.request.url else 4,
                        "library_total": 4,
                        "recent_start_year": 2023,
                        "recent_end_year": 2025,
                        "previous_start_year": 2020,
                        "previous_end_year": 2022,
                        "recent_work_count": 2,
                        "previous_work_count": 1,
                        "missing_primary_topic_count": 0,
                        "publication_cap_reached": False,
                        "recent_window_cap_reached": False,
                        "previous_window_cap_reached": False,
                        "scope_kind": "domains" if "domain_key=" in route.request.url else "all",
                        "domain_count": 1 if "domain_key=" in route.request.url else 0,
                        "domain_labels": ["Domain A"] if "domain_key=" in route.request.url else [],
                        "note": "Counts describe bounded OpenAlex records, not a forecast.",
                    },
                    "scope": {
                        "kind": "domains" if "domain_key=" in route.request.url else "all",
                        "domain_keys": (["domain:aaaaaaaaaaaaaaaaaaaa"] if "domain_key=" in route.request.url else []),
                        "domain_labels": ["Domain A"] if "domain_key=" in route.request.url else [],
                    },
                    "topics": [
                        {
                            "topic_id": "T101",
                            "name": "Evidence synthesis",
                            "subfield": "Research methods",
                            "field": "Social sciences",
                            "domain": "Social sciences",
                            "recent_count": 2,
                            "previous_count": 1,
                            "increase": 1,
                            "recent_works": [
                                {
                                    "openalex_work_id": "W501",
                                    "doi": "10.5/recent",
                                    "title": "A recent citing work",
                                    "year": 2025,
                                    "authors": ["Grace Hopper"],
                                    "cited_publications": [{"paper_id": 1, "title": "Own publication A"}],
                                },
                                {
                                    "openalex_work_id": "W502",
                                    "doi": "10.5/recent-b",
                                    "title": "Another recent citing work",
                                    "year": 2024,
                                    "authors": ["Katherine Johnson"],
                                    "cited_publications": [{"paper_id": 2, "title": "Own publication B"}],
                                },
                            ],
                            "previous_works": [
                                {
                                    "openalex_work_id": "W401",
                                    "doi": "10.5/earlier",
                                    "title": "An earlier citing work",
                                    "year": 2022,
                                    "authors": ["Dorothy Vaughan"],
                                    "cited_publications": [{"paper_id": 1, "title": "Own publication A"}],
                                }
                            ],
                        }
                    ],
                }
            ),
        )
        page.route(
            "**/my-publications/citing-authors*",
            lambda route: route.fulfill(
                json={
                    "computed_at": "2026-07-26T12:45:00+00:00",
                    "coverage": {
                        "checked": 2 if "domain_key=" in route.request.url else 4,
                        "with_doi": 2 if "domain_key=" in route.request.url else 4,
                        "total": 2 if "domain_key=" in route.request.url else 4,
                        "library_total": 4,
                        "unresolved_openalex_count": 0,
                        "start_year": 2020,
                        "end_year": 2025,
                        "citing_work_count": 2,
                        "coauthor_checked_publication_count": 2,
                        "coauthor_unresolved_publication_count": 0,
                        "excluded_coauthor_count": 1,
                        "missing_author_id_count": 0,
                        "source_authorship_cap_count": 0,
                        "citing_authorship_cap_count": 0,
                        "publication_cap_reached": False,
                        "citing_window_cap_reached": False,
                        "scope_kind": "domains" if "domain_key=" in route.request.url else "all",
                        "domain_count": 1 if "domain_key=" in route.request.url else 0,
                        "domain_labels": ["Domain A"] if "domain_key=" in route.request.url else [],
                        "note": "Repeated citation connections, not collaboration fit or a recommendation.",
                    },
                    "scope": {
                        "kind": "domains" if "domain_key=" in route.request.url else "all",
                        "domain_keys": (["domain:aaaaaaaaaaaaaaaaaaaa"] if "domain_key=" in route.request.url else []),
                        "domain_labels": ["Domain A"] if "domain_key=" in route.request.url else [],
                    },
                    "authors": [
                        {
                            "author_id": "A900",
                            "name": "Margaret Hamilton",
                            "citing_work_count": 2,
                            "cited_publication_count": 2,
                            "latest_year": 2025,
                            "citing_works": [
                                {
                                    "openalex_work_id": "W601",
                                    "doi": "10.6/one",
                                    "title": "A repeated citation connection",
                                    "year": 2025,
                                    "cited_publications": [{"paper_id": 1, "title": "Own publication A"}],
                                },
                                {
                                    "openalex_work_id": "W602",
                                    "doi": "10.6/two",
                                    "title": "Another citation connection",
                                    "year": 2024,
                                    "cited_publications": [{"paper_id": 2, "title": "Own publication B"}],
                                },
                            ],
                        }
                    ],
                }
            ),
        )
        page.route(
            "**/axes",
            lambda route: route.fulfill(json=[{"id": 7, "label": "My Publications", "kind": "my_publications"}]),
        )
        page.route("**/axes/7/clusters", lambda route: route.fulfill(json=[]))
        errors = _mount_app(page, server)

        page.get_by_role("tab", name="My Publications", exact=True).click()
        panel = page.locator('section[aria-labelledby="mypubs-citation-gaps-title"]')
        panel.wait_for()
        assert "A grounded neighboring work" in panel.inner_text()
        assert "1 shared reference across 2 of your publications" in panel.inner_text()
        domain_a = panel.locator(".mypubs-gap-scope-chip", has_text="Domain A")
        with page.expect_request(lambda request: "domain_key=domain%3Aaaaaaaaaaaaaaaaaaaaa" in request.url):
            domain_a.click()
        panel.locator(".mypubs-gap-title", has_text="A domain-scoped neighboring work").wait_for()
        assert domain_a.get_attribute("aria-pressed") == "true"
        assert "in Domain A" in panel.locator(".mypubs-gap-coverage").inner_text()
        anchor = panel.locator(".mypubs-gap-anchor")
        assert not anchor.is_visible()
        panel.locator(".mypubs-gap-evidence summary").click()
        assert anchor.is_visible() and "The shared reference" in anchor.inner_text()
        assert panel.get_by_role("button", name="Own publication A", exact=True).is_visible()
        assert panel.locator('a[href="https://openalex.org/W301"]').count() == 1

        topic_panel = page.locator('section[aria-labelledby="mypubs-emerging-topics-title"]')
        topic_panel.wait_for()
        assert "Evidence synthesis" in topic_panel.inner_text()
        assert "+1" in topic_panel.locator(".mypubs-topic-change").inner_text()
        topic_domain_a = topic_panel.locator(".mypubs-gap-scope-chip", has_text="Domain A")
        with page.expect_request(
            lambda request: "emerging-citing-topics" in request.url
            and "domain_key=domain%3Aaaaaaaaaaaaaaaaaaaaa" in request.url
        ):
            topic_domain_a.click()
        assert topic_domain_a.get_attribute("aria-pressed") == "true"
        topic_panel.locator(".mypubs-gap-evidence summary").click()
        assert topic_panel.get_by_text("A recent citing work", exact=False).is_visible()
        assert topic_panel.get_by_role("button", name="Own publication A", exact=True).first.is_visible()
        assert topic_panel.locator('a[href="https://openalex.org/W501"]').count() == 1

        author_panel = page.locator('section[aria-labelledby="mypubs-citing-authors-title"]')
        author_panel.wait_for()
        assert "Margaret Hamilton" in author_panel.inner_text()
        author_counts = " ".join(author_panel.locator(".mypubs-topic-change").inner_text().split())
        assert "2 of your publications · 2 citing works" in author_counts
        author_domain_a = author_panel.locator(".mypubs-gap-scope-chip", has_text="Domain A")
        with page.expect_request(
            lambda request: "citing-authors" in request.url
            and "domain_key=domain%3Aaaaaaaaaaaaaaaaaaaaa" in request.url
        ):
            author_domain_a.click()
        assert author_domain_a.get_attribute("aria-pressed") == "true"
        author_panel.locator(".mypubs-gap-evidence summary").click()
        assert author_panel.get_by_text("A repeated citation connection", exact=False).is_visible()
        assert author_panel.get_by_role("button", name="Own publication A", exact=True).is_visible()
        assert author_panel.locator('a[href="https://openalex.org/A900"]').count() == 1
        assert author_panel.locator('a[href="https://openalex.org/W601"]').count() == 1
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(120)
        _assert_no_document_horizontal_overflow(page, "My Publications grounded prospection / mobile")
        assert errors == []
        browser.close()


def test_statcheck_table_result_surfaces_provenance_and_coverage(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        # inc 400 moved the Details-pane "Statistics" section from the fused GET .../statcheck endpoint
        # (still used elsewhere, e.g. Discover/Cite) to a cache-then-explicit-rescan read at
        # .../statcheck/cached — this test's mock must match the endpoint actually called on mount, or the
        # real (unmocked) cache miss just renders "no cached result" and every assertion below times out.
        page.route(
            "**/papers/*/statcheck/cached",
            lambda route: route.fulfill(
                json={
                    "cached": True,
                    "checked": 1,
                    "inconsistent": 0,
                    "decision_errors": 1,
                    "computed_at": "2026-07-01T00:00:00",
                    "stale": False,
                    "results": [
                        {
                            "raw": "Memory | t(28) | 1.50 | .04",
                            "context": (
                                "Table headers: Outcome | Test (df) | Statistic | p-value. "
                                "Table row: Memory | t(28) | 1.50 | .04."
                            ),
                            "test_type": "t",
                            "reported_p": "p = .04",
                            "computed_p": 0.144,
                            "consistency": "decision-error",
                            "page": 1,
                            "page_end": 1,
                            "section": "Results",
                            "coordinate_precision": "region",
                            "attachment_id": 777,
                            "bbox_json": [
                                {
                                    "page": 1,
                                    "x0": 40,
                                    "y0": 75,
                                    "x1": 440,
                                    "y1": 110,
                                    "source_kind": "table-row",
                                    "coordinate_precision": "region",
                                }
                            ],
                            "source_kind": "table",
                            "table_index": 1,
                            "table_row": 2,
                            "table_caption": "Primary outcomes",
                        }
                    ],
                    "coverage": {
                        "prose_chunks": 4,
                        "attachments_scanned": 1,
                        "attachments_skipped": 0,
                        "pages_scanned": 1,
                        "tables_scanned": 1,
                        "table_rows_scanned": 3,
                        "table_results": 1,
                        "truncated": False,
                    },
                }
            ),
        )
        errors = _mount_app(page, server)

        page.locator(".paper").first.click()
        statistics = page.locator(".pane-detail .acc-header", has_text="Statistics").first
        statistics.click()
        source = page.locator(".statcheck-source")
        source.wait_for()
        assert source.inner_text() == "TABLE 1 · ROW 2"
        assert "1 from tables" in page.locator(".statcheck-summary").inner_text()
        assert "1 detected table" in page.locator(".statcheck-coverage").inner_text()
        assert "Memory | t(28) | 1.50 | .04" in page.locator(".statcheck-item").inner_text()
        assert (
            "Ambiguous/unlabeled tables"
            in page.locator(".detail-statcheck .statcheck-result > .statcheck-caveat").inner_text()
        )

        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(120)
        _assert_no_document_horizontal_overflow(page, "table-aware statcheck / mobile")
        page.set_viewport_size({"width": 1366, "height": 900})
        page.route("**/papers/*/pdf?attachment_id=777", lambda route: route.fulfill(status=404))
        with page.expect_request(lambda request: "attachment_id=777" in request.url) as source_request:
            page.locator(".statcheck-item-main").click()
        assert "attachment_id=777" in source_request.value.url
        assert errors == []
        browser.close()


def test_cite_opens_the_matched_pdf_attachment_and_names_it(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.route(
            "**/citations/suggest",
            lambda route: route.fulfill(
                json={
                    "suggestions": [
                        {
                            "paper_id": 1,
                            "title": "Facial Anomaly Perception",
                            "year": 2024,
                            "author": "Lovelace",
                            "match_score": 0.91,
                            "chunk_id": 991,
                            "quote": "Facial anomalies influence social judgments.",
                            "page_start": 1,
                            "page_end": 1,
                            "coordinate_precision": "region",
                            "bbox_json": None,
                            "attachment_id": 777,
                            "stance": None,
                        }
                    ],
                    "beyond_library_suggestions": [],
                    "source_coverage": [],
                }
            ),
        )
        page.route(
            "**/papers/1/pdf?attachment_id=777",
            lambda route: route.fulfill(
                path=str(PROJECT_ROOT / "tests" / "fixtures" / "seed.pdf"),
                content_type="application/pdf",
                headers={"Content-Disposition": 'inline; filename="social-perception-supplement.pdf"'},
            ),
        )
        errors = _mount_app(page, server)

        page.get_by_role("tab", name="Work", exact=True).click()
        page.get_by_role("tab", name="Cite", exact=True).click()
        page.locator(".cite-pane textarea").fill("Facial anomalies influence social judgments.")
        page.locator(".cite-pane .synth-actions button").click()
        card = page.locator(".cite-card", has_text="Facial Anomaly Perception")
        card.wait_for()
        with page.expect_request(lambda request: "attachment_id=777" in request.url):
            card.get_by_role("button", name="Open source region", exact=True).click()
        page.locator(".pdf-filename", has_text="social-perception-supplement.pdf").wait_for()
        page.locator(".pdf-region-note").wait_for()
        assert page.locator(".pdf-highlight").count() == 0
        page.set_viewport_size({"width": 375, "height": 812})
        page.locator(".pdf-filename", has_text="social-perception-supplement.pdf").wait_for(state="visible")
        _assert_no_document_horizontal_overflow(page, "Cite exact attachment / mobile")
        filename_box = page.locator(".pdf-filename").bounding_box()
        assert filename_box is not None and filename_box["width"] >= 80
        assert page.locator(".pdf-toolbar").evaluate("el => el.scrollWidth <= el.clientWidth + 2")
        assert errors == []
        browser.close()


def test_meta_preregistration_uses_full_synthesis_workspace_and_settings_chrome(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        errors = _mount_app(page, server)

        page.locator(".paper").first.click()
        page.get_by_role("tab", name="Synthesize", exact=True).click()
        visible_tabs = page.locator(".workspace-tabs:visible [role=tab]")
        assert visible_tabs.all_inner_texts() == ["Ask", "Critique", "Meta-Preregistration"]
        page.get_by_role("tab", name="Meta-Preregistration", exact=True).click()
        page.locator(".meta-preregistration .settings-card").first.wait_for()
        assert page.locator(".meta-preregistration .settings-card").count() == 2
        assert page.locator(".meta-preregistration .settings-input").count() >= 1
        _assert_no_document_horizontal_overflow(page, "Meta-Preregistration / desktop")

        meta_chrome = page.locator(".meta-preregistration .settings-card").first.evaluate(
            "el => { const s = getComputedStyle(el); return {padding:s.padding, radius:s.borderRadius, border:s.border, background:s.backgroundColor}; }"
        )
        page.get_by_role("tab", name="Settings", exact=True).click()
        settings_chrome = page.locator(".settings-view .settings-card").first.evaluate(
            "el => { const s = getComputedStyle(el); return {padding:s.padding, radius:s.borderRadius, border:s.border, background:s.backgroundColor}; }"
        )
        assert meta_chrome == settings_chrome

        page.get_by_role("tab", name="Synthesize", exact=True).click()
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(120)
        _assert_no_document_horizontal_overflow(page, "Meta-Preregistration / mobile")
        assert (
            page.locator(".registration-source-row").first.evaluate("el => getComputedStyle(el).flexDirection")
            == "column"
        )
        assert errors == []
        browser.close()


def test_meta_preregistration_ai_triage_is_reversible_and_restores_all_rows(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        triaged = {"value": False}
        version = {
            "id": 71,
            "link_id": 61,
            "attachment_id": 51,
            "provider": "manual-local",
            "content_hash": "a" * 64,
            "retrieved_at": "2026-08-01T12:00:00",
        }
        link = {
            "id": 61,
            "link_status": "confirmed",
            "linkage_class": "explicit-linkage",
            "linkage_label": "Explicitly linked",
            "provider": "manual-local",
            "external_id": "local-registration",
            "title": "Reader-confirmed registration",
            "contributors": [],
            "match_evidence": [{"kind": "paper-reference", "printed": True}],
            "registration_status": "public",
        }
        summary = {
            "id": 91,
            "paper_id": 1,
            "registration_version_id": 71,
            "status": "completed",
            "stale_reasons": [],
            "registration_content_hash": "a" * 64,
            "article_content_hash": "b" * 64,
            "supplement_content_hashes": [],
            "commitment_extraction_version": "test-extraction",
            "section_extraction_version": "test-sections",
            "retrieval_version": "test-retrieval",
            "comparison_version": "test-comparison",
            "configuration": {},
            "model_provider": None,
            "model_name": None,
            "created_at": "2026-08-01T12:00:00",
            "completed_at": "2026-08-01T12:00:01",
            "row_count": 2,
            "unreviewed_count": 2,
        }

        def comparison_detail():
            def triage_annotation(label, show, rationale):
                return {
                    "label": label,
                    "show_in_triage": show,
                    "rationale": rationale,
                    "concerns": [],
                    "basis": "Bounded paired evidence",
                    "provider_id": "fixture",
                    "model_id": "fixture-model",
                    "prompt_version": "registration-comparison-triage-v1",
                    "status": "current",
                    "stale_reasons": [],
                }

            row_base = {
                "run_id": 91,
                "timing_status": None,
                "registration_source_locator": None,
                "publication_source_locator": None,
                "search_scope": {
                    "expected_section_families": ["Methods"],
                    "sections_searched": ["Methods"],
                    "whole_article_expanded": False,
                    "supplements_searched": False,
                    "study_mapping": "Study 1",
                    "publication_sources": [],
                },
                "uncertainty": "Human inspection remains necessary.",
                "registration_content_hash": "a" * 64,
                "publication_attachment_checksum": "b" * 64,
                "review_state": "unreviewed",
                "note": None,
            }
            rows = [
                {
                    **row_base,
                    "id": 101,
                    "field_type": "primary-outcome",
                    "comparison_status": "potentially-changed",
                    "registration_evidence_text": "Accuracy was the planned primary outcome.",
                    "publication_evidence_text": "Response time was reported as the primary outcome.",
                    "explanation": "The named primary outcomes differ.",
                    "llm_triage": triage_annotation(
                        "prioritize", True, "A named primary-outcome distinction merits review"
                    )
                    if triaged["value"]
                    else None,
                },
                {
                    **row_base,
                    "id": 102,
                    "field_type": "design",
                    "comparison_status": "not-comparable",
                    "registration_evidence_text": "The study uses an online task.",
                    "publication_evidence_text": "Participants completed the task online.",
                    "explanation": "The descriptions use slightly different wording.",
                    "llm_triage": triage_annotation(
                        "likely_noise", False, "The paired passages appear substantively redundant"
                    )
                    if triaged["value"]
                    else None,
                },
            ]
            return {
                **summary,
                "article_source": [],
                "supplement_source": [],
                "rows": rows,
                "llm_triage_status": {
                    "status": "success" if triaged["value"] else "not_searched",
                    "annotated_count": 2 if triaged["value"] else 0,
                    "focused_count": 1 if triaged["value"] else 0,
                    "warning": None,
                },
                "framing": "Evidence crosswalk for human inspection, not a verdict.",
            }

        page.route("**/papers/1/registration-links?include_rejected=true", lambda route: route.fulfill(json=[link]))
        page.route("**/papers/1/registration-versions", lambda route: route.fulfill(json=[version]))
        page.route("**/papers/1/registration-comparisons", lambda route: route.fulfill(json=[summary]))
        page.route("**/papers/1/registration-comparisons/91", lambda route: route.fulfill(json=comparison_detail()))

        def run_triage(route):
            triaged["value"] = True
            route.fulfill(
                json={
                    "run_id": 91,
                    "llm_triage_status": {
                        "status": "success",
                        "annotated_count": 2,
                        "focused_count": 1,
                        "warning": None,
                    },
                }
            )

        page.route("**/papers/1/registration-comparisons/91/llm-triage", run_triage)
        errors = _mount_app(page, server)

        page.locator(".paper").first.click()
        page.get_by_role("tab", name="Synthesize", exact=True).click()
        page.get_by_role("tab", name="Meta-Preregistration", exact=True).click()
        page.get_by_role("button", name="Triage rows with AI", exact=True).wait_for()
        assert page.locator(".registration-comparison-row").count() == 2

        page.get_by_role("button", name="Triage rows with AI", exact=True).click()
        page.get_by_role("button", name="AI-focused", exact=True).wait_for()
        assert page.locator(".registration-comparison-row").count() == 1
        assert page.get_by_text("A named primary-outcome distinction merits review", exact=True).is_visible()
        assert page.get_by_text("The descriptions use slightly different wording.", exact=True).count() == 0

        page.get_by_role("button", name="All rows", exact=True).click()
        assert page.locator(".registration-comparison-row").count() == 2
        assert page.get_by_text("The descriptions use slightly different wording.", exact=True).is_visible()
        page.set_viewport_size({"width": 375, "height": 812})
        _assert_no_document_horizontal_overflow(page, "Meta-Preregistration AI triage / mobile")
        assert errors == []
        browser.close()


def test_status_popover_tracks_synchronous_ai_and_navigates_to_its_ui(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        errors = _mount_app(page, server)
        page.evaluate(
            """() => {
              const originalFetch = window.fetch;
              window.__finishHelpRequest = null;
              window.fetch = (input, init) => {
                if (String(input).includes('/help/ask')) {
                  return new Promise(resolve => {
                    window.__finishHelpRequest = () => resolve(new Response(
                      JSON.stringify({answer:'Use Add or drag a PDF into Callosum.', references:[]}),
                      {status:200, headers:{'Content-Type':'application/json'}}));
                  });
                }
                return originalFetch(input, init);
              };
            }"""
        )

        page.get_by_role("tab", name="Help", exact=True).click()
        page.get_by_placeholder("Ask the help assistant…").fill("How do I import a PDF?")
        page.get_by_role("button", name="Ask", exact=True).click()
        page.wait_for_function("() => typeof window.__finishHelpRequest === 'function'")
        assert errors == [], f"unexpected console/page errors while Help AI is running: {errors}"
        assert page.get_by_role("tab", name="Library", exact=True).count() == 1, page.locator("body").inner_text()[
            :1000
        ]

        page.get_by_role("tab", name="Library", exact=True).click()
        page.locator(".status-menu-toggle").click()
        row = page.locator(".status-row", has_text="Drafting a Help answer")
        row.wait_for()
        assert row.get_by_text("Provider AI", exact=True).is_visible()
        timing_text = row.locator(".status-row-eta").inner_text()
        assert "elapsed" in timing_text
        assert "Timing varies by provider" in timing_text
        row.get_by_role("button", name="Drafting a Help answer", exact=True).click()
        assert page.get_by_role("tab", name="Help", exact=True).get_attribute("aria-selected") == "true"

        page.evaluate("window.__finishHelpRequest()")
        page.locator(".status-menu-toggle").click()
        done_row = page.locator(".status-row", has_text="Drafting a Help answer")
        done_row.locator(".status-row-done").wait_for()
        assert done_row.locator(".status-row-done").inner_text().startswith("Done in ")

        page.set_viewport_size({"width": 375, "height": 812})
        page.locator(".status-menu-toggle").wait_for(state="visible")
        _assert_no_document_horizontal_overflow(page, "Status popover / mobile")
        assert errors == []
        browser.close()


def test_tool_panes_resist_visual_drift(server: str):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium not launchable: {exc}")

        page = browser.new_page(viewport={"width": 1366, "height": 900})
        errors = _mount_app(page, server)

        _assert_no_document_horizontal_overflow(page, "desktop initial")
        _assert_accordion_headers_visible(page, ".pane-sidebar", "desktop theory")
        _assert_accordion_headers_visible(page, ".pane-detail", "desktop methods")
        _walk_accordion_sections(page, ".pane-sidebar", "desktop theory")
        _walk_accordion_sections(page, ".pane-detail", "desktop methods")

        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_function(
            "() => document.querySelector('.app.mobile') || window.innerWidth > 760",
            timeout=30000,
        )
        _assert_no_document_horizontal_overflow(page, "mobile library")
        workspace_select = page.locator("#mobile-workspace-select")
        assert workspace_select.count() == 1, "mobile workspace select missing"
        assert page.locator(".menubar-nav").count() == 0, "desktop workspace tab strip rendered on mobile"
        workspace_select.select_option("discover")
        page.wait_for_function("() => localStorage.getItem('callosum.workspace') === 'discover'", timeout=30000)
        assert page.locator(".workspace-tabs:visible").count() >= 1
        _assert_no_document_horizontal_overflow(page, "mobile discover")
        workspace_select.select_option("help")
        page.wait_for_function("() => localStorage.getItem('callosum.workspace') === 'help'", timeout=30000)
        assert "Help" in page.inner_text("body")
        _assert_no_document_horizontal_overflow(page, "mobile help")
        workspace_select.select_option("library")

        panel_button = page.locator(".mobile-nav-btn", has_text="Panels")
        if panel_button.count():
            panel_button.first.click()
            page.wait_for_timeout(120)
            _assert_no_document_horizontal_overflow(page, "mobile panels")
            _assert_accordion_headers_visible(page, ".pane-sidebar", "mobile theory")
            _walk_accordion_sections(page, ".pane-sidebar", "mobile theory")

        detail_button = page.locator(".mobile-nav-btn", has_text="Details")
        if detail_button.count():
            detail_button.first.click()
            page.wait_for_timeout(120)
            _assert_no_document_horizontal_overflow(page, "mobile details")
            _assert_accordion_headers_visible(page, ".pane-detail", "mobile methods")
            _walk_accordion_sections(page, ".pane-detail", "mobile methods")

        browser.close()

    assert errors == [], f"unexpected console/page errors during visual drift pass: {errors}"
