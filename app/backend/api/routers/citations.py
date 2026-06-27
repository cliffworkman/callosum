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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.citations.render import (
    DEFAULT_LOCALE,
    DEFAULT_STYLE,
    LOCALES,
    MAX_CLUSTERS,
    MAX_ITEMS_PER_CLUSTER,
    STYLE_IDS,
    CitationEngineUnavailable,
    list_styles,
    render_document,
    render_papers,
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


class CitationCluster(BaseModel):
    citationID: str | None = None
    items: list[dict[str, Any]] = Field(min_length=1, max_length=MAX_ITEMS_PER_CLUSTER)


class RenderDocumentRequest(BaseModel):
    citations: list[CitationCluster] = Field(max_length=MAX_CLUSTERS)
    style: str = DEFAULT_STYLE
    locale: str = DEFAULT_LOCALE


@router.get("/citations/styles")
def citation_styles() -> dict[str, Any]:
    return {
        "styles": list_styles(),
        "locales": list(LOCALES),
        "default_style": DEFAULT_STYLE,
        "default_locale": DEFAULT_LOCALE,
    }


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
    clusters = [c.model_dump() for c in payload.citations]
    try:
        return render_document(clusters, style=payload.style, locale=payload.locale)
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


class SuggestResponse(BaseModel):
    suggestions: list[SuggestionResponse]


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
    return SuggestResponse(suggestions=[_suggestion_response(item) for item in items])


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
