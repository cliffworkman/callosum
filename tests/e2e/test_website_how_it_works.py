"""Browser smoke for the public How Callosum Works page."""

from __future__ import annotations

import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

if not os.environ.get("CALLOSUM_RUN_E2E"):
    pytest.skip("set CALLOSUM_RUN_E2E=1 to run the browser e2e smoke", allow_module_level=True)

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import expect, sync_playwright  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return


def test_how_it_works_pipeline_navigation_and_progressive_enhancement():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(_QuietHandler, directory=str(PROJECT_ROOT / "www")),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(origin + "/how-it-works.html", wait_until="networkidle")

            expect(page.get_by_role("tab")).to_have_count(8)
            expect(page.locator('[role="tabpanel"]:visible')).to_have_count(1)
            expect(page.get_by_role("tab", name=re.compile(r"Import$"))).to_have_attribute("aria-selected", "true")
            page.get_by_role("tab", name=re.compile(r"Verify$")).click()
            expect(page.locator("#stage-panel-verify")).to_be_visible()
            assert page.evaluate("location.hash") == "#stage-verify"
            page.get_by_role("tab", name=re.compile(r"Verify$")).press("ArrowRight")
            expect(page.get_by_role("tab", name=re.compile(r"Trace$"))).to_have_attribute("aria-selected", "true")

            page.set_viewport_size({"width": 375, "height": 812})
            page.reload(wait_until="networkidle")
            assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            assert errors == []

            no_js_context = browser.new_context(java_script_enabled=False, viewport={"width": 1200, "height": 900})
            no_js = no_js_context.new_page()
            no_js.goto(origin + "/how-it-works.html", wait_until="load")
            expect(no_js.get_by_role("tabpanel")).to_have_count(8)
            expect(no_js.locator('[role="tabpanel"]:visible')).to_have_count(8)
            no_js_context.close()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
