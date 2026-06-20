"""Papers, chunks, and PDF-streaming endpoints (read-only)."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi import status as http_status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.metadata import enrich_paper_metadata_from_crossref
from app.backend.metadata.abstract_display import abstract_plain_text, clean_abstract_for_display
from app.backend.metadata.citation_export import render_citations
from app.backend.metadata.paper_edits import RESERVED_CSL_KEYS, build_paper_update
from app.backend.persistence.repository import (
    get_attachments_for_paper,
    get_chunks_for_paper,
    get_paper,
    get_paper_counts,
    get_papers_for_export,
    list_papers,
    purge_all_trashed,
    purge_paper,
    refresh_processing_tier,
    restore_paper,
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
    attachment_count: int
    chunk_count: int
    attachments: list[AttachmentResponse]
    tags: list[PaperTagRef] = []


# Caps for the generic "More" passthrough (free-form scalar csl fields a DOI populated). The
# named core fields below carry their own length caps; the generic patch is the one place
# arbitrary keys arrive, so it is bounded explicitly (rule #4: validate untrusted input).
CSL_PATCH_MAX_KEYS = 60
CSL_PATCH_KEY_MAX_LEN = 64
CSL_PATCH_VALUE_MAX_LEN = 4000
AUTHOR_MAX_LEN = 1000
_CSL_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class PaperUpdateRequest(BaseModel):
    # Partial edit of a paper's bibliographic record (inc 49). All fields optional; only those in
    # model_fields_set are applied. Scalar columns + the CSL record (papers.csl_json) are kept in
    # sync by build_paper_update; an explicit null/"" clears the field. `csl` is the generic "More"
    # passthrough for scalar CSL keys a DOI populated beyond the curated core.
    title: str | None = Field(default=None, max_length=2000)
    abstract: str | None = Field(default=None, max_length=100_000)
    authors: list[str] | None = Field(default=None, max_length=500)
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
    deleted: bool = Query(default=False),  # true → the Trash listing (soft-deleted papers)
    axis_id: int | None = Query(default=None),  # filter the listing to the papers assigned to this axis
    tag_id: int | None = Query(default=None),  # filter the listing to the papers carrying this tag
    sort: str = Query(default="added"),  # library ordering; unknown keys fall back to "added" (allowlisted in repo)
    conn: Connection = Depends(get_connection),
) -> list[PaperListItem]:
    rows = list_papers(
        conn, limit=limit, offset=offset, q=q, only_deleted=deleted, axis_id=axis_id, tag_id=tag_id, sort=sort
    )
    return [_paper_list_item(row) for row in rows]


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


@router.get("/papers/{paper_id}/pdf", response_model=None)
def paper_pdf(paper_id: int, conn: Connection = Depends(get_connection)) -> FileResponse:
    # Path is resolved ONLY from the attachment row keyed by the integer
    # paper_id — never from anything the client supplies. A single DB lookup.
    attachment_rows = get_attachments_for_paper(conn, paper_id)
    path = _local_attachment_path(_select_primary_pdf_attachment(attachment_rows))
    if path is None:
        raise HTTPException(status_code=404, detail="PDF not available locally for this paper")
    return FileResponse(
        path,
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=path.name,
    )


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
    edits = _edits_from_request(request)
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
    conn.commit()
    return _detail_for(conn, paper_id)


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


def _edits_from_request(request: PaperUpdateRequest) -> dict[str, Any]:
    """Normalise the user-set fields into the dict build_paper_update consumes.

    Strings are stripped with ""→None (clears the field); title must stay non-empty; the generic
    `csl` passthrough is key/value-validated. Only fields in model_fields_set are included.
    """
    fields = request.model_fields_set
    edits: dict[str, Any] = {}
    for name in fields:
        value = getattr(request, name)
        if name == "title":
            title = (value or "").strip()
            if not title:
                raise HTTPException(status_code=422, detail="Title must not be empty")
            edits["title"] = title
        elif name in ("year", "month", "day"):
            edits[name] = value
        elif name == "authors":
            edits["authors"] = _clean_authors(value)
        elif name == "csl":
            edits["csl"] = _validate_csl_patch(value)
        else:
            edits[name] = _norm_str(value)
    return edits


def _norm_str(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_authors(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    cleaned: list[str] = []
    for author in value:
        text = (author or "").strip()
        if not text:
            continue
        if len(text) > AUTHOR_MAX_LEN:
            raise HTTPException(status_code=422, detail="Author name exceeds the maximum length")
        cleaned.append(text)
    return cleaned


def _validate_csl_patch(value: dict[str, str | None] | None) -> dict[str, str | None] | None:
    if value is None:
        return None
    if len(value) > CSL_PATCH_MAX_KEYS:
        raise HTTPException(status_code=422, detail="Too many additional fields")
    cleaned: dict[str, str | None] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or len(key) > CSL_PATCH_KEY_MAX_LEN or not _CSL_KEY_RE.match(key):
            raise HTTPException(status_code=422, detail="Invalid additional-field name")
        if key in RESERVED_CSL_KEYS:
            raise HTTPException(
                status_code=422, detail=f"'{key}' is edited through its own field, not the additional fields"
            )
        if raw is not None:
            if not isinstance(raw, str) or len(raw) > CSL_PATCH_VALUE_MAX_LEN:
                raise HTTPException(status_code=422, detail="Additional-field value is invalid or too long")
            raw = raw.strip() or None
        cleaned[key] = raw
    return cleaned


def _crossref(app: FastAPI) -> CrossrefClient:
    injected = app.state.crossref_client
    if injected is not None:
        return injected
    return CrossrefClient()


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
        attachment_count=attachment_count,
        chunk_count=chunk_count,
        attachments=[_attachment_response(item) for item in attachments],
        tags=[PaperTagRef(id=int(t["id"]), name=t["name"]) for t in (tags or [])],
    )


def _select_primary_pdf_attachment(rows: list[Any]) -> Any | None:
    """Pick the paper's primary PDF attachment from its attachment rows.

    Prefers PDF attachments, then those marked role='primary', falling back to
    the first available attachment so single-attachment papers still resolve.
    """
    if not rows:
        return None
    pdfs = [row for row in rows if _is_pdf_attachment(row)]
    candidates = pdfs or list(rows)
    primary = [row for row in candidates if (row["role"] or "").strip().lower() == "primary"]
    ordered = primary or candidates
    return ordered[0] if ordered else None


def _is_pdf_attachment(row: Any) -> bool:
    content_type = (row["content_type"] or "").strip().lower()
    attachment_type = (row["attachment_type"] or "").strip().lower()
    return content_type == "application/pdf" or attachment_type == "pdf"


def _local_attachment_path(row: Any) -> Path | None:
    """Resolve a streamable local file path from a trusted attachment row.

    The path comes only from the database row (resolved_path, then
    original_path); no client-supplied path is ever followed. Returns None when
    the attachment is URL-only, marked not-present, or missing on disk so the
    endpoint can answer with an honest 404 instead of a 500.
    """
    if row is None:
        return None
    if row["storage_mode"] == "url":
        return None
    if row["availability"] != "available":
        return None
    raw_path = row["resolved_path"] or row["original_path"]
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_file():
        return None
    return path


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
