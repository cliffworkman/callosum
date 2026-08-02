"""Narrowly scoped hosted feedback relay application."""

from __future__ import annotations

import ipaddress
import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.backend.feedback.domain import SCHEMA_VERSION, validate_feedback_payload
from app.backend.feedback.http import FeedbackHttpError, read_feedback_json
from feedback_relay.publisher import FeedbackPublisher, PublicationError
from feedback_relay.slack import SlackWebhookPublisher
from sync_server.auth import InvalidToken, JwksVerifier, TokenVerifier
from sync_server.rate_limit import RateLimiter

logger = logging.getLogger("callosum.feedback_relay")


def _error(status_code: int, code: str, message: str, report_id: str | None = None, **headers: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "report_id": report_id, "error": {"code": code, "message": message}},
        headers=headers,
    )


def _verifier_from_env() -> TokenVerifier | None:
    issuer = os.getenv("CALLOSUM_FEEDBACK_OIDC_ISSUER", "").strip()
    audience = os.getenv("CALLOSUM_FEEDBACK_OIDC_AUDIENCE", "").strip()
    if not issuer or not audience:
        return None
    return JwksVerifier(issuer, audience, os.getenv("CALLOSUM_FEEDBACK_OIDC_JWKS_URL"))


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _client_ip(request: Request, trust_proxy_headers: bool) -> str:
    candidate = request.client.host if request.client else "unknown"
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            candidate = forwarded
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "unknown"


def _rate_key(request: Request, verifier: TokenVerifier | None, trust_proxy_headers: bool) -> str:
    auth = request.headers.get("authorization", "")
    if auth and verifier is not None:
        if not auth.startswith("Bearer "):
            raise InvalidToken("invalid bearer token")
        identity = verifier.verify(auth.removeprefix("Bearer ").strip())
        return f"account:{identity.sub}"
    return f"ip:{_client_ip(request, trust_proxy_headers)}"


def create_app(
    *,
    publisher: FeedbackPublisher | None = None,
    rate_limiter: RateLimiter | None = None,
    verifier: TokenVerifier | None = None,
    trust_proxy_headers: bool = False,
) -> FastAPI:
    relay = FastAPI(title="Callosum Feedback Relay", version="1")
    relay.state.publisher = publisher
    relay.state.rate_limiter = rate_limiter or RateLimiter(max_requests=5, window=600)
    relay.state.verifier = verifier
    relay.state.trust_proxy_headers = trust_proxy_headers

    @relay.get("/health")
    def health() -> dict:
        return {"app": "callosum-feedback-relay", "configured": relay.state.publisher is not None}

    @relay.post("/feedback/reports", status_code=201)
    async def submit(request: Request) -> JSONResponse:
        started = time.monotonic()
        report_id: str | None = None
        report_type: str | None = None
        try:
            rate_key = _rate_key(request, relay.state.verifier, relay.state.trust_proxy_headers)
        except InvalidToken:
            return _error(401, "invalid_authentication", "The supplied account session is invalid.")
        limiter: RateLimiter = relay.state.rate_limiter
        if not limiter.allow(rate_key):
            retry_after = str(limiter.retry_after(rate_key))
            logger.warning(
                "feedback rejected outcome=rate_limited duration_ms=%d", round((time.monotonic() - started) * 1000)
            )
            return _error(
                429, "rate_limited", "Too many feedback reports were submitted.", **{"Retry-After": retry_after}
            )

        try:
            payload = await read_feedback_json(request)
            report_id = payload.get("report_id") if isinstance(payload.get("report_id"), str) else None
            report_type = payload.get("report_type") if isinstance(payload.get("report_type"), str) else None
            if payload.get("schema_version") != SCHEMA_VERSION:
                return _error(
                    422, "unsupported_schema_version", "This feedback report version is not supported.", report_id
                )
            report = validate_feedback_payload(payload)
            publisher = relay.state.publisher
            if publisher is None:
                return _error(
                    503, "feedback_service_unavailable", "Feedback publication is disabled.", report.report_id
                )
            publication = await run_in_threadpool(publisher.publish, report)
        except FeedbackHttpError as exc:
            return _error(exc.status_code, exc.code, exc.message, report_id)
        except ValidationError:
            return _error(422, "invalid_report", "Please review the feedback fields and try again.", report_id)
        except PublicationError as exc:
            status = 503 if exc.unavailable else 502
            code = "feedback_service_unavailable" if exc.unavailable else "submission_failed"
            logger.warning(
                "feedback publication failed report_id=%s schema=%s type=%s outcome=%s duration_ms=%d",
                report_id,
                SCHEMA_VERSION,
                report_type,
                exc.code,
                round((time.monotonic() - started) * 1000),
            )
            return _error(status, code, "The feedback report could not be published.", report_id)
        except Exception:
            logger.error(
                "feedback publication exception report_id=%s schema=%s type=%s outcome=internal_error duration_ms=%d",
                report_id,
                SCHEMA_VERSION,
                report_type,
                round((time.monotonic() - started) * 1000),
            )
            return _error(502, "submission_failed", "The feedback report could not be published.", report_id)

        logger.info(
            "feedback published report_id=%s schema=%s type=%s provider=%s outcome=published duration_ms=%d",
            report.report_id,
            SCHEMA_VERSION,
            report.report_type.value,
            publication.provider,
            round((time.monotonic() - started) * 1000),
        )
        return JSONResponse(status_code=201, content={"ok": True, "report_id": report.report_id, "status": "published"})

    return relay


def _default_app() -> FastAPI:
    max_requests = _bounded_int_env("CALLOSUM_FEEDBACK_RATE_LIMIT", 5, 1, 100)
    window = _bounded_int_env("CALLOSUM_FEEDBACK_RATE_WINDOW_SECONDS", 600, 60, 86_400)
    trust_proxy = os.getenv("CALLOSUM_FEEDBACK_TRUST_PROXY_HEADERS", "").strip().lower() in {"1", "true", "yes"}
    return create_app(
        publisher=SlackWebhookPublisher.from_env(),
        rate_limiter=RateLimiter(max_requests=max_requests, window=window),
        verifier=_verifier_from_env(),
        trust_proxy_headers=trust_proxy,
    )


app = _default_app()
