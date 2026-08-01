"""Local deterministic extraction of evidence-bearing registration commitments."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.persistence.registration_commitments_repo import (
    get_registration_version,
    list_registration_commitments,
    replace_registration_commitments,
)
from app.backend.persistence.repository import get_chunks_for_attachment
from app.backend.persistence.sqlite_retry import run_write
from app.backend.registration_commitments import EXTRACTION_VERSION, extract_commitments

router = APIRouter()


class RegistrationCommitmentOut(BaseModel):
    id: int
    version_id: int
    paper_id: int
    link_id: int
    attachment_id: int | None = None
    field_type: str
    study_label: str | None = None
    ordinal: int
    structured_value: dict[str, Any] = Field(default_factory=dict)
    evidence_text: str
    source_section: str | None = None
    source_key: str
    page: int | None = None
    chunk_id: int | None = None
    source_locator: dict[str, Any] = Field(default_factory=dict)
    extraction_method: str
    extraction_confidence: Literal["high", "medium", "low"]
    registration_content_hash: str
    extraction_version: str


class CommitmentExtractionResult(BaseModel):
    paper_id: int
    version_id: int
    extraction_version: str
    commitment_count: int
    commitments: list[RegistrationCommitmentOut]
    local_only: bool = True
    note: str = "Canonical placement is an extraction aid, not a judgment about the registration or paper."


@router.post(
    "/papers/{paper_id}/registration-versions/{version_id}/commitments/extract",
    response_model=CommitmentExtractionResult,
)
def extract_registration_commitments(
    paper_id: int,
    version_id: int,
    engine: Engine = Depends(get_engine),
) -> CommitmentExtractionResult:
    def write(conn: Connection):
        version = get_registration_version(conn, paper_id, version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="Registration version not found on this paper")
        if version["attachment_id"] is None:
            raise HTTPException(status_code=409, detail="Registration version has no local attachment to inspect")
        chunks = get_chunks_for_attachment(conn, int(version["attachment_id"]))
        candidates = extract_commitments(version, chunks)
        return replace_registration_commitments(
            conn,
            version,
            candidates,
            extraction_version=EXTRACTION_VERSION,
        )

    rows = run_write(engine, write)
    commitments = [_commitment_out(row) for row in rows]
    return CommitmentExtractionResult(
        paper_id=paper_id,
        version_id=version_id,
        extraction_version=EXTRACTION_VERSION,
        commitment_count=len(commitments),
        commitments=commitments,
    )


@router.get(
    "/papers/{paper_id}/registration-versions/{version_id}/commitments",
    response_model=list[RegistrationCommitmentOut],
)
def registration_commitment_list(
    paper_id: int,
    version_id: int,
    conn: Connection = Depends(get_connection),
) -> list[RegistrationCommitmentOut]:
    if get_registration_version(conn, paper_id, version_id) is None:
        raise HTTPException(status_code=404, detail="Registration version not found on this paper")
    return [
        _commitment_out(row)
        for row in list_registration_commitments(
            conn,
            paper_id,
            version_id,
            extraction_version=EXTRACTION_VERSION,
        )
    ]


def _commitment_out(row) -> RegistrationCommitmentOut:
    return RegistrationCommitmentOut(
        id=row["id"],
        version_id=row["version_id"],
        paper_id=row["paper_id"],
        link_id=row["link_id"],
        attachment_id=row["attachment_id"],
        field_type=row["field_type"],
        study_label=row["study_label"],
        ordinal=row["ordinal"],
        structured_value=dict(row["structured_value_json"] or {}),
        evidence_text=row["evidence_text"],
        source_section=row["source_section"],
        source_key=row["source_key"],
        page=row["page"],
        chunk_id=row["chunk_id"],
        source_locator=dict(row["source_locator_json"] or {}),
        extraction_method=row["extraction_method"],
        extraction_confidence=row["extraction_confidence"],
        registration_content_hash=row["registration_content_hash"],
        extraction_version=row["extraction_version"],
    )
