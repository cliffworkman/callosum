"""Papers, chunks, and library-facet endpoints (PDF file-serving lives in `paper_files.py`)."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.routers.paper_edit_input import edits_from_request
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.metadata import enrich_paper_metadata_from_crossref, enrich_paper_metadata_multi
from app.backend.metadata.abstract_display import abstract_plain_text, clean_abstract_for_display
from app.backend.metadata.citation_export import render_citations
from app.backend.metadata.enrich_sources import build_default_enrich_registry
from app.backend.metadata.paper_edits import build_paper_update
from app.backend.methods.retraction import auto_check_retractions
from app.backend.persistence.repository import (
    PRIORITY_LEVELS,
    get_attachments_for_paper,
    get_chunks_for_paper,
    get_paper,
    get_paper_counts,
    get_papers_for_export,
    list_item_types,
    list_papers,
    purge_all_trashed,
    purge_paper,
    refresh_processing_tier,
    restore_paper,
    set_paper_priority,
    set_paper_read,
    soft_delete_paper,
    update_paper_metadata,
)
from app.backend.persistence.tags_repo import get_tags_for_paper
from integrations.crossref import CrossrefClient

router = APIRouter()


class PaperListItem(BaseModel):
    id: int
    title: str
    authors: list[str]
    year: int | None = None
    venue: str | None = None
    citation_key: str | None = None
    processing_tier: str
    attachment_count: int
    chunk_count: int
    cited_by_count: int | None = None  # inc 210 (A2): verbatim OpenAlex cited-by count (None = not fetched)
    cited_by_as_of: str | None = None  # the "as of <date>" attribution (retrieved_at, ISO)
    read_at: str | None = None  # inc 220: NULL = unread; ISO timestamp = the user marked it read
    priority: str | None = None  # inc 220: user triage label (high/normal/low); NULL = unset


class AttachmentResponse(BaseModel):
    id: int
    filename: str | None = None
    storage_mode: str
    availability: str
    original_path: str | None = None
    resolved_path: str | None = None
    checksum: str | None = None
    file_size: int | None = None
    content_type: str
    import_source: str | None = None
    attachment_type: str | None = None
    role: str | None = None
    # Open-access acquisition labels (set when fetched from an OA database; null for user-imported files).
    oa_color: str | None = None  # gold / green / bronze
    oa_version: str | None = None  # vor / am / preprint
    oa_source: str | None = None  # resolver id (e.g. "openalex")
    oa_landing_page_url: str | None = None
    oa_license: str | None = None
    oa_bronze_unstable: bool = False  # bronze: free-to-read without a license, may revert to paywalled


class PaperTagRef(BaseModel):
    id: int
    name: str
    source: str | None = None  # tag provenance (user / zotero / keyword:crossref / …) — the UI styles by it
    color: str | None = None  # inc 207: optional user-chosen palette key (NULL = uncolored)


class PaperDetailResponse(BaseModel):
    id: int
    title: str
    abstract: str | None = None  # raw stored value (may be a JATS XML fragment)
    abstract_display: str | None = None  # display-only cleaned allowlisted HTML (derived, not stored)
    abstract_text: str | None = None  # display-only tag-free plain text (the editable textarea uses this)
    authors: list[str]
    year: int | None = None
    doi: str | None = None
    venue: str | None = None
    item_type: str | None = None
    language: str | None = None
    publication_date: str | None = None
    first_author_family_name: str | None = None
    imported_source: str | None = None
    openalex_work_id: str | None = None
    semantic_scholar_paper_id: str | None = None
    zotero_library_id: str | None = None
    zotero_item_key: str | None = None
    citation_key: str | None = None
    processing_tier: str
    csl_json: dict[str, Any]
    extra_urls: list[str] = []  # additional URLs beyond the primary CSL URL (inc 214)
    attachment_count: int
    chunk_count: int
    attachments: list[AttachmentResponse]
    tags: list[PaperTagRef] = []
    read_at: str | None = None  # inc 220: NULL = unread; ISO timestamp = the user marked it read
    priority: str | None = None  # inc 220: user triage label (high/normal/low); NULL = unset


class ReadStateRequest(BaseModel):
    read: bool  # inc 220: True = mark read (stamp read_at), False = mark unread (clear)


class PriorityRequest(BaseModel):
    priority: str | None = None  # inc 220: "high"/"normal"/"low" or null to clear; validated vs PRIORITY_LEVELS


class PaperUpdateRequest(BaseModel):
    # Partial edit of a paper's bibliographic record (inc 49). All fields optional; only those in
    # model_fields_set are applied. Scalar columns + the CSL record (papers.csl_json) are kept in
    # sync by build_paper_update; an explicit null/"" clears the field. `csl` is the generic "More"
    # passthrough for scalar CSL keys a DOI populated beyond the curated core.
    title: str | None = Field(default=None, max_length=2000)
    abstract: str | None = Field(default=None, max_length=100_000)
    authors: list[str] | None = Field(default=None, max_length=500)
    translators: list[str] | None = Field(default=None, max_length=500)
    year: int | None = Field(default=None, ge=0, le=3000)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    venue: str | None = Field(default=None, max_length=2000)
    volume: str | None = Field(default=None, max_length=100)
    issue: str | None = Field(default=None, max_length=100)
    page: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=100)
    url: str | None = Field(default=None, max_length=2000)
    item_type: str | None = Field(default=None, max_length=100)
    doi: str | None = Field(default=None, max_length=255)
    citation_key: str | None = Field(default=None, max_length=255)
    pmid: str | None = Field(default=None, max_length=100)
    arxiv: str | None = Field(default=None, max_length=100)
    issn: str | None = Field(default=None, max_length=100)
    isbn: str | None = Field(default=None, max_length=100)
    extra_urls: list[str] | None = Field(default=None, max_length=50)  # additional URLs beyond the primary (inc 214)
    csl: dict[str, str | None] | None = Field(default=None)


class ChunkResponse(BaseModel):
    id: int
    paper_id: int
    attachment_id: int
    text: str
    section: str | None = None
    page_start: int
    page_end: int
    char_start: int | None = None
    char_end: int | None = None
    bbox_json: Any | None = None
    bbox_coordinate_system: str
    extraction_tool: str
    extraction_version: str
    chunking_strategy: str
    chunk_version: str
    source_attachment_checksum: str


@router.get("/papers", response_model=list[PaperListItem])
def papers_index(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    search_field: str = Query(default="all"),  # search scope: all / title / author / journal (allowlisted in repo)
    deleted: bool = Query(default=False),  # true → the Trash listing (soft-deleted papers)
    axis_id: int | None = Query(default=None),  # filter the listing to the papers assigned to this axis
    axis_hide_uncertain: bool = Query(default=False),  # with axis_id: match the card's assigned-only view (A10)
    tag_id: int | None = Query(default=None),  # filter the listing to the papers carrying this tag
    item_type: str | None = Query(default=None),  # filter to a single CSL item type (bound; see list_item_types)
    needs_review: bool = Query(default=False),  # the "Unsorted" view: scaffold / Crossref-unresolved / no source
    signal: str | None = Query(
        default=None
    ),  # filter to a Methods-producer signal (allowlisted in repo), e.g. statcheck
    finding: str | None = Query(default=None),  # the "to review" queue: papers with unreviewed candidate findings
    read_status: str | None = Query(default=None),  # inc 220: "read" / "unread" filter
    priority: str | None = Query(default=None),  # inc 220: filter to a priority level (allowlisted in repo)
    sort: str = Query(default="added"),  # library ordering; unknown keys fall back to "added" (allowlisted in repo)
    conn: Connection = Depends(get_connection),
) -> list[PaperListItem]:
    rows = list_papers(
        conn,
        limit=limit,
        offset=offset,
        q=q,
        search_field=search_field,
        only_deleted=deleted,
        axis_id=axis_id,
        axis_hide_uncertain=axis_hide_uncertain,
        tag_id=tag_id,
        item_type=item_type,
        needs_review=needs_review,
        signal=signal,
        finding=finding,
        read_status=read_status,
        priority=priority,
        sort=sort,
    )
    return [_paper_list_item(row) for row in rows]


class ItemTypeCount(BaseModel):
    item_type: str
    count: int


@router.get("/papers/item-types", response_model=list[ItemTypeCount])
def papers_item_types(conn: Connection = Depends(get_connection)) -> list[ItemTypeCount]:
    """Distinct CSL item types present in the live library + counts (inc 91) — drives the Type filter so it
    only offers types that exist. Registered before /papers/{paper_id} so the literal segment wins."""
    return [ItemTypeCount(item_type=row["item_type"], count=row["count"]) for row in list_item_types(conn)]


@router.get("/papers/{paper_id}", response_model=PaperDetailResponse)
def paper_detail(paper_id: int, conn: Connection = Depends(get_connection)) -> PaperDetailResponse:
    try:
        paper = get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    attachments = get_attachments_for_paper(conn, paper_id)
    counts = get_paper_counts(conn, paper_id)
    return _paper_detail(
        paper,
        attachments=attachments,
        attachment_count=counts["attachment_count"],
        chunk_count=counts["chunk_count"],
        tags=get_tags_for_paper(conn, paper_id),
    )


@router.get("/papers/{paper_id}/chunks", response_model=list[ChunkResponse])
def paper_chunks(
    paper_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> list[ChunkResponse]:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return [_chunk_response(row) for row in get_chunks_for_paper(conn, paper_id, limit=limit, offset=offset)]


@router.patch("/papers/{paper_id}", response_model=PaperDetailResponse)
def update_paper(
    paper_id: int,
    request: PaperUpdateRequest,
    conn: Connection = Depends(get_connection),
) -> PaperDetailResponse:
    try:
        paper = get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    edits = edits_from_request(request)
    if not edits:
        raise HTTPException(status_code=422, detail="No updatable fields provided")
    try:
        update_paper_metadata(conn, paper_id, **build_paper_update(paper, edits))
        refresh_processing_tier(conn, paper_id)
        conn.commit()
    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="That DOI is already on another paper") from None
    return _detail_for(conn, paper_id)


@router.post("/papers/{paper_id}/re-resolve", response_model=PaperDetailResponse)
def reresolve_paper(
    paper_id: int,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> PaperDetailResponse:
    # Re-run Crossref enrichment against the paper's (possibly just-corrected) DOI. Forces past the
    # user-edited guard because the user explicitly asked. Only the DOI leaves the machine (public
    # Crossref, like import) — this is NOT the Gemini library-text egress gate. A network/Crossref
    # miss returns "unresolved" (graceful) — never a 500.
    try:
        paper = get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    if not (paper["doi"] or "").strip():
        raise HTTPException(status_code=422, detail="Set a DOI before re-resolving from Crossref")
    enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=_crossref(request.app), force=True)
    # inc 224: a re-resolved DOI can newly reveal a retraction — auto-check now (inc-134 hook; best-effort).
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
    result = enrich_paper_metadata_multi(
        conn,
        paper_id,
        registry=registry,
        search_provider=getattr(request.app.state, "enrich_search_provider", None),
    )
    # inc 224: gap-fill can recover a missing DOI (Pass 0) → now checkable; auto-check retraction (inc-134 hook).
    auto_check_retractions(conn, [paper_id], checkers=request.app.state.retraction_checkers)
    conn.commit()
    return FillMetadataResponse(
        filled_fields=list(result.filled_fields),
        doi=result.doi,
        still_missing_doi=result.still_missing_doi,
        paper=_detail_for(conn, paper_id),
    )


@router.delete("/papers/{paper_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_paper(paper_id: int, conn: Connection = Depends(get_connection)) -> Response:
    # Soft-delete (move to Trash): hidden from the library/axes/clustering but kept + restorable.
    if not soft_delete_paper(conn, paper_id):
        raise HTTPException(status_code=404, detail="Paper not found or already in Trash")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post("/papers/{paper_id}/restore", response_model=PaperDetailResponse)
def restore_paper_endpoint(paper_id: int, conn: Connection = Depends(get_connection)) -> PaperDetailResponse:
    if not restore_paper(conn, paper_id):
        raise HTTPException(status_code=404, detail="Paper not found in Trash")
    conn.commit()
    return _detail_for(conn, paper_id)


@router.post("/papers/{paper_id}/read", response_model=PaperDetailResponse)
def set_read_endpoint(
    paper_id: int, payload: ReadStateRequest, conn: Connection = Depends(get_connection)
) -> PaperDetailResponse:
    """Mark a paper read/unread — a manual user toggle (inc 220). 404 if the paper doesn't exist."""
    if not set_paper_read(conn, paper_id, payload.read):
        raise HTTPException(status_code=404, detail="Paper not found")
    conn.commit()
    return _detail_for(conn, paper_id)


