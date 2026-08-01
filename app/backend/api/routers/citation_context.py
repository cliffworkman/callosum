"""Citation context — "how this paper is cited" (B4 SP1, inc 232; the scite analogue).

``POST /papers/citation-context/run {paper_id}`` (async) resolves a library paper's DOI, fetches the **citing
sentences** from Semantic Scholar, and classifies each one's stance **locally** with our NLI (support / contrast /
mention) — showing the real sentence + confidence, aggregated as honest **counts** (never a composite score). A
*signal, not a verdict* (Principles #2/#4/#7). Egress = the DOI → Semantic Scholar (public bibliographic metadata,
cached), **NOT** the Gemini library-text gate; the classification runs entirely locally.

Own router (3-segment ``/papers/citation-context/*`` path, registered before ``papers.router``) — the
citation_counts.py precedent.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select

from app.backend.api.job_store import JobStore
from app.backend.metadata.abstract_display import abstract_plain_text
from app.backend.methods.citation_context import classify_citation_contexts
from app.backend.persistence.schema import papers
from app.backend.summarization.verification import StanceScorer, default_stance_scorer
from integrations.semantic_scholar.adapter import SemanticScholarClient

router = APIRouter(tags=["citation-context"])


class ClassifiedCitationModel(BaseModel):
    citing_title: str | None = None
    citing_year: int | None = None
    citing_authors: list[str] = []
    citing_doi: str | None = None
    sentence: str = ""
    stance: str | None = None
    confidence: float | None = None
    is_influential: bool = False


class CitationContextReportModel(BaseModel):
    total_citations: int
    with_context: int
    classified: int
    counts: dict[str, int] = {}
    items: list[ClassifiedCitationModel] = []


class CitationContextProgress(BaseModel):
    current: int
    total: int
    label: str
    eta_seconds: int | None = None


class CitationContextResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: CitationContextReportModel | None = None
    progress: CitationContextProgress | None = None


class CitationContextRequest(BaseModel):
    paper_id: int
    # "citations" = how OTHERS cite this paper (SP1, incoming); "references" = how THIS paper cites its sources (SP2).
    direction: Literal["citations", "references"] = "citations"


def _stance_scorer(app: FastAPI) -> StanceScorer:
    """Injected ``app.state.stance_scorer`` wins (tests); else a lazily-built + cached local NLI scorer (the
    citations.py::_suggest_stance_scorer pattern)."""
    injected = getattr(app.state, "stance_scorer", None)
    if injected is not None:
        return injected
    cached = getattr(app.state, "_citation_context_scorer", None)
    if cached is None:
        cached = default_stance_scorer()
        app.state._citation_context_scorer = cached
    return cached


@router.post(
    "/papers/citation-context/run",
    response_model=CitationContextResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def citation_context_run(
    body: CitationContextRequest, background_tasks: BackgroundTasks, request: Request
) -> CitationContextResponse:
    with request.app.state.engine.begin() as conn:
        row = conn.execute(select(papers.c.id, papers.c.doi).where(papers.c.id == body.paper_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not row["doi"]:
        raise HTTPException(
            status_code=422, detail="This paper has no DOI, so Semantic Scholar can't look up its citation graph."
        )
    job_id = request.app.state.citation_context_jobs.create(nav={"paper_id": body.paper_id})
    background_tasks.add_task(_run_citation_context_job, request.app, job_id, body.paper_id, body.direction)
    return CitationContextResponse(job_id=job_id, status="pending")


@router.get("/papers/citation-context/run/{job_id}", response_model=CitationContextResponse)
def citation_context_status(job_id: str, request: Request) -> CitationContextResponse:
    job = request.app.state.citation_context_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Citation-context job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = (
        CitationContextProgress(
            current=job.progress.current,
            total=job.progress.total,
            label=job.progress.label,
            eta_seconds=job.eta_seconds(),
        )
        if job.progress is not None
        else None
    )
    return CitationContextResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


def _run_citation_context_job(app: FastAPI, job_id: str, paper_id: int, direction: str = "citations") -> None:
    jobs: JobStore[CitationContextResponse] = app.state.citation_context_jobs
    jobs.mark_running(job_id)
    client: SemanticScholarClient = app.state.semantic_scholar_client or SemanticScholarClient()
    try:
        with app.state.engine.begin() as conn:
            row = (
                conn.execute(select(papers.c.doi, papers.c.abstract, papers.c.title).where(papers.c.id == paper_id))
                .mappings()
                .first()
            )
            if row is None or not row["doi"]:
                jobs.mark_error(job_id, "Paper not found or has no DOI.")
                return
            if direction == "references":
                # SP2 (outgoing): how THIS paper cites its sources. Each cited paper carries its OWN claim (set on
                # the context), so the constant focal_claim is unused ("").
                jobs.mark_progress(job_id, 0, 1, "Fetching references from Semantic Scholar")
                contexts = client.fetch_reference_contexts(conn, row["doi"])
                focal_claim = ""
            else:
                # SP1 (incoming): how OTHERS cite this paper. Classify each citing sentence against the focal claim.
                jobs.mark_progress(job_id, 0, 1, "Fetching citations from Semantic Scholar")
                contexts = client.fetch_citation_contexts(conn, row["doi"])
                focal_claim = (abstract_plain_text(row["abstract"]) or "").strip() or (row["title"] or "")
            jobs.mark_progress(job_id, 1, 1, "Classifying citation stance")
            report = classify_citation_contexts(
                contexts=contexts, focal_claim=focal_claim, stance_scorer=_stance_scorer(app)
            )
        jobs.mark_done(
            job_id,
            CitationContextResponse(
                job_id=job_id, status="done", report=CitationContextReportModel(**report.to_dict())
            ),
        )
    except Exception as exc:  # noqa: BLE001 — any fetch/classify failure becomes a graceful job error, never a crash
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
