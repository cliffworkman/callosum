from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.backend.feedback.domain import REPORT_ID_PATTERN, new_report_id, validate_feedback_payload


def bug_payload() -> dict:
    return {
        "schema_version": 1,
        "report_id": "fb_" + "a" * 32,
        "report_type": "bug",
        "title": "PDF viewer stays blank",
        "description": "The PDF tab opens but the page does not render.",
        "component": "pdf_viewer",
        "app_version": "0.3.8",
        "operating_system": "Windows 11",
        "installation_type": "tauri",
        "contact": None,
        "contact_permitted": False,
        "submitted_at": datetime(2026, 8, 2, 12, 0, tzinfo=UTC).isoformat(),
        "actual_behavior": "The viewer remains completely blank.",
        "expected_behavior": "The selected PDF should render normally.",
        "reproduction_steps": ["Open a manuscript", "Reopen its PDF"],
        "reproducibility": "sometimes",
        "reporter_assessed_impact": "normal",
    }


def feature_payload() -> dict:
    payload = bug_payload()
    for field in (
        "actual_behavior",
        "expected_behavior",
        "reproduction_steps",
        "reproducibility",
        "reporter_assessed_impact",
    ):
        payload.pop(field)
    payload.update(
        {
            "report_type": "feature",
            "title": "Add a compact reading timer",
            "description": "A small optional timer would support focused reading sessions.",
            "requested_capability": "Provide an optional timer in the PDF reader.",
            "problem_or_workflow": "I currently leave Callosum to time focused reading sessions.",
            "current_workaround": None,
            "why_it_matters": "It would keep focused reading work in one place.",
        }
    )
    return payload


def test_valid_bug_and_feature_reports() -> None:
    assert validate_feedback_payload(bug_payload()).report_type.value == "bug"
    assert validate_feedback_payload(feature_payload()).report_type.value == "feature"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("report_type", "incident"),
        ("component", "arbitrary_destination"),
        ("installation_type", "secret-build"),
        ("reproducibility", "probably"),
        ("reporter_assessed_impact", "objective-critical"),
    ],
)
def test_rejects_malformed_enums(field: str, value: str) -> None:
    payload = bug_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        validate_feedback_payload(payload)


@pytest.mark.parametrize("field", ["title", "description", "actual_behavior", "expected_behavior"])
def test_missing_required_fields(field: str) -> None:
    payload = bug_payload()
    payload.pop(field)
    with pytest.raises(ValidationError):
        validate_feedback_payload(payload)


def test_rejects_unsupported_schema_unknown_fields_and_naive_timestamp() -> None:
    for change in (
        {"schema_version": 2},
        {"slack_blocks": [{"type": "section"}]},
        {"webhook_url": "https://example.invalid"},
        {"submitted_at": "2026-08-02T12:00:00"},
    ):
        payload = bug_payload()
        payload.update(change)
        with pytest.raises(ValidationError):
            validate_feedback_payload(payload)


def test_enforces_field_and_collection_lengths() -> None:
    too_long = bug_payload()
    too_long["title"] = "x" * 161
    with pytest.raises(ValidationError):
        validate_feedback_payload(too_long)
    too_many_steps = bug_payload()
    too_many_steps["reproduction_steps"] = [str(index) for index in range(13)]
    with pytest.raises(ValidationError):
        validate_feedback_payload(too_many_steps)
    long_step = bug_payload()
    long_step["reproduction_steps"] = ["x" * 501]
    with pytest.raises(ValidationError):
        validate_feedback_payload(long_step)


def test_normalizes_whitespace_without_damaging_unicode_or_punctuation() -> None:
    payload = bug_payload()
    payload["title"] = "  PDF\tviewer   — café  "
    payload["description"] = "  First\tline.\r\n\r\n\r\n Second   line: α < β.  "
    payload["reproduction_steps"] = ["  Open\tPDF  "]
    report = validate_feedback_payload(payload)
    assert report.title == "PDF viewer — café"
    assert report.description == "First line.\n\nSecond line: α < β."
    assert report.reproduction_steps == ["Open PDF"]


def test_contact_is_optional_and_requires_explicit_permission() -> None:
    assert validate_feedback_payload(bug_payload()).contact is None
    permitted = bug_payload()
    permitted.update(contact=" researcher@example.org ", contact_permitted=True)
    assert validate_feedback_payload(permitted).contact == "researcher@example.org"
    forbidden = deepcopy(permitted)
    forbidden["contact_permitted"] = False
    with pytest.raises(ValidationError):
        validate_feedback_payload(forbidden)


def test_report_ids_are_random_per_report_and_strictly_validated() -> None:
    identifiers = {new_report_id() for _ in range(100)}
    assert len(identifiers) == 100
    assert all(REPORT_ID_PATTERN.fullmatch(identifier) for identifier in identifiers)
    payload = bug_payload()
    payload["report_id"] = "fb_123"
    with pytest.raises(ValidationError):
        validate_feedback_payload(payload)
