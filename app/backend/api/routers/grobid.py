"""GROBID settings + per-paper/bulk structure-parsing endpoints (backlog #30 Stage 2, task 9).

GROBID is a separately-running, opt-in Docker service (``integrations/grobid/client.py``); this router is the
API surface around it: ``GET /grobid/status`` + ``POST /grobid/settings`` read/write the plain, non-secret
``grobid_url`` preference (mirrors ``local_base_url``, ``app_settings.py``); ``POST /grobid/test-connection``
pings GROBID's own liveness endpoint (mirrors ``/settings/test-key``'s always-200 shape, but — unlike a real LLM
ping — sends zero payload, so it needs no egress gate at all, even for a non-loopback URL: nothing about a bare
liveness check reveals library content, invariant #3's actual target); ``POST /grobid/papers/{id}/parse`` and
``POST /grobid/library/parse`` (bulk) send a paper's PDF bytes to GROBID, so THOSE are egress-gated exactly like
a non-loopback custom LLM provider endpoint (``llm.providers.requires_egress`` / ``is_loopback_url`` — a
loopback GROBID server needs no consent; a non-loopback one does).

New sibling router (the ``paper_enrich.py`` / ``methods_retraction.py`` / ``sync_shares.py`` precedent) — not
grown inside an existing router. Both parse endpoints share one ``grobid_parse_jobs`` ``JobStore`` (registered in
``app.py``, Status-tracked per invariant #5 via ``status.py``'s ``JOB_NAV_DEFAULTS``/``JOB_LABELS``): a per-paper
job and a bulk job are the same kind of work at different scope, exactly like this store naming already reads.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend import app_settings
from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import JobProgressOut, _progress_out
from app.backend.api.routers.paper_files import _local_attachment_path, _select_primary_pdf_attachment
from app.backend.grobid_pipeline import paper_ids_with_sections, parse_paper_structure
from app.backend.llm.providers import requires_egress
from app.backend.persistence.repository import get_attachments_for_paper, get_paper, list_live_paper_ids
from app.backend.persistence.sqlite_retry import run_write
from integrations.gemini import GeminiConfig
from integrations.grobid.client import GrobidError
from integrations.grobid.tei_parse import GrobidParseError

_log = logging.getLogger("callosum.grobid")
GROBID_PARSE_WORKERS = 2  # lowered 2026-08-26 (was 4): 4 concurrent requests exhausted a real self-hosted
# GROBID's internal engine pool, 503-ing 100% of a 216-paper bulk run -- see backlog #58. The client's own
# retry-on-503 (integrations/grobid/client.py) absorbs remaining transient pool contention.

router = APIRouter(tags=["grobid"])

_UNCONFIGURED_DETAIL = "Configure a GROBID server URL in Settings before parsing."
_EGRESS_REFUSED_DETAIL = (
    "AI features are off. Enable data egress in Settings to send this PDF to a non-loopback GROBID server."
)


# --- settings + status -------------------------------------------------------------------------------------


class GrobidStatusResponse(BaseModel):
    configured: bool
    url: str | None = None


class GrobidSettingsRequest(BaseModel):
    url: str | None = Field(default=None, max_length=500)


def _status() -> GrobidStatusResponse:
    url = app_settings.stored_grobid_url()
    return GrobidStatusResponse(configured=bool(url), url=url)


@router.get("/grobid/status", response_model=GrobidStatusResponse)
def grobid_status() -> GrobidStatusResponse:
    return _status()


@router.post("/grobid/settings", response_model=GrobidStatusResponse)
def set_grobid_settings(body: GrobidSettingsRequest) -> GrobidStatusResponse:
    app_settings.set_grobid_url(body.url)
    return _status()


# --- test connection (no egress gate -- a bare liveness ping carries zero library content) -----------------


class GrobidTestConnectionResult(BaseModel):
    ok: bool
    detail: str


@router.post("/grobid/test-connection", response_model=GrobidTestConnectionResult)
def test_connection() -> GrobidTestConnectionResult:
    """Ping GROBID's own ``/api/isalive`` liveness check (any 2xx = alive) against the STORED url — mirrors
    ``/settings/test-key``'s zero-argument, always-200 shape. No egress gate: the ping sends no PDF/library
    content, so consent (which exists to protect library TEXT, invariant #3) doesn't apply to it."""
    url = app_settings.stored_grobid_url()
    if not url:
        return GrobidTestConnectionResult(ok=False, detail="No GROBID URL is set.")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{url.rstrip('/')}/api/isalive")
    except httpx.HTTPError as exc:
        return GrobidTestConnectionResult(ok=False, detail=f"Could not reach GROBID: {exc}")
    if 200 <= resp.status_code < 300:
        return GrobidTestConnectionResult(ok=True, detail="GROBID is reachable.")
    return GrobidTestConnectionResult(ok=False, detail=f"GROBID returned HTTP {resp.status_code}.")


# --- shared egress gate for the two parse endpoints ----------------------------------------------------------


@dataclass(frozen=True)
class _GrobidEgressProbe:
    """Minimal duck-typed config so ``requires_egress`` can ask its ENDPOINT-based question (inc 256) about the
    GROBID url specifically -- NOT the active LLM provider. ``provider`` must be a non-empty, non-"gemini" name:
    ``requires_egress``/``_wire_of`` fall back to "gemini" (always-egress) for a falsy provider, which would
    wrongly gate a loopback GROBID url -- this mirrors ``llm/egress.py``'s own ``_EgressProbe`` shape."""

    provider: str = "grobid"
    wire_format: str | None = None
    base_url: str | None = None


def _egress_refused(base_url: str) -> bool:
    """True iff ``base_url`` is non-loopback and the user hasn't consented to data egress -- the identical gate
    a non-loopback custom LLM provider endpoint gets (invariant #3), applied to GROBID's own configured url."""
    if not requires_egress(_GrobidEgressProbe(base_url=base_url)):
        return False
    return not GeminiConfig.from_environment().data_egress_enabled


# --- per-paper parse -----------------------------------------------------------------------------------------


class GrobidParseResult(BaseModel):
    sections_found: int
    chunks_mapped: int


class GrobidParseResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: GrobidParseResult | None = None


@router.post(
    "/grobid/papers/{paper_id}/parse", response_model=GrobidParseResponse, status_code=http_status.HTTP_202_ACCEPTED
)
def parse_paper(
    paper_id: int, background_tasks: BackgroundTasks, request: Request, conn: Connection = Depends(get_connection)
) -> GrobidParseResponse:
    base_url = app_settings.stored_grobid_url()
    if not base_url:
        raise HTTPException(status_code=409, detail=_UNCONFIGURED_DETAIL)
    if _egress_refused(base_url):
        raise HTTPException(status_code=403, detail=_EGRESS_REFUSED_DETAIL)
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    pdf_path = _local_attachment_path(_select_primary_pdf_attachment(get_attachments_for_paper(conn, paper_id)))
    if pdf_path is None:
        raise HTTPException(status_code=422, detail="This paper has no local PDF to parse.")
    job_id = request.app.state.grobid_parse_jobs.create(nav={"paper_id": paper_id})
    background_tasks.add_task(_run_grobid_parse_job, request.app, job_id, paper_id, base_url)
    return GrobidParseResponse(job_id=job_id, status="pending")


@router.get("/grobid/papers/{paper_id}/parse/{job_id}", response_model=GrobidParseResponse)
def parse_paper_status(paper_id: int, job_id: str, request: Request) -> GrobidParseResponse:
    job = request.app.state.grobid_parse_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Parse job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return GrobidParseResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_grobid_parse_job(app: FastAPI, job_id: str, paper_id: int, base_url: str) -> None:
    jobs: JobStore[GrobidParseResponse] = app.state.grobid_parse_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        with engine.connect() as conn:
            attachment = _select_primary_pdf_attachment(get_attachments_for_paper(conn, paper_id))
            pdf_path = _local_attachment_path(attachment)
        if pdf_path is None:
            jobs.mark_error(job_id, "This paper has no local PDF to parse.")
            return
        pdf_bytes = pdf_path.read_bytes()
        attachment_id = attachment["id"]
        result = run_write(
            engine, lambda conn: parse_paper_structure(conn, paper_id, attachment_id, pdf_bytes, base_url)
        )
        jobs.mark_done(
            job_id,
            GrobidParseResponse(job_id=job_id, status="done", result=GrobidParseResult(**result)),
            nav={"paper_id": paper_id},
        )
    except (GrobidError, GrobidParseError) as exc:
        jobs.mark_error(job_id, str(exc))
    except Exception as exc:  # noqa: BLE001 -- any other failure becomes a graceful job error, never a crash
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


# --- bulk (library-wide) parse ---------------------------------------------------------------------------------


class GrobidBulkParseSummary(BaseModel):
    papers: int = 0  # live papers considered
    papers_parsed: int = 0
    papers_skipped: int = 0  # no local PDF, or that paper's parse failed (on_item_error="skip")
    sections_found: int = 0
    chunks_mapped: int = 0


class GrobidBulkParseResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: GrobidBulkParseSummary | None = None
    progress: JobProgressOut | None = None


class GrobidLibraryParseRequest(BaseModel):
    # Both scoping options are mutually exclusive conveniences over the same "which live papers" question;
    # paper_ids wins if both are somehow set (the Library-view bulk-select action always sends only paper_ids).
    paper_ids: list[int] | None = None
    only_unparsed: bool = False


@router.post("/grobid/library/parse", response_model=GrobidBulkParseResponse, status_code=http_status.HTTP_202_ACCEPTED)
def parse_library(
    background_tasks: BackgroundTasks, request: Request, body: GrobidLibraryParseRequest | None = None
) -> GrobidBulkParseResponse:
    base_url = app_settings.stored_grobid_url()
    if not base_url:
        raise HTTPException(status_code=409, detail=_UNCONFIGURED_DETAIL)
    if _egress_refused(base_url):
        raise HTTPException(status_code=403, detail=_EGRESS_REFUSED_DETAIL)
    scope = body or GrobidLibraryParseRequest()
    job_id = request.app.state.grobid_parse_jobs.create()
    background_tasks.add_task(
        _run_grobid_bulk_parse_job, request.app, job_id, base_url, scope.paper_ids, scope.only_unparsed
    )
    return GrobidBulkParseResponse(job_id=job_id, status="pending")


@router.get("/grobid/library/parse/{job_id}", response_model=GrobidBulkParseResponse)
def parse_library_status(job_id: str, request: Request) -> GrobidBulkParseResponse:
    job = request.app.state.grobid_parse_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Parse job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return GrobidBulkParseResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _bulk_parse_one(conn: Connection, paper_id: int, base_url: str) -> dict | None:
    """One paper's worth of work inside a single ``run_write`` unit -- None means "skipped, no local PDF"
    (not an error); a real parse failure propagates so the caller's ``on_item_error="skip"`` handling logs +
    skips it, mirroring ``library_enrich.py``'s exact per-item shape."""
    attachment = _select_primary_pdf_attachment(get_attachments_for_paper(conn, paper_id))
    pdf_path = _local_attachment_path(attachment)
    if pdf_path is None:
        return None
    pdf_bytes = pdf_path.read_bytes()
    return parse_paper_structure(conn, paper_id, attachment["id"], pdf_bytes, base_url)


def _papers_with_local_pdf(conn: Connection, candidate_ids: list[int]) -> list[int]:
    """Filter to only papers with a locally-resolvable primary PDF attachment. GROBID has nothing to do for a
    metadata-only paper -- excluding these upfront (rather than counting them as "considered" and letting
    _bulk_parse_one silently no-op on each) keeps papers_skipped meaning a real failure, not "no PDF", and
    keeps only_unparsed from perpetually re-counting papers that can never be parsed."""
    return [
        pid
        for pid in candidate_ids
        if _local_attachment_path(_select_primary_pdf_attachment(get_attachments_for_paper(conn, pid))) is not None
    ]


def _run_grobid_bulk_parse_job(
    app: FastAPI, job_id: str, base_url: str, paper_ids: list[int] | None = None, only_unparsed: bool = False
) -> None:
    jobs: JobStore[GrobidBulkParseResponse] = app.state.grobid_parse_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        with engine.connect() as conn:
            live_ids = set(list_live_paper_ids(conn))
            if paper_ids:
                ids = [pid for pid in paper_ids if pid in live_ids]
            elif only_unparsed:
                already_parsed = paper_ids_with_sections(conn)
                ids = [pid for pid in live_ids if pid not in already_parsed]
            else:
                ids = list(live_ids)
            ids = _papers_with_local_pdf(conn, ids)
        total = len(ids)
        parsed = skipped = sections_found = chunks_mapped = 0
        completed = 0
        # ThreadPoolExecutor-based concurrent batch (inc 418 precedent, library_enrich.py's exact shape): each
        # paper's parse+write runs in its own run_write unit so the SQLite write lock is released between papers;
        # one paper's hard failure is skipped (on_item_error="skip"), never aborting the whole library batch.
        with ThreadPoolExecutor(max_workers=GROBID_PARSE_WORKERS) as pool:
            futures = {
                pool.submit(
                    run_write, engine, lambda conn, pid=paper_id: _bulk_parse_one(conn, pid, base_url)
                ): paper_id
                for paper_id in ids
            }
            for future in as_completed(futures):
                completed += 1
                paper_id = futures[future]
                try:
                    result = future.result()
                    if result is None:
                        skipped += 1
                    else:
                        parsed += 1
                        sections_found += result["sections_found"]
                        chunks_mapped += result["chunks_mapped"]
                except Exception as exc:  # noqa: BLE001 -- batch resilience is the contract
                    skipped += 1
                    _log.warning("grobid bulk parse: skipped paper %s: %s", paper_id, exc)
                jobs.mark_progress(job_id, completed, total, "Parsing document structure")
        jobs.mark_done(
            job_id,
            GrobidBulkParseResponse(
                job_id=job_id,
                status="done",
                summary=GrobidBulkParseSummary(
                    papers=total,
                    papers_parsed=parsed,
                    papers_skipped=skipped,
                    sections_found=sections_found,
                    chunks_mapped=chunks_mapped,
                ),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
