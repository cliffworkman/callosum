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

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, SentenceTransformerEmbeddingModel
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
from app.backend.summarization.verification import default_stance_scorer

router = APIRouter()


class ContestedClaimResponse(BaseModel):
    claim: str
    passage: str  # verbatim, from the OTHER paper — the grounding
    other_paper_id: int
    page: int | None = None
    stance: str
    confidence: float


class MethodSignalResponse(BaseModel):
    kind: str
    label: str
    detail: str | None = None


class ScrutinyBackboneResponse(BaseModel):
    method_signals: list[MethodSignalResponse] = []
    citation_signal: dict | None = None
    contested_claims: list[ContestedClaimResponse] = []


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


class CandidateListResponse(BaseModel):
    candidates: list[CandidateResponse] = []


class CandidateStatusResponse(BaseModel):
    id: int
    status: str


def _cr_deps(app: FastAPI):
    """(embed_model, vector_store, stance_scorer) — the test seam (`critical_review_deps`) wins, else app.state
    defaults + the local NLI stance scorer. The seam lets endpoint tests inject fakes with no model load."""
    seam = getattr(app.state, "critical_review_deps", None)
    if seam is not None:
        return seam["embed_model"], seam["vector_store"], seam["stance_scorer"]
    embed = app.state.embedding_model or SentenceTransformerEmbeddingModel(
        name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL
    )
    store = app.state.vector_store or SQLiteVecVectorStore()
    return embed, store, default_stance_scorer()


@router.post(
    "/papers/{paper_id}/critical-read",
    response_model=CriticalReadStartResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def critical_read_start(
    paper_id: int, background_tasks: BackgroundTasks, request: Request, conn: Connection = Depends(get_connection)
) -> CriticalReadStartResponse:
    # Async (embeds + NLI over the corpus is slow): returns a job id to poll. Validate the paper first. Tier 1 is
    # fully local — no egress gate here; egress applies only to the Tier-2 candidate generator (a later endpoint).
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    job_id = request.app.state.critical_review_jobs.create()
    background_tasks.add_task(_run_critical_read_job, request.app, job_id, paper_id)
    return CriticalReadStartResponse(job_id=job_id, status="pending")


@router.get("/critical-read/{job_id}", response_model=CriticalReadJobResponse)
def critical_read_status(job_id: str, request: Request) -> CriticalReadJobResponse:
    job = request.app.state.critical_review_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Critical-read job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return CriticalReadJobResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_critical_read_job(app: FastAPI, job_id: str, paper_id: int) -> None:
    jobs: JobStore[CriticalReadJobResponse] = app.state.critical_review_jobs
    jobs.mark_running(job_id)
    try:
        embed_model, vector_store, stance_scorer = _cr_deps(app)
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
                other_chunk_ids=other_paper_chunk_embedding_ids(conn, paper_id),
            )
            backbone = build_scrutiny_backbone(conn, paper_id, contested_claims=contested)
        jobs.mark_done(
            job_id,
            CriticalReadJobResponse(
                job_id=job_id,
                status="done",
                backbone=ScrutinyBackboneResponse(
                    method_signals=[MethodSignalResponse(**signal) for signal in backbone.method_signals],
                    citation_signal=backbone.citation_signal,
                    contested_claims=[
                        ContestedClaimResponse(
                            claim=c.claim,
                            passage=c.passage,
                            other_paper_id=c.other_paper_id,
                            page=c.page,
                            stance=c.stance,
                            confidence=c.confidence,
                        )
                        for c in backbone.contested_claims
                    ],
                ),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


@router.get("/papers/{paper_id}/critical-read/candidates", response_model=CandidateListResponse)
def critical_read_candidates(paper_id: int, conn: Connection = Depends(get_connection)) -> CandidateListResponse:
    rows = repo.list_candidates(conn, paper_id)
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
            )
            for r in rows
        ]
    )


def _set_candidate_status(candidate_id: int, status: str, conn: Connection) -> CandidateStatusResponse:
    if not repo.set_status(conn, candidate_id, status):
        raise HTTPException(status_code=404, detail="Candidate not found")
    conn.commit()
    return CandidateStatusResponse(id=candidate_id, status=status)


@router.post("/critical-read/candidates/{candidate_id}/accept", response_model=CandidateStatusResponse)
def accept_candidate(candidate_id: int, conn: Connection = Depends(get_connection)) -> CandidateStatusResponse:
    return _set_candidate_status(candidate_id, "accepted", conn)


@router.post("/critical-read/candidates/{candidate_id}/reject", response_model=CandidateStatusResponse)
def reject_candidate(candidate_id: int, conn: Connection = Depends(get_connection)) -> CandidateStatusResponse:
    return _set_candidate_status(candidate_id, "rejected", conn)
