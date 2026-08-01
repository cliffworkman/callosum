"""Acquire a user-confirmed public registration and preserve its canonical version locally."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection, select
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.persistence.registration_schema import registration_document_versions
from app.backend.persistence.registration_versions_repo import (
    get_registration_link,
    get_registration_version_by_hash,
    list_registration_versions,
    record_acquired_registration_version,
    record_local_registration_version,
    registration_version_summary,
)
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write
from app.backend.registration_acquisition.domain import RegistrationAcquisitionError
from app.backend.registration_acquisition.providers import build_registration_acquisition_registry
from app.backend.registration_acquisition.storage import import_acquired_registration, managed_registration_path

router = APIRouter()


class AcquisitionStart(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]


class AcquisitionResult(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    paper_id: int | None = None
    link_id: int | None = None
    version_id: int | None = None
    attachment_id: int | None = None
    content_hash: str | None = None
    changed: bool | None = None


class RegistrationVersionOut(BaseModel):
    id: int
    link_id: int
    paper_id: int
    attachment_id: int | None = None
    provider: str
    external_id: str
    content_hash: str
    canonical_url: str | None = None
    registered_at: str | None = None
    registration_status: str | None = None
    schema_name: str | None = None
    schema_version: str | None = None
    retrieved_at: datetime


class RegistrationVersionDetail(RegistrationVersionOut):
    structured: dict[str, Any] = Field(default_factory=dict)
    rendered_text: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/papers/{paper_id}/registration-links/{link_id}/acquire",
    response_model=AcquisitionStart,
    status_code=202,
)
def start_registration_acquisition(
    paper_id: int,
    link_id: int,
    background: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> AcquisitionStart:
    link = get_registration_link(conn, paper_id, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Registration link not found on this paper")
    if link["link_status"] != "confirmed" or not link["user_confirmed"]:
        raise HTTPException(status_code=409, detail="Confirm the registration candidate before acquiring it.")
    if link["registration_status"] in {"withdrawn", "unavailable", "embargoed"}:
        raise HTTPException(
            status_code=409,
            detail=f"The confirmed registration is {link['registration_status']} and has no public artifact to acquire.",
        )
    job_id = request.app.state.registration_acquisition_jobs.create()
    background.add_task(_run_acquisition_job, request.app, job_id, paper_id, link_id)
    return AcquisitionStart(job_id=job_id, status="pending")


@router.get("/registration-acquisition/{job_id}", response_model=AcquisitionResult)
def registration_acquisition_status(job_id: str, request: Request) -> AcquisitionResult:
    job = request.app.state.registration_acquisition_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Registration acquisition job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return AcquisitionResult(job_id=job_id, status=job.status, detail=job.detail)


@router.get("/papers/{paper_id}/registration-versions", response_model=list[RegistrationVersionOut])
def registration_versions(paper_id: int, conn: Connection = Depends(get_connection)) -> list[RegistrationVersionOut]:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return [
        RegistrationVersionOut(**registration_version_summary(row))
        for row in list_registration_versions(conn, paper_id)
    ]


@router.get(
    "/papers/{paper_id}/registration-versions/{version_id}",
    response_model=RegistrationVersionDetail,
)
def registration_version_detail(
    paper_id: int, version_id: int, conn: Connection = Depends(get_connection)
) -> RegistrationVersionDetail:
    row = (
        conn.execute(
            select(registration_document_versions).where(
                registration_document_versions.c.id == version_id,
                registration_document_versions.c.paper_id == paper_id,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Registration version not found on this paper")
    return RegistrationVersionDetail(
        **registration_version_summary(row),
        structured=dict(row["structured_json"] or {}),
        rendered_text=row["rendered_text"],
        source_metadata=dict(row["source_metadata_json"] or {}),
    )


def _run_acquisition_job(app: FastAPI, job_id: str, paper_id: int, link_id: int) -> None:
    jobs: JobStore[AcquisitionResult] = app.state.registration_acquisition_jobs
    jobs.mark_running(job_id)
    temp_path: Path | None = None
    managed_path: Path | None = None
    try:
        with app.state.engine.connect() as conn:
            link_row = get_registration_link(conn, paper_id, link_id)
            if link_row is None or link_row["link_status"] != "confirmed" or not link_row["user_confirmed"]:
                raise RegistrationAcquisitionError("The confirmed registration link is no longer available.")
            link = dict(link_row)
        if link["provider"] == "manual-local":
            if link["attachment_id"] is None:
                raise RegistrationAcquisitionError("The local registration link has no attachment.")

            def record_local(conn: Connection) -> int:
                _require_still_confirmed(conn, paper_id, link_id)
                return record_local_registration_version(conn, paper_id, link_id, int(link["attachment_id"]))

            version_id = run_write(app.state.engine, record_local)
            result = AcquisitionResult(
                job_id=job_id,
                status="done",
                paper_id=paper_id,
                link_id=link_id,
                version_id=version_id,
                attachment_id=link["attachment_id"],
                content_hash=link["content_hash"],
                changed=False,
            )
            jobs.mark_done(job_id, result, nav={"paper_id": paper_id})
            return
        registry = app.state.registration_acquisition_registry or build_registration_acquisition_registry()
        acquired = registry.acquire(link)
        if acquired.registration_status in {"withdrawn", "unavailable", "embargoed"}:
            raise RegistrationAcquisitionError(
                f"The registry now reports this registration as {acquired.registration_status}; no artifact was imported."
            )
        with app.state.engine.connect() as conn:
            _require_still_confirmed(conn, paper_id, link_id)
            existing = get_registration_version_by_hash(conn, link_id, acquired.content_hash)
        if existing is not None and existing["attachment_id"] is not None:

            def record_existing(conn: Connection) -> tuple[int, bool]:
                _require_still_confirmed(conn, paper_id, link_id)
                return record_acquired_registration_version(
                    conn, paper_id, link_id, int(existing["attachment_id"]), acquired
                )

            version_id, _ = run_write(app.state.engine, record_existing)
            result = AcquisitionResult(
                job_id=job_id,
                status="done",
                paper_id=paper_id,
                link_id=link_id,
                version_id=version_id,
                attachment_id=existing["attachment_id"],
                content_hash=acquired.content_hash,
                changed=False,
            )
            jobs.mark_done(job_id, result, nav={"paper_id": paper_id})
            return
        temp_dir = Path(tempfile.gettempdir()) / "callosum-registration-acquire"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"registration-{uuid4().hex}{acquired.file_suffix}"
        temp_path.write_bytes(acquired.file_bytes)
        managed_path = managed_registration_path(acquired)

        def write(conn: Connection) -> tuple[dict, int]:
            _require_still_confirmed(conn, paper_id, link_id)
            attachment = import_acquired_registration(conn, paper_id, acquired, temp_path, managed_path)
            version_id, _ = record_acquired_registration_version(
                conn, paper_id, link_id, int(attachment["attachment_id"]), acquired
            )
            return attachment, version_id

        attachment, version_id = run_write(app.state.engine, write)
        result = AcquisitionResult(
            job_id=job_id,
            status="done",
            paper_id=paper_id,
            link_id=link_id,
            version_id=version_id,
            attachment_id=attachment["attachment_id"],
            content_hash=acquired.content_hash,
            changed=True,
        )
        jobs.mark_done(job_id, result, nav={"paper_id": paper_id})
    except Exception as exc:
        if managed_path is not None:
            managed_path.unlink(missing_ok=True)
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _require_still_confirmed(conn: Connection, paper_id: int, link_id: int) -> None:
    current = get_registration_link(conn, paper_id, link_id)
    if current is None or current["link_status"] != "confirmed" or not current["user_confirmed"]:
        raise RegistrationAcquisitionError("The registration match is no longer confirmed; acquisition was stopped.")
