"""Per-paper metadata-enrichment actions — re-resolve (force re-fetch) + fill-metadata (gap-fill).

Split from `papers.py` (inc 226) to keep it under the 600-line cap and to house the per-identifier re-resolve
`source` branch. The routes keep their exact paths (`/papers/{id}/re-resolve`, `/papers/{id}/fill-metadata`), so
the QA surface is unchanged. Included in `app.py` before `papers.router`. Re-uses `_detail_for` + the response
models from `papers.py` (no cycle — papers.py never imports this module).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.routers.paper_models import PaperDetailResponse
from app.backend.api.routers.papers import _detail_for
from app.backend.metadata import (
    enrich_paper_metadata_from_crossref,
    enrich_paper_metadata_from_identifier,
    enrich_paper_metadata_multi,
)
from app.backend.metadata.enrich_sources import build_default_enrich_registry
from app.backend.methods.retraction import auto_check_retractions
from app.backend.persistence.repository import get_paper
from integrations.crossref import CrossrefClient

router = APIRouter()


def _crossref(app: FastAPI) -> CrossrefClient:
    injected = app.state.crossref_client
    if injected is not None:
        return injected
    return CrossrefClient()


class ReResolveRequest(BaseModel):
    # Which identifier's source to force-re-fetch the record from (inc 226). Default keeps the original DOI 🔎.
    source: Literal["crossref", "pmid", "arxiv"] = "crossref"


@router.post("/papers/{paper_id}/re-resolve", response_model=PaperDetailResponse)
def reresolve_paper(
    paper_id: int,
    request: Request,
    payload: ReResolveRequest | None = None,
    conn: Connection = Depends(get_connection),
) -> PaperDetailResponse:
    # Force-re-fetch this paper's full bibliographic record from a chosen identifier's source: crossref (DOI →
    # Crossref), pmid (PubMed via OpenAlex), or arxiv (the arXiv DOI via OpenAlex). Forces past the user-edited
    # guard because the user explicitly asked. Only the identifier leaves the machine (public metadata, like
    # import) — NOT the Gemini library-text egress gate. A miss leaves the record unchanged — never a 500.
    source = payload.source if payload else "crossref"
    try:
        paper = get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    if source == "crossref":
        if not (paper["doi"] or "").strip():
            raise HTTPException(status_code=422, detail="Set a DOI before re-resolving from Crossref")
        enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=_crossref(request.app), force=True)
    else:
        csl = paper["csl_json"] or {}
        ident = str((csl.get("PMID") if source == "pmid" else csl.get("arxiv")) or "").strip()
        if not ident:
            label = "PMID" if source == "pmid" else "arXiv ID"
            raise HTTPException(status_code=422, detail=f"Set a {label} before re-fetching from that source")
        enrich_paper_metadata_from_identifier(
            conn, paper_id, source=source, openalex_client=request.app.state.openalex_client, force=True
        )
    # inc 224: a (re-)resolved identifier can newly reveal a retraction — auto-check now (inc-134 hook; best-effort).
    auto_check_retractions(conn, [paper_id], checkers=request.app.state.retraction_checkers)
    conn.commit()
    return _detail_for(conn, paper_id)


class FillMetadataResponse(BaseModel):
    filled_fields: list[str]
    doi: str | None
    still_missing_doi: bool
    paper: PaperDetailResponse


@router.post("/papers/{paper_id}/fill-metadata", response_model=FillMetadataResponse)
def fill_metadata(paper_id: int, request: Request, conn: Connection = Depends(get_connection)) -> FillMetadataResponse:
    # Multi-pass GAP-FILL of ONE paper (inc 217): recover a missing DOI (PDF scan → Crossref title-search) then
    # fill ONLY empty fields from the source cascade — never overwrites a value you typed (distinct from the
    # force-overwrite /re-resolve). Public bibliographic-metadata egress, NOT the Gemini library-text gate.
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    registry = request.app.state.enrich_registry or build_default_enrich_registry(
        crossref_client=request.app.state.crossref_client, openalex_client=request.app.state.openalex_client
    )
    try:
        result = enrich_paper_metadata_multi(
            conn,
            paper_id,
            registry=registry,
            search_provider=getattr(request.app.state, "enrich_search_provider", None),
        )
        # inc 224: gap-fill can recover a missing DOI (Pass 0) → now checkable; auto-check retraction (inc-134 hook).
        auto_check_retractions(conn, [paper_id], checkers=request.app.state.retraction_checkers)
        conn.commit()
    except IntegrityError as exc:
        conn.rollback()
        raise HTTPException(status_code=409, detail=_metadata_integrity_detail(exc)) from None
    return FillMetadataResponse(
        filled_fields=list(result.filled_fields),
        doi=result.doi,
        still_missing_doi=result.still_missing_doi,
        paper=_detail_for(conn, paper_id),
    )


def _metadata_integrity_detail(exc: IntegrityError) -> str:
    message = str(exc.orig)
    if "papers.doi" in message:
        return (
            "This database still has the legacy unique DOI constraint. Restart Callosum so migration "
            "0040_allow_duplicate_paper_dois can run, then try Fill missing fields again."
        )
    return "Metadata fill would duplicate a canonical external identifier on another paper."
