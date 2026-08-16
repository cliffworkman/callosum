"""Browser smoke for the built, backend-free static demo."""

from __future__ import annotations

import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

if not os.environ.get("CALLOSUM_RUN_E2E"):
    pytest.skip("set CALLOSUM_RUN_E2E=1 to run the browser e2e smoke", allow_module_level=True)

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import expect, sync_playwright  # noqa: E402

from app.backend.api.startup import PROJECT_ROOT  # noqa: E402
from tools.demo.build_demo import build_demo  # noqa: E402


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return


def test_static_demo_starts_in_library_exposes_saved_methods_and_never_leaves_origin(tmp_path):
    site = tmp_path / "callosum-demo"
    build_demo(PROJECT_ROOT / "demo" / "snapshot-v1.json", site, "/callosum-demo/")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(tmp_path)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    route = origin + "/callosum-demo/synthesis/"
    errors: list[str] = []
    requests: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                permissions=["clipboard-read", "clipboard-write"],
            )
            page = context.new_page()
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            page.goto(route, wait_until="networkidle")
            page.wait_for_selector(".paper")
            assert page.locator(".paper:visible").count() == 3
            expect(page.locator(".paper.sel .paper-title")).to_contain_text("Morality is in the eye")
            assert page.get_by_role("tab", name="Library", exact=True).get_attribute("aria-selected") == "true"
            assert page.locator(".menubar-nav [role=tab]").all_inner_texts() == [
                "My Publications",
                "Library",
                "Synthesize",
                "Discover",
                "Work",
            ]
            assert page.locator(".summary-sentence:visible").count() == 0
            assert "Saved online demo" in page.locator(".demo-mode-banner").inner_text()
            mutation_status = page.evaluate(
                """async () => {
                    const response = await window.CALLOSUM_DATA_PROVIDER.fetch('/summarize', {method: 'POST'});
                    return response.status;
                }"""
            )
            assert mutation_status == 405
            assert "unavailable" in page.locator(".demo-mode-banner").inner_text().lower()
            page.get_by_role("button", name="Dismiss demo notice", exact=True).click()
            # A just-triggered action-specific lock remains visible for its bounded seven-second alert window;
            # dismissing the persistent card takes effect as soon as that useful explanation clears.
            expect(page.locator(".demo-mode-banner")).to_have_count(0, timeout=10_000)

            search = page.get_by_placeholder("Search title, author, journal…")
            search.fill("Morality")
            expect(page.locator(".paper:visible")).to_have_count(1)
            assert "Morality is in the eye" in page.locator(".paper-title:visible").inner_text()
            search.fill("")
            expect(page.locator(".paper:visible")).to_have_count(3)

            # WIP is the real Library sub-workspace over two generated synthetic manuscripts, not a parallel UI.
            page.get_by_role("button", name="WIP", exact=True).click()
            expect(page.locator(".wip-card:visible")).to_have_count(2)
            expect(page.locator(".demo-wip-note")).to_contain_text("genuine saved check results")
            page.locator(".wip-card:visible").first.dblclick()
            expect(page.locator(".wip-work-tabs")).to_be_visible()
            expect(page.locator(".workspace-slot:visible .settings-note")).to_contain_text(
                "Synthetic public-demo manuscript"
            )
            expect(page.locator('.workspace-slot:visible input[placeholder="Integrated review"]')).to_be_disabled()
            page.get_by_role("button", name="Structure", exact=True).click()
            expect(page.locator(".workspace-slot:visible .wip-section-row select").first).to_be_disabled()
            page.get_by_role("button", name="References", exact=True).click()
            expect(page.locator(".wip-reference-row:visible")).to_have_count(3)
            expect(page.locator(".wip-reference-row:visible select").first).to_be_disabled()
            page.get_by_role("button", name="Checks", exact=True).click()
            expect(page.locator(".wip-tool-run:visible")).to_have_count(5)
            expect(page.get_by_role("button", name="Run statcheck", exact=True)).to_be_disabled()
            expect(
                page.locator(".workspace-slot:visible .ref-panel").get_by_role(
                    "button", name="Check references", exact=True
                )
            ).to_be_disabled()
            expect(page.locator(".wip-checkpoint-row:visible")).to_have_count(9)
            expect(page.get_by_text("Funding searches", exact=True)).to_be_visible()
            expect(page.get_by_text("Journal searches", exact=True)).to_be_visible()
            page.get_by_role("button", name="Library", exact=True).click()
            expect(page.locator(".paper:visible")).to_have_count(3)

            # The saved organizational layer uses the same Axes / Tags / Queue panels as the desktop app.
            page.locator(".acc-header", has_text="Axes").click()
            page.get_by_role("tab", name="Axes", exact=True).click()
            expect(page.locator(".axis-label")).to_have_count(2)
            page.locator(".axis-label", has_text="Anomalous-is-bad bias").click()
            expect(page.locator(".axis-item:not(.axis-mypubs) .axis-paper")).to_have_count(3)
            page.get_by_role("tab", name="Tags", exact=True).click()
            expect(page.locator(".tags-panel-item")).to_have_count(4)
            page.get_by_role("tab", name="Queue", exact=True).click()
            expect(page.locator(".queue-row")).to_have_count(3)
            expect(page.locator(".queue-group-head.pr-high")).to_contain_text("High 1")
            expect(page.locator(".queue-group-head.pr-normal")).to_contain_text("Normal 1")
            expect(page.locator(".queue-group-head.pr-none")).to_contain_text("Unprioritized 1")

            # Each paper exposes its authentic saved statcheck response and all four checklist endpoints.
            expected_statcheck = ("9 checked", "2 checked", "7 checked")
            for paper_index in range(3):
                page.locator(".paper:visible").nth(paper_index).click()
                page.locator(".acc-header", has_text="Statistics").click()
                expect(page.locator(".detail-statcheck:visible .statcheck-summary")).to_contain_text(
                    expected_statcheck[paper_index]
                )
                expect(page.locator(".detail-statcheck:visible .statcheck-actions button")).to_be_disabled()

                page.locator(".acc-header", has_text="Checklists").click()
                page.get_by_role("tab", name="Transparency signals", exact=True).click()
                expect(page.locator(".pane-tab.active .lmm-summary").first).to_contain_text("7 checks")
                expect(page.locator(".pane-tab.active .bayes-check-item")).to_have_count(7)

                page.get_by_role("tab", name="Mixed-model reporting", exact=True).click()
                if paper_index < 2:
                    expect(page.locator(".pane-tab.active .lmm-summary").first).to_contain_text("7 checks")
                else:
                    expect(page.locator(".pane-tab.active .tag-suggest-empty")).to_contain_text(
                        "doesn't appear to use a linear mixed model"
                    )

                page.get_by_role("tab", name="Bayesian statistics", exact=True).click()
                expect(page.locator(".pane-tab.active .tag-suggest-empty")).to_contain_text(
                    "doesn't appear to report a Bayesian analysis"
                )

                page.get_by_role("tab", name="Meta-analysis reporting", exact=True).click()
                if paper_index == 2:
                    expect(page.locator(".pane-tab.active .tag-suggest-empty")).to_contain_text(
                        "doesn't appear to report a meta-analysis"
                    )
                else:
                    expect(page.locator(".pane-tab.active .lmm-summary").first).to_contain_text("7 checks")
                    expect(page.locator(".pane-tab.active .bayes-check-item")).to_have_count(7)

            if page.locator(".detail-tags:visible").count() == 0:
                page.locator(".acc-header", has_text="Details").click()
            page.get_by_role("button", name="Show saved suggestions", exact=False).click()
            expect(page.locator(".detail-tags .tag-suggest-chip")).to_have_count(8)

            # The saved Status receipt is persistent and opens the exact completed synthesis.
            page.get_by_role("button", name="Status", exact=False).click()
            synthesis_receipt = page.get_by_role("button", name="Synthesize · Ask", exact=True)
            expect(synthesis_receipt).to_be_visible()
            synthesis_row = page.locator(".status-row").filter(has=synthesis_receipt)
            expect(synthesis_row.locator(".status-row-done")).to_have_text("Done")
            expect(page.locator(".status-row-dismiss")).to_have_count(0)
            synthesis_receipt.click()
            page.wait_for_selector(".summary-sentence")
            assert page.locator(".summary-sentence").count() == 5
            assert page.locator(".summary-sentence.flagged").count() == 0
            expect(page.locator(".synth-overview")).to_be_visible()
            expect(page.locator(".synth-overview .overview-line")).to_have_count(2)
            page.locator(".synth-overview .overview-line").first.click()
            assert page.locator("#summary-claim-1").evaluate("element => element.classList.contains('claim-flash')")
            assert "Generation is unavailable" in page.locator(".demo-synth-note").inner_text()

            local_citation = page.locator(".citation").first
            local_citation.locator("summary").click()
            local_citation.locator("button", has_text="Open source").first.click()
            page.wait_for_selector(".pdf-page-wrap", timeout=60_000)
            assert page.locator(".pdf-page-wrap").count() >= 1

            page.goto(route, wait_until="networkidle")
            page.wait_for_selector(".paper")
            assert page.locator(".summary-sentence:visible").count() == 0

            # Every published-paper Meta-Reference outcome is a real saved result, including honest zero-context rows.
            expected_meta_reference = (
                (0, 0, 0, 0, 0, 0),
                (66, 4, 4, 12, 12, 29),
                (36, 4, 4, 12, 2, 26),
            )
            for paper_index, (
                checked,
                active,
                signal_count,
                candidate_count,
                incoming_count,
                outgoing_count,
            ) in enumerate(expected_meta_reference):
                page.get_by_role("tab", name="Library", exact=True).click()
                page.locator(".paper:visible").nth(paper_index).click()
                page.get_by_role("tab", name="Work", exact=True).click()
                page.get_by_role("tab", name="Meta-Reference", exact=True).click()
                meta_reference = page.locator(".cite-workspace:visible")
                expect(meta_reference.locator(".ref-summary")).to_contain_text(
                    f"Checked {checked} linked references · {active} active reference signals"
                )
                expect(meta_reference.locator(".ref-card")).to_have_count(active)
                expect(meta_reference.get_by_role("button", name="Check references", exact=True)).to_be_disabled()
                for button in meta_reference.locator(".ref-review-btn").all():
                    expect(button).to_be_disabled()
                subsections = meta_reference.locator(":scope > .settings-subsection")
                expect(subsections).to_have_count(3)
                concentration = subsections.nth(0)
                expect(concentration.locator(".cite-equity-signal")).to_have_count(signal_count)
                expect(concentration.locator(".cite-equity-cand")).to_have_count(candidate_count)
                for button in (
                    concentration.locator(".cite-equity-cand .btn-link").filter(has_text="Add to library").all()
                ):
                    expect(button).to_be_disabled()
                expect(subsections.nth(1).locator(".citec-item")).to_have_count(incoming_count)
                expect(subsections.nth(2).locator(".citec-item")).to_have_count(outgoing_count)

            # Demo mode restores every real top-level workspace and subtab without relaxing the static boundary.
            page.get_by_role("tab", name="Discover", exact=True).click()
            assert page.locator(".workspace-slot:visible .workspace-tabs [role=tab]").all_inner_texts() == [
                "Feed",
                "Search",
                "Journals",
                "Funding",
                "Followed Authors",
            ]
            expect(page.locator(".workspace-slot:visible .demo-workspace-note")).to_contain_text("Saved demo view")
            expect(page.locator(".feed-sub:visible")).to_have_count(9)
            expect(page.locator(".feed-item:visible")).to_have_count(200)
            expect(
                page.locator(".settings-note:visible", has_text="same 200-item default as live Callosum")
            ).to_be_visible()
            page.get_by_role("button", name="Starred", exact=True).click()
            expect(page.locator(".feed-item:visible")).to_have_count(1)
            page.get_by_role("button", name="Reset read/star practice", exact=True).click()
            expect(page.locator(".feed-item:visible")).to_have_count(0)
            page.get_by_role("button", name="All", exact=True).click()
            expect(page.locator(".feed-item:visible")).to_have_count(200)
            page.get_by_role("button", name="Refresh", exact=True).click()
            expect(page.locator(".demo-mode-banner")).to_contain_text("external journal and search providers")
            page.get_by_role("tab", name="Funding", exact=True).click()
            expect(page.locator(".workspace-slot:visible .demo-workspace-note")).to_contain_text("Saved demo view")
            expect(page.locator(".funding-card:visible").first).to_be_visible()
            expect(page.locator(".funding-llm-status:visible")).to_contain_text("45 items")
            expect(page.get_by_role("button", name="LLM-triaged", exact=True)).to_have_class("tags-srcfilter-btn on")
            funding_summary = page.locator(".funding-result-summary:visible")
            expect(funding_summary).to_contain_text("44")
            expect(funding_summary).to_contain_text("grouped results in the full saved run")
            with page.expect_download() as download_info:
                page.get_by_role("button", name="Export CSV", exact=True).click()
            assert download_info.value.suggested_filename == "funding-run-1.csv"
            assert "llm_triage_label" in download_info.value.path().read_text(encoding="utf-8")
            page.get_by_role("tab", name="Search", exact=True).click()
            expect(page.locator(".discover-item:visible")).to_have_count(5)
            expect(page.locator(".workspace-slot:visible .demo-workspace-note")).to_contain_text("Saved demo view")
            page.get_by_role("tab", name="Journals", exact=True).click()
            expect(page.locator(".pub-card:visible")).to_have_count(8)
            page.get_by_role("tab", name="Followed Authors", exact=True).click()
            expect(page.locator(".followed-authors .gap-row:visible")).to_have_count(50)
            page.get_by_role("button", name="Refresh all", exact=True).click()
            expect(page.locator(".demo-mode-banner")).to_contain_text("local backend and OpenAlex access")
            page.get_by_role("tab", name="Work", exact=True).click()
            assert page.locator(".workspace-slot:visible .workspace-tabs [role=tab]").all_inner_texts() == [
                "Cite",
                "Meta-Reference",
                "CRediT",
                "Statements",
                "Meta-Analyze",
            ]
            page.get_by_role("tab", name="Statements", exact=True).click()
            expect(page.locator(".workspace-slot:visible .demo-workspace-note")).to_contain_text("Saved demo view")
            expect(page.locator(".statements-block:visible")).to_have_count(7)
            page.get_by_role("tab", name="CRediT", exact=True).click()
            expect(page.locator(".credit-output:visible")).to_contain_text("Clifford I. Workman")
            page.get_by_role("tab", name="Cite", exact=True).click()
            expect(page.locator(".cite-results:visible")).to_be_visible()
            expect(page.locator(".cite-card:visible").first).to_be_visible()
            page.locator(".cite-card:visible").first.get_by_role("button", name="Cite", exact=True).click()
            expect(
                page.locator(".cite-card:visible").first.get_by_role("button", name="Copied ✓", exact=True)
            ).to_be_visible()
            page.get_by_role("tab", name="Meta-Analyze", exact=True).click()
            expect(page.locator(".wb-grid:visible tbody tr")).to_have_count(3)
            with page.expect_download() as workbench_download:
                page.locator(".wb-head").get_by_role("button", name="metafor", exact=True).click()
            assert workbench_download.value.suggested_filename.endswith("-metafor.csv")
            expect(page.locator(".wb-grid:visible .wb-cellin").first).to_be_disabled()

            page.get_by_role("tab", name="My Publications", exact=True).click()
            expect(page.locator(".mypubs-head h2")).to_contain_text("Clifford I. Workman")
            expect(page.locator(".mypubs-pubs-title")).to_have_text("Publications (2)")
            expect(page.locator(".mypubs-pubs .paper")).to_have_count(2)
            expect(page.locator(".mypubs-pubs .paper-tier", has_text="METADATA ONLY")).to_have_count(0)
            expect(page.locator(".mypubs-summary-text")).to_contain_text("facial appearance")
            expect(page.locator(".mypubs-summary .settings-note")).to_contain_text("Saved research-summary draft")
            expect(page.locator(".mypubs-domains .domain-row")).to_have_count(1)
            expect(page.locator(".mypubs-domains .settings-note")).to_contain_text(
                "starts at four confirmed publications"
            )
            page.locator(".mypubs-chart-flip").get_by_role("button", name="Citations", exact=True).click()
            citation_chart = page.get_by_role("img", name="Citations by year", exact=True)
            expect(citation_chart).to_be_visible()
            expect(citation_chart.locator(".pubs-bar")).to_have_count(2)
            page.locator(".mypubs-pubs .paper-cite").first.click()
            expect(page.locator(".axis-modal-head")).to_contain_text("Cited by")
            expect(page.locator(".citing-row")).to_have_count(30)
            expect(page.locator(".axis-modal-note:visible")).to_contain_text("saved cited-by result")
            expect(page.locator(".citing-import").first).to_be_disabled()
            page.locator(".citing-close").click()
            gap_panel = page.locator('section[aria-labelledby="mypubs-citation-gaps-title"]')
            expect(gap_panel.locator(".mypubs-gap-card")).to_have_count(25)
            expect(gap_panel.get_by_role("button", name="↻ Refresh gaps", exact=True)).to_be_disabled()
            topic_panel = page.locator('section[aria-labelledby="mypubs-emerging-topics-title"]')
            expect(topic_panel.locator(".mypubs-topic-card")).to_have_count(4)
            expect(topic_panel.get_by_role("button", name="↻ Refresh topics", exact=True)).to_be_disabled()
            author_panel = page.locator('section[aria-labelledby="mypubs-citing-authors-title"]')
            expect(author_panel.locator(".mypubs-topic-card")).to_have_count(3)
            expect(author_panel.get_by_role("button", name="↻ Refresh authors", exact=True)).to_be_disabled()
            page.get_by_role("tab", name="Help", exact=True).click()
            expect(page.locator(".help-section").first).to_be_visible()
            page.get_by_role("tab", name="Settings", exact=True).click()
            assert page.get_by_role("tab", name="Settings", exact=True).count() == 1, errors
            expect(page.get_by_role("tab", name="Settings", exact=True)).to_have_attribute("aria-selected", "true")

            page.get_by_role("tab", name="Synthesize", exact=True).click()
            page.wait_for_selector(".summary-sentence")
            assert page.locator(".summary-sentence").count() == 5
            page.get_by_role("tab", name="Critique", exact=True).click()
            expect(page.locator(".cr-backbone")).to_be_visible()
            assert page.locator(".cr-backbone .bayes-check-item").count() >= 2
            expect(page.get_by_text("Saved deterministic critical read", exact=False)).to_be_visible()

            # He et al. carries the saved, deterministic OSF registration/publication crosswalk through the real UI.
            page.get_by_role("tab", name="Library", exact=True).click()
            page.locator(".paper:visible").filter(has_text="What is good is beautiful").click()
            page.get_by_role("tab", name="Synthesize", exact=True).click()
            page.get_by_role("tab", name="Meta-Preregistration", exact=True).click()
            expect(page.locator(".registration-candidate-card")).to_have_count(1)
            expect(page.locator(".registration-comparison-row")).to_have_count(12)
            expect(page.locator(".registration-row-triage:visible")).to_have_count(12)
            expect(page.get_by_role("button", name="AI-focused", exact=True)).to_be_visible()
            page.get_by_role("button", name="All rows", exact=True).click()
            expect(page.locator(".registration-comparison-row")).to_have_count(12)
            expect(page.locator(".registration-row-triage:visible")).to_have_count(12)
            expect(page.get_by_text("No explicit reuse license", exact=False).first).to_be_visible()
            expect(page.get_by_role("button", name="Re-run comparison", exact=True)).to_be_disabled()
            page.set_viewport_size({"width": 375, "height": 812})
            page.reload(wait_until="networkidle")
            page.wait_for_selector(".paper")
            assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            assert errors == []
            assert all(url.startswith(origin + "/callosum-demo/") for url in requests)
            assert not any("/health" in url or "/papers?" in url or "/summaries/" in url for url in requests)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
