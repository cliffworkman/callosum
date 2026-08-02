"""Strict, size-bounded JSON request parsing for feedback ingress surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import Request

from app.backend.feedback.domain import MAX_FEEDBACK_BODY_BYTES


@dataclass(frozen=True)
class FeedbackHttpError(Exception):
    status_code: int
    code: str
    message: str


async def read_feedback_json(request: Request) -> dict:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise FeedbackHttpError(415, "invalid_content_type", "Feedback reports must use application/json.")

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_FEEDBACK_BODY_BYTES:
                raise FeedbackHttpError(413, "report_too_large", "The feedback report is too large.")
        except ValueError:
            raise FeedbackHttpError(400, "invalid_report", "The feedback report is malformed.") from None

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_FEEDBACK_BODY_BYTES:
            raise FeedbackHttpError(413, "report_too_large", "The feedback report is too large.")
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FeedbackHttpError(400, "invalid_report", "The feedback report is malformed.") from None
    if not isinstance(decoded, dict):
        raise FeedbackHttpError(422, "invalid_report", "The feedback report must be a JSON object.")
    return decoded
