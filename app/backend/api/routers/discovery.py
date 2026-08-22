"""Literature discovery endpoints (backlog #28, inc 183) — the Search tab's backend.

`GET /discovery/search?q=` fans out to the SourceProvider registry, dedups across sources, marks `in_library`, and
returns the **complete** list (no filtering — relevance highlight is SP1b). `POST /discovery/save` creates a
metadata-only library paper (deduped; no PDF fetch). Public-metadata search (Crossref now) — NOT the egress gate.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app.backend.api.dependencies import get_connection, get_engine, resolve_embedding_model
from app.backend.discovery.relevance import score_axis_relevance
from app.backend.discovery.search import run_search, save_item
from app.backend.embeddings.models import EmbeddingModel
from app.backend.metadata import enrich_paper_metadata_multi
from app.backend.metadata.enrich_sources import build_default_enrich_registry
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()


def _enrich_saved_paper_bg(app: FastAPI, paper_id: int) -> None:
    """Background: run the multi-pass enrich on a just-saved discovery paper (inc 307) so it arrives with the same
    keyword tags (OpenAlex topics + PubMed MeSH + Crossref subjects) + gap-fills as any enriched paper. Rides the
    app registry (hermetic in tests: an empty `app.state.enrich_registry` fetches nothing). Fail-closed — a save is
    never blocked or failed by enrichment; this runs after the response is sent."""
    try:
        registry = app.state.enrich_registry or build_default_enrich_registry(
            crossref_client=app.state.crossref_client, openalex_client=app.state.openalex_client
        )
        run_write(app.state.engine, lambda conn: enrich_paper_metadata_multi(conn, paper_id, registry=registry))
    except Exception:  # noqa: BLE001 — background enrichment is best-effort; never surface to the caller
        pass


# The embedding model is heavy to load; cache the default on app.state (a sync endpoint must not reload it per
# request). An injected model (tests) always wins. Mirrors citations.py / summaries.py so the vectors match the
# model the library + axes were embedded with — and so the relevance "match" agrees with the axis-card confidence.
def _discovery_model(request: Request) -> EmbeddingModel:
    return resolve_embedding_model(request.app)


class RelevanceItem(BaseModel):
    dedup_key: str = Field(min_length=1, max_length=400)
    title: str = Field(default="", max_length=2000)
    abstract: str | None = Field(default=None, max_length=20000)


class RelevanceRequest(BaseModel):
    items: list[RelevanceItem] = Field(min_length=1, max_length=50)


class SaveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    doi: str | None = Field(default=None, max_length=300)
    pmid: str | None = Field(default=None, max_length=40)  # inc 307: drives PubMed MeSH on the background enrich
    abstract: str | None = Field(default=None, max_length=20000)
    authors: list[str] = Field(default_factory=list, max_length=500)
    journal: str | None = Field(default=None, max_length=600)
    year: int | None = Field(default=None, ge=1000, le=2100)
    url: str | None = Field(default=None, max_length=2000)


@router.get("/discovery/search")
def discovery_search(
    request: Request,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=25, ge=1, le=50),
    source: str | None = Query(default=None, min_length=1, max_length=50),
    conn: Connection = Depends(get_connection),
) -> dict[str, Any]:
    registry = request.app.state.discovery_registry
    source_name = (source or "").strip().lower() or None
    if source_name and source_name not in registry.kinds:
        raise HTTPException(status_code=422, detail=f"Unknown discovery source: {source_name}")
    items = run_search(conn, registry, q.strip(), limit, source=source_name)
    return {"items": [item.to_dict() for item in items]}


@router.get("/discovery/sources")
def discovery_sources(request: Request) -> dict[str, Any]:
    registry = request.app.state.discovery_registry
    return {"sources": registry.source_meta}


@router.post("/discovery/relevance")
def discovery_relevance(
    payload: RelevanceRequest,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> dict[str, Any]:
    """SP1b: HIGHLIGHT likely axis matches WITHIN the complete list (never filter/reorder). Returns the
    best-matching axis + similarity per item that clears that axis's cutoff; below-cutoff items are simply absent
    (no badge ≠ "irrelevant"). Local — embeddings over the user's own axes; no egress."""
    items = [{"dedup_key": it.dedup_key, "text": f"{it.title} {it.abstract or ''}".strip()} for it in payload.items]
    relevance = score_axis_relevance(conn, items, embedding_model=_discovery_model(request))
    return {"relevance": relevance}


@router.post("/discovery/save")
def discovery_save(
    payload: SaveRequest, request: Request, background: BackgroundTasks, engine: Engine = Depends(get_engine)
) -> dict[str, Any]:
    def _do(conn: Connection) -> dict[str, Any]:
        return save_item(
            conn,
            title=payload.title.strip(),
            doi=payload.doi,
            pmid=payload.pmid,
            abstract=payload.abstract,
            authors=payload.authors,
            journal=payload.journal,
            year=payload.year,
            url=payload.url,
        )

    result = run_write(engine, _do)
    # inc 307: a newly-saved paper skips the enrich cascade (bare create), so enrich it in the background — it
    # arrives with the same keyword tags as any enriched paper. The save response returns immediately.
    if result.get("created") and (payload.doi or payload.pmid):
        background.add_task(_enrich_saved_paper_bg, request.app, int(result["paper_id"]))
    return result
