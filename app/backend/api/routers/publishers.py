"""PUBLISHERS "where to submit" — the async journal-finder endpoint (inc TBD, backlog #40).

``POST /methods/publishers/run`` takes either a library ``paper_id`` (uses its stored abstract + OpenAlex
``primary_topic``) or a pasted ``abstract`` + a ``subject`` keyword (resolved to an OpenAlex topic). It derives a
candidate journal pool **from the topic** (never the abstract), enriches per-journal facts (OpenAlex ``/sources`` +
DOAJ), embeds the abstract **locally**, and returns a uniform factual profile per journal ranked by fit — optionally
moved by an open-science ``weighting`` (0.0 = fit-only; the SP1b UI sets it via the first-use choice gate).

The abstract never leaves the machine (embedded locally). Egress is public bibliographic metadata (topic id / subject
keyword / source ids / ISSNs) — **NOT** the Gemini library-text gate. No composite score, no "predatory" label; every
candidate appears. Own router (3-segment ``/methods/publishers/*`` path — the citation_equity precedent). Ephemeral
job result; no table/migration.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.backend.acquisition.registry import PaperRef
from app.backend.api.job_store import JobStore
from app.backend.embeddings.models import SentenceTransformerEmbeddingModel
from app.backend.metadata.abstract_display import abstract_plain_text
from app.backend.methods.publishers import MAX_PROFILES, build_profiles
from app.backend.persistence.schema import papers
from integrations.doaj.journals import DoajJournalsClient
from integrations.openalex.adapter import OpenAlexClient
from integrations.openalex.sources import OpenAlexSourcesClient

# SPECTER v1 scientific-paper embeddings — abstract ↔ journal-scope relatedness, via the existing sentence-transformers
# stack (no new dependency; a ~440 MB model download on first use). Mirrors citation_equity's OVERLOOKED_EMBED_MODEL.
PUBLISHERS_EMBED_MODEL = "sentence-transformers/allenai-specter"
MAX_ABSTRACT_CHARS = 20000

router = APIRouter(tags=["publishers"])


class PublishersRequest(BaseModel):
    paper_id: int | None = None
    abstract: str | None = None
    subject: str | None = None
    weighting: float = Field(default=0.0, ge=0.0, le=1.0)
    top_k: int = Field(default=MAX_PROFILES, ge=1, le=50)


class JournalProfileModel(BaseModel):
    source_id: str
    display_name: str | None = None
    issns: list[str] = []
    homepage_url: str | None = None
    fit: float
    oa_color: str
    is_in_doaj: bool
    apc_amount: float | None = None
    apc_currency: str | None = None
    apc_waiver: bool
    license: list[str] = []
    doaj_seal: bool
    two_year_mean_citedness: float | None = None
    h_index: int | None = None
    works_count: int | None = None
    legitimacy_signals: list[str] = []
    legitimacy_absent: list[str] = []
    elevated_for: list[str] = []


class PublishersReportModel(BaseModel):
    profiles: list[JournalProfileModel] = []
    considered: int = 0
    shown: int = 0
    weighting: float = 0.0
    topic_id: str | None = None


class PublishersProgress(BaseModel):
    current: int
    total: int
    label: str
    eta_seconds: int | None = None


class PublishersResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: PublishersReportModel | None = None
    progress: PublishersProgress | None = None


@router.post("/methods/publishers/run", response_model=PublishersResponse, status_code=http_status.HTTP_202_ACCEPTED)
def publishers_run(body: PublishersRequest, background_tasks: BackgroundTasks, request: Request) -> PublishersResponse:
    # Exactly one input mode: a library paper (its stored abstract + primary_topic), or a pasted abstract + subject.
    has_paper = body.paper_id is not None
    has_pasted = bool((body.abstract or "").strip()) and bool((body.subject or "").strip())
    if has_paper and (body.abstract or body.subject):
        raise HTTPException(status_code=422, detail="Provide either a paper_id or an abstract+subject, not both.")
    if not has_paper and not has_pasted:
        raise HTTPException(status_code=422, detail="Provide a paper_id, or both an abstract and a subject.")
    if body.abstract and len(body.abstract) > MAX_ABSTRACT_CHARS:
        raise HTTPException(status_code=422, detail="Abstract is too long.")
    if has_paper:
        with request.app.state.engine.begin() as conn:
            row = conn.execute(select(papers.c.id, papers.c.doi).where(papers.c.id == body.paper_id)).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        if not row["doi"]:
            raise HTTPException(status_code=422, detail="This paper has no DOI, so OpenAlex can't resolve its topic.")
    job_id = request.app.state.publishers_jobs.create()
    background_tasks.add_task(_run_publishers_job, request.app, job_id, body)
    return PublishersResponse(job_id=job_id, status="pending")


@router.get("/methods/publishers/run/{job_id}", response_model=PublishersResponse)
def publishers_status(job_id: str, request: Request) -> PublishersResponse:
    job = request.app.state.publishers_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Publishers job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = (
        PublishersProgress(
            current=job.progress.current,
            total=job.progress.total,
            label=job.progress.label,
            eta_seconds=job.eta_seconds(),
        )
        if job.progress is not None
        else None
    )
    return PublishersResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


def _publishers_model(app: FastAPI):
    """Injected `app.state.embedding_model` wins (tests); else a lazily-built + cached SPECTER model (mirror
    citation_equity.py::_overlooked_model)."""
    injected = app.state.embedding_model
    if injected is not None:
        return injected
    cached = getattr(app.state, "_publishers_model", None)
    if cached is None:
        cached = SentenceTransformerEmbeddingModel(name=PUBLISHERS_EMBED_MODEL, version=PUBLISHERS_EMBED_MODEL)
        app.state._publishers_model = cached
    return cached


def _run_publishers_job(app: FastAPI, job_id: str, body: PublishersRequest) -> None:
    jobs: JobStore[PublishersResponse] = app.state.publishers_jobs
    jobs.mark_running(job_id)
    sources_client = app.state.openalex_sources_client or OpenAlexSourcesClient()
    doaj_client = app.state.doaj_journals_client or DoajJournalsClient()
    oa_client = app.state.openalex_client or OpenAlexClient()
    try:
        with app.state.engine.begin() as conn:
            jobs.mark_progress(job_id, 1, 3, "Resolving topic")
            topic_id, abstract = _resolve_topic_and_abstract(conn, body, sources_client, oa_client)
            if not topic_id:
                jobs.mark_error(job_id, "Couldn't resolve a research topic for this input.")
                return
            jobs.mark_progress(job_id, 2, 3, "Fetching candidate journals")
            stubs = sources_client.fetch_candidate_sources(conn, topic_id)
            source_ids = [s.source_id for s in stubs]
            details = sources_client.fetch_source_details(conn, source_ids)
            candidates = [details[sid] for sid in source_ids if sid in details]  # preserve frequency order
            doaj_by_issn = {}
            for meta in candidates:
                if not meta.is_in_doaj:
                    continue
                issn = meta.issn_l or (meta.issns[0] if meta.issns else None)
                if issn and issn not in doaj_by_issn:
                    journal = doaj_client.fetch_journal(conn, issn)
                    if journal is not None:
                        doaj_by_issn[issn] = journal
            jobs.mark_progress(job_id, 3, 3, "Ranking journals")
            report = build_profiles(
                candidates,
                doaj_by_issn,
                abstract=abstract,
                embedding_model=_publishers_model(app),
                weighting=body.weighting,
                top_k=body.top_k,
            )
        model = PublishersReportModel(
            profiles=[JournalProfileModel(**p.to_dict()) for p in report.profiles],
            considered=report.considered,
            shown=report.shown,
            weighting=report.weighting,
            topic_id=topic_id,
        )
        jobs.mark_done(job_id, PublishersResponse(job_id=job_id, status="done", report=model))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _resolve_topic_and_abstract(conn, body, sources_client, oa_client) -> tuple[str | None, str]:
    """(topic_id, abstract) for the run. Paper path: the paper's stored abstract + its OpenAlex primary_topic.
    Paste path: the pasted abstract + the subject resolved to a topic. The abstract is only ever embedded locally."""
    if body.paper_id is not None:
        row = (
            conn.execute(select(papers.c.title, papers.c.abstract, papers.c.doi).where(papers.c.id == body.paper_id))
            .mappings()
            .first()
        )
        if row is None or not row["doi"]:
            return None, ""
        meta = oa_client.fetch_work_meta_for(conn, PaperRef(doi=row["doi"])) or {}
        topic = meta.get("primary_topic") or {}
        topic_id = topic.get("id")
        title = str(row["title"] or "").strip()
        body_text = abstract_plain_text(row["abstract"]) or ""
        abstract = (title + ". " + body_text).strip(" .")
        return topic_id, abstract
    topic_id = sources_client.fetch_topic_for_subject(conn, body.subject or "")
    return topic_id, (body.abstract or "").strip()
