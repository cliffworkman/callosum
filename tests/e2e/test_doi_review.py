"""Real assembled UI review flow with exact acceptance PDF, isolated DB and fake resolver."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

if not os.environ.get("CALLOSUM_RUN_E2E"):
    pytest.skip("set CALLOSUM_RUN_E2E=1 for browser regression", allow_module_level=True)

from playwright.sync_api import expect, sync_playwright  # noqa: E402

from app.backend.api import create_app  # noqa: E402
from app.backend.api.routers import capture  # noqa: E402
from app.backend.capture import pairing  # noqa: E402
from app.backend.embeddings.vector_store import InMemoryVectorStore  # noqa: E402
from tests.api_helpers import ApiFakeEmbeddingModel  # noqa: E402
from tests.test_capture import _envelope  # noqa: E402
from tests.test_provisional_doi_review import DOI, PDF, TITLE, Resolver  # noqa: E402


@pytest.mark.parametrize("edit_doi", [False, True])
def test_observed_doi_requires_preview_then_explicit_confirmation(temp_db_url, tmp_path, monkeypatch, edit_doi):
    monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", "ui")
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    Path(os.environ["CALLOSUM_SETTINGS_PATH"]).write_text(
        json.dumps({"onboarding_completed": True, "onboarding_version": 2}), encoding="utf-8"
    )
    capture._reset_for_tests()
    resolver = Resolver(resolved=False)
    app = create_app(
        db_url=temp_db_url,
        crossref_client=resolver,
        embedding_model=ApiFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=base, timeout=30, trust_env=False) as client:
            for _ in range(150):
                if server.started:
                    break
                time.sleep(0.1)
            assert server.started
            session = client.post("/capture/session", json={"pairing_secret": pairing.ensure_pairing_secret()})
            assert session.status_code == 200
            headers = {
                "x-callosum-capture": "browser-capture-v1",
                "Authorization": "Bearer " + session.json()["session_token"],
            }
            payload = _envelope(
                producer_kind="direct-pdf",
                pdf_bytes_from_active_tab=True,
                identifiers={},
                creators=[],
                year=None,
                field_provenance={},
                title="pmed.0020124.pdf",
                source_url="https://example.org/pmed.0020124.pdf",
            )
            admitted = client.post("/capture/item", json=payload, headers=headers)
            uploaded = client.post(
                f"/capture/item/{admitted.json()['capture_id']}/pdf",
                content=PDF.read_bytes(),
                headers={**headers, "content-type": "application/pdf"},
            )
            assert uploaded.json()["status"] == "direct_pdf_queued_for_review"
            item = client.get("/library/import-queue").json()["items"][0]
            path = f"/library/import-queue/{item['artifact_id']}"
            before = client.get(path).json()["evidence"]
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1200, "height": 900})
                errors, confirmations = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "request",
                    lambda req: confirmations.append(req.post_data_json) if req.url.endswith("/confirm") else None,
                )
                page.goto(base)
                page.get_by_role("button", name="Import Queue (1)").click()
                expect(page.get_by_text("Observed DOI — not verified as this paper.", exact=False)).to_be_visible()
                expect(page.get_by_role("button", name="Confirm this identity")).to_have_count(0)
                assert resolver.calls == [] and confirmations == []
                page.screenshot(path=str(tmp_path / "observed-doi.png"))
                page.get_by_role("button", name="Review DOI", exact=True).click()
                field = page.get_by_role("textbox", name="DOI to review")
                expect(field).to_have_value(DOI)
                if edit_doi:
                    field.fill("10.1234/manually-selected")
                page.get_by_role("button", name="Look up", exact=True).click()
                expect(page.locator(".reffind-outcome.err")).to_contain_text("unresolved")
                expect(page.get_by_role("button", name="Confirm this identity")).to_have_count(0)
                assert confirmations == [] and client.get(path).json()["evidence"] == before
                resolver.resolved = True
                page.get_by_role("button", name="Look up", exact=True).click()
                expect(page.get_by_text(TITLE, exact=True)).to_be_visible()
                expect(page.get_by_role("button", name="Confirm this identity")).to_be_visible()
                assert confirmations == [] and client.get(path).json()["evidence"] == before
                page.screenshot(path=str(tmp_path / "resolved-preview.png"))
                page.get_by_role("button", name="Confirm this identity").click()
                expect(page.get_by_role("button", name="Import Queue (1)")).to_have_count(0, timeout=30000)
                assert len(confirmations) == 1
                assert confirmations[0]["source"] == ("manual" if edit_doi else "candidate")
                after = client.get(path).json()["evidence"]
                assert all(after[key] == before[key] for key in ("candidates", "title_candidates", "resolutions"))
                assert after["user_actions"][-1]["action"] == (
                    "user_entered_doi" if edit_doi else "user_confirmed_candidate"
                )
                assert not errors
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=30)
        capture._reset_for_tests()