@router.post("/papers/{paper_id}/priority", response_model=PaperDetailResponse)
def set_priority_endpoint(
    paper_id: int, payload: PriorityRequest, conn: Connection = Depends(get_connection)
) -> PaperDetailResponse:
    """Set/clear the user's reading priority (high/normal/low or null) — a hand-set triage label, never an AI
    score (inc 220). 422 off-allowlist; 404 if the paper doesn't exist."""
    if payload.priority is not None and payload.priority not in PRIORITY_LEVELS:
        raise HTTPException(status_code=422, detail=f"priority must be one of {PRIORITY_LEVELS} or null")
    if not set_paper_priority(conn, paper_id, payload.priority):
        raise HTTPException(status_code=404, detail="Paper not found")
    conn.commit()
    return _detail_for(conn, paper_id)


# Permanent (irreversible) delete — only reachable for a paper already in Trash (inc 65). Purges the paper's
# embeddings + sqlite-vec vectors too, so nothing orphans (an orphaned paper-embedding crashes retrieval).
@router.delete("/papers/{paper_id}/permanent", status_code=http_status.HTTP_204_NO_CONTENT)
def purge_paper_endpoint(paper_id: int, request: Request, conn: Connection = Depends(get_connection)) -> Response:
    if not purge_paper(conn, paper_id, vector_store=_vector_store(request.app)):
        # missing or still live — a live paper must be soft-deleted (moved to Trash) before it can be purged
        raise HTTPException(status_code=404, detail="Paper not found in Trash")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


