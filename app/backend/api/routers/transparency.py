"""Transparency-signals auditor endpoint (backlog #44, inc 250/251).

GET /papers/{id}/transparency — deterministic, local, read-only. Reads the paper's extracted text and returns 7
open-science-disclosure detectors (present / not-found / not-applicable). No score, no verdict; "not-found" ≠ "absent"
(silence≠certificate). No chunks → all detectors run over empty text (the frontend gates the "process a PDF first"
state). Mirrors GET /papers/{id}/meta-analysis.

inc 251 adds the library-wide **persistence** layer (the statcheck inc-97 pattern): POST /methods/transparency/run
batch-runs every live paper, persisting present-disclosure FACTs + per-disclosure check statuses (see
methods/transparency_findings.py); GET /methods/transparency/summary drives the review-queue chip. See
methods/transparency.py (the detector) + methods/transparency_findings.py (the producer).
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import fitz
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.acquisition.fetch import MAX_OA_PDF_BYTES, library_dir
from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.job_store import JobStore
from app.backend.api.local_only import require_local_file_access
from app.backend.methods.evidence_anchors import anchor_evidence, pdf_attachment_ids_for_chunks
from app.backend.methods.registration_references import extract_registration_references, normalize_manual_reference
from app.backend.methods.transparency import detect_transparency
from app.backend.methods.transparency_findings import persist_transparency
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.persistence.document_roles import ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES
from app.backend.persistence.registration_links_repo import confirm_local_registration_attachment
from app.backend.persistence.registration_references_repo import (
    add_manual_registration_reference,
    list_registration_references,
    set_attachment_document_role,
)
from app.backend.persistence.repository import (
    get_attachments_for_paper,
    get_chunks_for_paper,
    get_paper,
    list_live_paper_ids,
    refresh_processing_tier,
)
from app.backend.persistence.signals_repo import count_transparency_review, count_transparency_status
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()
_log = logging.getLogger("callosum.transparency")


class TransparencyCheckOut(BaseModel):
    key: str
    label: str
    status: str  # present | not-found | not-applicable
    evidence: str | None = None
    page: int | None = None
    page_end: int | None = None
    coordinate_precision: str | None = None
    bbox_json: Any | None = None
    attachment_id: int | None = None
    note: str | None = None
    explainer: str
    basis: str


class TransparencyResponse(BaseModel):
    checks: list[TransparencyCheckOut]
    registration_reference_state: Literal[
        "not-detected", "language-detected", "reference-detected", "multiple-references-detected"
    ]
    registration_references: list["RegistrationReferenceOut"]


class RegistrationReferenceOut(BaseModel):
    id: int | None = None
    provider: str
    external_id: str
    canonical_url: str | None = None
    visible_text: str | None = None
    evidence_snippet: str | None = None
    page: int | None = None
    attachment_id: int | None = None
    extraction_method: str
    evidence_class: str
    explicitly_printed: bool
    coordinate_precision: str | None = None
    bbox_json: Any | None = None


class ManualRegistrationReferenceIn(BaseModel):
    value: str = Field(min_length=1, max_length=2000)


class AttachmentRoleIn(BaseModel):
    role: Literal["preregistration", "protocol", "supplement", "article-fulltext", "other"]


@router.get("/papers/{paper_id}/transparency", response_model=TransparencyResponse)
def paper_transparency(paper_id: int, conn: Connection = Depends(get_connection)) -> TransparencyResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    chunks = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES)
    pdf_attachment_ids = pdf_attachment_ids_for_chunks(conn, chunks)
    report = detect_transparency(chunks)
    references = _registration_reference_outputs(conn, paper_id, chunks, pdf_attachment_ids)
    prereg_signal = next(check for check in report.checks if check.key == "preregistration")
    registration_signal = next(check for check in report.checks if check.key == "registration")
    if len(references) > 1:
        reference_state = "multiple-references-detected"
    elif references:
        reference_state = "reference-detected"
    elif prereg_signal.status == "present" or registration_signal.status == "present":
        reference_state = "language-detected"
    else:
        reference_state = "not-detected"
    return TransparencyResponse(
        checks=[
            TransparencyCheckOut(
                key=c.key,
                label=c.label,
                status=c.status,
                evidence=c.evidence,
                page=c.page,
                **anchor_evidence(conn, chunks, c.evidence, c.page, pdf_attachment_ids=pdf_attachment_ids),
                note=c.note,
                explainer=c.explainer,
                basis=c.basis,
            )
            for c in report.checks
        ],
        registration_reference_state=reference_state,
        registration_references=references,
    )


def _registration_reference_outputs(conn, paper_id, chunks, pdf_attachment_ids) -> list[RegistrationReferenceOut]:
    persisted = [dict(row) for row in list_registration_references(conn, paper_id)]
    live = [reference.to_dict() | {"id": None} for reference in extract_registration_references(chunks)]
    combined: list[dict] = []
    seen: set[tuple[str, str, int | None]] = set()
    for row in [*persisted, *live]:
        key = (row["provider"], str(row["external_id"]).casefold(), row.get("attachment_id"))
        if key in seen:
            continue
        seen.add(key)
        anchor = anchor_evidence(
            conn,
            chunks,
            row.get("evidence_snippet"),
            row.get("page"),
            pdf_attachment_ids=pdf_attachment_ids,
        )
        if row.get("attachment_id") is not None:
            anchor["attachment_id"] = row["attachment_id"]
        combined.append(row | anchor)
    return [RegistrationReferenceOut(**row) for row in combined]


@router.post("/papers/{paper_id}/registration-references", response_model=RegistrationReferenceOut, status_code=201)
def add_registration_reference(
    paper_id: int, payload: ManualRegistrationReferenceIn, engine: Engine = Depends(get_engine)
) -> RegistrationReferenceOut:
    try:
        reference = normalize_manual_reference(payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    def _write(conn: Connection) -> RegistrationReferenceOut:
        try:
            get_paper(conn, paper_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Paper not found") from None
        reference_id = add_manual_registration_reference(conn, paper_id, reference)
        return RegistrationReferenceOut(id=reference_id, **reference.to_dict())

    return run_write(engine, _write)


@router.patch(
    "/papers/{paper_id}/attachments/{attachment_id}/document-role",
    response_model=dict,
)
def update_attachment_document_role(
    paper_id: int, attachment_id: int, payload: AttachmentRoleIn, engine: Engine = Depends(get_engine)
) -> dict:
    def _write(conn: Connection) -> dict:
        try:
            get_paper(conn, paper_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Paper not found") from None
        if not set_attachment_document_role(conn, paper_id, attachment_id, payload.role):
            raise HTTPException(status_code=404, detail="Attachment not found on this paper")
        if payload.role == "preregistration":
            confirm_local_registration_attachment(conn, paper_id, attachment_id)
        refresh_processing_tier(conn, paper_id)
        return {"paper_id": paper_id, "attachment_id": attachment_id, "role": payload.role}

    return run_write(engine, _write)


@router.post(
    "/papers/{paper_id}/registration-attachments",
    response_model=dict,
    status_code=201,
    dependencies=[Depends(require_local_file_access)],
)
async def attach_local_registration_pdf(
    paper_id: int,
    request: Request,
    filename: str = Query(default="registration.pdf", max_length=255),
    engine: Engine = Depends(get_engine),
) -> dict:
    """Import a browser-selected local PDF. Raw bytes stay on this machine; no provider request occurs."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_OA_PDF_BYTES:
                raise HTTPException(status_code=413, detail="Registration PDF exceeds the 80 MiB limit.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from None
    temp_path = Path(tempfile.gettempdir()) / f"callosum-registration-{uuid4().hex}.pdf"
    total = 0
    try:
        with temp_path.open("wb") as handle:
            async for block in request.stream():
                total += len(block)
                if total > MAX_OA_PDF_BYTES:
                    raise HTTPException(status_code=413, detail="Registration PDF exceeds the 80 MiB limit.")
                handle.write(block)
        with temp_path.open("rb") as handle:
            magic = handle.read(5)
        if total < 5 or magic != b"%PDF-":
            raise HTTPException(status_code=422, detail="The selected file is not a PDF.")
        try:
            with fitz.open(temp_path) as document:
                if document.page_count < 1:
                    raise ValueError("no pages")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"The selected PDF could not be opened: {exc}") from None

        with engine.connect() as conn:
            try:
                get_paper(conn, paper_id)
            except NoResultFound:
                raise HTTPException(status_code=404, detail="Paper not found") from None
            existing_names = {
                Path(str(row["resolved_path"] or row["original_path"] or "")).name
                for row in get_attachments_for_paper(conn, paper_id)
            }
        managed_root = library_dir()
        managed_root.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_registration_filename(filename, existing_names)
        managed_path = managed_root / safe_name
        shutil.move(str(temp_path), str(managed_path))
        try:
            result = run_write(engine, lambda conn: _attach_and_confirm_local(conn, paper_id, managed_path))
        except Exception:
            managed_path.unlink(missing_ok=True)
            raise
        return {"paper_id": paper_id, "filename": safe_name, **result}
    finally:
        temp_path.unlink(missing_ok=True)


