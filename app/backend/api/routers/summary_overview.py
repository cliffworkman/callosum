"""Supplementary synthesis-Overview lifecycle and retry API."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_engine, resolve_llm_config
from app.backend.persistence.repository import get_summary
from app.backend.summarization.overview_lifecycle import (
    OverviewStatus,
    acquire_overview,
    generate_overview,
    overview_status_for_row,
)

router = APIRouter()


class OverviewRetryResponse(BaseModel):
    summary_id: int
    accepted: bool
    overview_status: OverviewStatus


@router.post(
    "/summaries/{summary_id}/overview/retry",
    response_model=OverviewRetryResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def summary_overview_retry(
    summary_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    engine: Engine = Depends(get_engine),
) -> OverviewRetryResponse:
    generator = resolve_overview_generator(request.app)
    if generator is None:
        raise HTTPException(status_code=409, detail="Overview generation is not currently available")
    with engine.begin() as conn:
        try:
            summary = get_summary(conn, summary_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Summary not found") from None
        current = overview_status_for_row(summary)
        if current == "complete":
            return OverviewRetryResponse(summary_id=summary_id, accepted=False, overview_status="complete")
        acquired = acquire_overview(conn, summary_id, allow_pending=True, allow_failed=True)
    if not acquired:
        raise HTTPException(status_code=409, detail="Overview is not currently retryable")
    background_tasks.add_task(
        generate_overview,
        engine,
        summary_id=summary_id,
        generator=generator,
        acquired=True,
    )
    return OverviewRetryResponse(summary_id=summary_id, accepted=True, overview_status="running")


def resolve_overview_generator(api: FastAPI):
    from app.backend.llm.egress import EgressGatedOverviewGenerator
    from app.backend.llm.providers import requires_egress
    from integrations.gemini.overview import GeminiOverviewGenerator

    config = resolve_llm_config(api)
    inner = api.state.overview_generator
    if inner is None:
        # Cloud providers require consent + a key. Loopback providers need neither.
        if requires_egress(config) and not (config.data_egress_enabled and config.resolved_api_key()):
            return None
        inner = GeminiOverviewGenerator(config=config)
    return EgressGatedOverviewGenerator(
        inner=inner,
        data_egress_enabled=config.data_egress_enabled,
        provider=config.provider,
        wire_format=config.wire_format,
        base_url=config.base_url,
    )
