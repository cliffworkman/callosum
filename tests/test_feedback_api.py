from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.feedback.domain import BugReport, FeatureRequest
from app.backend.feedback.relay_client import (
    FeedbackRelayError,
    HttpFeedbackRelayClient,
    RelaySubmissionResult,
)
from feedback_relay.app import create_app as create_relay_app
from feedback_relay.publisher import PublicationResult
from tests.test_feedback_domain import bug_payload


class FakeRelayClient:
    def __init__(self, failure: FeedbackRelayError | None = None) -> None:
        self.failure = failure
        self.reports: list[BugReport | FeatureRequest] = []
        self.tokens: list[str | None] = []

    def submit(self, report: BugReport | FeatureRequest, *, access_token: str | None = None) -> RelaySubmissionResult:
        if self.failure:
            raise self.failure
        self.reports.append(report)
        self.tokens.append(access_token)
        return RelaySubmissionResult(report_id=report.report_id)


class FakePublisher:
    def __init__(self) -> None:
        self.reports: list[BugReport | FeatureRequest] = []

    def publish(self, report: BugReport | FeatureRequest) -> PublicationResult:
        self.reports.append(report)
        return PublicationResult(provider="fake", publication_id=report.report_id)


def test_local_feedback_capability_exposes_only_safe_metadata(temp_db_url: str, monkeypatch) -> None:
    monkeypatch.setenv("CALLOSUM_APP_VERSION", "0.3.8")
    with TestClient(create_app(temp_db_url, feedback_relay_client=FakeRelayClient())) as client:
        response = client.get("/feedback/capability")
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert response.json()["app_version"] == "0.3.8"
    assert response.json()["installation_type"] == "tauri"
    assert response.json()["report_id"].startswith("fb_")
    assert "url" not in response.text.lower()
    assert "slack" not in response.text.lower()


def test_local_feedback_success_requires_relay_confirmation(temp_db_url: str) -> None:
    relay = FakeRelayClient()
    payload = bug_payload()
    with TestClient(create_app(temp_db_url, feedback_relay_client=relay)) as client:
        response = client.post("/feedback/reports", json=payload)
    assert response.status_code == 201
    assert response.json() == {"ok": True, "report_id": payload["report_id"], "status": "published"}
    assert relay.reports[0].report_id == payload["report_id"]


def test_local_api_to_hosted_relay_to_fake_publisher_vertical_slice(temp_db_url: str) -> None:
    publisher = FakePublisher()
    with TestClient(create_relay_app(publisher=publisher)) as hosted:
        relay_client = HttpFeedbackRelayClient("http://localhost/feedback/reports", client=hosted)
        with TestClient(create_app(temp_db_url, feedback_relay_client=relay_client)) as local:
            response = local.post("/feedback/reports", json=bug_payload())
    assert response.status_code == 201
    assert publisher.reports[0].report_id == bug_payload()["report_id"]


def test_local_feedback_disabled_and_failure_contract(temp_db_url: str, monkeypatch) -> None:
    monkeypatch.delenv("CALLOSUM_FEEDBACK_RELAY_URL", raising=False)
    with TestClient(create_app(temp_db_url)) as client:
        assert client.get("/feedback/capability").json()["enabled"] is False
        unavailable = client.post("/feedback/reports", json=bug_payload())
    assert unavailable.status_code == 503
    assert unavailable.json()["error"] == {
        "code": "feedback_service_unavailable",
        "message": "Feedback reporting is not configured.",
    }

    relay = FakeRelayClient(FeedbackRelayError("rate_limited", "Wait before retrying.", status_code=429))
    with TestClient(create_app(temp_db_url, feedback_relay_client=relay)) as client:
        failed = client.post("/feedback/reports", json=bug_payload())
    assert failed.status_code == 429
    assert failed.json()["error"] == {"code": "rate_limited", "message": "Wait before retrying."}


def test_local_feedback_rejects_invalid_input_before_relay(temp_db_url: str) -> None:
    relay = FakeRelayClient()
    payload = bug_payload()
    payload["channel"] = "arbitrary"
    with TestClient(create_app(temp_db_url, feedback_relay_client=relay)) as client:
        invalid = client.post("/feedback/reports", json=payload)
        wrong_type = client.post("/feedback/reports", content="{}", headers={"content-type": "text/plain"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_report"
    assert wrong_type.status_code == 415
    assert relay.reports == []


def test_local_feedback_logs_no_report_body_or_contact(temp_db_url: str) -> None:
    payload = bug_payload()
    payload.update(
        description="PRIVATE LOCAL BODY SENTINEL", contact="private-contact@example.org", contact_permitted=True
    )
    records: list[str] = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record.getMessage())
    target = logging.getLogger("callosum.feedback")
    target.addHandler(handler)
    try:
        with TestClient(create_app(temp_db_url, feedback_relay_client=FakeRelayClient())) as client:
            assert client.post("/feedback/reports", json=payload).status_code == 201
    finally:
        target.removeHandler(handler)
    logs = "\n".join(records)
    assert payload["report_id"] in logs
    assert "PRIVATE LOCAL BODY" not in logs
    assert "private-contact" not in logs