class EmptyTrashResponse(BaseModel):
    purged: int


@router.post("/papers/trash/empty", response_model=EmptyTrashResponse)
def empty_trash_endpoint(request: Request, conn: Connection = Depends(get_connection)) -> EmptyTrashResponse:
    # Permanently delete every trashed paper. Literal 3-segment path → no collision with /papers/{paper_id}.
    purged = purge_all_trashed(conn, vector_store=_vector_store(request.app))
    conn.commit()
    return EmptyTrashResponse(purged=purged)


class ExportCitationsRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1)
    format: Literal["bibtex", "ris", "csl-json"]  # Pydantic rejects anything else → 422


@router.post("/papers/export")
def export_citations(payload: ExportCitationsRequest, conn: Connection = Depends(get_connection)) -> Response:
    # Render the LIVE selected papers' stored metadata as BibTeX/RIS/CSL-JSON. Read-only, local (no egress);
    # the filename is a constant (no request data in the path); the renderers escape their output format.
    rows = get_papers_for_export(conn, payload.paper_ids)
    if not rows:
        raise HTTPException(status_code=422, detail="No existing (non-trashed) papers to export")
    text, media_type, ext = render_citations(rows, payload.format)
    return Response(
        content=text,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="callosum-citations.{ext}"'},
    )


