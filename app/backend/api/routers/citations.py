"""Formatted-citation endpoints (inc 106; document render inc 107) — the word-processor-integration spine.

`GET /citations/styles` lists the bundled CSL styles + locales; `POST /citations/render` turns selected papers
into formatted in-text citations + a bibliography in a chosen style (via the citeproc-js sidecar). Read-only,
local, no egress. Reuses `repository.get_papers_for_export` (live papers only) for the canonical `csl_json`.

`POST /citations/render-document` (inc 107) is the **word-processor adapter contract**: an adapter scans the
document for citation fields (each carrying its own embedded CSL-JSON), POSTs the clusters **in document order**,
and gets back the **position-aware** in-text per field (numeric renumbering, author-date disambiguation) + the
bibliography to write back. Self-contained — it renders from the passed payloads, no library lookup.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.citations.beyond_library import (
    MAX_BEYOND_RESULTS,
    BeyondLibrarySuggestion,
    ProviderStatus,
    anchors_from_suggestions,
    suggest_beyond_library,
)
from app.backend.citations.render import (
    DEFAULT_LOCALE,
    DEFAULT_STYLE,
    MAX_CLUSTERS,
    MAX_ITEMS_PER_CLUSTER,
    STYLE_IDS,
    CitationEngineUnavailable,
    render_document,
    render_papers,
)
from app.backend.citations.style_manager import (
    MAX_STYLE_QUERY,
    catalog_response,
    preview_style,
    update_style_preferences,
)
from app.backend.citations.suggest import MAX_TEXT_LEN, Suggestion, suggest_citations
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.persistence.repository import get_papers_for_export
from app.backend.summarization.verification import StanceScorer, default_stance_scorer

router = APIRouter()


class RenderCitationsRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1, max_length=5000)
    style: str = DEFAULT_STYLE
    locale: str = DEFAULT_LOCALE


class StylePreviewRequest(BaseModel):
    style: str = DEFAULT_STYLE
    locale: str = DEFAULT_LOCALE


class StylePreferencesRequest(BaseModel):
    style: str
    locale: str = DEFAULT_LOCALE
    favorite: bool | None = None
    set_default: bool = False
    mark_used: bool = False


# CSL's fixed locator-label vocabulary (CSL 1.0.2 term list — confirmed against the bundled locale XML; no
# "timestamp" or generic "other" exists). A `label` outside this set is rejected with a clean 422 rather than
# silently reaching citeproc-js, which would just render it oddly rather than erroring.
CSL_LOCATOR_LABELS = frozenset(
    {
        "book",
        "chapter",
        "column",
        "figure",
        "folio",
        "issue",
        "line",
        "note",
        "opus",
        "page",
        "paragraph",
        "part",
        "scene",
        "section",
        "sub-verbo",
        "supplement",
        "table",
        "verse",
        "volume",
    }
)


class CitationItem(BaseModel):
    """One item inside a citation cluster (inc TBD, P0 phase 3 — backlog #33/#34): the CSL-JSON bibliographic
    fields (title/author/issued/…) pass through untouched via ``extra="allow"``; the fields below are
    per-*occurrence* citeproc-cite properties (never written into the paper's own library record) — named after
    citeproc-js's own ``citationItems`` vocabulary so there is no translation layer between what the LibreOffice
    adapter's mark payload stores (P0 phase 1) and what actually reaches citeproc (P0 phase 3's
    ``citeproc_runner.js`` change). ``suppress_author``/``author_only`` use hyphenated wire aliases to match
    citeproc's own property names; a caller must use the hyphenated form (no ``populate_by_name`` — one wire
    shape, not two)."""

    model_config = ConfigDict(extra="allow")

    locator: str | None = Field(default=None, max_length=200)
    label: str | None = Field(default=None)
    prefix: str | None = Field(default=None, max_length=300)
    suffix: str | None = Field(default=None, max_length=300)
    suppress_author: bool = Field(default=False, alias="suppress-author")
    author_only: bool = Field(default=False, alias="author-only")

    @field_validator("label")
    @classmethod
    def _validate_label(cls, v: str | None) -> str | None:
        if v is not None and v not in CSL_LOCATOR_LABELS:
            raise ValueError(f"unknown locator label {v!r}; must be one of {sorted(CSL_LOCATOR_LABELS)}")
        return v


class CitationCluster(BaseModel):
    citationID: str | None = None
    items: list[CitationItem] = Field(min_length=1, max_length=MAX_ITEMS_PER_CLUSTER)
    # CSL note styles use the real note number for first/subsequent/ibid position state. Zero remains the
    # backwards-compatible in-text/default value for every existing adapter.
    noteIndex: int = Field(default=0, ge=0, le=MAX_CLUSTERS, strict=True)


class UncitedItem(BaseModel):
    """A bibliography-only entry (P1 item #11, backlog #33/#34) — a work with no in-text citation mark in the
    document (a "further reading" item). CSL-JSON fields pass through untouched via ``extra="allow"``, same as
    `CitationItem`; the only field this model itself cares about is `id`, matched against
    `bibliography_exclude_ids` and citeproc's own item registry."""

    model_config = ConfigDict(extra="allow")
    id: str


class RenderDocumentRequest(BaseModel):
    citations: list[CitationCluster] = Field(max_length=MAX_CLUSTERS)
    style: str = DEFAULT_STYLE
    locale: str = DEFAULT_LOCALE
    # P1 item #11 (backlog #33/#34): bibliography editing. Both additive/optional — existing callers unaffected.
    uncited_items: list[UncitedItem] = Field(default=[], max_length=MAX_ITEMS_PER_CLUSTER)
    bibliography_exclude_ids: list[str] = Field(default=[], max_length=MAX_CLUSTERS)


@router.get("/citations/styles")
def citation_styles(q: str = Query(default="", max_length=MAX_STYLE_QUERY)) -> dict[str, Any]:
    try:
        return catalog_response(q)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/citations/styles/preview")
def citation_style_preview(payload: StylePreviewRequest) -> dict[str, Any]:
    try:
        return preview_style(payload.style, payload.locale)
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.put("/citations/styles/preferences")
def citation_style_preferences(payload: StylePreferencesRequest) -> dict[str, Any]:
    try:
        update_style_preferences(
            payload.style,
            payload.locale,
            favorite=payload.favorite,
            set_default=payload.set_default,
            mark_used=payload.mark_used,
        )
        return catalog_response()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/citations/render")
def render_citations(payload: RenderCitationsRequest, conn: Connection = Depends(get_connection)) -> dict[str, Any]:
    if payload.style not in STYLE_IDS:
        raise HTTPException(status_code=422, detail="Unknown citation style")
    rows = get_papers_for_export(conn, payload.paper_ids)
    if not rows:
        raise HTTPException(status_code=422, detail="No existing (non-trashed) papers to render")
    try:
        return render_papers(rows, style=payload.style, locale=payload.locale)
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/citations/render-document")
def render_citation_document(payload: RenderDocumentRequest) -> dict[str, Any]:
    if payload.style not in STYLE_IDS:
        raise HTTPException(status_code=422, detail="Unknown citation style")
    # by_alias=True: CitationItem's suppress_author/author_only dump as the hyphenated citeproc-cite property
    # names (P0 phase 3) — the wire shape render_document()/citeproc_runner.js expect, not the Python attribute.
    clusters = [c.model_dump(by_alias=True) for c in payload.citations]
    uncited = [u.model_dump() for u in payload.uncited_items]
    try:
        return render_document(
            clusters,
            style=payload.style,
            locale=payload.locale,
            uncited_items=uncited,
            bibliography_exclude_ids=payload.bibliography_exclude_ids,
        )
    except CitationEngineUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── Highlight-to-suggest / evaluate (inc 156) — the cite-while-you-write adapter contract ─────────────────────
# Given a draft sentence, suggest library papers to cite + (optionally) evaluate each candidate's stance. Fully
# local (local embeddings + local NLI), NO egress. Evidence is region precision; the author picks (no auto-insert).


class SuggestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LEN)
    top_k: int = Field(default=5, ge=1, le=20)
    evaluate: bool = True
    include_beyond_library: bool = False
    beyond_top_k: int = Field(default=5, ge=1, le=MAX_BEYOND_RESULTS)


