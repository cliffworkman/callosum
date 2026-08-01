"""Persisted evidence-bound registration/publication crosswalks with staleness and review state."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine, select

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.job_store import JobStore
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, SentenceTransformerEmbeddingModel
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, SUPPLEMENT
from app.backend.persistence.registration_commitments_repo import (
    get_registration_version,
    list_registration_commitments,
    replace_registration_commitments,
)
from app.backend.persistence.registration_comparisons_repo import (
    create_comparison_run,
    current_link_hash,
    get_comparison_run,
    list_comparison_rows,
    list_comparison_runs,
    mark_comparison_stale,
    set_comparison_review,
    source_snapshot,
)
from app.backend.persistence.registration_schema import paper_registration_links
from app.backend.persistence.repository import get_chunks_for_attachment, get_chunks_for_paper
from app.backend.persistence.schema import attachments
from app.backend.persistence.sqlite_retry import run_write
from app.backend.registration_commitments import EXTRACTION_VERSION, extract_commitments
from app.backend.registration_comparison import COMPARISON_VERSION, compare_registration_to_publication
from app.backend.registration_retrieval import RETRIEVAL_VERSION, retrieve_publication_evidence

router = APIRouter()


class ComparisonStartRequest(BaseModel):
    version_id: int
    include_supplements: bool = False
    expand_beyond_expected_sections: bool = True
    top_k: int = Field(default=3, ge=1, le=5)


class ComparisonStart(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]


class ComparisonJobResult(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    paper_id: int | None = None
    run_id: int | None = None
    row_count: int | None = None


class ComparisonRunSummary(BaseModel):
    id: int
    paper_id: int
    link_id: int
    registration_version_id: int
    status: Literal["completed", "stale"]
    stale_reasons: list[str]
    registration_content_hash: str
    commitment_extraction_version: str
    retrieval_version: str
    comparison_version: str
    configuration: dict[str, Any]
    model_versions: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None
    row_count: int = 0
    unreviewed_count: int = 0


class ComparisonRowOut(BaseModel):
    id: int
    run_id: int
    commitment_id: int | None = None
    field_type: str
    registration_value: dict[str, Any] | None = None
    registration_evidence_text: str | None = None
    registration_source_locator: dict[str, Any] | None = None
    publication_value: dict[str, Any] | None = None
    publication_evidence_text: str | None = None
    publication_source_locator: dict[str, Any] | None = None
    comparison_status: str
    timing_status: str | None = None
    explanation: str
    uncertainty: str
    search_scope: dict[str, Any]
    registration_version_id: int
    registration_content_hash: str
    publication_attachment_id: int | None = None
    publication_attachment_checksum: str | None = None
    review_state: Literal["unreviewed", "reviewed", "dismissed"]
    note: str | None = None


class ComparisonRunDetail(ComparisonRunSummary):
    article_source: list[dict[str, Any]]
    supplement_source: list[dict[str, Any]]
    rows: list[ComparisonRowOut]
    framing: str = (
        "This is an evidence crosswalk for human inspection, not a compliance, integrity, or author judgment."
    )


class ComparisonReviewUpdate(BaseModel):
    review_state: Literal["unreviewed", "reviewed", "dismissed"]
    note: str | None = Field(default=None, max_length=5000)


@router.post("/papers/{paper_id}/registration-comparisons", response_model=ComparisonStart, status_code=202)
def start_registration_comparison(
    paper_id: int,
    payload: ComparisonStartRequest,
    background: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> ComparisonStart:
    version = get_registration_version(conn, paper_id, payload.version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Registration version not found on this paper")
    job_id = request.app.state.registration_comparison_jobs.create()
    background.add_task(_run_comparison_job, request.app, job_id, paper_id, payload.model_dump())
    return ComparisonStart(job_id=job_id, status="pending")


@router.get("/registration-comparisons/jobs/{job_id}", response_model=ComparisonJobResult)
def registration_comparison_job(job_id: str, request: Request) -> ComparisonJobResult:
    job = request.app.state.registration_comparison_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Registration comparison job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ComparisonJobResult(job_id=job_id, status=job.status, detail=job.detail)


@router.get("/papers/{paper_id}/registration-comparisons", response_model=list[ComparisonRunSummary])
def registration_comparison_runs(paper_id: int, engine: Engine = Depends(get_engine)) -> list[ComparisonRunSummary]:
    with engine.connect() as conn:
        runs = list_comparison_runs(conn, paper_id)
    return [_run_summary(engine, row) for row in runs]


@router.get("/papers/{paper_id}/registration-comparisons/{run_id}", response_model=ComparisonRunDetail)
def registration_comparison_detail(
    paper_id: int,
    run_id: int,
    engine: Engine = Depends(get_engine),
) -> ComparisonRunDetail:
    with engine.connect() as conn:
        run = get_comparison_run(conn, paper_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Registration comparison not found on this paper")
    summary = _run_summary(engine, run)
    with engine.connect() as conn:
        refreshed = get_comparison_run(conn, paper_id, run_id)
        rows = list_comparison_rows(conn, run_id)
    return ComparisonRunDetail(
        **(
            summary.model_dump()
            | {
                "status": refreshed["status"],
                "stale_reasons": list(refreshed["stale_reasons_json"] or []),
                "article_source": list(refreshed["article_source_json"] or []),
                "supplement_source": list(refreshed["supplement_source_json"] or []),
                "rows": [_row_out(row) for row in rows],
            }
        )
    )


@router.post("/registration-comparison-rows/{row_id}/review", response_model=ComparisonRowOut)
def review_registration_comparison_row(
    row_id: int,
    payload: ComparisonReviewUpdate,
    engine: Engine = Depends(get_engine),
) -> ComparisonRowOut:
    row = run_write(
        engine,
        lambda conn: set_comparison_review(conn, row_id, payload.review_state, payload.note),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Registration comparison row not found")
    return _row_out(row)


def _run_comparison_job(app: FastAPI, job_id: str, paper_id: int, configuration: dict[str, Any]) -> None:
    jobs: JobStore[ComparisonJobResult] = app.state.registration_comparison_jobs
    jobs.mark_running(job_id)
    try:
        version_id = int(configuration["version_id"])
        with app.state.engine.connect() as conn:
            version = get_registration_version(conn, paper_id, version_id)
            if version is None:
                raise ValueError("Registration version is no longer available on this paper.")
            commitments = list_registration_commitments(
                conn, paper_id, version_id, extraction_version=EXTRACTION_VERSION
            )
        if not commitments:

            def extract_and_write(conn: Connection):
                current = get_registration_version(conn, paper_id, version_id)
                chunks = get_chunks_for_attachment(conn, int(current["attachment_id"]))
                candidates = extract_commitments(current, chunks)
                return replace_registration_commitments(
                    conn, current, candidates, extraction_version=EXTRACTION_VERSION
                )

            commitments = run_write(app.state.engine, extract_and_write)
        with app.state.engine.connect() as conn:
            version = get_registration_version(conn, paper_id, version_id)
            article_chunks = [
                dict(row) | {"document_role": "article-fulltext"}
                for row in get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES)
            ]
            supplement_chunks = (
                [
                    dict(row) | {"document_role": "supplement"}
                    for row in get_chunks_for_paper(conn, paper_id, document_roles=(SUPPLEMENT,))
                ]
                if configuration["include_supplements"]
                else []
            )
            article_fingerprint, article_source = source_snapshot(conn, article_chunks)
            supplement_fingerprint, supplement_source = source_snapshot(conn, supplement_chunks)
            attachment_ids = {int(row["attachment_id"]) for row in (*article_chunks, *supplement_chunks)}
            checksums = {
                int(row["id"]): row["checksum"]
                for row in conn.execute(select(attachments).where(attachments.c.id.in_(attachment_ids))).mappings()
            }
        model = app.state.embedding_model or SentenceTransformerEmbeddingModel(
            name=DEFAULT_EMBEDDING_MODEL,
            version=DEFAULT_EMBEDDING_MODEL,
            local_files_only=True,
        )
        retrievals = retrieve_publication_evidence(
            commitments,
            article_chunks,
            supplement_chunks,
            model=model,
            include_supplements=bool(configuration["include_supplements"]),
            expand_beyond_expected=bool(configuration["expand_beyond_expected_sections"]),
            top_k=int(configuration["top_k"]),
        )
        proposals = compare_registration_to_publication(
            commitments,
            retrievals,
            [*article_chunks, *supplement_chunks],
            attachment_checksums=checksums,
            registration_version_id=version_id,
            registration_content_hash=str(version["content_hash"]),
        )
        run_id = run_write(
            app.state.engine,
            lambda conn: create_comparison_run(
                conn,
                paper_id=paper_id,
                link_id=int(version["link_id"]),
                registration_version_id=version_id,
                registration_content_hash=str(version["content_hash"]),
                article_fingerprint=article_fingerprint,
                supplement_fingerprint=supplement_fingerprint if configuration["include_supplements"] else None,
                article_source=article_source,
                supplement_source=supplement_source,
                commitment_extraction_version=EXTRACTION_VERSION,
                retrieval_version=RETRIEVAL_VERSION,
                comparison_version=COMPARISON_VERSION,
                configuration=configuration,
                model_versions={"embedding": {"name": model.name, "version": model.version}},
                proposals=proposals,
            ),
        )
        jobs.mark_done(
            job_id,
            ComparisonJobResult(
                job_id=job_id,
                status="done",
                paper_id=paper_id,
                run_id=run_id,
                row_count=len(proposals),
            ),
            nav={"paper_id": paper_id},
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _run_summary(engine: Engine, run) -> ComparisonRunSummary:
    reasons = _stale_reasons(engine, run)
    if reasons and (run["status"] != "stale" or list(run["stale_reasons_json"] or []) != reasons):
        run_write(engine, lambda conn: mark_comparison_stale(conn, int(run["id"]), reasons))
    with engine.connect() as conn:
        current = get_comparison_run(conn, int(run["paper_id"]), int(run["id"]))
        rows = list_comparison_rows(conn, int(run["id"]))
    return ComparisonRunSummary(
        id=current["id"],
        paper_id=current["paper_id"],
        link_id=current["link_id"],
        registration_version_id=current["registration_version_id"],
        status=current["status"],
        stale_reasons=list(current["stale_reasons_json"] or []),
        registration_content_hash=current["registration_content_hash"],
        commitment_extraction_version=current["commitment_extraction_version"],
        retrieval_version=current["retrieval_version"],
        comparison_version=current["comparison_version"],
        configuration=dict(current["configuration_json"] or {}),
        model_versions=dict(current["model_versions_json"] or {}),
        created_at=current["created_at"],
        completed_at=current["completed_at"],
        row_count=len(rows),
        unreviewed_count=sum(row["review_state"] == "unreviewed" for row in rows),
    )


def _stale_reasons(engine: Engine, run) -> list[str]:
    reasons = []
    with engine.connect() as conn:
        if current_link_hash(conn, int(run["link_id"])) != run["registration_content_hash"]:
            reasons.append("registration-content-changed")
        confirmed = conn.scalar(
            select(paper_registration_links.c.id).where(
                paper_registration_links.c.paper_id == run["paper_id"],
                paper_registration_links.c.link_status == "confirmed",
                paper_registration_links.c.id == run["link_id"],
            )
        )
        if confirmed is None:
            reasons.append("confirmed-registration-changed")
        article = get_chunks_for_paper(conn, int(run["paper_id"]), document_roles=ARTICLE_DOCUMENT_ROLES)
        article_fingerprint, _ = source_snapshot(conn, article)
        if article_fingerprint != run["article_fingerprint"]:
            reasons.append("article-attachment-or-extraction-changed")
        if bool((run["configuration_json"] or {}).get("include_supplements")):
            supplements = get_chunks_for_paper(conn, int(run["paper_id"]), document_roles=(SUPPLEMENT,))
            supplement_fingerprint, _ = source_snapshot(conn, supplements)
            if supplement_fingerprint != run["supplement_fingerprint"]:
                reasons.append("supplement-attachment-or-extraction-changed")
    if run["commitment_extraction_version"] != EXTRACTION_VERSION:
        reasons.append("commitment-extraction-version-changed")
    if run["retrieval_version"] != RETRIEVAL_VERSION:
        reasons.append("section-retrieval-version-changed")
    if run["comparison_version"] != COMPARISON_VERSION:
        reasons.append("comparison-version-changed")
    return reasons


def _row_out(row) -> ComparisonRowOut:
    return ComparisonRowOut(
        id=row["id"],
        run_id=row["run_id"],
        commitment_id=row["commitment_id"],
        field_type=row["field_type"],
        registration_value=dict(row["registration_value_json"]) if row["registration_value_json"] else None,
        registration_evidence_text=row["registration_evidence_text"],
        registration_source_locator=(
            dict(row["registration_source_locator_json"]) if row["registration_source_locator_json"] else None
        ),
        publication_value=dict(row["publication_value_json"]) if row["publication_value_json"] else None,
        publication_evidence_text=row["publication_evidence_text"],
        publication_source_locator=(
            dict(row["publication_source_locator_json"]) if row["publication_source_locator_json"] else None
        ),
        comparison_status=row["comparison_status"],
        timing_status=row["timing_status"],
        explanation=row["explanation"],
        uncertainty=row["uncertainty"],
        search_scope=dict(row["search_scope_json"] or {}),
        registration_version_id=row["registration_version_id"],
        registration_content_hash=row["registration_content_hash"],
        publication_attachment_id=row["publication_attachment_id"],
        publication_attachment_checksum=row["publication_attachment_checksum"],
        review_state=row["review_state"],
        note=row["note"],
    )