def _vector_store(api: FastAPI) -> VectorStore:
    injected = api.state.vector_store
    if injected is not None:
        return injected
    return SQLiteVecVectorStore()


def _detail_for(conn: Connection, paper_id: int) -> PaperDetailResponse:
    paper = get_paper(conn, paper_id)
    attachments = get_attachments_for_paper(conn, paper_id)
    counts = get_paper_counts(conn, paper_id)
    return _paper_detail(
        paper,
        attachments=attachments,
        attachment_count=counts["attachment_count"],
        chunk_count=counts["chunk_count"],
        tags=get_tags_for_paper(conn, paper_id),
    )


def _crossref(app: FastAPI) -> CrossrefClient:
    injected = app.state.crossref_client
    if injected is not None:
        return injected
    return CrossrefClient()


def _iso_or_none(value: Any) -> str | None:
    """A DateTime column (datetime) or its SQLite text form → an ISO string, else None (inc 210)."""
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _paper_list_item(row: Any) -> PaperListItem:
    return PaperListItem(
        id=row["id"],
        title=row["title"],
        authors=_authors_from_csl(row["csl_json"], fallback=row["first_author_family_name"]),
        year=row["year"],
        venue=row["venue"],
        citation_key=row["citation_key"],
        processing_tier=row["processing_tier"],
        attachment_count=row["attachment_count"],
        chunk_count=row["chunk_count"],
        cited_by_count=row["cited_by_count"] if "cited_by_count" in row.keys() else None,
        cited_by_as_of=_iso_or_none(row["cited_by_as_of"]) if "cited_by_as_of" in row.keys() else None,
        read_at=_iso_or_none(row["read_at"]),
        priority=row["priority"],
    )


