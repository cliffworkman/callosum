"""Critical-review supplement (backlog #12) — the "critical read" router.

Tier 1: an async job that runs the deterministic scrutiny backbone (`methods/critical_review.py`) for a single
paper — compose the paper's stored method signals + the cross-corpus contradiction detector. Fully local, no
egress. Tier 2 (the egress-gated LLM candidate generator) is added by a later increment as a sibling endpoint;
this router already exposes the candidate list + accept/reject, since the candidate store (inc-#12 t1) exists.

Mirrors the acquire-oa async-job pattern. The deterministic deps (embed model / vector store / NLI stance scorer)
come from ``app.state`` with a test seam (``app.state.critical_review_deps``) so endpoint tests never load a model.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import (
    get_connection,
    get_engine,
    resolve_embedding_model,
    resolve_llm_config,
    resolve_stance_scorer,
)
from app.backend.api.job_store import JobStore
from app.backend.api.job_timing import critical_read_timing_key
from app.backend.api.routers.critical_review_triage import (
    triage_and_persist_candidates,
    triage_contested,
    triage_contested_dicts,
)
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.methods.critical_review import (
    build_scrutiny_backbone,
    extract_claim_sentences,
    find_contested_claims,
    make_chunk_resolver,
    other_paper_chunk_embedding_ids,
)
from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()


class ContestedClaimResponse(BaseModel):
    claim: str
    passage: str  # verbatim, from the OTHER paper — the grounding
    other_paper_id: int
    page: int | None = None
    stance: str
    confidence: float
    llm_triage: dict | None = None  # optional, reversible display annotation — never persisted (ephemeral per-run)


class MethodSignalResponse(BaseModel):
    kind: str
    label: str
    detail: str | None = None
    notice_url: str | None = None


class ScrutinyBackboneResponse(BaseModel):
    method_signals: list[MethodSignalResponse] = []
    citation_signal: dict | None = None
    contested_claims: list[ContestedClaimResponse] = []
    triage_status: dict | None = None


class CriticalReadStartRequest(BaseModel):
    triage: bool = False


class CriticalReadStartResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]


class CriticalReadJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    backbone: ScrutinyBackboneResponse | None = None


class CandidateResponse(BaseModel):
    id: int
    paper_id: int
    concern: str
    anchor_quote: str
    page: int | None = None
    stance: str | None = None
    confidence: float | None = None
    status: str
    llm_triage: dict | None = None  # persisted, reversible display annotation — read-time attached + staleness-aware


class CandidateListResponse(BaseModel):
    candidates: list[CandidateResponse] = []


class GenerateCandidatesRequest(BaseModel):
    triage: bool = False


class CandidateStatusResponse(BaseModel):
    id: int
    status: str


def _cr_deps(app: FastAPI):
    """(embed_model, vector_store, stance_scorer) — the test seam (`critical_review_deps`) wins, else app.state
    defaults + the local NLI stance scorer. The seam lets endpoint tests inject fakes with no model load."""
    seam = getattr(app.state, "critical_review_deps", None)
    if seam is not None:
        return seam["embed_model"], seam["vector_store"], seam["stance_scorer"]
    embed = resolve_embedding_model(app)
    store = app.state.vector_store or SQLiteVecVectorStore()
    return embed, store, resolve_stance_scorer(app)


@router.post(
    "/papers/{paper_id}/critical-read",
    response_model=CriticalReadStartResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def critical_read_start(
    paper_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    body: CriticalReadStartRequest | None = None,
    conn: Connection = Depends(get_connection),
) -> CriticalReadStartResponse:
    # Async (embeds + NLI over the corpus is slow): returns a job id to poll. Validate the paper first. Tier 1 is
    # fully local — no egress gate here; egress applies only to Tier 2 and the optional triage stage below.
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    job_id = request.app.state.critical_review_jobs.create(nav={"paper_id": paper_id})
    want_triage = bool(body.triage) if body else False
    background_tasks.add_task(_run_critical_read_job, request.app, job_id, paper_id, want_triage)
    return CriticalReadStartResponse(job_id=job_id, status="pending")


@router.get("/critical-read/{job_id}", response_model=CriticalReadJobResponse)
async def critical_read_status(
    job_id: str,
    request: Request,
    wait_seconds: float = Query(default=0.0, ge=0.0, le=25.0),
) -> CriticalReadJobResponse:
    jobs: JobStore[CriticalReadJobResponse] = request.app.state.critical_review_jobs
    job = await jobs.wait_for_update(job_id, wait_seconds)
    if job is None:
        raise HTTPException(status_code=404, detail="Critical-read job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return CriticalReadJobResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_critical_read_job(app: FastAPI, job_id: str, paper_id: int, want_triage: bool = False) -> None:
    jobs: JobStore[CriticalReadJobResponse] = app.state.critical_review_jobs
    jobs.mark_running(job_id)
    try:
        embed_model, vector_store, stance_scorer = _cr_deps(app)
        calibration_key = critical_read_timing_key("critical-read-single", embed_model, stance_scorer)
        jobs.mark_stage(job_id, "preparing_evidence", "Preparing evidence", timing_key=calibration_key)
        engine: Engine = app.state.engine
        with engine.connect() as conn:
            contested = find_contested_claims(
                conn,
                paper_id,
                embed_model=embed_model,
                vector_store=vector_store,
                stance_scorer=stance_scorer,
                resolve_chunk=make_chunk_resolver(conn),
                claim_sentences=extract_claim_sentences(conn, paper_id),
                other_chunk_ids=other_paper_chunk_embedding_ids(
                    conn,
                    paper_id,
                    model_name=embed_model.name,
                    model_version=embed_model.version,
                    normalization=embed_model.normalization,
                ),
                on_stage=lambda key, label, size: jobs.mark_stage(
                    job_id, key, label, timing_key=calibration_key, workload_size=size
                ),
            )
            backbone = build_scrutiny_backbone(conn, paper_id, contested_claims=contested)
        contested_responses = [
            ContestedClaimResponse(
                claim=c.claim,
                passage=c.passage,
                other_paper_id=c.other_paper_id,
                page=c.page,
                stance=c.stance,
                confidence=c.confidence,
            )
            for c in backbone.contested_claims
        ]
        triage_status = None
        if want_triage:
            # No DB connection held during the triage provider call (LATENCY.md), mirroring inc-494's Overview
            # discipline — the connection above is already closed by this point.
            jobs.mark_stage(
                job_id, "triaging_claims", "Triaging claims with AI", timing_key=calibration_key, variable=True
            )
            triage_status = triage_contested(app, contested_responses)
        jobs.mark_stage(job_id, "finalizing_result", "Finalizing result", timing_key=calibration_key)
        jobs.mark_done(
            job_id,
            CriticalReadJobResponse(
                job_id=job_id,
                status="done",
                backbone=ScrutinyBackboneResponse(
                    method_signals=[MethodSignalResponse(**signal) for signal in backbone.method_signals],
                    citation_signal=backbone.citation_signal,
                    contested_claims=contested_responses,
                    triage_status=triage_status,
                ),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


@router.get("/papers/{paper_id}/critical-read/candidates", response_model=CandidateListResponse)
def critical_read_candidates(paper_id: int, conn: Connection = Depends(get_connection)) -> CandidateListResponse:
    from app.backend.methods.critical_review_triage import TRIAGE_PROMPT_VERSION
    from app.backend.persistence import critical_review_triage_repo as triage_repo

    rows = repo.list_candidates(conn, paper_id)
    stored = triage_repo.load_candidate_triage(conn, [r["id"] for r in rows])
    attached = triage_repo.attach_candidate_triage(rows, stored, current_prompt_version=TRIAGE_PROMPT_VERSION)
    return CandidateListResponse(
        candidates=[
            CandidateResponse(
                id=r["id"],
                paper_id=r["paper_id"],
                concern=r["concern"],
                anchor_quote=r["anchor_quote"],
                page=r["page"],
                stance=r["stance"],
                confidence=r["confidence"],
                status=r["status"],
                llm_triage=attached.get(r["id"]),
            )
            for r in rows
        ]
    )


@router.post("/papers/{paper_id}/critical-read/candidates/generate", response_model=CandidateListResponse)
def generate_candidates(
    paper_id: int,
    request: Request,
    body: GenerateCandidatesRequest | None = None,
    conn: Connection = Depends(get_connection),
) -> CandidateListResponse:
    # Tier 2 (egress-gated, invariant #3): the LLM PROPOSES concerns; each is admitted only through the #13
    # verbatim bar (verify_candidates → canonical_text_contains), annotated with a local NLI stance, and persisted
    # as a pending CANDIDATE the human accepts/rejects. A fake generator (test seam) still honors the egress gate.
    from app.backend.llm.managed_local import ManagedLocalTargetError
    from app.backend.llm.providers import ProviderError, requires_egress
    from app.backend.methods.critical_review import paper_full_text
    from integrations.gemini.critical_review import GeminiCriticalReviewGenerator, verify_candidates

    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None

    try:
        config = resolve_llm_config(request.app)
    except ManagedLocalTargetError as exc:
        raise HTTPException(
            status_code=422, detail=f"Local AI is not ready ({exc.code}). Check Settings → AI features."
        ) from None
    if requires_egress(config) and not config.data_egress_enabled:
        raise HTTPException(status_code=422, detail="AI critique requires data-egress consent (Settings → AI features)")
    generator = getattr(request.app.state, "critical_review_generator", None)
    if generator is None:
        if requires_egress(config) and not config.resolved_api_key():
            raise HTTPException(status_code=422, detail="AI critique requires an API key (Settings → AI features)")
        generator = GeminiCriticalReviewGenerator(config=config)

    _, _, stance_scorer = _cr_deps(request.app)
    paper_text = paper_full_text(conn, paper_id)
    try:
        drafts = generator.propose(paper_text=paper_text)
    except ProviderError as exc:
        raise HTTPException(status_code=422, detail=f"AI critique generation failed: {exc}") from None
    verified = verify_candidates(
        drafts,
        paper_id=paper_id,
        paper_text=paper_text,
        stance_scorer=stance_scorer,
        rejected_signatures=repo.rejected_signatures(conn, paper_id),
    )
    ids = repo.insert_candidates(conn, paper_id, verified)
    if body and body.triage and ids:
        candidates_for_triage = [{**cand, "id": cid} for cand, cid in zip(verified, ids, strict=False)]
        triage_and_persist_candidates(request.app, conn, candidates_for_triage)
    conn.commit()
    return critical_read_candidates(paper_id, conn)


def _set_candidate_status(candidate_id: int, status: str, conn: Connection) -> CandidateStatusResponse:
    if not repo.set_status(conn, candidate_id, status):
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateStatusResponse(id=candidate_id, status=status)


@router.post("/critical-read/candidates/{candidate_id}/accept", response_model=CandidateStatusResponse)
def accept_candidate(candidate_id: int, engine: Engine = Depends(get_engine)) -> CandidateStatusResponse:
    return run_write(engine, lambda conn: _set_candidate_status(candidate_id, "accepted", conn))


@router.post("/critical-read/candidates/{candidate_id}/reject", response_model=CandidateStatusResponse)
def reject_candidate(candidate_id: int, engine: Engine = Depends(get_engine)) -> CandidateStatusResponse:
    return run_write(engine, lambda conn: _set_candidate_status(candidate_id, "rejected", conn))


# --- Set (multi-paper) critical review (backlog #12) — a shared engine keyed on a chosen SET of papers ------------

MAX_SET_PAPERS = 12


class SetCriticalReadRequest(BaseModel):
    paper_ids: list[int]
    llm: bool = False
    triage: bool = False


class SetCriticalReadResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: dict | None = None


@router.post("/critical-read/set", response_model=SetCriticalReadResponse, status_code=http_status.HTTP_202_ACCEPTED)
def set_critical_read_start(
    body: SetCriticalReadRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> SetCriticalReadResponse:
    ids = list(dict.fromkeys(int(p) for p in body.paper_ids))  # de-dup, preserve order
    if not (2 <= len(ids) <= MAX_SET_PAPERS):
        raise HTTPException(status_code=422, detail=f"Select 2–{MAX_SET_PAPERS} papers for a set critical read.")
    for pid in ids:
        try:
            get_paper(conn, pid)
        except NoResultFound:
            raise HTTPException(status_code=404, detail=f"Paper {pid} not found") from None
    job_id = request.app.state.critical_review_set_jobs.create(nav={"paper_ids": ids})
    background_tasks.add_task(_run_set_critical_read_job, request.app, job_id, ids, bool(body.llm), bool(body.triage))
    return SetCriticalReadResponse(job_id=job_id, status="pending")


@router.get("/critical-read/set/{job_id}", response_model=SetCriticalReadResponse)
async def set_critical_read_status(
    job_id: str,
    request: Request,
    wait_seconds: float = Query(default=0.0, ge=0.0, le=25.0),
) -> SetCriticalReadResponse:
    jobs: JobStore[SetCriticalReadResponse] = request.app.state.critical_review_set_jobs
    job = await jobs.wait_for_update(job_id, wait_seconds)
    if job is None:
        raise HTTPException(status_code=404, detail="Set critical-read job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return SetCriticalReadResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_set_critical_read_job(
    app: FastAPI, job_id: str, set_ids: list[int], want_llm: bool, want_triage: bool = False
) -> None:
    from app.backend.methods.critical_review_set import set_aggregate, set_contested_claims

    jobs: JobStore[SetCriticalReadResponse] = app.state.critical_review_set_jobs
    jobs.mark_running(job_id)
    try:
        embed_model, vector_store, stance_scorer = _cr_deps(app)
        calibration_key = critical_read_timing_key("critical-read-set", embed_model, stance_scorer)
        jobs.mark_stage(
            job_id,
            "preparing_evidence",
            "Preparing evidence",
            timing_key=calibration_key,
            workload_size=len(set_ids),
        )
        engine: Engine = app.state.engine
        with engine.connect() as conn:
            contested = set_contested_claims(
                conn,
                set_ids,
                embed_model=embed_model,
                vector_store=vector_store,
                stance_scorer=stance_scorer,
                on_stage=lambda key, label, size: jobs.mark_stage(
                    job_id, key, label, timing_key=calibration_key, workload_size=size
                ),
            )
            aggregate = set_aggregate(conn, set_ids, contested)
        if want_llm:
            jobs.mark_stage(
                job_id,
                "generating_critiques",
                "Generating grounded critiques",
                timing_key=calibration_key,
                workload_size=len(set_ids),
                variable=True,
            )
            llm_status, candidates = _run_set_tier2(app, set_ids, stance_scorer, want_triage)
        else:
            llm_status = {"status": "not_searched", "detail": "AI critique was not requested for this run."}
            candidates = []
        triage_status = None
        if want_triage:
            # No DB connection is held during this provider call -- the connection above already closed.
            jobs.mark_stage(
                job_id, "triaging_claims", "Triaging claims with AI", timing_key=calibration_key, variable=True
            )
            triage_status = triage_contested_dicts(app, contested)
        jobs.mark_stage(job_id, "finalizing_result", "Finalizing result", timing_key=calibration_key)
        jobs.mark_done(
            job_id,
            SetCriticalReadResponse(
                job_id=job_id,
                status="done",
                report={
                    "aggregate": aggregate,
                    "contested_claims": contested,
                    "candidates": candidates,
                    "llm_status": llm_status,
                    "triage_status": triage_status,
                },
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _run_set_tier2(
    app: FastAPI, set_ids: list[int], stance_scorer, want_triage: bool = False
) -> tuple[dict, list[dict]]:
    # Tier 2 (egress-gated, invariant #3): the LLM proposes CROSS-PAPER concerns; each is admitted only through the
    # extended #13 bar (verify_set_candidates → verbatim anchor in some set paper), annotated with a local NLI stance,
    # and persisted as a pending CANDIDATE the human accepts/rejects. A fake generator (test seam) still honors the gate.
    from app.backend.llm.managed_local import ManagedLocalTargetError
    from app.backend.llm.providers import requires_egress
    from app.backend.methods.critical_review import paper_full_text
    from integrations.gemini.critical_review_set import GeminiSetCriticalReviewGenerator, verify_set_candidates

    try:
        config = resolve_llm_config(app)
    except ManagedLocalTargetError as exc:
        return {
            "status": "unavailable",
            "detail": f"Local AI is not ready ({exc.code}). Check Settings → AI features.",
        }, []
    if requires_egress(config) and not config.data_egress_enabled:
        return {
            "status": "unavailable",
            "detail": "AI critique needs data-egress consent (Settings → AI features).",
        }, []
    generator = getattr(app.state, "critical_review_set_generator", None)
    if generator is None:
        if requires_egress(config) and not config.resolved_api_key():
            return {"status": "unavailable", "detail": "AI critique needs an API key (Settings → AI features)."}, []
        generator = GeminiSetCriticalReviewGenerator(config=config)

    engine: Engine = app.state.engine
    response: list[dict] = []
    with engine.begin() as conn:
        set_papers = [
            {"index": i + 1, "paper_id": pid, "text": paper_full_text(conn, pid)} for i, pid in enumerate(set_ids)
        ]
        rejected: set[str] = set()
        for pid in set_ids:
            rejected |= repo.rejected_signatures(conn, pid)
        verified = verify_set_candidates(
            generator.propose(set_papers),
            set_papers=set_papers,
            stance_scorer=stance_scorer,
            rejected_signatures=rejected,
        )
        by_paper: dict[int, list[dict]] = {}
        for cand in verified:
            by_paper.setdefault(cand["paper_id"], []).append(cand)
        for pid, group in by_paper.items():
            ids = repo.insert_candidates(conn, pid, group)
            for cand, cid in zip(group, ids, strict=False):
                response.append(
                    {**cand, "id": cid, "status": "pending", "related_paper_ids_json": cand.get("related_paper_ids")}
                )
    if want_triage and response:
        # A separate, later connection -- no DB connection is held during either provider call (LATENCY.md).
        from app.backend.methods.critical_review_triage import TRIAGE_PROMPT_VERSION
        from app.backend.persistence import critical_review_triage_repo as triage_repo

        with engine.begin() as conn2:
            triage_and_persist_candidates(app, conn2, response)
            stored = triage_repo.load_candidate_triage(conn2, [c["id"] for c in response])
        attached = triage_repo.attach_candidate_triage(response, stored, current_prompt_version=TRIAGE_PROMPT_VERSION)
        for cand in response:
            cand["llm_triage"] = attached.get(cand["id"])
    detail = None if response else "No grounded cross-paper concerns surfaced."
    return {"status": "success", "count": len(response), "detail": detail}, response
