"""Papers, chunks, and library-facet endpoints (PDF file-serving lives in `paper_files.py`)."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi import status as http_status
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.backend.acquisition.fetch import library_dir
from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.routers.paper_edit_input import edits_from_request
from app.backend.api.routers.paper_files import _local_attachment_path, _select_primary_pdf_attachment
from app.backend.api.routers.paper_models import (
    AttachmentResponse,
    ChunkResponse,
    EmptyTrashResponse,
    ExportCitationsRequest,
    ItemTypeCount,
    PaperDetailResponse,
    PaperListItem,
    PaperPositionResponse,
    PaperTagRef,
    PaperUpdateRequest,
    PaperUrlRef,
    PriorityRequest,
    ReadStateRequest,
    ReprocessPdfResponse,
)
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.metadata.abstract_display import abstract_plain_text, clean_abstract_for_display
from app.backend.metadata.citation_export import render_citations
from app.backend.metadata.paper_edits import build_paper_update
from app.backend.paper_purge import ManagedFilePurgeError, purge_paper_permanently, purge_trash_permanently
from app.backend.pdf_processing.ingest import PdfReprocessEmptyExtraction, reprocess_pdf_attachment
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.paper_urls_repo import list_paper_urls, replace_paper_urls
from app.backend.persistence.repository import (
    PRIORITY_LEVELS,
    get_attachments_for_paper,
    get_chunks_for_paper,
    get_paper,
    get_paper_counts,
    get_paper_rank,
    get_papers_for_export,
    list_item_types,
    list_papers,
    refresh_processing_tier,
    restore_paper,
    set_paper_priority,
    set_paper_read,
    soft_delete_paper,
    update_paper_metadata,
)
from app.backend.persistence.signals_repo import get_retraction_status
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.tags_repo import get_tags_for_paper
from app.backend.usage import record_event

router = APIRouter()


class PaperFilterParams:
    """The library's full filter+sort contract, as a FastAPI dependency (inc 319) — shared by `papers_index`
    (`GET /papers`) and `paper_position` (`GET /papers/{id}/position`) so the two can never drift apart. FastAPI
    flattens a `Depends()` sub-dependency's fields into the same query string as inline params, so this is a pure
    internal refactor: `GET /papers`'s wire contract is unchanged."""

    def __init__(
        self,
        q: str | None = Query(
            default=None, max_length=500
        ),  # rule #4: cap length so `%<q>%` can't exceed SQLite's SQLITE_MAX_LIKE_PATTERN_LENGTH (50000) → 500
        search_field: str = Query(default="all"),  # all / title / author / journal (allowlisted in repo)
        deleted: bool = Query(default=False),  # true → the Trash listing (soft-deleted papers)
        axis_id: int | None = Query(default=None),  # filter the listing to the papers assigned to this axis
        axis_hide_uncertain: bool = Query(default=False),  # with axis_id: match the card's assigned-only view (A10)
        tag_id: int | None = Query(default=None),  # filter the listing to the papers carrying this tag
        item_type: str | None = Query(default=None),  # filter to a single CSL item type (bound; see list_item_types)
        needs_review: bool = Query(default=False),  # the "Unsorted" view: scaffold / Crossref-unresolved / no source
        signal: str | None = Query(
            default=None
        ),  # filter to a Methods-producer signal (allowlisted in repo), e.g. statcheck
        finding: str | None = Query(default=None),  # the "to review" queue: unreviewed candidate findings
        read_status: str | None = Query(default=None),  # inc 220: "read" / "unread" filter
        priority: str | None = Query(default=None),  # inc 220: filter to a priority level (allowlisted in repo)
        missing_pdf: bool = Query(
            default=False
        ),  # inc 301: only papers with no local PDF (mirrors Text-Health no_local_pdf)
        sort: str = Query(default="added"),  # library ordering; unknown keys fall back to "added" (allowlisted)
    ) -> None:
        self.q = q
        self.search_field = search_field
        self.deleted = deleted
        self.axis_id = axis_id
        self.axis_hide_uncertain = axis_hide_uncertain
        self.tag_id = tag_id
        self.item_type = item_type
        self.needs_review = needs_review
        self.signal = signal
        self.finding = finding
        self.read_status = read_status
        self.priority = priority
        self.missing_pdf = missing_pdf
        self.sort = sort

    def as_kwargs(self) -> dict[str, Any]:
        return {
            "q": self.q,
            "search_field": self.search_field,
            "only_deleted": self.deleted,
            "axis_id": self.axis_id,
            "axis_hide_uncertain": self.axis_hide_uncertain,
            "tag_id": self.tag_id,
            "item_type": self.item_type,
            "needs_review": self.needs_review,
            "signal": self.signal,
            "finding": self.finding,
            "read_status": self.read_status,
            "priority": self.priority,
            "missing_pdf": self.missing_pdf,
            "sort": self.sort,
        }