def _paper_detail(
    row: Any, *, attachments: list[Any], attachment_count: int, chunk_count: int, tags: list[Any] | None = None
) -> PaperDetailResponse:
    return PaperDetailResponse(
        id=row["id"],
        title=row["title"],
        abstract=row["abstract"],
        abstract_display=clean_abstract_for_display(row["abstract"]),
        abstract_text=abstract_plain_text(row["abstract"]),
        authors=_authors_from_csl(row["csl_json"], fallback=row["first_author_family_name"]),
        year=row["year"],
        doi=row["doi"],
        venue=row["venue"],
        item_type=row["item_type"],
        language=row["language"],
        publication_date=row["publication_date"],
        first_author_family_name=row["first_author_family_name"],
        imported_source=row["imported_source"],
        openalex_work_id=row["openalex_work_id"],
        semantic_scholar_paper_id=row["semantic_scholar_paper_id"],
        zotero_library_id=row["zotero_library_id"],
        zotero_item_key=row["zotero_item_key"],
        citation_key=row["citation_key"],
        processing_tier=row["processing_tier"],
        csl_json=row["csl_json"],
        extra_urls=_extra_urls_from_csl(row["csl_json"]),
        attachment_count=attachment_count,
        chunk_count=chunk_count,
        attachments=[_attachment_response(item) for item in attachments],
        tags=[
            PaperTagRef(id=int(t["id"]), name=t["name"], source=t["import_source"], color=t["color"])
            for t in (tags or [])
        ],
        read_at=_iso_or_none(row["read_at"]),
        priority=row["priority"],
    )


def _attachment_response(row: Any) -> AttachmentResponse:
    path = row["resolved_path"] or row["original_path"]
    return AttachmentResponse(
        id=row["id"],
        filename=_path_filename(path),
        storage_mode=row["storage_mode"],
        availability=row["availability"],
        original_path=row["original_path"],
        resolved_path=row["resolved_path"],
        checksum=row["checksum"],
        file_size=row["file_size"],
        content_type=row["content_type"],
        import_source=row["import_source"],
        attachment_type=row["attachment_type"],
        role=row["role"],
        oa_color=row["oa_color"],
        oa_version=row["oa_version"],
        oa_source=row["oa_source"],
        oa_landing_page_url=row["oa_landing_page_url"],
        oa_license=row["oa_license"],
        oa_bronze_unstable=bool(row["oa_bronze_unstable"]),
    )


def _path_filename(path: str | None) -> str | None:
    if not path:
        return None
    if "\\" in path:
        return PureWindowsPath(path).name
    return PurePosixPath(path).name


def _chunk_response(row: Any) -> ChunkResponse:
    return ChunkResponse(
        id=row["id"],
        paper_id=row["paper_id"],
        attachment_id=row["attachment_id"],
        text=row["text"],
        section=row["section"],
        page_start=row["page_start"],
        page_end=row["page_end"],
        char_start=row["char_start"],
        char_end=row["char_end"],
        bbox_json=row["bbox_json"],
        bbox_coordinate_system=row["bbox_coordinate_system"],
        extraction_tool=row["extraction_tool"],
        extraction_version=row["extraction_version"],
        chunking_strategy=row["chunking_strategy"],
        chunk_version=row["chunk_version"],
        source_attachment_checksum=row["source_attachment_checksum"],
    )


def _authors_from_csl(csl_json: Any, *, fallback: str | None) -> list[str]:
    if not isinstance(csl_json, dict):
        return [fallback] if fallback else []
    authors = []
    for author in csl_json.get("author") or []:
        if not isinstance(author, dict):
            continue
        literal = author.get("literal")
        family = author.get("family")
        given = author.get("given")
        if literal:
            authors.append(str(literal))
        elif family and given:
            authors.append(f"{given} {family}")
        elif family:
            authors.append(str(family))
    if not authors and fallback:
        authors.append(fallback)
    return authors


def _extra_urls_from_csl(csl_json: Any) -> list[str]:
    if not isinstance(csl_json, dict):
        return []
    return [str(u) for u in (csl_json.get("extra_urls") or []) if isinstance(u, str) and u.strip()]
