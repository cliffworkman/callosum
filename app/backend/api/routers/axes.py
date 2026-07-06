"""Axis endpoints: create / browse / score / correct user-defined axes (supervised).

An axis is a named organizing lens; the user writes a label + description, the system embeds
that text and scores every paper's similarity to it into three honest tiers (assigned ≥0.7 /
uncertain ≥0.5 / below-threshold, not stored). Scoring is slow (embeds + compares the whole
library) so it runs as an async job, mirroring the summarize job. Assignments are an embedding
similarity, never a categorical truth — the human can override (manually add/remove papers).
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
)
from fastapi import (
    status as http_status,
)
from pydantic import BaseModel
from sqlalchemy import Connection, Engine, update
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.api.routers.axes_models import (
    DEFAULT_AXIS_CUTOFF,
    AxisCreateRequest,
    AxisResponse,
    AxisScoreJobResponse,
    AxisScoreStartRequest,
    AxisScoreStartResponse,
    AxisSuggestJobResponse,
    AxisUpdateRequest,
    ClusterNodeResponse,
    ClusterPaperResponse,
    ManualAssignmentRequest,
    MergeAxesRequest,
    SuggestedAxisResponse,
    SuggestTermsRequest,
    SuggestTermsResponse,
)
from app.backend.clustering.axis_assignments import (
    CREATABLE_KINDS,
    CURATED_KIND,
    add_manual_assignment,
    append_member_position,
    axis_score_state,
    freeze_to_curated,
    manual_assignment_paper_ids,
    remove_assignment,
    restore_manual_assignments,
    revert_to_keyword,
    set_member_order,
)
from app.backend.clustering.axis_operations import merge_axes
from app.backend.clustering.axis_scoring import (
    AxisScoringConfig,
    create_axis,
    delete_axis,
    score_axis,
    update_axis,
)
from app.backend.clustering.axis_suggestion import apply_labels, suggest_axes
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.llm.egress import EgressGatedAxisClusterLabeler, EgressGatedAxisTermSuggester
from app.backend.persistence.profile_repo import get_profile
from app.backend.persistence.repository import (
    get_axis,
    get_cluster_nodes_for_axis,
    get_paper,
    get_papers_for_cluster_node,
    list_axes,
)
from app.backend.persistence.schema import axes
from integrations.gemini import (
    AxisClusterLabeler,
    AxisTermSuggester,
    DataEgressDisabledError,
    GeminiAxisClusterLabeler,
    GeminiAxisTermSuggester,
    GeminiConfig,
)

router = APIRouter()

# Supervised-axis scoring (inc 45): a paper is ASSIGNED to an axis at similarity >= the axis's cutoff
# ("gain"), UNCERTAIN in [AXIS_FLOOR, cutoff), and not stored below the floor (+ a never-empty fallback).
# The cutoff is user-adjustable per re-score and persisted on the axis (`axes.scoring_gain`); NULL there
# means "use DEFAULT_AXIS_CUTOFF". This absolute cutoff superseded inc-39's relative natural-break, which
# was systematically too exclusive on the smooth similarity declines real axes produce (it cut at the
# largest gap, which sits near the top). Recalibratable; eventual home = the Settings increment.
AXIS_FLOOR = 0.20
CUTOFF_MIN, CUTOFF_MAX = 0.20, 0.60


def _axis_config(cutoff: float) -> AxisScoringConfig:
    return AxisScoringConfig(assignment_mode="absolute", assignment_threshold=cutoff, uncertainty_threshold=AXIS_FLOOR)


def _clamp_cutoff(value: float | None, *, fallback: float) -> float:
    if value is None:
        return fallback
    return max(CUTOFF_MIN, min(CUTOFF_MAX, float(value)))


def _axis_cutoff(row) -> float:
    gain = row["scoring_gain"]
    return float(gain) if gain is not None else DEFAULT_AXIS_CUTOFF


SUPERVISED_AXIS_CONFIG = _axis_config(DEFAULT_AXIS_CUTOFF)  # the default; tests import this


@router.get("/axes", response_model=list[AxisResponse])
def axes_index(conn: Connection = Depends(get_connection)) -> list[AxisResponse]:
    return [_axis_response(conn, row) for row in list_axes(conn)]


@router.post("/axes", response_model=AxisResponse, status_code=http_status.HTTP_201_CREATED)
def create_axis_endpoint(request: AxisCreateRequest, conn: Connection = Depends(get_connection)) -> AxisResponse:
    label = request.label.strip()
    if not label:
        raise HTTPException(status_code=422, detail="Axis label must not be empty")
    if (
        request.kind not in CREATABLE_KINDS
    ):  # A7: only standard | curated are user-creatable (my_publications is resolver-only)
        raise HTTPException(status_code=422, detail=f"Unsupported axis kind: {request.kind}")
    description = request.description.strip() if request.description else None
    axis_id = create_axis(conn, label=label, description=description, kind=request.kind)
    conn.commit()
    return _axis_response(conn, get_axis(conn, axis_id))


@router.post("/axes/suggest-terms", response_model=SuggestTermsResponse)
def suggest_axis_terms(payload: SuggestTermsRequest, request: Request) -> SuggestTermsResponse:
    # Stateless: proposes related terms for the given axis text (the frontend curates them and folds
    # the chosen ones into the axis description, then re-scores). Egress-gated — Gemini is opt-in.
    label = payload.label.strip()
    if not label:
        raise HTTPException(status_code=422, detail="Axis label must not be empty")
    description = payload.description.strip() if payload.description else None
    try:
        terms = _axis_term_suggester(request.app).suggest(label=label, description=description)
    except DataEgressDisabledError:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI term suggestions need data egress: set CALLOSUM_ALLOW_DATA_EGRESS=1 and GOOGLE_API_KEY, then restart.",
        ) from None
    except Exception as exc:  # any Gemini/network failure → surface, never 500
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=f"Term suggestion failed: {type(exc).__name__}: {exc}",
        ) from None
    return SuggestTermsResponse(terms=terms)


@router.patch("/axes/{axis_id}", response_model=AxisResponse)
def update_axis_endpoint(
    axis_id: int,
    request: AxisUpdateRequest,
    conn: Connection = Depends(get_connection),
) -> AxisResponse:
    axis = get_axis(conn, axis_id)
    if axis is None:
        raise HTTPException(status_code=404, detail="Axis not found")
    fields = request.model_fields_set
    if not ({"label", "description", "kind"} & fields):
        raise HTTPException(status_code=422, detail="No updatable fields provided")
    kwargs: dict[str, str | None] = {}
    if "label" in fields:
        label = (request.label or "").strip()
        if not label:
            raise HTTPException(status_code=422, detail="Axis label must not be empty")
        kwargs["label"] = label
    if "description" in fields:
        kwargs["description"] = request.description.strip() if request.description else None
    if kwargs:
        update_axis(conn, axis_id, **kwargs)
    # A7 (inc 211): the keyword<->curated switch. Only standard<->curated; never to/from my_publications.
    if "kind" in fields and request.kind is not None and request.kind != axis["kind"]:
        if request.kind not in CREATABLE_KINDS:
            raise HTTPException(status_code=422, detail=f"Unsupported axis kind: {request.kind}")
        if axis["kind"] == "standard" and request.kind == CURATED_KIND:
            freeze_to_curated(
                conn, axis_id=axis_id, cutoff=_axis_cutoff(axis)
            )  # snapshot shown members → manual+ordered
        elif axis["kind"] == CURATED_KIND and request.kind == "standard":
            revert_to_keyword(conn, axis_id=axis_id)  # members kept, order cleared, axis → stale
        else:
            raise HTTPException(status_code=422, detail=f"Cannot switch axis kind {axis['kind']} → {request.kind}")
    conn.commit()
    return _axis_response(conn, get_axis(conn, axis_id))


@router.delete("/axes/{axis_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_axis_endpoint(axis_id: int, conn: Connection = Depends(get_connection)) -> Response:
    if get_axis(conn, axis_id) is None:
        raise HTTPException(status_code=404, detail="Axis not found")
    delete_axis(conn, axis_id)
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post("/axes/merge", response_model=AxisResponse)
def merge_axes_endpoint(request: MergeAxesRequest, conn: Connection = Depends(get_connection)) -> AxisResponse:
    # Local-only: union the merged axes' manual assignments into the survivor, set its composed
    # text, delete the sources. The survivor becomes stale; the frontend re-scores it.
    label = request.label.strip()
    if not label:
        raise HTTPException(status_code=422, detail="Merged axis label must not be empty")
    merge_ids = list(dict.fromkeys(request.merge_axis_ids))  # de-dupe, preserve order
    if request.keep_axis_id in merge_ids:
        raise HTTPException(status_code=422, detail="The surviving axis cannot also be in the merge list")
    if not merge_ids:
        raise HTTPException(status_code=422, detail="Provide at least one axis to merge into the survivor")
    if get_axis(conn, request.keep_axis_id) is None:
        raise HTTPException(status_code=404, detail="Surviving axis not found")
    for axis_id in merge_ids:
        if get_axis(conn, axis_id) is None:
            raise HTTPException(status_code=404, detail=f"Axis {axis_id} not found")
    description = request.description.strip() if request.description else None
    merge_axes(conn, keep_axis_id=request.keep_axis_id, merge_axis_ids=merge_ids, label=label, description=description)
    conn.commit()
    return _axis_response(conn, get_axis(conn, request.keep_axis_id))


@router.post("/axes/{axis_id}/score", response_model=AxisScoreStartResponse, status_code=http_status.HTTP_202_ACCEPTED)
def score_axis_start(
    axis_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    payload: AxisScoreStartRequest | None = None,
    conn: Connection = Depends(get_connection),
) -> AxisScoreStartResponse:
    axis = get_axis(conn, axis_id)
    if axis is None:
        raise HTTPException(status_code=404, detail="Axis not found")
    cutoff = _clamp_cutoff(payload.gain if payload else None, fallback=_axis_cutoff(axis))
    job_id = request.app.state.axis_score_jobs.create()
    background_tasks.add_task(_run_axis_score_job, request.app, job_id, axis_id, cutoff)
    return AxisScoreStartResponse(job_id=job_id, status="pending")


@router.get("/axes/score/{job_id}", response_model=AxisScoreJobResponse)
def score_axis_status(job_id: str, request: Request) -> AxisScoreJobResponse:
    job = request.app.state.axis_score_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Axis score job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return AxisScoreJobResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.post("/axes/suggest", response_model=AxisSuggestJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def suggest_axes_start(background_tasks: BackgroundTasks, request: Request) -> AxisSuggestJobResponse:
    # Async (clustering the whole library + optional Gemini labels is slow): returns a job id to poll.
    job_id = request.app.state.axis_suggest_jobs.create()
    background_tasks.add_task(_run_axis_suggest_job, request.app, job_id)
    return AxisSuggestJobResponse(job_id=job_id, status="pending")


@router.get("/axes/suggest/{job_id}", response_model=AxisSuggestJobResponse)
def suggest_axes_status(job_id: str, request: Request) -> AxisSuggestJobResponse:
    job = request.app.state.axis_suggest_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Axis suggestion job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return AxisSuggestJobResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.get("/axes/{axis_id}/clusters", response_model=list[ClusterNodeResponse])
def axis_clusters(axis_id: int, conn: Connection = Depends(get_connection)) -> list[ClusterNodeResponse]:
    axis = get_axis(conn, axis_id)
    if axis is None:
        raise HTTPException(status_code=404, detail="Axis not found")
    cutoff = _axis_cutoff(axis)
    # inc 84: surface the starred flag on the My Publications axis's papers (a no-op set for every other axis).
    is_my_pubs = (axis["kind"] if "kind" in axis else "standard") == "my_publications"
    profile = get_profile(conn) if is_my_pubs else None
    starred_ids = {int(x) for x in ((profile or {}).get("starred_paper_ids") or [])} if is_my_pubs else set()
    # inc 118 (SP2 #16): paper_id → research-domain label, so the My Publications card can group its rows by domain.
    domain_by_id: dict[int, str] = {}
    if is_my_pubs:
        for d in (profile or {}).get("research_domains") or []:
            label = d.get("label") or "Domain"
            for pid in d.get("paper_ids") or []:
                domain_by_id[int(pid)] = label
    nodes = []
    for node in get_cluster_nodes_for_axis(conn, axis_id):
        rows = get_papers_for_cluster_node(conn, int(node["id"]))
        # Recompute the tier from the stored confidences against this axis's cutoff (absolute, inc 45):
        # assigned = scored similarity >= cutoff; uncertain = the rest. No persisted tier.
        assigned_ids = {int(row["id"]) for row in rows if row["confidence"] is not None and row["confidence"] >= cutoff}
        papers = [_cluster_paper_response(paper, assigned_ids, starred_ids, domain_by_id) for paper in rows]
        nodes.append(
            ClusterNodeResponse(
                id=node["id"],
                axis_id=node["axis_id"],
                parent_id=node["parent_id"],
                label=node["label"],
                description=node["description"],
                confidence=node["confidence"],
                papers=papers,
            )
        )
    return nodes


@router.post("/axes/{axis_id}/papers", response_model=ClusterPaperResponse, status_code=http_status.HTTP_201_CREATED)
def add_axis_paper(
    axis_id: int, request: ManualAssignmentRequest, conn: Connection = Depends(get_connection)
) -> ClusterPaperResponse:
    axis = get_axis(conn, axis_id)
    if axis is None:
        raise HTTPException(status_code=404, detail="Axis not found")
    try:
        paper = get_paper(conn, request.paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    add_manual_assignment(conn, axis_id=axis_id, paper_id=request.paper_id)
    if axis["kind"] == CURATED_KIND:  # A7: a curated axis appends new members at the end of the manual order
        append_member_position(conn, axis_id=axis_id, paper_id=request.paper_id)
    conn.commit()
    return ClusterPaperResponse(
        id=int(paper["id"]), title=paper["title"], confidence=None, status="manual", manual=True
    )


@router.delete("/axes/{axis_id}/papers/{paper_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_axis_paper(axis_id: int, paper_id: int, conn: Connection = Depends(get_connection)) -> Response:
    if get_axis(conn, axis_id) is None:
        raise HTTPException(status_code=404, detail="Axis not found")
    if not remove_assignment(conn, axis_id=axis_id, paper_id=paper_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


class AxisOrderRequest(BaseModel):
    paper_ids: list[int]


@router.put("/axes/{axis_id}/order", status_code=http_status.HTTP_204_NO_CONTENT)
def set_axis_order(axis_id: int, request: AxisOrderRequest, conn: Connection = Depends(get_connection)) -> Response:
    # A7 (inc 211): set the manual member order of a CURATED axis. The SP2 drag-reorder reuses this verbatim.
    axis = get_axis(conn, axis_id)
    if axis is None:
        raise HTTPException(status_code=404, detail="Axis not found")
    if axis["kind"] != CURATED_KIND:
        raise HTTPException(status_code=422, detail="Order applies only to a curated axis")
    try:
        set_member_order(conn, axis_id=axis_id, paper_ids=request.paper_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


def _run_axis_score_job(app: FastAPI, job_id: str, axis_id: int, cutoff: float = DEFAULT_AXIS_CUTOFF) -> None:
    jobs: JobStore[AxisScoreJobResponse] = app.state.axis_score_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        engine: Engine = app.state.engine
        with engine.begin() as conn:
            manual = manual_assignment_paper_ids(conn, axis_id)
            result = score_axis(
                conn,
                axis_id=axis_id,
                model=model,
                vector_store=store,
                config=_axis_config(cutoff),
            )
            restore_manual_assignments(conn, axis_id=axis_id, paper_ids=manual)
            conn.execute(update(axes).where(axes.c.id == axis_id).values(scoring_gain=cutoff))  # remember the cutoff
        assigned = sum(1 for s in result.scores if s.status == "assigned")
        uncertain = sum(1 for s in result.scores if s.status == "uncertain")
        jobs.mark_done(
            job_id,
            AxisScoreJobResponse(
                job_id=job_id,
                status="done",
                axis_id=result.axis_id,
                cluster_node_id=result.cluster_node_id,
                assigned_count=assigned,
                uncertain_count=uncertain,
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _run_axis_suggest_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[AxisSuggestJobResponse] = app.state.axis_suggest_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        engine: Engine = app.state.engine
        with engine.begin() as conn:  # clustering is local; the conn closes before any Gemini call
            suggestions = suggest_axes(conn, model=model)
        suggestions = apply_labels(
            suggestions, labeler=_axis_cluster_labeler(app)
        )  # egress-gated polish; local fallback
        jobs.mark_done(
            job_id,
            AxisSuggestJobResponse(
                job_id=job_id,
                status="done",
                suggestions=[
                    SuggestedAxisResponse(
                        label=s.label,
                        terms=s.terms,
                        paper_ids=s.paper_ids,
                        paper_titles=s.paper_titles,
                        size=s.size,
                    )
                    for s in suggestions
                ],
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _embedding_model(app: FastAPI) -> EmbeddingModel:
    injected = app.state.embedding_model
    if injected is not None:
        return injected
    return SentenceTransformerEmbeddingModel(name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL)


def _vector_store(app: FastAPI) -> VectorStore:
    injected = app.state.vector_store
    if injected is not None:
        return injected
    return SQLiteVecVectorStore()


def _axis_term_suggester(app: FastAPI) -> AxisTermSuggester:
    config = GeminiConfig.from_environment()
    inner = app.state.axis_term_suggester
    if inner is None:
        inner = GeminiAxisTermSuggester(config=config)
    # Authoritative egress gate at the seam — covers the injected suggester AND the default (endpoint-aware: a
    # loopback provider needs no egress consent).
    return EgressGatedAxisTermSuggester(
        inner=inner,
        data_egress_enabled=config.data_egress_enabled,
        provider=config.provider,
        wire_format=config.wire_format,
        base_url=config.base_url,
    )


def _axis_cluster_labeler(app: FastAPI) -> AxisClusterLabeler:
    config = GeminiConfig.from_environment()
    inner = app.state.axis_cluster_labeler
    if inner is None:
        inner = GeminiAxisClusterLabeler(config=config)
    # Authoritative egress gate at the seam — covers the injected labeler AND the default.
    return EgressGatedAxisClusterLabeler(
        inner=inner,
        data_egress_enabled=config.data_egress_enabled,
        provider=config.provider,
        wire_format=config.wire_format,
        base_url=config.base_url,
    )


def _axis_response(conn: Connection, row) -> AxisResponse:
    state = axis_score_state(conn, int(row["id"]), cutoff=_axis_cutoff(row))
    return AxisResponse(
        id=row["id"],
        label=row["label"],
        description=row["description"],
        scored=bool(state["scored"]),
        stale=bool(state["stale"]),
        assignment_count=int(state["assignment_count"]),
        created_at=row["created_at"],
        scoring_gain=_axis_cutoff(row),
        kind=row["kind"] if "kind" in row else "standard",
        uncertain_count=int(state["uncertain_count"]),
    )


def _cluster_paper_response(
    paper, assigned_ids: set[int], starred_ids: set[int] = frozenset(), domain_by_id: dict[int, str] | None = None
) -> ClusterPaperResponse:
    confidence = paper["confidence"]
    if confidence is None:
        status = "manual"  # confidence IS NULL → a human override, not a scored assignment
    elif int(paper["id"]) in assigned_ids:
        status = "assigned"  # above the natural break in this axis's ranking
    else:
        status = "uncertain"  # scored + stored, but below the break (a candidate to confirm)
    return ClusterPaperResponse(
        id=paper["id"],
        title=paper["title"],
        confidence=confidence,
        status=status,
        manual=confidence is None,
        starred=int(paper["id"]) in starred_ids,
        domain=(domain_by_id or {}).get(int(paper["id"])),
        position=paper["position"] if "position" in paper.keys() else None,
    )
