"""Versioned, bounded feedback domain models shared by the desktop and hosted relay."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

SCHEMA_VERSION = 1
MAX_FEEDBACK_BODY_BYTES = 32_768
REPORT_ID_PATTERN = re.compile(r"^fb_[0-9a-f]{32}$")


class ReportType(StrEnum):
    BUG = "bug"
    FEATURE = "feature"


class FeedbackComponent(StrEnum):
    LIBRARY = "library"
    PDF_VIEWER = "pdf_viewer"
    SYNTHESIS = "synthesis"
    DISCOVERY = "discovery"
    WORK = "work"
    SETTINGS = "settings"
    DESKTOP_APP = "desktop_app"
    INTEGRATIONS = "integrations"
    OTHER = "other"


class InstallationType(StrEnum):
    TAURI = "tauri"
    BROWSER = "browser"
    SOURCE = "source"
    OTHER = "other"


class Reproducibility(StrEnum):
    ALWAYS = "always"
    SOMETIMES = "sometimes"
    ONCE = "once"
    NOT_YET = "not_yet"


class ReporterAssessedImpact(StrEnum):
    BLOCKING = "blocking"
    MAJOR = "major"
    NORMAL = "normal"
    MINOR = "minor"


def new_report_id() -> str:
    """Return a non-sequential, per-report identifier; never a device or installation fingerprint."""
    return f"fb_{uuid4().hex}"


def _single_line(value: str) -> str:
    return " ".join(value.split())


def _multiline(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in normalized.split("\n")]
    output: list[str] = []
    for line in lines:
        if line or (output and output[-1]):
            output.append(line)
    return "\n".join(output).strip()


class FeedbackBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal[1]
    report_id: str = Field(pattern=r"^fb_[0-9a-f]{32}$")
    report_type: ReportType
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    component: FeedbackComponent
    app_version: str = Field(min_length=1, max_length=64)
    operating_system: str = Field(min_length=1, max_length=128)
    installation_type: InstallationType
    contact: str | None = Field(default=None, max_length=320)
    contact_permitted: bool = False
    submitted_at: datetime

    @field_validator("title", "app_version", "operating_system", "contact", mode="before")
    @classmethod
    def normalize_single_line(cls, value: object) -> object:
        return _single_line(value) if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        return _multiline(value) if isinstance(value, str) else value

    @field_validator("submitted_at")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("submitted_at must include a timezone")
        return value

    @model_validator(mode="after")
    def contact_requires_permission(self) -> FeedbackBase:
        if self.contact and not self.contact_permitted:
            raise ValueError("contact must be omitted unless follow-up contact is permitted")
        return self


class BugReport(FeedbackBase):
    report_type: Literal[ReportType.BUG]
    actual_behavior: str = Field(min_length=10, max_length=4000)
    expected_behavior: str = Field(min_length=10, max_length=4000)
    reproduction_steps: list[str] = Field(min_length=1, max_length=12)
    reproducibility: Reproducibility
    reporter_assessed_impact: ReporterAssessedImpact

    @field_validator("actual_behavior", "expected_behavior", mode="before")
    @classmethod
    def normalize_multiline_fields(cls, value: object) -> object:
        return _multiline(value) if isinstance(value, str) else value

    @field_validator("reproduction_steps", mode="before")
    @classmethod
    def normalize_steps(cls, value: object) -> object:
        if isinstance(value, list):
            return [_single_line(item) if isinstance(item, str) else item for item in value]
        return value

    @field_validator("reproduction_steps")
    @classmethod
    def bound_steps(cls, value: list[str]) -> list[str]:
        if any(not step or len(step) > 500 for step in value):
            raise ValueError("each reproduction step must contain 1 to 500 characters")
        return value


class FeatureRequest(FeedbackBase):
    report_type: Literal[ReportType.FEATURE]
    requested_capability: str = Field(min_length=10, max_length=3000)
    problem_or_workflow: str = Field(min_length=10, max_length=3000)
    current_workaround: str | None = Field(default=None, max_length=2000)
    why_it_matters: str = Field(min_length=10, max_length=3000)

    @field_validator(
        "requested_capability", "problem_or_workflow", "current_workaround", "why_it_matters", mode="before"
    )
    @classmethod
    def normalize_feature_fields(cls, value: object) -> object:
        return _multiline(value) if isinstance(value, str) else value


FeedbackReport = Annotated[BugReport | FeatureRequest, Field(discriminator="report_type")]
FEEDBACK_REPORT_ADAPTER = TypeAdapter(FeedbackReport)


def validate_feedback_payload(payload: object) -> BugReport | FeatureRequest:
    """Validate a decoded payload without accepting arbitrary nested objects or unknown fields."""
    return FEEDBACK_REPORT_ADAPTER.validate_python(payload)
