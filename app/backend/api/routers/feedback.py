"""Local feedback API: metadata/capability plus a fixed-destination proxy to the hosted relay."""

from __future__ import annotations

import logging
import os
import platform
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.backend.api.routers.health import reported_app_version
from app.backend.api.routers.sync import _fresh_access_token
from app.backend.feedback.domain import SCHEMA_VERSION, new_report_id, validate_feedback_payload
from app.backend.feedback.http import FeedbackHttpError, read_feedback_json
from app.backend.feedback.relay_client import FeedbackRelayError

router = APIRouter()
logger = logging.getLogger("callosum.feedback")


def _error(status_code: int, code: str, message: str, report_id: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "report_id": report_id, "error": {"code": code, "message": message}},
    )


@router.get("/feedback/capability")
def feedback_capability(request: Request) -> dict:
    return {
        "enabled": request.app.state.feedback_relay_client is not None,
        "schema_version": SCHEMA_VERSION,
        "report_id": new_report_id(),
        "app_version": reported_app_version() or "unknown",
        "operating_system": f"{platform.system()} {platform.release()}".strip(),
        "installation_type": "tauri" if os.getenv("CALLOSUM_APP_VERSION") else "source",
    }


@router.post("/feedback/reports", status_code=201)
async def submit_feedback(request: Request) -> JSONResponse:
    started = time.monotonic()
    report_id: str | None = None
    report_type: str | None = None
    try:
        payload = await read_feedback_json(request)
        report_id = payload.get("report_id") if isinstance(payload.get("report_id"), str) else None
        report_type = payload.get("report_type") if isinstance(payload.get("report_type"), str) else None
        if payload.get("schema_version") != SCHEMA_VERSION:
            return _error(
                422, "unsupported_schema_version", "This feedback report version is not supported.", report_id
            )
        report = validate_feedback_payload(payload)
        relay = request.app.state.feedback_relay_client
        if relay is None:
            return _error(
                503, "feedback_service_unavailable", "Feedback reporting is not configured.", report.report_id
            )
        result = await run_in_threadpool(relay.submit, report, access_token=_fresh_access_token(request))
    except FeedbackHttpError as exc:
        return _error(exc.status_code, exc.code, exc.message, report_id)
    except ValidationError:
        return _error(422, "invalid_report", "Please review the feedback fields and try again.", report_id)
    except FeedbackRelayError as exc:
        logger.warning(
            "feedback relay failed report_id=%s schema=%s type=%s outcome=%s duration_ms=%d",
            report_id,
            SCHEMA_VERSION,
            report_type,
            exc.code,
            round((time.monotonic() - started) * 1000),
        )
        return _error(exc.status_code, exc.code, exc.safe_message, report_id)
    except Exception:
        logger.error(
            "feedback relay exception report_id=%s schema=%s type=%s duration_ms=%d",
            report_id,
            SCHEMA_VERSION,
            report_type,
            round((time.monotonic() - started) * 1000),
        )
        return _error(502, "submission_failed", "The feedback report could not be submitted.", report_id)

    logger.info(
        "feedback published report_id=%s schema=%s type=%s outcome=published duration_ms=%d",
        result.report_id,
        SCHEMA_VERSION,
        report.report_type.value,
        round((time.monotonic() - started) * 1000),
    )
    return JSONResponse(status_code=201, content={"ok": True, "report_id": result.report_id, "status": "published"})
