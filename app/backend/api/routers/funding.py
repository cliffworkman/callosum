"""Funding Discovery — Theory-pane latent funding prospect finder."""

from __future__ import annotations

import csv
import io
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi import status as http_status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.backend.api.job_store import JobStore
from app.backend.funding.engine import LatentFundingFitEngine
from app.backend.funding.export import export_run_rows
from app.backend.funding.llm_triage import FundingLlmTriageEvaluator
from app.backend.funding.profile import profile_from_paper, profile_from_text
from app.backend.funding.providers import (
    GRANTS_GOV_PROVIDER,
    CrossrefFundingProvider,
    GrantsGovClient,
    NullAwardHistoryProvider,
    OpenAlexFundingProvider,
)
from app.backend.funding.repo import persist_search_result
from app.backend.funding.resolver import OpportunityResolver
from app.backend.funding.run_report import funding_run_report, funding_run_summaries
from app.backend.funding.saved_repo import (
    list_saved_items,
    refresh_saved_items,
    save_item,
    unsave_item,
    update_saved_item,
)
from app.backend.funding.triage_repo import persist_llm_triage_annotations
from app.backend.persistence.wip_repo import get_manuscript

MAX_RESEARCH_TEXT_CHARS = 20000
MAX_LLM_CONTEXT_CHARS = 20000

router = APIRouter(tags=["funding-discovery"])


class FundingRunRequest(BaseModel):
    paper_id: int | None = None
    manuscript_id: int | None = None  # inc 403: a WIP manuscript has no papers.id -- tags provenance on the
    # existing freeform "description" path rather than being a third exclusive mode (see funding_run's validation).
    description: str | None = None
    field: str | None = None
    llm_triage: bool = False


class FundingRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: dict[str, Any] | None = None
    progress: dict[str, Any] | None = None


class FundingLlmTriageRequest(BaseModel):
    report: dict[str, Any]
    paper_id: int | None = None
    description: str | None = None
    field: str | None = None


class SaveFundingItemRequest(BaseModel):
    item_kind: Literal["opportunity", "scheme", "prospect"]
    canonical_item_id: int
    notes: str | None = Field(default=None, max_length=5000)


class UpdateSavedFundingItemRequest(BaseModel):
    workflow_state: (
        Literal["saved", "reviewing", "considering", "planning", "applying", "submitted", "archived"] | None
    ) = None
    notes: str | None = Field(default=None, max_length=5000)


