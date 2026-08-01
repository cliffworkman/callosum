from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Connection, delete, insert, select

from app.backend.persistence.registration_schema import registration_commitments, registration_document_versions
from app.backend.registration_commitments.domain import CommitmentCandidate


def get_registration_version(conn: Connection, paper_id: int, version_id: int):
    return (
        conn.execute(
            select(registration_document_versions).where(
                registration_document_versions.c.id == version_id,
                registration_document_versions.c.paper_id == paper_id,
            )
        )
        .mappings()
        .first()
    )


def replace_registration_commitments(
    conn: Connection,
    version,
    candidates: Sequence[CommitmentCandidate],
    *,
    extraction_version: str,
) -> list:
    conn.execute(
        delete(registration_commitments).where(
            registration_commitments.c.version_id == version["id"],
            registration_commitments.c.extraction_version == extraction_version,
        )
    )
    for ordinal, candidate in enumerate(candidates):
        conn.execute(
            insert(registration_commitments).values(
                version_id=version["id"],
                paper_id=version["paper_id"],
                link_id=version["link_id"],
                attachment_id=version["attachment_id"],
                field_type=candidate.field_type,
                study_label=candidate.study_label,
                ordinal=ordinal,
                structured_value_json=candidate.structured_value,
                evidence_text=candidate.evidence_text,
                source_section=candidate.source_section,
                source_key=candidate.source_key,
                page=candidate.page,
                chunk_id=candidate.chunk_id,
                source_locator_json=candidate.source_locator,
                extraction_method=candidate.extraction_method,
                extraction_confidence=candidate.extraction_confidence,
                registration_content_hash=version["content_hash"],
                extraction_version=extraction_version,
            )
        )
    return list_registration_commitments(
        conn,
        int(version["paper_id"]),
        int(version["id"]),
        extraction_version=extraction_version,
    )


def list_registration_commitments(
    conn: Connection,
    paper_id: int,
    version_id: int,
    *,
    extraction_version: str | None = None,
) -> list:
    stmt = select(registration_commitments).where(
        registration_commitments.c.paper_id == paper_id,
        registration_commitments.c.version_id == version_id,
    )
    if extraction_version is not None:
        stmt = stmt.where(registration_commitments.c.extraction_version == extraction_version)
    return list(
        conn.execute(stmt.order_by(registration_commitments.c.ordinal, registration_commitments.c.id)).mappings()
    )
