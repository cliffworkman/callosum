"""Duplicate-detection + merge endpoints (inc 56 / 161) — an async scan job, a persistent "not a duplicate"
dismiss, and a non-destructive **merge**.

Flag-only detection + dismiss are entirely **local** (no egress): the scan reads the library and flags
likely-duplicate groups for review; the user resolves by trashing a copy (soft-delete), marking a group **not a
duplicate** (persisted, inc 64, so the scan never re-flags it), or **merging** them (inc 161 — fold every copy's
source data onto a survivor; the others go to Trash; see `metadata/paper_merge.py`). Extracted from `papers.py`
(inc 64) to keep that module under the 600-line cap. Registered BEFORE `papers.router` in `app.py` so the literal
`/papers/duplicates` + `/papers/merge` segments win over `/papers/{paper_id}`.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, Engine, select

from app.backend.api.dependencies import get_connection, get_engine, resolve_embedding_model
from app.backend.api.job_store import JobStore
from app.backend.clustering.duplicate_detection import find_duplicate_groups
from app.backend.embeddings.models import EmbeddingModel
from app.backend.metadata.paper_merge import MergeConflictError, MergeValidationError, merge_papers
from app.backend.metadata.paper_unmerge import UnmergeError, merge_origin, unmerge
from app.backend.persistence.dedup_repo import (
    dismiss_duplicate_pairs,
    list_dismissed_duplicate_pairs,
    undismiss_duplicate_pair,
)
from app.backend.persistence.schema import papers
from app.backend.persistence.sqlite_retry import run_write
from app.backend.usage import record_event

router = APIRouter()


class DuplicatePaperRef(BaseModel):
    id: int
    title: str
    authors: list[str] = []
    year: int | None = None
    venue: str | None = None


class DuplicateGroupResponse(BaseModel):
    reason: str
    confidence: float
    papers: list[DuplicatePaperRef]


class DedupJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    groups: list[DuplicateGroupResponse] | None = None


class DismissDuplicatesRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=2)  # the group's papers → "these are not duplicates of each other"


class UndismissDuplicatesRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=2)  # remove the "not a duplicate" mark among these papers


class DismissedPaperRef(BaseModel):
    id: int
    title: str


class DismissedPairResponse(BaseModel):
    low: DismissedPaperRef
    high: DismissedPaperRef


class DismissedPairsResponse(BaseModel):
    pairs: list[DismissedPairResponse]


@router.post("/papers/duplicates", response_model=DedupJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def scan_duplicates_start(background_tasks: BackgroundTasks, request: Request) -> DedupJobResponse:
    # Async (scanning + embedding the whole library is slow): returns a job id to poll. A remounted modal or
    # concurrent request resumes the one active scan instead of creating duplicate work/Status rows.
    jobs: JobStore[DedupJobResponse] = request.app.state.dedup_jobs
    job_id, created = jobs.create_or_get_active()
    job = jobs.get(job_id)
    if created:
        background_tasks.add_task(_run_dedup_job, request.app, job_id)
    return DedupJobResponse(job_id=job_id, status=job.status if job is not None else "pending")


@router.get("/papers/duplicates/dismissed", response_model=DismissedPairsResponse)
def list_dismissed_duplicates(conn: Connection = Depends(get_connection)) -> DismissedPairsResponse:
    # Registered BEFORE /papers/duplicates/{job_id} so the literal "dismissed" isn't captured as a job id.
    rows = list_dismissed_duplicate_pairs(conn)
    return DismissedPairsResponse(
        pairs=[
            DismissedPairResponse(
                low=DismissedPaperRef(id=int(row["paper_id_low"]), title=row["low_title"] or "Untitled"),
                high=DismissedPaperRef(id=int(row["paper_id_high"]), title=row["high_title"] or "Untitled"),
            )
            for row in rows
        ]
    )


@router.get("/papers/duplicates/{job_id}", response_model=DedupJobResponse)
def scan_duplicates_status(job_id: str, request: Request) -> DedupJobResponse:
    job = request.app.state.dedup_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Duplicate-scan job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return DedupJobResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.post("/papers/duplicates/dismiss", status_code=http_status.HTTP_204_NO_CONTENT)
def dismiss_duplicates(payload: DismissDuplicatesRequest, engine: Engine = Depends(get_engine)) -> Response:
    # Persist "not a duplicate" for every pair within the group, so the scan never re-flags it. Store only
    # canonical (low < high) pairs of EXISTING live papers (a non-existent / trashed id would violate the FK).
    def _do(conn: Connection) -> Response:
        existing = {
            int(row[0])
            for row in conn.execute(
                select(papers.c.id).where(papers.c.id.in_(set(payload.paper_ids)), papers.c.deleted_at.is_(None))
            )
        }
        ids = sorted(existing)
        if len(ids) < 2:
            raise HTTPException(
                status_code=422, detail="Need at least two existing papers to dismiss as not-duplicates"
            )
        pairs = [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]  # sorted → (low, high)
        dismiss_duplicate_pairs(conn, pairs)
        record_event(conn, "duplicate_resolved", count=1)  # one resolution decision, not the O(n^2) pair count
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


@router.post("/papers/duplicates/undismiss", status_code=http_status.HTTP_204_NO_CONTENT)
def undismiss_duplicates(payload: UndismissDuplicatesRequest, engine: Engine = Depends(get_engine)) -> Response:
    # Remove the "not a duplicate" mark among these papers, so the scan can flag them again. Idempotent:
    # removing a pair that isn't dismissed is a no-op. Non-destructive (drops a preference, not any paper).
    def _do(conn: Connection) -> Response:
        ids = sorted(set(payload.paper_ids))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                undismiss_duplicate_pair(conn, ids[i], ids[j])  # canonical (low, high)
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


class MergeMetadata(BaseModel):
    # The chosen scalar field values for the surviving record (the dialog's per-field picks). Only the fields the
    # client sets become `edits` for `build_paper_update` (omitted → the survivor keeps its own value). Keys match
    # the Details-editor field names. `extra="forbid"` so an unknown field is a 422, not a silent drop.
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    abstract: str | None = None
    venue: str | None = None
    language: str | None = None
    item_type: str | None = None
    doi: str | None = None
    citation_key: str | None = None
    url: str | None = None
    pmid: str | None = None
    arxiv: str | None = None
    issn: str | None = None
    isbn: str | None = None
    volume: str | None = None
    issue: str | None = None
    page: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    authors: list[str] | None = None
    translators: list[str] | None = None


class MergePapersRequest(BaseModel):
    survivor_id: int
    merged_ids: list[int] = Field(min_length=1, max_length=20)  # the copies folded into the survivor
    metadata: MergeMetadata = Field(default_factory=MergeMetadata)
    primary_attachment_id: int | None = None


class MergePapersResponse(BaseModel):
    survivor_id: int
    merged_ids: list[int]
    trashed: list[int]
    merge_operation_id: int  # the undo handle (#16) — POST /merge/{id}/undo reverses it


class UnmergeResponse(BaseModel):
    survivor_id: int
    restored_ids: list[int]


class MergeOriginResponse(BaseModel):
    merge_operation_id: int
    merged_from_titles: list[str]


@router.post("/papers/merge", response_model=MergePapersResponse)
def merge_papers_endpoint(payload: MergePapersRequest, engine: Engine = Depends(get_engine)) -> MergePapersResponse:
    # Non-destructive merge (inc 161): fold every merged copy's source data onto the survivor; the others become
    # merged-away husks. Reversible via un-merge (#16). Local, bound-param, transaction all-or-nothing.
    def _do(conn: Connection) -> MergePapersResponse:
        try:
            result = merge_papers(
                conn,
                survivor_id=payload.survivor_id,
                merged_ids=payload.merged_ids,
                metadata=payload.metadata.model_dump(exclude_unset=True),
                primary_attachment_id=payload.primary_attachment_id,
            )
        except MergeConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except MergeValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        record_event(conn, "duplicate_resolved", count=1)
        return MergePapersResponse(
            survivor_id=result.survivor_id,
            merged_ids=result.merged_ids,
            trashed=result.trashed,
            merge_operation_id=result.merge_operation_id,
        )

    return run_write(engine, _do)


@router.post("/merge/{merge_operation_id}/undo", response_model=UnmergeResponse)
def unmerge_endpoint(merge_operation_id: int, engine: Engine = Depends(get_engine)) -> UnmergeResponse:
    # Reverse a merge exactly from its snapshot (#16): survivor's record restored, husks brought back with their
    # moved data, added union links removed. All-or-nothing.
    def _do(conn: Connection) -> UnmergeResponse:
        try:
            result = unmerge(conn, merge_operation_id=merge_operation_id)
        except UnmergeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return UnmergeResponse(survivor_id=result.survivor_id, restored_ids=result.restored_ids)

    return run_write(engine, _do)


@router.get("/papers/{paper_id}/merge-origin", response_model=MergeOriginResponse | None)
def merge_origin_endpoint(paper_id: int, conn: Connection = Depends(get_connection)) -> MergeOriginResponse | None:
    # For the survivor's Detail "Merged from … — Un-merge" affordance. Registered before /papers/{paper_id}.
    origin = merge_origin(conn, paper_id)
    if origin is None:
        return None
    return MergeOriginResponse(
        merge_operation_id=origin["merge_operation_id"], merged_from_titles=origin["merged_from_titles"]
    )


def _embedding_model(app: FastAPI) -> EmbeddingModel:
    return resolve_embedding_model(app)


def _run_dedup_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[DedupJobResponse] = app.state.dedup_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        engine: Engine = app.state.engine
        # inc D: a read-only scan (find_duplicate_groups only SELECTs + compares in memory) runs on a READ
        # connection — it must never open a write transaction (which could hold the write lock).
        with engine.connect() as conn:  # read-only scan; entirely local (no egress)
            groups = find_duplicate_groups(conn, model=model)
        jobs.mark_done(
            job_id,
            DedupJobResponse(
                job_id=job_id,
                status="done",
                groups=[
                    DuplicateGroupResponse(
                        reason=g.reason,
                        confidence=g.confidence,
                        papers=[DuplicatePaperRef(**ref) for ref in g.papers],
                    )
                    for g in groups
                ],
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
