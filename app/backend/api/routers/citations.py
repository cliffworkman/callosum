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

from fastapi import APIRouter, Depends, HTTPException
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
from app.backend.persistence.repository import get_papers_for_export

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
