"""Publication boundary for feedback destinations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.backend.feedback.domain import BugReport, FeatureRequest


@dataclass(frozen=True)
class PublicationResult:
    provider: str
    publication_id: str


class PublicationError(Exception):
    def __init__(self, code: str, *, unavailable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.unavailable = unavailable


class FeedbackPublisher(Protocol):
    def publish(self, report: BugReport | FeatureRequest) -> PublicationResult: ...