@router.get("/papers", response_model=list[PaperListItem])
def papers_index(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    filters: PaperFilterParams = Depends(),
    conn: Connection = Depends(get_connection),
) -> list[PaperListItem]:
    rows = list_papers(conn, limit=limit, offset=offset, **filters.as_kwargs())
    return [_paper_list_item(row) for row in rows]


@router.get("/papers/{paper_id}/position", response_model=PaperPositionResponse)
def paper_position(
    paper_id: int,
    filters: PaperFilterParams = Depends(),
    conn: Connection = Depends(get_connection),
) -> PaperPositionResponse:
    """0-based rank of `paper_id` within the exact filtered+sorted set `GET /papers` would return for the same
    params (inc 319) — drives the library's "reveal the selected paper" scroll. 404 means the paper doesn't match
    these filters (deleted/trashed mismatch, or excluded by a facet); the frontend takes that as "skip the
    reveal," never as license to relax the filter itself."""
    index = get_paper_rank(conn, paper_id, **filters.as_kwargs())
    if index is None:
        raise HTTPException(status_code=404, detail="paper not found under the given filters")
    return PaperPositionResponse(index=index)


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
        urls=list_paper_urls(conn, paper_id),
        attachment_count=counts["attachment_count"],
        chunk_count=counts["chunk_count"],
        tags=get_tags_for_paper(conn, paper_id),
        retraction_status=(get_retraction_status(conn, paper_id) or {}).get("status"),
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
    return [
        _chunk_response(row)
        for row in get_chunks_for_paper(
            conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES, limit=limit, offset=offset
        )
    ]


@router.post("/papers/{paper_id}/reprocess-pdf", response_model=ReprocessPdfResponse)
def reprocess_paper_pdf(
    paper_id: int, request: Request, conn: Connection = Depends(get_connection)
) -> ReprocessPdfResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    attachment = _select_primary_pdf_attachment(get_attachments_for_paper(conn, paper_id))
    pdf_path = _local_attachment_path(attachment)
    if attachment is None or pdf_path is None:
        raise HTTPException(status_code=422, detail="This paper has no local PDF to reprocess.")
    try:
        result = reprocess_pdf_attachment(
            conn,
            paper_id,
            int(attachment["id"]),
            pdf_path,
            vector_store=_vector_store(request.app),
            embedding_model=_embedding_model(request.app),
        )
    except PdfReprocessEmptyExtraction as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    conn.commit()
    return ReprocessPdfResponse(
        paper_id=paper_id,
        attachment_id=int(result["attachment_id"]),
        chunks_removed=int(result["chunks_removed"]),
        chunks_created=int(result["chunks_created"]),
        chunk_version=result["chunk_version"],
    )