class StanceResponse(BaseModel):
    label: str  # "support" | "contrast" | "mention"
    confidence: float
    probs: dict[str, float]


class SuggestionResponse(BaseModel):
    paper_id: int
    title: str | None = None
    year: int | None = None
    author: str | None = None
    match_score: float
    chunk_id: int
    quote: str
    page_start: int | None = None
    page_end: int | None = None
    coordinate_precision: str
    bbox_json: Any | None = None
    stance: StanceResponse | None = None


class BeyondSuggestionResponse(BaseModel):
    dedup_key: str
    title: str
    sources: list[str] = []
    doi: str | None = None
    abstract: str | None = None
    authors: list[str] = []
    journal: str | None = None
    year: int | None = None
    url: str | None = None
    in_library: bool = False
    reason: str
    reason_kind: str
    evidence_text: str
    evidence_kind: str
    metadata_overlap: float
    relationship_kind: str | None = None
    relationship_label: str | None = None
    anchor_paper_id: int | None = None
    anchor_title: str | None = None
    stance: StanceResponse | None = None


class SourceCoverageResponse(BaseModel):
    provider_id: str
    status: str
    result_count: int = 0
    warning: str | None = None


class SuggestResponse(BaseModel):
    suggestions: list[SuggestionResponse]
    beyond_library_suggestions: list[BeyondSuggestionResponse] = []
    source_coverage: list[SourceCoverageResponse] = []


