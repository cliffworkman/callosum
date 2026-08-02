"""Fixed-destination HTTP client used by the local API to reach the hosted feedback relay."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.backend.feedback.domain import BugReport, FeatureRequest

DEFAULT_RELAY_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class RelaySubmissionResult:
    report_id: str


class FeedbackRelayError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.status_code = status_code


class FeedbackRelayClient(Protocol):
    def submit(
        self, report: BugReport | FeatureRequest, *, access_token: str | None = None
    ) -> RelaySubmissionResult: ...


def _validated_relay_url(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("feedback relay URL is invalid")
    is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise ValueError("feedback relay URL must use HTTPS")
    return value


class HttpFeedbackRelayClient:
    def __init__(self, url: str, *, client: httpx.Client | None = None, timeout: float = DEFAULT_RELAY_TIMEOUT_SECONDS):
        self._url = _validated_relay_url(url)
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False)

    @classmethod
    def from_env(cls) -> HttpFeedbackRelayClient | None:
        url = os.getenv("CALLOSUM_FEEDBACK_RELAY_URL", "").strip()
        if not url:
            return None
        try:
            timeout = float(os.getenv("CALLOSUM_FEEDBACK_RELAY_TIMEOUT_SECONDS", str(DEFAULT_RELAY_TIMEOUT_SECONDS)))
        except ValueError:
            timeout = DEFAULT_RELAY_TIMEOUT_SECONDS
        return cls(url, timeout=max(1.0, min(timeout, 15.0)))

    def submit(self, report: BugReport | FeatureRequest, *, access_token: str | None = None) -> RelaySubmissionResult:
        headers = {"Accept": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            response = self._client.post(self._url, json=report.model_dump(mode="json"), headers=headers)
        except httpx.TimeoutException as exc:
            raise FeedbackRelayError(
                "feedback_service_unavailable", "The feedback service timed out.", status_code=503
            ) from exc
        except httpx.HTTPError as exc:
            raise FeedbackRelayError(
                "feedback_service_unavailable", "The feedback service is unavailable.", status_code=503
            ) from exc

        safe_by_status = {
            400: ("invalid_report", "The feedback report is malformed."),
            413: ("report_too_large", "The feedback report is too large."),
            415: ("invalid_report", "The feedback report has an unsupported format."),
            422: ("invalid_report", "Please review the highlighted feedback fields."),
            429: ("rate_limited", "Too many feedback reports were submitted. Please try again later."),
            503: ("feedback_service_unavailable", "The feedback service is unavailable."),
        }
        if response.status_code != 201:
            code, message = safe_by_status.get(
                response.status_code, ("submission_failed", "The feedback report could not be submitted.")
            )
            safe_status = response.status_code if response.status_code in {413, 422, 429} else 503
            raise FeedbackRelayError(code, message, status_code=safe_status)
        try:
            data = response.json()
            report_id = data["report_id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise FeedbackRelayError("submission_failed", "The feedback service returned an invalid response.") from exc
        if report_id != report.report_id:
            raise FeedbackRelayError("submission_failed", "The feedback service returned an invalid response.")
        return RelaySubmissionResult(report_id=report_id)
