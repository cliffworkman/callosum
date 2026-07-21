"""Pydantic models for paper routes, split out to keep papers.py focused on route logic."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
    cited_by_count: int | None = None
    cited_by_as_of: str | None = None
    retraction_status: str | None = None
    read_at: str | None = None
    priority: str | None = None


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
    oa_color: str | None = None
    oa_version: str | None = None
    oa_source: str | None = None
    oa_landing_page_url: str | None = None
    oa_license: str | None = None
    oa_bronze_unstable: bool = False


class PaperTagRef(BaseModel):
    id: int
    name: str
    source: str | None = None
    color: str | None = None
    locked: bool = False


class PaperUrlRef(BaseModel):
    id: int | None = None
    url: str
    label: str | None = None
    source: str | None = None


class PaperDetailResponse(BaseModel):
    id: int
    title: str
    abstract: str | None = None
    abstract_display: str | None = None
    abstract_text: str | None = None
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
    extra_urls: list[str] = []
    urls: list[PaperUrlRef] = []
    attachment_count: int
    chunk_count: int
    attachments: list[AttachmentResponse]
    tags: list[PaperTagRef] = []
    retraction_status: str | None = None
    read_at: str | None = None
    priority: str | None = None


class ReadStateRequest(BaseModel):
    read: bool


class PriorityRequest(BaseModel):
    priority: str | None = None


class PaperUpdateRequest(BaseModel):
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
    extra_urls: list[str] | None = Field(default=None, max_length=50)
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


class ReprocessPdfResponse(BaseModel):
    paper_id: int
    attachment_id: int
    chunks_removed: int
    chunks_created: int
    chunk_version: str | None = None


class ItemTypeCount(BaseModel):
    item_type: str
    count: int


class PaperPositionResponse(BaseModel):
    index: int  # 0-based rank within the exact filtered+sorted set GET /papers would return for the same params


class EmptyTrashResponse(BaseModel):
    purged: int


class ExportCitationsRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1)
    format: Literal["bibtex", "ris", "csl-json"]
