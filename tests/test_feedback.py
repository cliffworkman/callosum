from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.feedback import bundle, destination

# The autouse conftest fixture points CALLOSUM_SETTINGS_PATH at a per-test tmp file, so the feedback root
# (`<settings dir>/feedback`) is per-test too — these never touch the real ~/.callosum store.

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff" + b"\x00" * 64


def _client(temp_db_url: str) -> TestClient:
    return TestClient(create_app(db_url=temp_db_url))


def _b64(data: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def test_destination_is_blank_by_default_and_round_trips(temp_db_url: str) -> None:
    # callosum ships with NO hard-coded maintainer address — a report is never pre-addressed for the user.
    client = _client(temp_db_url)
    config = client.get("/feedback/config").json()
    assert config["destination_email"] == ""
    assert config["destination_source"] is None

    r = client.put("/feedback/config", json={"set_destination_email": True, "destination_email": " a@b.org "})
    assert r.status_code == 200
    assert r.json()["destination_email"] == "a@b.org"
    assert r.json()["destination_source"] == "ui"
    assert client.get("/feedback/config").json()["destination_email"] == "a@b.org"

    client.put("/feedback/config", json={"set_destination_email": True, "destination_email": ""})
    assert client.get("/feedback/config").json()["destination_email"] == ""


def test_destination_env_fallback(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(destination.DESTINATION_ENV_VAR, "packaged@example.org")
    config = _client(temp_db_url).get("/feedback/config").json()
    assert config == {**config, "destination_email": "packaged@example.org", "destination_source": "env"}


def test_destination_rejects_a_non_address(temp_db_url: str) -> None:
    r = _client(temp_db_url).put("/feedback/config", json={"set_destination_email": True, "destination_email": "nope"})
    assert r.status_code == 422


def test_config_diagnostics_are_previewable_and_carry_no_secrets(temp_db_url: str) -> None:
    # Inspectability: GET returns EXACTLY what a submit would attach, so the form can show it first.
    diagnostics = _client(temp_db_url).get("/feedback/config").json()["diagnostics"]
    assert diagnostics["app"] == "callosum"
    assert diagnostics["ai_provider"] == "gemini"  # the provider id only
    assert set(diagnostics) & {"python", "platform", "db_revision", "data_egress_enabled"}
    joined = " ".join(diagnostics.values()).lower()
    assert "api_key" not in diagnostics and "sqlite" not in joined  # no key, no DB path
    assert temp_db_url.lower() not in joined


def test_submit_writes_a_bundle_and_returns_a_mailto_draft(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    client.put("/feedback/config", json={"set_destination_email": True, "destination_email": "maint@example.org"})
    r = client.post(
        "/feedback",
        json={
            "kind": "bug",
            "title": "PDF renders blank in two-up",
            "body": "Expected two pages; got white.",
            "steps": "1. open a paper\n2. switch to two-up",
            "reply_to": "me@example.edu",
            "client_diagnostics": {"user_agent": "Chromium", "viewport": "1440x900"},
            "screenshot": _b64(PNG),
        },
    )
    assert r.status_code == 201
    data = r.json()

    report = Path(data["report_path"])
    assert report.is_file() and report.name == "report.md"
    assert Path(data["screenshot_path"]).read_bytes() == PNG
    assert Path(data["screenshot_path"]).name == "screenshot.png"
    assert report.parent == Path(data["directory"])
    assert bundle.feedback_root().resolve() in report.parents  # written inside the feedback root, nowhere else

    text = report.read_text(encoding="utf-8")
    assert text == data["report_markdown"]  # the UI shows/copies exactly what was written
    assert "# [Bug report] PDF renders blank in two-up" in text
    assert "## Steps to reproduce" in text
    assert "| client.user_agent | Chromium |" in text
    assert "me@example.edu" in text

    assert data["mailto_url"].startswith("mailto:maint%40example.org?subject=")
    assert "callosum" in data["mailto_url"]


def test_submit_without_a_destination_still_saves_the_report(temp_db_url: str) -> None:
    # No address set → no draft to open, but the user's notes are never dropped on the floor.
    r = _client(temp_db_url).post(
        "/feedback", json={"kind": "feature", "title": "Sort by date added", "body": "please"}
    )
    assert r.status_code == 201
    assert r.json()["mailto_url"] is None
    assert Path(r.json()["report_path"]).is_file()
    assert "## What you'd like" in Path(r.json()["report_path"]).read_text(encoding="utf-8")


def test_diagnostics_are_opt_out(temp_db_url: str) -> None:
    r = _client(temp_db_url).post(
        "/feedback",
        json={
            "kind": "bug",
            "title": "No diagnostics please",
            "body": "opting out",
            "include_diagnostics": False,
            "client_diagnostics": {"user_agent": "Chromium"},
        },
    )
    text = Path(r.json()["report_path"]).read_text(encoding="utf-8")
    assert "## Diagnostics" not in text
    assert "Chromium" not in text  # the client half is dropped with the rest


@pytest.mark.parametrize(
    "payload",
    [
        "data:image/png;base64," + base64.b64encode(b"not a png at all").decode(),  # wrong magic bytes
        "data:text/html;base64," + base64.b64encode(b"<script>").decode(),  # not an image at all
        "!!!not base64!!!",
    ],
)
def test_submit_rejects_a_screenshot_that_is_not_an_image(temp_db_url: str, payload: str) -> None:
    r = _client(temp_db_url).post("/feedback", json={"kind": "bug", "title": "t", "body": "b", "screenshot": payload})
    assert r.status_code == 422


def test_submit_rejects_an_oversized_screenshot(temp_db_url: str) -> None:
    oversized = PNG + b"\x00" * (bundle.SCREENSHOT_MAX_BYTES + 1)
    r = _client(temp_db_url).post(
        "/feedback", json={"kind": "bug", "title": "t", "body": "b", "screenshot": _b64(oversized)}
    )
    assert r.status_code == 422


def test_submit_requires_a_title_and_a_description(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    assert client.post("/feedback", json={"kind": "bug", "title": "   ", "body": "b"}).status_code == 422
    assert client.post("/feedback", json={"kind": "bug", "title": "t", "body": ""}).status_code == 422
    assert client.post("/feedback", json={"kind": "nonsense", "title": "t", "body": "b"}).status_code == 422


def test_a_hostile_title_cannot_escape_the_feedback_folder(temp_db_url: str) -> None:
    # The folder name is built server-side from a timestamp + a sanitized slug — a path-ish title is inert.
    r = _client(temp_db_url).post(
        "/feedback", json={"kind": "bug", "title": "../../../../etc/passwd", "body": "traversal attempt"}
    )
    assert r.status_code == 201
    directory = Path(r.json()["directory"])
    assert bundle.feedback_root().resolve() == directory.parent
    assert ".." not in directory.name


def test_diagnostic_values_cannot_forge_the_report_table(temp_db_url: str) -> None:
    r = _client(temp_db_url).post(
        "/feedback",
        json={
            "kind": "bug",
            "title": "injection",
            "body": "b",
            "client_diagnostics": {"ua": "a | b\n| forged | row |"},
        },
    )
    text = Path(r.json()["report_path"]).read_text(encoding="utf-8")
    assert "| forged | row |" not in text
    assert "| client.ua | a \\| b \\| forged \\| row \\| |" in text


def test_client_diagnostics_are_bounded(temp_db_url: str) -> None:
    r = _client(temp_db_url).post(
        "/feedback",
        json={
            "kind": "bug",
            "title": "bounded",
            "body": "b",
            "client_diagnostics": {f"k{i}": "v" * 500 for i in range(60)},
        },
    )
    text = Path(r.json()["report_path"]).read_text(encoding="utf-8")
    assert text.count("| client.") == 24  # CLIENT_DIAGNOSTICS_MAX_KEYS
    assert "v" * 301 not in text


def test_a_jpeg_screenshot_keeps_its_own_extension(temp_db_url: str) -> None:
    r = _client(temp_db_url).post(
        "/feedback",
        json={"kind": "bug", "title": "jpeg", "body": "b", "screenshot": _b64(JPEG, "image/jpeg")},
    )
    assert Path(r.json()["screenshot_path"]).name == "screenshot.jpg"


def test_two_reports_in_the_same_second_do_not_collide(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    body = {"kind": "bug", "title": "same title", "body": "b"}
    first = client.post("/feedback", json=body).json()["directory"]
    second = client.post("/feedback", json=body).json()["directory"]
    assert first != second
    assert Path(first).is_dir() and Path(second).is_dir()


def test_mailto_body_is_truncated_but_points_at_the_full_report(temp_db_url: str) -> None:
    client = _client(temp_db_url)
    client.put("/feedback/config", json={"set_destination_email": True, "destination_email": "maint@example.org"})
    r = client.post("/feedback", json={"kind": "bug", "title": "long", "body": "x" * 19_000})
    url = r.json()["mailto_url"]
    assert len(url) < 4_000  # mail clients truncate/reject very long mailto: arguments
    assert "truncated" in url
    assert "x" * 19_000 in Path(r.json()["report_path"]).read_text(encoding="utf-8")  # the file itself is complete
