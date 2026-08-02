"""Slack incoming-webhook publisher with isolated, non-executable untrusted formatting."""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

import httpx

from app.backend.feedback.domain import BugReport, FeatureRequest, ReportType
from feedback_relay.publisher import PublicationError, PublicationResult

SLACK_TIMEOUT_SECONDS = 5.0
_MASS_MENTION_RE = re.compile(r"@(channel|here|everyone)\b", re.IGNORECASE)
_SLACK_CONTROL_RE = re.compile(r"<((?:[@!][^>\n]{0,100}|(?:https?|mailto):[^>\n]{0,500}))>", re.IGNORECASE)


def neutralize_slack_formatting(value: str) -> str:
    """Keep ordinary text legible while disabling mass mentions, entity mentions, and link markup."""
    value = _MASS_MENTION_RE.sub(lambda match: f"@\u200b{match.group(1)}", value)
    return _SLACK_CONTROL_RE.sub(lambda match: f"‹{match.group(1)}›", value)


def _plain_block(text: str) -> dict:
    return {"type": "section", "text": {"type": "plain_text", "text": text, "emoji": False}}


def _section_blocks(label: str, value: str | None) -> list[dict]:
    if not value:
        return []
    safe = neutralize_slack_formatting(value)
    prefix = f"{label}:\n"
    first_room = 3000 - len(prefix)
    chunks = [safe[:first_room]]
    rest = safe[first_room:]
    while rest:
        chunks.append(rest[:3000])
        rest = rest[3000:]
    return [_plain_block(prefix + chunks[0]), *[_plain_block(chunk) for chunk in chunks[1:]]]


def _label(value: object) -> str:
    return str(value).replace("_", " ").title()


def format_slack_message(report: BugReport | FeatureRequest) -> dict:
    kind = "BUG" if report.report_type == ReportType.BUG else "FEATURE"
    title = neutralize_slack_formatting(report.title)
    header = f"[{kind}] {title}"[:150]
    metadata = [
        f"Report ID: {report.report_id}",
        f"Component: {_label(report.component.value)}",
        f"Callosum: {neutralize_slack_formatting(report.app_version)}",
        f"OS: {neutralize_slack_formatting(report.operating_system)}",
        f"Installation: {_label(report.installation_type.value)}",
        f"Contact permitted: {'Yes' if report.contact_permitted else 'No'}",
        f"Submitted: {report.submitted_at.isoformat()}",
    ]
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": header, "emoji": False}},
        _plain_block("\n".join(metadata)),
        *_section_blocks("Title", report.title),
        *_section_blocks("Description", report.description),
    ]
    if report.contact_permitted and report.contact:
        blocks.extend(_section_blocks("Contact", report.contact))
    if isinstance(report, BugReport):
        blocks[1]["text"]["text"] += (
            f"\nReporter-assessed impact: {_label(report.reporter_assessed_impact.value)}"
            f"\nReproducibility: {_label(report.reproducibility.value)}"
        )
        blocks.extend(_section_blocks("Observed", report.actual_behavior))
        blocks.extend(_section_blocks("Expected", report.expected_behavior))
        steps = "\n".join(f"{index}. {step}" for index, step in enumerate(report.reproduction_steps, 1))
        blocks.extend(_section_blocks("Reproduction steps", steps))
    else:
        blocks.extend(_section_blocks("Requested capability", report.requested_capability))
        blocks.extend(_section_blocks("Problem or workflow", report.problem_or_workflow))
        blocks.extend(_section_blocks("Current workaround", report.current_workaround))
        blocks.extend(_section_blocks("Why it matters", report.why_it_matters))

    return {"text": f"[{kind}] Callosum feedback {report.report_id}", "blocks": blocks[:50]}


def _validated_webhook_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"hooks.slack.com", "hooks.slack-gov.com"}
        or parsed.username
        or parsed.password
        or parsed.fragment
        or not parsed.path.startswith("/services/")
    ):
        raise ValueError("feedback Slack webhook configuration is invalid")
    return value


class SlackWebhookPublisher:
    def __init__(self, webhook_url: str, *, client: httpx.Client | None = None, timeout: float = SLACK_TIMEOUT_SECONDS):
        self._webhook_url = _validated_webhook_url(webhook_url)
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False)

    @classmethod
    def from_env(cls) -> SlackWebhookPublisher | None:
        webhook_url = os.getenv("CALLOSUM_FEEDBACK_SLACK_WEBHOOK_URL", "").strip()
        return cls(webhook_url) if webhook_url else None

    def publish(self, report: BugReport | FeatureRequest) -> PublicationResult:
        try:
            response = self._client.post(self._webhook_url, json=format_slack_message(report))
        except httpx.TimeoutException as exc:
            raise PublicationError("slack_timeout", unavailable=True) from exc
        except httpx.HTTPError as exc:
            raise PublicationError("slack_unavailable", unavailable=True) from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise PublicationError("slack_rejected")
        return PublicationResult(provider="slack", publication_id=report.report_id)
