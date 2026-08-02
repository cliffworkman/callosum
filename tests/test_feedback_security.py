from __future__ import annotations

from pathlib import Path

import pytest

from app.backend.feedback.relay_client import HttpFeedbackRelayClient
from feedback_relay.slack import SlackWebhookPublisher

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_slack_secret_setting_is_absent_from_distributed_client_sources() -> None:
    forbidden = ("CALLOSUM_FEEDBACK_SLACK_WEBHOOK_URL", "hooks.slack.com/services/")
    client_files = [
        PROJECT_ROOT / "app" / "frontend",
        PROJECT_ROOT / "callosum-app.html",
        PROJECT_ROOT / "app" / "desktop-shell" / "packaging" / "stage_source.py",
    ]
    client_files.extend((PROJECT_ROOT / "app" / "frontend" / "js").glob("*.jsx"))
    client_files.extend(
        [PROJECT_ROOT / "app" / "frontend" / "index.html", PROJECT_ROOT / "app" / "frontend" / "styles.css"]
    )
    tauri = PROJECT_ROOT / "app" / "desktop-shell" / "src-tauri"
    client_files.extend((tauri / "src").rglob("*.rs"))
    client_files.extend([tauri / "tauri.conf.json", tauri / "Cargo.toml"])
    for file in client_files:
        if not file.is_file():
            continue
        text = file.read_text(encoding="utf-8", errors="ignore")
        assert all(secret not in text for secret in forbidden), file


def test_only_hosted_relay_runtime_reads_the_slack_webhook_setting() -> None:
    runtime_hits: list[Path] = []
    for root in (PROJECT_ROOT / "app" / "backend", PROJECT_ROOT / "integrations", PROJECT_ROOT / "feedback_relay"):
        for file in root.rglob("*.py"):
            if "CALLOSUM_FEEDBACK_SLACK_WEBHOOK_URL" in file.read_text(encoding="utf-8", errors="ignore"):
                runtime_hits.append(file.relative_to(PROJECT_ROOT))
    assert runtime_hits == [Path("feedback_relay/slack.py")]


@pytest.mark.parametrize(
    "url",
    [
        "http://feedback.example.org/feedback/reports",
        "https://user:password@feedback.example.org/feedback/reports",
        "file:///tmp/socket",
    ],
)
def test_desktop_relay_configuration_rejects_downgrade_and_credentials(url: str) -> None:
    with pytest.raises(ValueError, match="feedback relay URL"):
        HttpFeedbackRelayClient(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.slack.com/services/TEST/FAKE/SECRET",
        "https://example.org/services/TEST/FAKE/SECRET",
        "https://user:pass@hooks.slack.com/services/TEST/FAKE/SECRET",
        "https://hooks.slack.com/not-services/TEST",
    ],
)
def test_slack_publisher_rejects_non_slack_or_credentialed_webhooks(url: str) -> None:
    with pytest.raises(ValueError, match="webhook configuration"):
        SlackWebhookPublisher(url)
