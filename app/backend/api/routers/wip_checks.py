"""Local deterministic checks over exact WIP manuscript snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.backend.api.wip_security import require_local_wip
from app.backend.funding.run_report import funding_run_summaries
from app.backend.llm.egress import DataEgressDisabledError
from app.backend.llm.providers import ProviderError, requires_egress
from app.backend.methods.bayes import audit_completeness, run_bayes
from app.backend.methods.lmm import audit_lmm
from app.backend.methods.metaanalysis import audit_meta_analysis
from app.backend.methods.statcheck import run_statcheck
from app.backend.methods.transparency import detect_transparency
from app.backend.pdf_processing.quote_matching import anchor_quote
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.wip_bayes_repo import store_bayes_run
from app.backend.persistence.wip_checks_repo import (
    list_journal_runs,
    list_tool_runs,
    store_analytic_flexibility_run,
    store_lmm_run,
    store_statcheck_run,
    store_transparency_run,
    update_finding_disposition,
)
from app.backend.persistence.wip_meta_analysis_repo import store_meta_analysis_run
from app.backend.persistence.wip_provenance_repo import prepare_snapshot, record_snapshot
from app.backend.persistence.wip_repo import add_activity, get_manuscript
from app.backend.wip.analytic_flexibility_text import wip_methods_text
from app.backend.wip.content import ContentIdentityError
from app.backend.wip.paths import trusted_child
from integrations.gemini.analytic_flexibility_assistant import AnalyticFlexibilityAssistant
from integrations.gemini.generator import GeminiConfig

router = APIRouter(prefix="/wip", dependencies=[Depends(require_local_wip)])

_EGRESS_REFUSED_DETAIL = (
    "Analytic-flexibility surfacing requires explicit data-egress consent (Settings -> AI features)."
)


class FindingPatch(BaseModel):
    disposition: Literal[
        "open",
        "acknowledged",
        "resolved",
        "dismissed",
        "false-positive",
        "deferred",
        "superseded",
    ]
    resolution_notes: str | None = Field(default=None, max_length=5000)


@router.get("/manuscripts/{manuscript_id}/checks")
def checks_list(manuscript_id: int, request: Request) -> dict:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
        return {
            "tools": [
                {"id": "statcheck", "label": "Statcheck", "kind": "deterministic-local"},
                {"id": "transparency", "label": "Transparency", "kind": "deterministic-local"},
                {"id": "lmm", "label": "Mixed-model reporting", "kind": "deterministic-local"},
                {"id": "bayes", "label": "Bayesian reporting", "kind": "deterministic-local"},
                {"id": "meta-analysis", "label": "Meta-analysis reporting", "kind": "deterministic-local"},
                {"id": "analytic-flexibility", "label": "Analytic-flexibility surfacing", "kind": "provider-ai"},
            ],
            "runs": list_tool_runs(conn, manuscript_id),
        }


@router.post("/manuscripts/{manuscript_id}/checks/statcheck")
def statcheck_run(manuscript_id: int, request: Request) -> dict:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
    run_write(
        request.app.state.engine,
        lambda conn: add_activity(conn, manuscript_id, "tool-run-started", "Started statcheck"),
    )
    try:
        with request.app.state.engine.connect() as conn:
            prepared = prepare_snapshot(conn, manuscript_id)
    except ContentIdentityError as exc:
        failure = exc
        run_write(
            request.app.state.engine,
            lambda conn: add_activity(
                conn,
                manuscript_id,
                "tool-run-failed",
                f"Statcheck could not run: {failure}",
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    chunks = [
        {
            "text": block.text,
            "page_start": block.page_start,
            "page_end": block.page_end,
            "section": block.section,
        }
        for block in prepared.identity.blocks
    ]
    report = run_statcheck(chunks)

    def persist(conn):
        snapshot, _ = record_snapshot(conn, prepared, reason="tool-run", reason_detail="statcheck")
        return store_statcheck_run(conn, prepared, int(snapshot["id"]), report)

    return run_write(request.app.state.engine, persist)


@router.post("/manuscripts/{manuscript_id}/checks/transparency")
def transparency_run(manuscript_id: int, request: Request) -> dict:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
    run_write(
        request.app.state.engine,
        lambda conn: add_activity(
            conn,
            manuscript_id,
            "tool-run-started",
            "Started transparency disclosure check",
        ),
    )
    try:
        with request.app.state.engine.connect() as conn:
            prepared = prepare_snapshot(conn, manuscript_id)
    except ContentIdentityError as exc:
        run_write(
            request.app.state.engine,
            lambda conn: add_activity(
                conn,
                manuscript_id,
                "tool-run-failed",
                "Transparency check could not run",
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    report = detect_transparency(list(prepared.identity.blocks))

    def persist(conn):
        snapshot, _ = record_snapshot(conn, prepared, reason="tool-run", reason_detail="transparency")
        return store_transparency_run(conn, prepared, int(snapshot["id"]), report)

    return run_write(request.app.state.engine, persist)


@router.post("/manuscripts/{manuscript_id}/checks/lmm")
def lmm_run(manuscript_id: int, request: Request) -> dict:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
    run_write(
        request.app.state.engine,
        lambda conn: add_activity(conn, manuscript_id, "tool-run-started", "Started mixed-model reporting audit"),
    )
    try:
        with request.app.state.engine.connect() as conn:
            prepared = prepare_snapshot(conn, manuscript_id)
    except ContentIdentityError as exc:
        run_write(
            request.app.state.engine,
            lambda conn: add_activity(
                conn,
                manuscript_id,
                "tool-run-failed",
                "Mixed-model reporting audit could not run",
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    report = audit_lmm(list(prepared.identity.blocks))

    def persist(conn):
        snapshot, _ = record_snapshot(conn, prepared, reason="tool-run", reason_detail="lmm")
        return store_lmm_run(conn, prepared, int(snapshot["id"]), report)

    return run_write(request.app.state.engine, persist)


@router.post("/manuscripts/{manuscript_id}/checks/bayes")
def bayes_run(manuscript_id: int, request: Request) -> dict:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
    run_write(
        request.app.state.engine,
        lambda conn: add_activity(conn, manuscript_id, "tool-run-started", "Started Bayesian reporting audit"),
    )
    try:
        with request.app.state.engine.connect() as conn:
            prepared = prepare_snapshot(conn, manuscript_id)
    except ContentIdentityError as exc:
        run_write(
            request.app.state.engine,
            lambda conn: add_activity(
                conn,
                manuscript_id,
                "tool-run-failed",
                "Bayesian reporting audit could not run",
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    chunks = list(prepared.identity.blocks)
    report = run_bayes(chunks)
    completeness = audit_completeness(chunks)

    def persist(conn):
        snapshot, _ = record_snapshot(conn, prepared, reason="tool-run", reason_detail="bayes")
        return store_bayes_run(conn, prepared, int(snapshot["id"]), report, completeness)

    return run_write(request.app.state.engine, persist)


@router.post("/manuscripts/{manuscript_id}/checks/meta-analysis")
def meta_analysis_run(manuscript_id: int, request: Request) -> dict:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
    run_write(
        request.app.state.engine,
        lambda conn: add_activity(conn, manuscript_id, "tool-run-started", "Started meta-analysis reporting audit"),
    )
    try:
        with request.app.state.engine.connect() as conn:
            prepared = prepare_snapshot(conn, manuscript_id)
    except ContentIdentityError as exc:
        run_write(
            request.app.state.engine,
            lambda conn: add_activity(
                conn,
                manuscript_id,
                "tool-run-failed",
                "Meta-analysis reporting audit could not run",
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    report = audit_meta_analysis(list(prepared.identity.blocks))

    def persist(conn):
        snapshot, _ = record_snapshot(conn, prepared, reason="tool-run", reason_detail="meta-analysis")
        return store_meta_analysis_run(conn, prepared, int(snapshot["id"]), report)

    return run_write(request.app.state.engine, persist)


@router.post("/manuscripts/{manuscript_id}/checks/analytic-flexibility")
def analytic_flexibility_run(manuscript_id: int, request: Request) -> dict:
    # Egress consent is checked BEFORE any manuscript lookup or DB work (mirrors routers/grobid.py and the
    # Library-side routers/analytic_flexibility.py -- the consent gate wins even over a 404).
    config = GeminiConfig.from_environment()
    if requires_egress(config) and not config.data_egress_enabled:
        raise HTTPException(status_code=403, detail=_EGRESS_REFUSED_DETAIL)
    with request.app.state.engine.connect() as conn:
        manuscript = get_manuscript(conn, manuscript_id)
        if manuscript is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
    run_write(
        request.app.state.engine,
        lambda conn: add_activity(conn, manuscript_id, "tool-run-started", "Started analytic-flexibility surfacing"),
    )
    try:
        with request.app.state.engine.connect() as conn:
            prepared = prepare_snapshot(conn, manuscript_id)
    except ContentIdentityError as exc:
        run_write(
            request.app.state.engine,
            lambda conn: add_activity(
                conn,
                manuscript_id,
                "tool-run-failed",
                "Analytic-flexibility surfacing could not run",
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Local, no-network scoping first; the network call (if any) happens next, OUTSIDE any run_write-wrapped
    # closure -- run_write retries its whole closure on a SQLite lock, which would risk re-issuing the LLM
    # call. Persistence (record_snapshot + store_analytic_flexibility_run below) is pure DB writes and is the
    # only part safely wrapped in run_write.
    scoping = wip_methods_text(list(prepared.identity.blocks))
    candidates: list[dict] = []
    if scoping["text"] is not None:
        try:
            proposals = AnalyticFlexibilityAssistant(config).propose(text=scoping["text"])
        except DataEgressDisabledError as exc:  # defense in depth -- the pre-check above should already catch this
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ProviderError as exc:
            run_write(
                request.app.state.engine,
                lambda conn: add_activity(
                    conn,
                    manuscript_id,
                    "tool-run-failed",
                    "Analytic-flexibility surfacing could not run -- the AI provider failed",
                ),
            )
            raise HTTPException(status_code=502, detail=f"The AI provider failed: {exc}") from None
        pdf_path = (
            trusted_child(manuscript["root_path"], prepared.relative_path)
            if Path(prepared.relative_path).suffix.casefold() == ".pdf"
            else None
        )
        for proposal in proposals:
            anchor = (
                anchor_quote(pdf_path, proposal["quote"])
                if pdf_path is not None
                else {"anchor_state": "unanchored", "page": None, "bbox_json": None, "reason": "no_pdf"}
            )
            candidates.append({**proposal, **anchor})

    def persist(conn):
        snapshot, _ = record_snapshot(conn, prepared, reason="tool-run", reason_detail="analytic-flexibility")
        return store_analytic_flexibility_run(
            conn,
            prepared,
            int(snapshot["id"]),
            candidates,
            methods_text_found=scoping["text"] is not None,
            scoped=scoping["scoped"],
        )

    return run_write(request.app.state.engine, persist)


@router.get("/manuscripts/{manuscript_id}/funding-runs")
def funding_runs_list(manuscript_id: int, request: Request) -> dict:
    # inc 403: Discover > Funding tags a run's research_funding_profiles.source_kind/source_id when it's run
    # against a WIP manuscript (funding.py's _run_funding_job) -- this just reads that same table back, scoped
    # to this manuscript, so the run history is visible from the manuscript's own workspace tab too.
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
        runs = funding_run_summaries(conn, limit=25, source_kind="wip-manuscript", source_id=str(manuscript_id))
    return {"runs": runs}


@router.get("/manuscripts/{manuscript_id}/journal-runs")
def journal_runs_list(manuscript_id: int, request: Request) -> dict:
    # inc 404: publishers.py records a receipt here only when its request carried this manuscript_id -- the
    # paper/abstract paths never write to this table, so this list is purely additive to that existing feature.
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
        runs = list_journal_runs(conn, manuscript_id)
    return {"runs": runs}


@router.patch("/findings/{finding_id}")
def finding_patch(finding_id: int, payload: FindingPatch, request: Request) -> dict:
    try:
        result = run_write(
            request.app.state.engine,
            lambda conn: update_finding_disposition(
                conn,
                finding_id,
                disposition=payload.disposition,
                notes=payload.resolution_notes,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="WIP finding not found")
    return result
