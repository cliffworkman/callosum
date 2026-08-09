"""Citation concentration (inc 227, backlog #25; reworked inc 229) — the structural shape of a paper's reference list.

``POST /methods/citation-equity/run {paper_id}`` (async) resolves a library paper's OpenAlex ``referenced_works``,
fetches each reference's metadata, samples the paper's *field* (its OpenAlex primary topic), and computes 4
**descriptive** structural signals (self-citation, reliance on highly-cited work, venue + institutional
concentration) — each shown against the field with an inspectable basis. It is a *signal, never a verdict*
(Principles #2/#7), and — load-bearing — it **never categorizes the people cited** (no gender/race/nationality/
region; the earlier "Global South" geography signal was removed in inc 229, *rejected on principle*: sorting authors
into a group to measure bias reifies the category). Honest about coverage (#6). Egress is **public OpenAlex
metadata**, NOT the Gemini library-text gate; the per-reference + field fetches are cached, so re-runs are cheap.

Own router (3-segment ``/methods/citation-equity/*`` path) — the citation_counts.py precedent. The audit is
ephemeral (the job result), no table/migration: it is recomputable and the OpenAlex calls are cached.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.backend.acquisition.registry import PaperRef
from app.backend.api.job_store import JobStore
from app.backend.api.routers.papers import _authors_from_csl
from app.backend.embeddings.models import SentenceTransformerEmbeddingModel
from app.backend.methods.citation_equity import audit_reference_list
from app.backend.methods.overlooked_work import rank_overlooked
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.schema import papers
from integrations.openalex.adapter import OpenAlexClient

# SPECTER v1 scientific-paper embeddings (inc 228) — title+abstract relatedness, loadable via the existing
# sentence-transformers stack (no new dependency; a ~440 MB model download on first use). SPECTER2 (needs the
# `adapters` library) / SciNCL are documented quality upgrades — swap the name here.
OVERLOOKED_EMBED_MODEL = "sentence-transformers/allenai-specter"

# inc 457: the self-citation field baseline's sample-size target, chosen from a real empirical calibration study
# (bootstrap-resampling a 200-paper pilot across 6 fields — see tools/citation_concentration_study.py + inc-456
# notes). "Computable" coverage (a field paper having both a reference list and author ids) varies 18%-74% by
# field, so a second cap bounds worst-case cost in a low-coverage field: a low-coverage field's baseline may
# honestly rest on fewer than the target N (disclosed via the sample-size count), rather than the audit chasing
# the target across nearly the whole 200-paper field sample.
SELF_CITATION_BASELINE_TARGET_N = 40
SELF_CITATION_BASELINE_MAX_CHECKS = 100

# P2 item #18 (backlog #33/#34, inc 463): mirrors methods_retraction.py's own check-selected cap (inc 459).
MAX_EQUITY_CHECK_SELECTED = 100

router = APIRouter(tags=["citation-equity"])


class SignalModel(BaseModel):
    key: str
    label: str
    summary: str
    list_pct: float | None = None
    field_pct: float | None = None
    basis: list[str] = []
    coverage: str = ""
    coverage_fraction: float | None = None  # the share the number is actually computed over (honest #6)
    low_coverage: bool = False  # True when computed over <50% of references → shown but flagged low-confidence (#4)


class EquityReportModel(BaseModel):
    references_total: int
    references_resolved: int
    field_topic: dict | None = None
    field_sample_size: int = 0
    signals: list[SignalModel] = []


class EquityProgress(BaseModel):
    current: int
    total: int
    label: str
    eta_seconds: int | None = None


class CitationEquityResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: EquityReportModel | None = None
    progress: EquityProgress | None = None


class CitationEquityRequest(BaseModel):
    paper_id: int


def _family(name: str) -> str:
    parts = str(name).strip().split()
    return parts[-1].lower() if parts else ""


@router.post(
    "/methods/citation-equity/run",
    response_model=CitationEquityResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def citation_equity_run(
    body: CitationEquityRequest, background_tasks: BackgroundTasks, request: Request
) -> CitationEquityResponse:
    # Validate synchronously so the client gets a clean 404/422 without polling: the audit needs the paper's DOI
    # to resolve its OpenAlex references.
    with request.app.state.engine.begin() as conn:
        row = conn.execute(select(papers.c.id, papers.c.doi).where(papers.c.id == body.paper_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not row["doi"]:
        raise HTTPException(status_code=422, detail="This paper has no DOI, so OpenAlex can't resolve its references.")
    job_id = request.app.state.citation_equity_jobs.create(nav={"paper_id": body.paper_id})
    background_tasks.add_task(_run_citation_equity_job, request.app, job_id, body.paper_id)
    return CitationEquityResponse(job_id=job_id, status="pending")


@router.get("/methods/citation-equity/run/{job_id}", response_model=CitationEquityResponse)
def citation_equity_status(job_id: str, request: Request) -> CitationEquityResponse:
    job = request.app.state.citation_equity_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Citation-equity job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = (
        EquityProgress(
            current=job.progress.current,
            total=job.progress.total,
            label=job.progress.label,
            eta_seconds=job.eta_seconds(),
        )
        if job.progress is not None
        else None
    )
    return CitationEquityResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


class EquityCheckSelectedRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1, max_length=MAX_EQUITY_CHECK_SELECTED)


@router.post("/methods/citation-equity/check-selected", response_model=EquityReportModel)
def citation_equity_check_selected(payload: EquityCheckSelectedRequest, request: Request) -> EquityReportModel:
    """Citation-concentration signals for exactly a caller-named list of papers (P2 item #18, backlog #33/#34,
    inc 463) — the LibreOffice adapter's "Citation coverage audit…" command's backend, scoped to whichever
    papers are actually cited in the open manuscript right now, not a WIP manuscript's `wip_references` list or
    a Library paper's own OpenAlex reference graph. Synchronous (no `JobStore`): bounded to the document's own
    distinct cited papers, typically far fewer than the full reference-graph traversal + self-citation
    field-baseline check the Library-paper/WIP versions run as background jobs.

    Reuses `audit_reference_list` completely unmodified with the exact honest-degraded path
    `wip_citation_equity.py` already established: no stored author identity for a live Writer document (no
    fabricated author-identity proxy), and no field-topic comparison (the document has no OpenAlex record of
    its own to draw one from).
    """
    client = request.app.state.openalex_client or OpenAlexClient()
    refs: list[dict] = []
    with request.app.state.engine.begin() as conn:
        for paper_id in payload.paper_ids:
            row = (
                conn.execute(select(papers.c.doi, papers.c.title).where(papers.c.id == paper_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                continue  # a paper id no longer in the library -- skipped, not fatal (every other per-ref skip)
            ref = PaperRef(doi=row["doi"]) if row["doi"] else PaperRef(title=row["title"])
            meta = client.fetch_work_meta_for(conn, ref)
            if meta:
                refs.append(meta)
    report = audit_reference_list(
        refs=refs,
        focal_author_families=set(),
        field=[],
        field_topic=None,
        references_total=len(payload.paper_ids),
    )
    return EquityReportModel(**report.to_dict())


def _compute_self_citation_baseline(
    conn, client: OpenAlexClient, field: list[dict], *, jobs: JobStore, job_id: str
) -> tuple[float | None, int]:
    """inc 457: the field average of each field-sample paper's OWN self-citation rate (its own references
    authored by any of its own authors, matched by real OpenAlex author id — cheaper + more precise than the
    focal paper's name-overlap heuristic, and free of an extra metadata fetch since `field` already carries each
    paper's `referenced_works`/`author_ids`). Stops once `SELF_CITATION_BASELINE_TARGET_N` rates are collected,
    or once `SELF_CITATION_BASELINE_MAX_CHECKS` raw field papers have been checked, whichever comes first (see
    the module-level constants' docstring for why the second cap exists). Returns `(None, 0)` if nothing was
    computable — never a fabricated 0."""
    rates: list[float] = []
    checked = 0
    for paper in field:
        if len(rates) >= SELF_CITATION_BASELINE_TARGET_N or checked >= SELF_CITATION_BASELINE_MAX_CHECKS:
            break
        ref_ids = paper.get("referenced_works") or []
        author_ids = paper.get("author_ids") or []
        if not ref_ids or not author_ids:
            continue  # not computable for this field paper -- skipped, not fabricated as 0
        checked += 1
        hits = client.fetch_self_citation_hit_count(conn, ref_ids=ref_ids, author_ids=author_ids)
        if hits is not None:
            rates.append(hits / len(ref_ids))
        jobs.mark_progress(job_id, checked, SELF_CITATION_BASELINE_MAX_CHECKS, "Computing field self-citation baseline")
    if not rates:
        return None, 0
    return sum(rates) / len(rates), len(rates)


def _run_citation_equity_job(app: FastAPI, job_id: str, paper_id: int) -> None:
    jobs: JobStore[CitationEquityResponse] = app.state.citation_equity_jobs
    jobs.mark_running(job_id)
    client = app.state.openalex_client or OpenAlexClient()
    try:
        with app.state.engine.begin() as conn:
            row = (
                conn.execute(
                    select(papers.c.doi, papers.c.csl_json, papers.c.first_author_family_name).where(
                        papers.c.id == paper_id
                    )
                )
                .mappings()
                .first()
            )
            if row is None or not row["doi"]:
                jobs.mark_error(job_id, "Paper not found or has no DOI.")
                return
            ref = PaperRef(doi=row["doi"])
            families = {
                _family(a) for a in _authors_from_csl(row["csl_json"], fallback=row["first_author_family_name"])
            }
            families = {f for f in families if f}
            ref_ids = client.fetch_referenced_works(conn, ref)
            total = len(ref_ids)
            # The focal paper's primary_topic = the field baseline (read from the now-cached by-DOI fetch, no extra HTTP).
            focal_meta = client.fetch_work_meta_for(conn, ref)
            field_topic = (focal_meta or {}).get("primary_topic")
            refs: list[dict] = []
            for i, wid in enumerate(ref_ids):
                meta = client.fetch_work_meta(
                    conn, wid
                )  # per-ref errors are skipped (counted in coverage), never fatal
                if meta:
                    refs.append(meta)
                jobs.mark_progress(job_id, i + 1, total, "Fetching reference metadata")
            field = client.fetch_field_sample(conn, field_topic["id"]) if field_topic else []
            baseline_pct, baseline_n = _compute_self_citation_baseline(conn, client, field, jobs=jobs, job_id=job_id)
            report = audit_reference_list(
                refs=refs,
                focal_author_families=families,
                field=field,
                field_topic=field_topic,
                references_total=total,
                self_citation_field_baseline=baseline_pct,
                self_citation_field_baseline_n=baseline_n,
            )
        jobs.mark_done(
            job_id,
            CitationEquityResponse(job_id=job_id, status="done", report=EquityReportModel(**report.to_dict())),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


# --- SP2 (inc 228): the topical overlooked-work remediation -------------------------------------------------------


class OverlookedCandidateModel(BaseModel):
    openalex_work_id: str | None = None
    doi: str | None = None
    title: str
    authors: list[str] = []
    year: int | None = None
    venue: str | None = None
    match: float  # the labeled local cosine to the focal paper (the "why", not a verdict)
    shared_concepts: list[str] = []
    abstract: str | None = None
    in_library: bool = False


class OverlookedReportModel(BaseModel):
    candidates: list[OverlookedCandidateModel] = []
    pool_size: int = 0  # union candidate pool (related ∪ topic) before exclusions
    considered: int = 0  # after excluding the already-cited + the focal paper
    shown: int = 0  # how many cleared the topical-relevance bar (= len(candidates))
    field_topic: dict | None = None


class OverlookedResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: OverlookedReportModel | None = None
    progress: EquityProgress | None = None


def _overlooked_model(app: FastAPI):
    """The scientific-paper embedding model (inc 228) — injected `app.state.embedding_model` wins (tests); else a
    lazily-built + cached SPECTER model (mirror discovery.py::_discovery_model)."""
    injected = app.state.embedding_model
    if injected is not None:
        return injected
    cached = getattr(app.state, "_overlooked_model", None)
    if cached is None:
        cached = SentenceTransformerEmbeddingModel(name=OVERLOOKED_EMBED_MODEL, version=OVERLOOKED_EMBED_MODEL)
        app.state._overlooked_model = cached
    return cached


@router.post(
    "/methods/citation-equity/overlooked",
    response_model=OverlookedResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def overlooked_run(
    body: CitationEquityRequest, background_tasks: BackgroundTasks, request: Request
) -> OverlookedResponse:
    with request.app.state.engine.begin() as conn:
        row = conn.execute(select(papers.c.id, papers.c.doi).where(papers.c.id == body.paper_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not row["doi"]:
        raise HTTPException(status_code=422, detail="This paper has no DOI, so OpenAlex can't resolve related work.")
    job_id = request.app.state.overlooked_jobs.create(nav={"paper_id": body.paper_id})
    background_tasks.add_task(_run_overlooked_job, request.app, job_id, body.paper_id)
    return OverlookedResponse(job_id=job_id, status="pending")


@router.get("/methods/citation-equity/overlooked/{job_id}", response_model=OverlookedResponse)
def overlooked_status(job_id: str, request: Request) -> OverlookedResponse:
    job = request.app.state.overlooked_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Overlooked-work job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = (
        EquityProgress(
            current=job.progress.current,
            total=job.progress.total,
            label=job.progress.label,
            eta_seconds=job.eta_seconds(),
        )
        if job.progress is not None
        else None
    )
    return OverlookedResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


def _run_overlooked_job(app: FastAPI, job_id: str, paper_id: int) -> None:
    jobs: JobStore[OverlookedResponse] = app.state.overlooked_jobs
    jobs.mark_running(job_id)
    client = app.state.openalex_client or OpenAlexClient()
    try:
        with app.state.engine.begin() as conn:
            row = conn.execute(select(papers.c.doi).where(papers.c.id == paper_id)).mappings().first()
            if row is None or not row["doi"]:
                jobs.mark_error(job_id, "Paper not found or has no DOI.")
                return
            ref = PaperRef(doi=row["doi"])
            jobs.mark_progress(job_id, 1, 3, "Finding related work")
            focal_csl = client.fetch_work_csl(conn, ref) or {}
            focal_text = (str(focal_csl.get("title") or "") + ". " + str(focal_csl.get("abstract") or "")).strip()
            focal_meta = client.fetch_work_meta_for(conn, ref) or {}
            focal_id = focal_meta.get("openalex_work_id")
            cited = set(client.fetch_referenced_works(conn, ref))  # exclude what's already cited
            # union candidate pool: OpenAlex related-works (tight) ∪ the topic sample (broad)
            related = client.fetch_works_by_ids(conn, focal_meta.get("related_works") or [])
            topic = focal_meta.get("primary_topic")
            field = client.fetch_topic_candidates(conn, topic["id"]) if topic else []
            jobs.mark_progress(job_id, 2, 3, "Gathering candidates")
            by_id: dict[str, dict] = {}
            for c in [*related, *field]:
                wid = c.get("openalex_work_id")
                if not wid or wid in cited or wid == focal_id:
                    continue  # skip the already-cited + the focal paper itself
                by_id.setdefault(wid, c)
            pool = list(by_id.values())
            for c in pool:  # mark "already in your library" (by W-id or DOI)
                hit = find_existing_paper_by_identity(
                    conn, openalex_work_id=c.get("openalex_work_id"), doi=c.get("doi")
                )
                c["in_library"] = hit is not None
            jobs.mark_progress(job_id, 3, 3, "Ranking by topical relevance")
            ranked = rank_overlooked(
                focal_text=focal_text,
                candidates=pool,
                focal_concepts=focal_meta.get("concepts"),
                embedding_model=_overlooked_model(app),
            )
        report = OverlookedReportModel(
            candidates=[OverlookedCandidateModel(**c.to_dict()) for c in ranked],
            pool_size=len(related) + len(field),
            considered=len(pool),
            shown=len(ranked),
            field_topic=topic,
        )
        jobs.mark_done(job_id, OverlookedResponse(job_id=job_id, status="done", report=report))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
