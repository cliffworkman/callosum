"""Local section- and study-aware publication evidence retrieval for registration commitments."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, SentenceTransformerEmbeddingModel
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, SUPPLEMENT
from app.backend.persistence.registration_commitments_repo import (
    get_registration_version,
    list_registration_commitments,
)
from app.backend.persistence.repository import get_chunks_for_paper
from app.backend.registration_commitments import EXTRACTION_VERSION
from app.backend.registration_retrieval import RETRIEVAL_VERSION, retrieve_publication_evidence

router = APIRouter()


class RegistrationRetrievalRequest(BaseModel):
    version_id: int
    include_supplements: bool = False
    expand_beyond_expected_sections: bool = True
    top_k: int = Field(default=3, ge=1, le=5)


class PublicationEvidenceOut(BaseModel):
    chunk_id: int
    attachment_id: int
    document_role: Literal["article-fulltext", "supplement"]
    text: str
    context_text: str
    section: str | None = None
    section_family: str
    page_start: int
    page_end: int
    bbox: Any = None
    similarity: float
    search_phase: Literal["expected-sections", "whole-article", "supplement"]


class CommitmentRetrievalOut(BaseModel):
    commitment_id: int
    field_type: str
    expected_section_families: list[str]
    sections_searched: list[str]
    whole_article_expanded: bool
    supplements_searched: bool
    searched_chunk_ids: list[int]
    searched_attachment_ids: list[int]
    study_mapping: Literal["matched", "unscoped", "ambiguous"]
    study_labels_found: list[str]
    hits: list[PublicationEvidenceOut]
    non_detection_note: str = "Not locating evidence in the searched sections is not proof that the item is unreported."


class RegistrationRetrievalResult(BaseModel):
    paper_id: int
    version_id: int
    registration_content_hash: str
    commitment_extraction_version: str
    retrieval_version: str
    local_only: bool = True
    results: list[CommitmentRetrievalOut]


@router.post("/papers/{paper_id}/registration-evidence/retrieve", response_model=RegistrationRetrievalResult)
def retrieve_registration_publication_evidence(
    paper_id: int,
    payload: RegistrationRetrievalRequest,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> RegistrationRetrievalResult:
    version = get_registration_version(conn, paper_id, payload.version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Registration version not found on this paper")
    commitments = list_registration_commitments(
        conn,
        paper_id,
        payload.version_id,
        extraction_version=EXTRACTION_VERSION,
    )
    if not commitments:
        raise HTTPException(status_code=409, detail="Extract canonical registration commitments before retrieval.")
    article_chunks = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES)
    supplement_chunks = (
        get_chunks_for_paper(conn, paper_id, document_roles=(SUPPLEMENT,)) if payload.include_supplements else []
    )
    model = request.app.state.embedding_model
    if model is None:
        model = SentenceTransformerEmbeddingModel(
            name=DEFAULT_EMBEDDING_MODEL,
            version=DEFAULT_EMBEDDING_MODEL,
            local_files_only=True,
        )
    retrievals = retrieve_publication_evidence(
        commitments,
        article_chunks,
        supplement_chunks,
        model=model,
        include_supplements=payload.include_supplements,
        expand_beyond_expected=payload.expand_beyond_expected_sections,
        top_k=payload.top_k,
    )
    return RegistrationRetrievalResult(
        paper_id=paper_id,
        version_id=payload.version_id,
        registration_content_hash=version["content_hash"],
        commitment_extraction_version=EXTRACTION_VERSION,
        retrieval_version=RETRIEVAL_VERSION,
        results=[
            CommitmentRetrievalOut(
                commitment_id=item.commitment_id,
                field_type=item.field_type,
                expected_section_families=list(item.expected_section_families),
                sections_searched=list(item.sections_searched),
                whole_article_expanded=item.whole_article_expanded,
                supplements_searched=item.supplements_searched,
                searched_chunk_ids=list(item.searched_chunk_ids),
                searched_attachment_ids=list(item.searched_attachment_ids),
                study_mapping=item.study_mapping,
                study_labels_found=list(item.study_labels_found),
                hits=[PublicationEvidenceOut(**hit.__dict__) for hit in item.hits],
            )
            for item in retrievals
        ],
    )
