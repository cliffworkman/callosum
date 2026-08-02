from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import httpx
from fastapi.testclient import TestClient

from app.backend.feedback.domain import BugReport, FeatureRequest, validate_feedback_payload
from feedback_relay.app import create_app
from feedback_relay.publisher import PublicationError, PublicationResult
from feedback_relay.slack import SlackWebhookPublisher, format_slack_message, neutralize_slack_formatting
from sync_server.auth import Identity, InvalidToken
from sync_server.rate_limit import RateLimiter
from tests.test_feedback_domain import bug_payload, feature_payload


@dataclass
class FakePublisher:
    failure: Exception | None = None
    reports: list[BugReport | FeatureRequest] = field(default_factory=list)

    def publish(self, report: BugReport | FeatureRequest) -> PublicationResult:
        if self.failure:
            raise self.failure
        self.reports.append(report)
        return PublicationResult(provider="fake", publication_id=report.report_id)


class FakeVerifier:
    def verify(self, token: str) -> Identity:
        if token != "valid":
            raise InvalidToken("invalid")
        return Identity(sub="account-1")


def test_relay_publishes_valid_bug_and_feature_reports() -> None:
    publisher = FakePublisher()
    with TestClient(create_app(publisher=publisher)) as client:
        for payload in (bug_payload(), feature_payload()):
            response = client.post("/feedback/reports", json=payload)
            assert response.status_code == 201
            assert response.json() == {"ok": True, "report_id": payload["report_id"], "status": "published"}
    assert [report.report_type.value for report in publisher.reports] == ["bug", "feature"]


def test_relay_fails_closed_without_a_publisher() -> None:
    with TestClient(create_app(publisher=None)) as client:
        assert client.get("/health").json()["configured"] is False
        response = client.post("/feedback/reports", json=bug_payload())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "feedback_service_unavailable"


def test_relay_handles_timeout_rejection_and_unexpected_publisher_failure() -> None:
    cases = [
        (PublicationError("slack_timeout", unavailable=True), 503, "feedback_service_unavailable"),
        (PublicationError("slack_rejected"), 502, "submission_failed"),
        (RuntimeError("private failure"), 502, "submission_failed"),
    ]
    for failure, status, code in cases:
        with TestClient(create_app(publisher=FakePublisher(failure=failure))) as client:
            response = client.post("/feedback/reports", json=bug_payload())
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert "private failure" not in response.text


def test_relay_rejects_malformed_wrong_type_oversized_and_unsupported_requests() -> None:
    with TestClient(create_app(publisher=FakePublisher())) as client:
        malformed = client.post("/feedback/reports", content="{", headers={"content-type": "application/json"})
        wrong_type = client.post("/feedback/reports", content="{}", headers={"content-type": "text/plain"})
        oversized = client.post(
            "/feedback/reports", content=b"{" + b"x" * 32768, headers={"content-type": "application/json"}
        )
        unsupported_payload = bug_payload()
        unsupported_payload["schema_version"] = 2
        unsupported = client.post("/feedback/reports", json=unsupported_payload)
    assert (malformed.status_code, malformed.json()["error"]["code"]) == (400, "invalid_report")
    assert (wrong_type.status_code, wrong_type.json()["error"]["code"]) == (415, "invalid_content_type")
    assert (oversized.status_code, oversized.json()["error"]["code"]) == (413, "report_too_large")
    assert (unsupported.status_code, unsupported.json()["error"]["code"]) == (422, "unsupported_schema_version")


def test_relay_rate_limits_by_ip_and_supports_verified_account_buckets() -> None:
    limiter = RateLimiter(max_requests=1, window=600)
    with TestClient(create_app(publisher=FakePublisher(), rate_limiter=limiter, verifier=FakeVerifier())) as client:
        first = client.post("/feedback/reports", json=bug_payload())
        limited = client.post("/feedback/reports", json=bug_payload())
        account = client.post("/feedback/reports", json=bug_payload(), headers={"authorization": "Bearer valid"})
        invalid = client.post("/feedback/reports", json=bug_payload(), headers={"authorization": "Bearer nope"})
    assert first.status_code == 201
    assert limited.status_code == 429
    assert limited.headers["retry-after"]
    assert account.status_code == 201
    assert invalid.status_code == 401


def test_relay_ignores_desktop_bearer_when_optional_oidc_is_not_configured() -> None:
    with TestClient(create_app(publisher=FakePublisher())) as client:
        response = client.post("/feedback/reports", json=bug_payload(), headers={"authorization": "Bearer opaque"})
    assert response.status_code == 201


def test_relay_logs_only_safe_metadata() -> None:
    payload = bug_payload()
    payload["description"] = "PRIVATE BODY SENTINEL"
    payload["contact"] = "PRIVATE-CONTACT@example.org"
    payload["contact_permitted"] = True
    records: list[str] = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record.getMessage())
    target = logging.getLogger("callosum.feedback_relay")
    target.addHandler(handler)
    try:
        with TestClient(create_app(publisher=FakePublisher())) as client:
            response = client.post("/feedback/reports", json=payload)
    finally:
        target.removeHandler(handler)
    logs = "\n".join(records)
    assert response.status_code == 201
    assert payload["report_id"] in logs
    assert "PRIVATE BODY SENTINEL" not in logs
    assert "PRIVATE-CONTACT" not in logs


def test_slack_formatter_neutralizes_mentions_entity_syntax_and_links() -> None:
    payload = bug_payload()
    payload["title"] = "Do not ping @channel"
    payload["description"] = "@here @everyone <@U123> <!subteam^S123> <https://evil.invalid|click> — café α."
    report = validate_feedback_payload(payload)
    message = format_slack_message(report)
    encoded = json.dumps(message, ensure_ascii=False)
    assert "@channel" not in encoded
    assert "@here" not in encoded
    assert "@everyone" not in encoded
    assert "<@U123>" not in encoded
    assert "<!subteam" not in encoded
    assert "<https://" not in encoded
    assert "café α" in encoded
    assert all(block["text"]["type"] == "plain_text" for block in message["blocks"])
    assert neutralize_slack_formatting("ordinary @person and α < β") == "ordinary @person and α < β"


def test_slack_publisher_posts_fixed_structured_payload_and_hides_response_body() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    publisher = SlackWebhookPublisher("https://hooks.slack.com/services/TEST/FAKE/SECRET-SENTINEL", client=client)
    report = validate_feedback_payload(feature_payload())
    result = publisher.publish(report)
    assert result == PublicationResult(provider="slack", publication_id=report.report_id)
    assert requests[0].url.host == "hooks.slack.com"
    assert json.loads(requests[0].content)["blocks"]


def test_slack_publisher_maps_timeout_and_non_success_without_returning_slack_details() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("SECRET-SENTINEL", request=request)

    timeout_publisher = SlackWebhookPublisher(
        "https://hooks.slack.com/services/TEST/FAKE/SECRET-SENTINEL",
        client=httpx.Client(transport=httpx.MockTransport(timeout_handler)),
    )
    try:
        timeout_publisher.publish(validate_feedback_payload(bug_payload()))
    except PublicationError as exc:
        assert exc.code == "slack_timeout"
        assert exc.unavailable is True
    else:
        raise AssertionError("timeout should fail")

    rejected = SlackWebhookPublisher(
        "https://hooks.slack.com/services/TEST/FAKE/SECRET-SENTINEL",
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(403, text="private body"))),
    )
    try:
        rejected.publish(validate_feedback_payload(bug_payload()))
    except PublicationError as exc:
        assert exc.code == "slack_rejected"
        assert "private body" not in str(exc)
    else:
        raise AssertionError("non-success should fail")