@router.post("/citations/suggest", response_model=SuggestResponse)
def suggest_citations_endpoint(
    payload: SuggestRequest,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> SuggestResponse:
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    items = suggest_citations(
        conn,
        text=payload.text,
        model=_suggest_model(request),
        vector_store=_suggest_vector_store(request),
        top_k=payload.top_k,
        evaluate=payload.evaluate,
        stance_scorer=_suggest_stance_scorer(request),
    )
    beyond_items: list[BeyondLibrarySuggestion] = []
    coverage: list[ProviderStatus] = []
    if payload.include_beyond_library:
        beyond_items, coverage = suggest_beyond_library(
            conn,
            text=payload.text,
            registry=request.app.state.discovery_registry,
            top_k=payload.beyond_top_k,
            evaluate=payload.evaluate,
            stance_scorer=_suggest_stance_scorer(request),
            openalex_provider=getattr(request.app.state, "citation_openalex_provider", None),
            anchors=anchors_from_suggestions(conn, items),
            openalex_client=request.app.state.openalex_client,
        )
    return SuggestResponse(
        suggestions=[_suggestion_response(item) for item in items],
        beyond_library_suggestions=[_beyond_response(item) for item in beyond_items],
        source_coverage=[SourceCoverageResponse(**status.to_dict()) for status in coverage],
    )


def _suggestion_response(item: Suggestion) -> SuggestionResponse:
    stance = (
        StanceResponse(label=item.stance.label, confidence=item.stance.confidence, probs=item.stance.probs)
        if item.stance is not None
        else None
    )
    return SuggestionResponse(
        paper_id=item.paper_id,
        title=item.title,
        year=item.year,
        author=item.author,
        match_score=item.match_score,
        chunk_id=item.chunk_id,
        quote=item.quote,
        page_start=item.page_start,
        page_end=item.page_end,
        coordinate_precision=item.coordinate_precision,
        bbox_json=item.bbox_json,
        stance=stance,
    )


def _beyond_response(item: BeyondLibrarySuggestion) -> BeyondSuggestionResponse:
    data = item.to_dict()
    stance = data.pop("stance", None)
    if stance is not None:
        data["stance"] = StanceResponse(**stance)
    return BeyondSuggestionResponse(**data)


# The embedding + NLI models are heavy to load, so cache the defaults on app.state (a synchronous endpoint must
# not reload them per request). An injected model/store/scorer (tests) always wins. The embedding model mirrors
# summaries.py exactly so it matches the model the library was embedded with.
def _suggest_model(request: Request) -> EmbeddingModel:
    injected = request.app.state.embedding_model
    if injected is not None:
        return injected
    cached = getattr(request.app.state, "_suggest_model", None)
    if cached is None:
        cached = SentenceTransformerEmbeddingModel(name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL)
        request.app.state._suggest_model = cached
    return cached


def _suggest_vector_store(request: Request) -> VectorStore:
    injected = request.app.state.vector_store
    return injected if injected is not None else SQLiteVecVectorStore()


def _suggest_stance_scorer(request: Request) -> StanceScorer:
    injected = getattr(request.app.state, "stance_scorer", None)
    if injected is not None:
        return injected
    cached = getattr(request.app.state, "_suggest_stance_scorer", None)
    if cached is None:
        cached = default_stance_scorer()
        request.app.state._suggest_stance_scorer = cached
    return cached
