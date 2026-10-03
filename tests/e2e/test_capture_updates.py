"""Local regression: committed capture -> visible queue, without focus/reload or a real extension.

This deliberately does not replace Cliff's real-Chrome/packaged-Mac acceptance.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

import fitz
import httpx
import pytest
import uvicorn

if not os.environ.get("CALLOSUM_RUN_E2E"):
    pytest.skip("set CALLOSUM_RUN_E2E=1 for browser regression", allow_module_level=True)

from playwright.sync_api import sync_playwright  # noqa: E402

from app.backend.api import create_app  # noqa: E402
from app.backend.api.routers import capture  # noqa: E402
from app.backend.capture import pairing  # noqa: E402
from app.backend.embeddings.vector_store import InMemoryVectorStore  # noqa: E402
from tests.api_helpers import ApiFakeEmbeddingModel  # noqa: E402
from tests.test_capture import _envelope, _FakeCrossref  # noqa: E402


def test_capture_queue_becomes_visible_without_focus_or_reload(temp_db_url, tmp_path, monkeypatch, record_property):
    monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", "ui")
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    settings = Path(os.environ["CALLOSUM_SETTINGS_PATH"])
    settings.write_text(json.dumps({"onboarding_completed": True, "onboarding_version": 2}), encoding="utf-8")
    capture._reset_for_tests()
    app = create_app(
        db_url=temp_db_url,
        crossref_client=_FakeCrossref(resolved=False),
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
        with httpx.Client(base_url=base, timeout=10, trust_env=False) as client:
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
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                page.locator(".lib-frame").wait_for(state="visible")
                # Wait for the actual observer's initial fetch + held subscription to be active.
                for _ in range(100):
                    if app.state.capture_updates._waiters:
                        break
                    page.wait_for_timeout(20)
                assert app.state.capture_updates._waiters
                timings = []
                for index in range(1, 4):
                    payload = _envelope(
                        producer_kind="direct-pdf",
                        pdf_bytes_from_active_tab=True,
                        identifiers={},
                        creators=[],
                        year=None,
                        field_provenance={},
                        title=f"fixture-{index}.pdf",
                        source_url=f"https://example.org/fixture-{index}.pdf",
                    )
                    admitted = client.post("/capture/item", json=payload, headers=headers)
                    assert admitted.status_code == 200
                    with fitz.open() as doc:
                        doc.new_page().insert_text((72, 72), f"Capture visibility fixture {index}")
                        pdf = doc.tobytes()
                    started = time.perf_counter()
                    uploaded = client.post(
                        f"/capture/item/{admitted.json()['capture_id']}/pdf",
                        content=pdf,
                        headers={**headers, "content-type": "application/pdf"},
                    )
                    completed = time.perf_counter()
                    assert uploaded.status_code == 200
                    assert uploaded.json()["status"] == "direct_pdf_queued_for_review"
                    page.get_by_role("button", name=f"Import Queue ({index})").wait_for(state="visible", timeout=2000)
                    visible = time.perf_counter()
                    timings.append(
                        {
                            "upload_to_visible_ms": round((visible - started) * 1000, 1),
                            "response_to_visible_ms": round((visible - completed) * 1000, 1),
                        }
                    )
                record_property("capture_visibility_timings", json.dumps(timings))
                print("CAPTURE_VISIBILITY_TIMINGS", json.dumps(timings))
                page.screenshot(path=str(tmp_path / "capture-queue.png"))
                assert not errors
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=30)
        capture._reset_for_tests()
        assert not thread.is_alive()