@router.post("/funding-discovery/run", response_model=FundingRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def funding_run(body: FundingRunRequest, background_tasks: BackgroundTasks, request: Request) -> FundingRunResponse:
    has_paper = body.paper_id is not None
    has_manuscript = body.manuscript_id is not None
    has_text = bool((body.description or "").strip())
    if has_paper and has_manuscript:
        raise HTTPException(status_code=422, detail="Provide either a paper_id or a manuscript_id, not both.")
    if has_paper and has_text:
        raise HTTPException(status_code=422, detail="Provide either a paper_id or a research description, not both.")
    if not has_paper and not has_text:
        raise HTTPException(status_code=422, detail="Provide a paper_id or a research description.")
    if body.description and len(body.description) > MAX_RESEARCH_TEXT_CHARS:
        raise HTTPException(status_code=422, detail="Research description is too long.")
    if has_paper:
        with request.app.state.engine.begin() as conn:
            profile = profile_from_paper(conn, int(body.paper_id))
        if profile is None:
            raise HTTPException(status_code=404, detail="Paper not found")
    if has_manuscript:
        with request.app.state.engine.connect() as conn:
            if get_manuscript(conn, int(body.manuscript_id)) is None:
                raise HTTPException(status_code=404, detail="WIP manuscript not found")
    nav = {"paper_id": int(body.paper_id)} if body.paper_id is not None else None
    job_id = request.app.state.funding_jobs.create(nav=nav)
    background_tasks.add_task(_run_funding_job, request.app, job_id, body)
    return FundingRunResponse(job_id=job_id, status="pending")


@router.get("/funding-discovery/run/{job_id}", response_model=FundingRunResponse)
def funding_status(job_id: str, request: Request) -> FundingRunResponse:
    job = request.app.state.funding_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Funding Discovery job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = None
    if job.progress is not None:
        progress = {
            "current": job.progress.current,
            "total": job.progress.total,
            "label": job.progress.label,
            "eta_seconds": job.eta_seconds(),
        }
    return FundingRunResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


@router.post("/funding-discovery/llm-triage")
def funding_llm_triage(body: FundingLlmTriageRequest, request: Request) -> dict[str, Any]:
    report = _bounded_report_for_triage(body.report)
    if not _report_has_funding_items(report):
        raise HTTPException(status_code=422, detail="No funding results are available to triage.")
    if body.paper_id is not None:
        with request.app.state.engine.begin() as conn:
            research_context = _paper_research_context(conn, int(body.paper_id))
            if not research_context:
                raise HTTPException(status_code=404, detail="Paper not found")
    else:
        if body.description and len(body.description) > MAX_RESEARCH_TEXT_CHARS:
            raise HTTPException(status_code=422, detail="Research description is too long.")
        research_context = _manual_research_context(
            FundingRunRequest(description=body.description or "", field=body.field or "", llm_triage=True)
        )
    status = _run_llm_triage(request.app, report, research_context)
    report["llm_triage_status"] = status
    run_id = report.get("run_id")
    if run_id is not None:
        with request.app.state.engine.begin() as conn:
            if funding_run_report(conn, int(run_id)) is None:
                raise HTTPException(status_code=404, detail="Funding Discovery run not found")
            persist_llm_triage_annotations(conn, int(run_id), report, status)
            persisted = funding_run_report(conn, int(run_id))
        if persisted is not None:
            report = persisted
    return {"report": report, "llm_triage_status": status}


@router.post("/funding-discovery/save")
def funding_save(body: SaveFundingItemRequest, request: Request) -> dict[str, Any]:
    with request.app.state.engine.begin() as conn:
        try:
            return save_item(
                conn,
                item_kind=body.item_kind,
                canonical_item_id=body.canonical_item_id,
                notes=body.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/funding-discovery/saved")
def funding_saved(request: Request) -> dict[str, Any]:
    with request.app.state.engine.begin() as conn:
        return {"items": list_saved_items(conn)}


@router.post("/funding-discovery/saved/refresh")
def funding_saved_refresh(request: Request) -> dict[str, Any]:
    with request.app.state.engine.begin() as conn:
        return refresh_saved_items(
            conn,
            opportunity_detail_lookup=_saved_opportunity_lookup(request.app, conn),
            application_surface_lookup=_saved_application_surface_lookup(request.app, conn),
        )


@router.delete("/funding-discovery/saved/{saved_item_id}")
def funding_unsave(saved_item_id: int, request: Request) -> dict[str, Any]:
    with request.app.state.engine.begin() as conn:
        try:
            return {"unsaved": unsave_item(conn, saved_item_id)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/funding-discovery/saved/{saved_item_id}")
def funding_saved_update(saved_item_id: int, body: UpdateSavedFundingItemRequest, request: Request) -> dict[str, Any]:
    with request.app.state.engine.begin() as conn:
        try:
            return {
                "item": update_saved_item(
                    conn,
                    saved_item_id,
                    workflow_state=body.workflow_state,
                    notes=body.notes,
                )
            }
        except ValueError as exc:
            msg = str(exc)
            status_code = 422 if "Unknown" in msg else 404
            raise HTTPException(status_code=status_code, detail=msg) from exc


@router.get("/funding-discovery/runs")
def funding_runs(request: Request, limit: int = Query(default=8, ge=1, le=25)) -> dict[str, Any]:
    with request.app.state.engine.begin() as conn:
        return {"runs": funding_run_summaries(conn, limit=limit)}


@router.get("/funding-discovery/runs/{run_id}")
def funding_run_detail(run_id: int, request: Request) -> dict[str, Any]:
    with request.app.state.engine.begin() as conn:
        report = funding_run_report(conn, run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Funding Discovery run not found")
    return {"report": report}


FUNDING_EXPORT_COLUMNS = [
    "item_kind",
    "canonical_item_id",
    "title",
    "organization_name",
    "scheme_name",
    "status",
    "next_deadline",
    "deadlines",
    "amount",
    "eligibility",
    "identity_resolution_quality",
    "source_provider",
    "source_url",
    "application_route",
    "top_signals",
    "matched_facets",
    "interpretation_boundary",
    "llm_triage_label",
    "llm_triage_status",
    "llm_triage_show_in_triage",
    "llm_triage_rationale",
    "llm_triage_prompt_version",
]


@router.get("/funding-discovery/runs/{run_id}/export.csv")
def funding_export_csv(run_id: int, request: Request) -> Response:
    with request.app.state.engine.begin() as conn:
        rows = export_run_rows(conn, run_id)
    if rows is None:
        raise HTTPException(status_code=404, detail="Funding Discovery run not found")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FUNDING_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="funding-discovery-run-{run_id}.csv"'},
    )


def _run_funding_job(app: FastAPI, job_id: str, body: FundingRunRequest) -> None:
    jobs: JobStore[FundingRunResponse] = app.state.funding_jobs
    jobs.mark_running(job_id)
    try:
        report: dict[str, Any]
        research_context = ""
        with app.state.engine.begin() as conn:
            jobs.mark_progress(job_id, 1, 5, "Building research funding profile")
            if body.paper_id is not None:
                profile = profile_from_paper(conn, int(body.paper_id))
                if profile is None:
                    jobs.mark_error(job_id, "Paper not found")
                    return
                research_context = _paper_research_context(conn, int(body.paper_id))
            elif body.manuscript_id is not None:
                research_context = _manual_research_context(body)
                manuscript = get_manuscript(conn, int(body.manuscript_id))
                manuscript_title = (manuscript or {}).get("display_title")
                profile = profile_from_text(
                    body.description or "",
                    field=body.field or "",
                    source_kind="wip-manuscript",
                    source_id=str(body.manuscript_id),
                    title=manuscript_title,
                )
            else:
                research_context = _manual_research_context(body)
                profile = profile_from_text(
                    body.description or "",
                    field=body.field or "",
                    source_kind="manual",
                    title=None,
                )
            jobs.mark_progress(job_id, 2, 5, "Searching funding evidence")
            award_provider = getattr(app.state, "funding_award_provider", None) or NullAwardHistoryProvider()
            awards, local_status = award_provider.search_awards(conn, profile)
            oa_provider = getattr(app.state, "funding_openalex_provider", None) or OpenAlexFundingProvider()
            cr_provider = getattr(app.state, "funding_crossref_provider", None) or CrossrefFundingProvider()
            oa_awards, oa_status = oa_provider.search_awards(conn, profile)
            cr_awards, cr_status = cr_provider.search_awards(conn, profile)
            all_awards = [*awards, *oa_awards, *cr_awards]
            local_surfaces = (
                award_provider.application_surfaces(awards) if hasattr(award_provider, "application_surfaces") else []
            )
            jobs.mark_progress(job_id, 3, 5, "Generating funding prospects")
            prospects, recurring_schemes = LatentFundingFitEngine().generate(profile, all_awards)
            jobs.mark_progress(job_id, 4, 5, "Resolving current opportunities")
            grants_client = getattr(app.state, "funding_grants_gov_client", None)
            resolver = OpportunityResolver(grants_client)
            opportunities, recurring_schemes, prospects, surfaces, resolver_statuses = resolver.resolve(
                conn,
                profile,
                prospects,
                recurring_schemes,
            )
            surfaces = [*local_surfaces, *surfaces]
            statuses = [local_status, oa_status, cr_status, *resolver_statuses]
            jobs.mark_progress(job_id, 5, 5, "Persisting funding discovery run")
            report = persist_search_result(
                conn,
                profile=profile,
                awards=all_awards,
                opportunities=opportunities,
                recurring_schemes=recurring_schemes,
                prospects=prospects,
                surfaces=surfaces,
                statuses=statuses,
            )
        if body.llm_triage:
            jobs.mark_progress(job_id, 5, 5, "Evaluating apparent fit with AI")
            report["llm_triage_status"] = _run_llm_triage(app, report, research_context)
            with app.state.engine.begin() as conn:
                persist_llm_triage_annotations(conn, int(report["run_id"]), report, report["llm_triage_status"])
        else:
            report["llm_triage_status"] = {
                "provider_id": "configured-llm",
                "status": "not_searched",
                "warning": "LLM triage was not requested for this run.",
            }
        jobs.mark_done(job_id, FundingRunResponse(job_id=job_id, status="done", report=report))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _run_llm_triage(app: FastAPI, report: dict[str, Any], research_context: str) -> dict[str, Any]:
    from app.backend.llm.providers import requires_egress
    from integrations.gemini import GeminiConfig

    try:
        config = GeminiConfig.from_environment()
        if requires_egress(config) and not config.data_egress_enabled:
            return {
                "provider_id": "configured-llm",
                "status": "unavailable",
                "warning": "AI triage needs AI features/data-egress consent in Settings.",
            }
        evaluator = getattr(app.state, "funding_llm_triage_evaluator", None)
        if evaluator is None:
            if requires_egress(config) and not config.resolved_api_key():
                return {
                    "provider_id": "configured-llm",
                    "status": "unavailable",
                    "warning": "AI triage needs an API key in Settings.",
                }
            evaluator = FundingLlmTriageEvaluator(config=config)
        return evaluator.evaluate(report=report, research_context=research_context)
    except Exception as exc:  # noqa: BLE001
        return {
            "provider_id": "configured-llm",
            "status": "failed",
            "warning": f"AI triage failed; deterministic funding results are still shown. {type(exc).__name__}: {exc}",
        }


def _bounded_report_for_triage(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise HTTPException(status_code=422, detail="Funding report is required.")
    allowed_top = {
        "run_id",
        "profile",
        "provider_statuses",
        "result_counts",
        "open_opportunities",
        "recurring_schemes",
        "funding_prospects",
        "application_surfaces",
    }
    bounded = {key: report.get(key) for key in allowed_top if key in report}
    for section in ("open_opportunities", "recurring_schemes", "funding_prospects", "application_surfaces"):
        values = bounded.get(section)
        bounded[section] = [item for item in values[:100] if isinstance(item, dict)] if isinstance(values, list) else []
    return bounded


def _report_has_funding_items(report: dict[str, Any]) -> bool:
    return any(report.get(section) for section in ("open_opportunities", "recurring_schemes", "funding_prospects"))


def _saved_opportunity_lookup(app: FastAPI, conn) -> Any:
    def lookup(provider_id: str, provider_opportunity_id: str):
        if provider_id != GRANTS_GOV_PROVIDER:
            return None, "provider_not_supported"
        client = getattr(app.state, "funding_grants_gov_client", None) or GrantsGovClient()
        opportunity, status = client.fetch_opportunity(conn, provider_opportunity_id, refresh=True)
        if status.status == "failed":
            return None, "provider_unavailable"
        if opportunity is None:
            return None, "no_current_application_window_verified"
        return opportunity, "refreshed"

    return lookup


def _saved_application_surface_lookup(app: FastAPI, conn) -> Any:
    def lookup(item_kind: str, context: dict[str, Any]):
        org = str(context.get("organization_name") or "").strip()
        scheme = str(context.get("scheme_name") or "").strip()
        query = " ".join(part for part in (scheme, org) if part).strip()
        if not query:
            return None
        profile = profile_from_text(query, field="", source_kind=f"saved_{item_kind}", title=query)
        client = getattr(app.state, "funding_grants_gov_client", None) or GrantsGovClient()
        opportunities, status = client.search_opportunities(conn, profile, rows=10)
        if status.status == "failed":
            return None, "provider_unavailable"
        matched = _conservative_saved_surface_match(opportunities, organization_name=org, scheme_name=scheme)
        if matched is None:
            return None, "no_current_application_window_verified"
        return matched, "application_surface_refreshed"

    return lookup


def _conservative_saved_surface_match(opportunities: list[Any], *, organization_name: str, scheme_name: str):
    org_tokens = _significant_terms(organization_name)
    scheme_tokens = _significant_terms(scheme_name)
    for opp in opportunities:
        haystack = " ".join([opp.title or "", opp.organization_name or ""]).lower()
        if scheme_tokens and all(token in haystack for token in scheme_tokens):
            return opp
        if org_tokens and all(token in haystack for token in org_tokens):
            return opp
    return None


def _significant_terms(value: str) -> list[str]:
    stop = {"the", "and", "for", "with", "foundation", "fund", "trust", "program", "grant", "inc"}
    return [
        t for t in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if len(t) > 2 and t not in stop
    ]


def _manual_research_context(body: FundingRunRequest) -> str:
    parts = [body.description or "", body.field or ""]
    return "\n\n".join(p.strip() for p in parts if p and p.strip())[:MAX_LLM_CONTEXT_CHARS]


def _paper_research_context(conn, paper_id: int) -> str:
    from sqlalchemy import select

    from app.backend.metadata.abstract_display import abstract_plain_text
    from app.backend.persistence.schema import papers

    row = conn.execute(select(papers.c.title, papers.c.abstract).where(papers.c.id == paper_id)).mappings().first()
    if row is None:
        return ""
    title = str(row["title"] or "").strip()
    abstract = abstract_plain_text(row["abstract"]) or ""
    return "\n\n".join(part for part in (title, abstract) if part)[:MAX_LLM_CONTEXT_CHARS]
