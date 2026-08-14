"""Highlight-to-suggest / evaluate (inc 156, Track C SP1a) — the cite-while-you-write adapter contract.

Given a draft sentence, suggest library papers to cite + (optionally) evaluate each candidate's stance. Fully
local (local embeddings + local NLI), NO egress. Evidence is region precision; the author picks (no auto-insert).

Split out as its own sibling router (the inc-226/262/461 precedent — `paper_enrich.py`, `methods_retraction.py`,
`citation_stance.py`) because `citations.py` (home of the formatted-citation engine) crossed the 600-line cap
(rule #1) once inc 479's `current_heading`/`section_family`/`search_phase` fields (backlog #30 section-scoping)
landed on top of it. Mechanical extraction only — no behavior change; shares `request.app.state` exactly as the
endpoint did in `citations.py`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.citations.beyond_library import (
    MAX_BEYOND_RESULTS,
    BeyondLibrarySuggestion,
    ProviderStatus,
    anchors_from_suggestions,
    suggest_beyond_library,
)
from app.backend.citations.suggest import MAX_TEXT_LEN, Suggestion, suggest_citations
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.summarization.verification import StanceScorer, default_stance_scorer

router = APIRouter(tags=["citations"])


class SuggestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LEN)
    top_k: int = Field(default=5, ge=1, le=20)
    evaluate: bool = True
    include_beyond_library: bool = False
    beyond_top_k: int = Field(default=5, ge=1, le=MAX_BEYOND_RESULTS)
    current_heading: str | None = Field(default=None, max_length=300)


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
    attachment_id: int | None = None
    stance: StanceResponse | None = None
    section_family: str | None = None
    search_phase: str | None = None


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
        current_heading=payload.current_heading,
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
            semantic_scholar_client=request.app.state.semantic_scholar_client,
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
        attachment_id=item.attachment_id,
        stance=stance,
        section_family=item.section_family,
        search_phase=item.search_phase,
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
