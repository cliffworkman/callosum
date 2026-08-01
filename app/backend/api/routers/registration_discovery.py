"""Explicit, metadata-only registration discovery and confirmation/rejection lifecycle."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.job_store import JobStore
from app.backend.persistence.registration_links_repo import (
    list_registration_links,
    set_registration_link_status,
    upsert_registration_candidates,
)
from app.backend.persistence.registration_references_repo import list_registration_references
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write
from app.backend.registration_discovery.domain import DiscoveryReference, DiscoveryRequest
from app.backend.registration_discovery.providers import build_registration_discovery_registry

router = APIRouter()


class DiscoveryConsent(BaseModel):
    metadata_consent: bool
    fresh: bool = False


class DiscoveryStart(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    metadata_fields: list[str]


class ProviderStatusOut(BaseModel):
    provider: str
    status: str
    detail: str | None = None
    candidate_count: int = 0


class RegistrationLinkOut(BaseModel):
    id: int
    paper_id: int
    attachment_id: int | None = None
    provider: str
    external_id: str
    registration_doi: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    contributors: list[str] = Field(default_factory=list)
    registered_at: str | None = None
    registration_status: str | None = None
    schema_name: str | None = None
    link_status: str
    linkage_class: str
    linkage_label: str
    match_method: str
    match_evidence: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: bool
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryResult(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    metadata_fields: list[str] = Field(default_factory=list)
    providers: list[ProviderStatusOut] = Field(default_factory=list)
    candidates: list[RegistrationLinkOut] = Field(default_factory=list)


@router.get("/papers/{paper_id}/registration-discovery/preview")
def registration_discovery_preview(paper_id: int, conn: Connection = Depends(get_connection)) -> dict:
    try:
        paper = get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return {
        "metadata_fields": _metadata_fields(paper, list_registration_references(conn, paper_id)),
        "local_match_fields": _local_match_fields(paper),
        "notice": "Public registry discovery sends metadata only; paper and registration document text stay local.",
    }


@router.post("/papers/{paper_id}/registration-discovery", response_model=DiscoveryStart, status_code=202)
def start_registration_discovery(
    paper_id: int,
    payload: DiscoveryConsent,
    background: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> DiscoveryStart:
    if not payload.metadata_consent:
        raise HTTPException(status_code=422, detail="Confirm the metadata disclosure before searching registries.")
    try:
        paper = get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    fields = _metadata_fields(paper, list_registration_references(conn, paper_id))
    job_id = request.app.state.registration_discovery_jobs.create()
    background.add_task(_run_discovery_job, request.app, job_id, paper_id, payload.fresh, fields)
    return DiscoveryStart(job_id=job_id, status="pending", metadata_fields=fields)


@router.get("/registration-discovery/{job_id}", response_model=DiscoveryResult)
def registration_discovery_status(job_id: str, request: Request) -> DiscoveryResult:
    job = request.app.state.registration_discovery_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Registration discovery job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return DiscoveryResult(job_id=job_id, status=job.status, detail=job.detail)


@router.get("/papers/{paper_id}/registration-links", response_model=list[RegistrationLinkOut])
def registration_links(
    paper_id: int,
    include_rejected: bool = False,
    conn: Connection = Depends(get_connection),
) -> list[RegistrationLinkOut]:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return [_link_out(row) for row in list_registration_links(conn, paper_id, include_rejected=include_rejected)]


@router.post("/papers/{paper_id}/registration-links/{link_id}/confirm", response_model=RegistrationLinkOut)
def confirm_registration_link(paper_id: int, link_id: int, engine: Engine = Depends(get_engine)) -> RegistrationLinkOut:
    return _change_link(engine, paper_id, link_id, "confirmed", user_confirmed=True)


@router.post("/papers/{paper_id}/registration-links/{link_id}/reject", response_model=dict)
def reject_registration_link(paper_id: int, link_id: int, engine: Engine = Depends(get_engine)) -> dict:
    _change_link(engine, paper_id, link_id, "rejected", user_confirmed=False)
    return {"paper_id": paper_id, "link_id": link_id, "link_status": "rejected"}


def _change_link(engine: Engine, paper_id: int, link_id: int, status: str, *, user_confirmed: bool):
    def write(conn: Connection):
        row = next(
            (item for item in list_registration_links(conn, paper_id, include_rejected=True) if item["id"] == link_id),
            None,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Registration candidate not found on this paper")
        if status == "confirmed" and (
            row["link_status"] in {"withdrawn", "unavailable", "embargoed"}
            or row["registration_status"] in {"withdrawn", "unavailable", "embargoed"}
        ):
            raise HTTPException(
                status_code=409,
                detail="An unavailable, withdrawn, or embargoed registration cannot be confirmed.",
            )
        if not set_registration_link_status(conn, paper_id, link_id, status, user_confirmed=user_confirmed):
            raise HTTPException(status_code=404, detail="Registration candidate not found on this paper")
        changed = next(
            item for item in list_registration_links(conn, paper_id, include_rejected=True) if item["id"] == link_id
        )
        return _link_out(changed)

    return run_write(engine, write)


def _run_discovery_job(app: FastAPI, job_id: str, paper_id: int, fresh: bool, fields: list[str]) -> None:
    jobs: JobStore[DiscoveryResult] = app.state.registration_discovery_jobs
    jobs.mark_running(job_id)
    try:
        with app.state.engine.connect() as conn:
            request = _discovery_request(get_paper(conn, paper_id), list_registration_references(conn, paper_id), fresh)
        registry = app.state.registration_discovery_registry or build_registration_discovery_registry()
        candidates, reports = registry.discover(request)
        run_write(
            app.state.engine,
            lambda conn: upsert_registration_candidates(conn, paper_id, candidates, fresh=fresh),
        )
        with app.state.engine.connect() as conn:
            links = [_link_out(row) for row in list_registration_links(conn, paper_id)]
        jobs.mark_done(
            job_id,
            DiscoveryResult(
                job_id=job_id,
                status="done",
                metadata_fields=fields,
                providers=[
                    ProviderStatusOut(
                        provider=report.provider,
                        status=report.status,
                        detail=report.detail,
                        candidate_count=len(report.candidates),
                    )
                    for report in reports
                ],
                candidates=links,
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _discovery_request(paper, references, fresh: bool) -> DiscoveryRequest:
    csl = paper["csl_json"] or {}
    authors = tuple(
        " ".join(filter(None, (item.get("given"), item.get("family") or item.get("literal")))).strip()
        for item in csl.get("author") or []
        if isinstance(item, dict)
    )
    return DiscoveryRequest(
        paper_id=int(paper["id"]),
        doi=paper["doi"],
        title=paper["title"],
        authors=authors,
        year=paper["year"],
        references=tuple(
            DiscoveryReference(
                provider=row["provider"],
                external_id=row["external_id"],
                canonical_url=row["canonical_url"],
                extraction_method=row["extraction_method"],
                explicitly_printed=bool(row["explicitly_printed"]),
                evidence_snippet=row["evidence_snippet"],
            )
            for row in references
        ),
        fresh=fresh,
    )


def _metadata_fields(paper, references) -> list[str]:
    fields = [name for name, value in (("paper DOI", paper["doi"]), ("paper title", paper["title"])) if value]
    if references:
        fields.append("detected registration identifiers")
    return fields


def _local_match_fields(paper) -> list[str]:
    fields = []
    if (paper["csl_json"] or {}).get("author"):
        fields.append("author names")
    if paper["year"]:
        fields.append("publication year")
    return fields


def _link_out(row) -> RegistrationLinkOut:
    label = {
        "explicit-linkage": "Explicitly linked",
        "strong-contextual-match": "Probable match, confirm",
        "similarity-candidate": "Possible match, inspect",
    }[row["linkage_class"]]
    return RegistrationLinkOut(
        id=row["id"],
        paper_id=row["paper_id"],
        attachment_id=row["attachment_id"],
        provider=row["provider"],
        external_id=row["external_id"],
        registration_doi=row["registration_doi"],
        canonical_url=row["canonical_url"],
        title=row["title"],
        contributors=list(row["contributors_json"] or []),
        registered_at=row["registered_at"],
        registration_status=row["registration_status"],
        schema_name=row["schema_name"],
        link_status=row["link_status"],
        linkage_class=row["linkage_class"],
        linkage_label=label,
        match_method=row["match_method"],
        match_evidence=list(row["match_evidence_json"] or []),
        user_confirmed=bool(row["user_confirmed"]),
        source_metadata=dict(row["source_metadata_json"] or {}),
    )
