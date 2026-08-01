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

    # Isolate app-settings.json and pre-complete onboarding (inc 416): without this, a CI
    # runner with no prior ~/.callosum/app-settings.json shows the first-run wizard overlay,
    # which blocks every pre-existing smoke test's clicks on the app underneath.
    settings_path = tmp_path_factory.mktemp("e2e") / "app-settings.json"
    settings_path.write_text('{"onboarding_completed": true}', encoding="utf-8")

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
