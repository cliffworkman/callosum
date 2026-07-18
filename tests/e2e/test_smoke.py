"""Committed browser smoke test for the assembled frontend (CI's frontend gate).

Opt-in: the module is skipped unless ``CALLOSUM_RUN_E2E=1`` is set, so the default offline ``pytest``
run stays deterministic and dependency-light. CI sets the flag (after ``playwright install chromium``)
to exercise it. It spins up the real ``app.backend.api.app:app`` against a freshly migrated + seeded
temp database, loads ``/`` in headless Chromium, and asserts the React app mounts, the key surfaces
render, and there are **zero** console / page errors — the property the ephemeral ``.local/*_e2e``
manual checks used to verify by hand.
"""

from __future__ import annotations

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

    port = _free_port()
    env = {
        **os.environ,
        "CALLOSUM_DB_URL": db_url,
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