def _safe_registration_filename(filename: str, existing_names: set[str]) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[^A-Za-z0-9 _().-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")[:160] or "registration"
    candidate = f"{stem} (registration).pdf"
    index = 2
    while candidate in existing_names or (library_dir() / candidate).exists():
        candidate = f"{stem} (registration {index}).pdf"
        index += 1
    return candidate


def _attach_and_confirm_local(conn: Connection, paper_id: int, managed_path: Path) -> dict:
    result = attach_pdf_to_paper(
        conn,
        paper_id,
        managed_path,
        storage_mode="managed",
        original_path=str(managed_path),
        import_source="registration:manual-local",
        role="preregistration",
    )
    result["registration_link_id"] = confirm_local_registration_attachment(conn, paper_id, result["attachment_id"])
    return result


# --- inc 251: the library-wide persistence batch + the review-queue chip -------------------------------------------


class TransparencyRunSummary(BaseModel):
    total: int = 0  # live papers checked
    with_disclosures: int = 0  # papers with ≥1 detected disclosure


class TransparencyRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: TransparencyRunSummary | None = None


class TransparencyLibrarySummary(BaseModel):
    data_detected: int  # papers where data-availability was detected — a positive, checkable evidence signal
    data_not_detected: int  # papers where data-availability wasn't detected — a REVIEW QUEUE count, not a verdict


def _run_transparency_all_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[TransparencyRunResponse] = app.state.transparency_jobs
    jobs.mark_running(job_id)
    try:
        total = with_disclosures = 0
        engine = app.state.engine
        with engine.connect() as conn:
            paper_ids = list_live_paper_ids(conn)
        # inc C: persist each paper's transparency signals in its own committed transaction — lock released between.
        for i, paper_id in enumerate(paper_ids):
            total += 1
            try:
                result = run_write(
                    engine,
                    lambda conn, pid=paper_id: persist_transparency(
                        conn,
                        pid,
                        get_chunks_for_paper(conn, pid, document_roles=ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES),
                    ),
                )
                if result["present"] > 0:
                    with_disclosures += 1
            except Exception as exc:  # noqa: BLE001 — one bad paper never aborts the batch
                _log.warning("transparency batch: skipped paper %s: %s", paper_id, exc)
            jobs.mark_progress(job_id, i + 1, len(paper_ids), "Detecting transparency signals")
        jobs.mark_done(
            job_id,
            TransparencyRunResponse(
                job_id=job_id,
                status="done",
                summary=TransparencyRunSummary(total=total, with_disclosures=with_disclosures),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


@router.post("/methods/transparency/run", response_model=TransparencyRunResponse, status_code=202)
def transparency_run(background_tasks: BackgroundTasks, request: Request) -> TransparencyRunResponse:
    # Batch-detect transparency signals over every live paper (async) — persists present-disclosure FACTs +
    # per-disclosure check statuses; re-running overwrites. Local, no egress, no LLM. NEVER writes an absence as a FACT.
    job_id = request.app.state.transparency_jobs.create()
    background_tasks.add_task(_run_transparency_all_job, request.app, job_id)
    return TransparencyRunResponse(job_id=job_id, status="pending")


@router.get("/methods/transparency/run/{job_id}", response_model=TransparencyRunResponse)
def transparency_run_status(job_id: str, request: Request) -> TransparencyRunResponse:
    job = request.app.state.transparency_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Transparency run job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return TransparencyRunResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.get("/methods/transparency/summary", response_model=TransparencyLibrarySummary)
def transparency_library_summary(conn: Connection = Depends(get_connection)) -> TransparencyLibrarySummary:
    # Drives the Library-header Open Data chip with the positive detected signal. Keep the not-detected review count
    # available for the transparency panel; it is still only a "go look" queue, never "papers that hide their data."
    return TransparencyLibrarySummary(
        data_detected=count_transparency_status(conn, "data_availability", "detected"),
        data_not_detected=count_transparency_review(conn, "data_availability"),
    )
