from __future__ import annotations

from pathlib import Path

from app.backend.api.frontend import assemble_jsx


def test_feedback_surface_is_wired_to_the_local_api_with_exact_preview() -> None:
    raw = assemble_jsx()
    assert "function FeedbackLauncher(" in raw
    assert "function FeedbackDialog(" in raw
    assert "<FeedbackLauncher compact />" in raw and "<FeedbackLauncher />" in raw
    assert 'api("/feedback/capability")' in raw
    assert 'API_BASE + "/feedback/reports"' in raw
    assert "body: preview" in raw
    assert "Exact transmission preview" in raw
    assert "JSON.stringify(payload, null, 2)" in raw
    assert 'aria-modal="true"' in raw
    assert 'role="dialog"' in raw
    assert 'window.addEventListener("keydown", onKey, true)' in raw
    assert 'nav={{ modal: "feedback" }}' in raw


def test_feedback_surface_names_forbidden_automatic_collection_and_has_no_outbox() -> None:
    feedback = Path("app/frontend/js/18b_feedback.jsx").read_text(encoding="utf-8")
    assert "does not attach PDFs, library or" in feedback
    assert "file paths, logs, prompts, clipboard contents, or machine identifiers" in feedback
    assert "localStorage" not in feedback
    assert "indexedDB" not in feedback
    assert "webhook" not in feedback.lower()
    assert "hooks.slack" not in feedback.lower()
    assert "CALLOSUM_FEEDBACK_SLACK" not in feedback
    assert "slack_blocks" not in feedback
    assert "destination_channel" not in feedback