@router.patch("/papers/{paper_id}", response_model=PaperDetailResponse)
def update_paper(
    paper_id: int,
    request: PaperUpdateRequest,
    engine: Engine = Depends(get_engine),
) -> PaperDetailResponse:
    def _do(conn: Connection) -> PaperDetailResponse:
        try:
            paper = get_paper(conn, paper_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Paper not found") from None
        edits = edits_from_request(request)
        if not edits:
            raise HTTPException(status_code=422, detail="No updatable fields provided")
        try:
            update_paper_metadata(conn, paper_id, **build_paper_update(paper, edits))
            if "extra_urls" in edits:
                replace_paper_urls(conn, paper_id, edits["extra_urls"])
            refresh_processing_tier(conn, paper_id)
        except IntegrityError:
            # run_write rolls the unit back on any exception; a non-lock error propagates un-retried.
            raise HTTPException(status_code=409, detail="That identifier is already on another paper") from None
        return _detail_for(conn, paper_id)

    return run_write(engine, _do)


@router.delete("/papers/{paper_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_paper(paper_id: int, engine: Engine = Depends(get_engine)) -> Response:
    # Soft-delete (move to Trash): hidden from the library/axes/clustering but kept + restorable.
    def _do(conn: Connection) -> Response:
        if not soft_delete_paper(conn, paper_id):
            raise HTTPException(status_code=404, detail="Paper not found or already in Trash")
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


@router.post("/papers/{paper_id}/restore", response_model=PaperDetailResponse)
def restore_paper_endpoint(paper_id: int, engine: Engine = Depends(get_engine)) -> PaperDetailResponse:
    def _do(conn: Connection) -> PaperDetailResponse:
        if not restore_paper(conn, paper_id):
            raise HTTPException(status_code=404, detail="Paper not found in Trash")
        return _detail_for(conn, paper_id)

    return run_write(engine, _do)


@router.post("/papers/{paper_id}/read", response_model=PaperDetailResponse)
def set_read_endpoint(
    paper_id: int, payload: ReadStateRequest, request: Request, conn: Connection = Depends(get_connection)
) -> PaperDetailResponse:
    """Mark a paper read/unread — a manual user toggle (inc 220). 404 if the paper doesn't exist."""
    # Transaction-level retry so a collision with a concurrent write returns a value, not a 500 (see sqlite_retry).
    if not run_write(request.app.state.engine, lambda c: set_paper_read(c, paper_id, payload.read)):
        raise HTTPException(status_code=404, detail="Paper not found")
    return _detail_for(conn, paper_id)


@router.post("/papers/{paper_id}/priority", response_model=PaperDetailResponse)
def set_priority_endpoint(
    paper_id: int, payload: PriorityRequest, request: Request, conn: Connection = Depends(get_connection)
) -> PaperDetailResponse:
    """Set/clear the user's reading priority (high/normal/low or null) — a hand-set triage label, never an AI
    score (inc 220). 422 off-allowlist; 404 if the paper doesn't exist."""
    if payload.priority is not None and payload.priority not in PRIORITY_LEVELS:
        raise HTTPException(status_code=422, detail=f"priority must be one of {PRIORITY_LEVELS} or null")
    if not run_write(request.app.state.engine, lambda c: set_paper_priority(c, paper_id, payload.priority)):
        raise HTTPException(status_code=404, detail="Paper not found")
    return _detail_for(conn, paper_id)


# Permanent (irreversible) delete — only reachable for a paper already in Trash (inc 65). Purges the paper's
# embeddings + sqlite-vec vectors too, so nothing orphans (an orphaned paper-embedding crashes retrieval).
@router.delete("/papers/{paper_id}/permanent", status_code=http_status.HTTP_204_NO_CONTENT)
def purge_paper_endpoint(paper_id: int, request: Request, conn: Connection = Depends(get_connection)) -> Response:
    try:
        purged = purge_paper_permanently(
            conn,
            paper_id,
            vector_store=_vector_store(request.app),
            managed_library_dir=library_dir(),
        )
    except ManagedFilePurgeError as exc:
        raise HTTPException(status_code=409, detail=f"Paper remains in Trash: {exc}") from exc
    if not purged:
        raise HTTPException(status_code=404, detail="Paper not found in Trash")
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post("/papers/trash/empty", response_model=EmptyTrashResponse)
def empty_trash_endpoint(request: Request, conn: Connection = Depends(get_connection)) -> EmptyTrashResponse:
    # Permanently delete every trashed paper. Literal 3-segment path → no collision with /papers/{paper_id}.
    try:
        purged = purge_trash_permanently(
            conn,
            vector_store=_vector_store(request.app),
            managed_library_dir=library_dir(),
        )
    except ManagedFilePurgeError as exc:
        raise HTTPException(status_code=409, detail=f"Trash was not emptied: {exc}") from exc
    return EmptyTrashResponse(purged=purged)


@router.post("/papers/export")
def export_citations(payload: ExportCitationsRequest, engine: Engine = Depends(get_engine)) -> Response:
    # Render the LIVE selected papers' stored metadata as BibTeX/RIS/CSL-JSON. Read-only, local (no egress);
    # the filename is a constant (no request data in the path); the renderers escape their output format. Wrapped
    # in run_write (inc 281) since it now records a usage event -- a short write, retried transaction-level on a
    # transient SQLite writer lock rather than taking a raw connection and committing directly.
    def _do(conn: Connection) -> Response:
        rows = get_papers_for_export(conn, payload.paper_ids)
        if not rows:
            raise HTTPException(status_code=422, detail="No existing (non-trashed) papers to export")
        text, media_type, ext = render_citations(rows, payload.format)
        record_event(conn, "citation_export", count=len(rows))
        return Response(
            content=text,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="callosum-citations.{ext}"'},
        )

    return run_write(engine, _do)


def _vector_store(api: FastAPI) -> VectorStore:
    injected = api.state.vector_store
    if injected is not None:
        return injected
    return SQLiteVecVectorStore()


def _embedding_model(api: FastAPI) -> EmbeddingModel:
    injected = api.state.embedding_model
    if injected is not None:
        return injected
    return SentenceTransformerEmbeddingModel(name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL)


def _detail_for(conn: Connection, paper_id: int) -> PaperDetailResponse:
    paper = get_paper(conn, paper_id)
    attachments = get_attachments_for_paper(conn, paper_id)
    counts = get_paper_counts(conn, paper_id)
    return _paper_detail(
        paper,
        attachments=attachments,
        urls=list_paper_urls(conn, paper_id),
        attachment_count=counts["attachment_count"],
        chunk_count=counts["chunk_count"],
        tags=get_tags_for_paper(conn, paper_id),
        retraction_status=(get_retraction_status(conn, paper_id) or {}).get("status"),
    )


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
        retraction_status=row["retraction_status"] if "retraction_status" in row.keys() else None,
        correction_evidence_linked=(
            bool(row["correction_evidence_linked"]) if "correction_evidence_linked" in row.keys() else False
        ),
        read_at=_iso_or_none(row["read_at"]),
        priority=row["priority"],
    )


def _paper_detail(
    row: Any,
    *,
    attachments: list[Any],
    urls: list[Any],
    attachment_count: int,
    chunk_count: int,
    tags: list[Any] | None = None,
    retraction_status: str | None = None,
) -> PaperDetailResponse:
    extra_urls = _urls_from_rows(urls) or _extra_urls_from_csl(row["csl_json"])
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
        extra_urls=extra_urls,
        urls=[_paper_url_ref(item) for item in urls]
        or [PaperUrlRef(url=url, source="csl-extra-url") for url in extra_urls],
        attachment_count=attachment_count,
        chunk_count=chunk_count,
        attachments=[_attachment_response(item) for item in attachments],
        tags=[
            PaperTagRef(
                id=int(t["id"]), name=t["name"], source=t["import_source"], color=t["color"], locked=bool(t["locked"])
            )
            for t in (tags or [])
        ],
        retraction_status=retraction_status,
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


def _urls_from_rows(rows: list[Any]) -> list[str]:
    return [str(row["url"]) for row in rows if row["url"]]


def _paper_url_ref(row: Any) -> PaperUrlRef:
    return PaperUrlRef(id=int(row["id"]), url=row["url"], label=row["label"], source=row["source"])
