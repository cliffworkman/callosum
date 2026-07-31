"""Persistence for extracted/manual registration-reference evidence."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Connection, delete, insert, or_, select, update

from app.backend.methods.registration_references import RegistrationReference
from app.backend.persistence.document_roles import (
    ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES,
    attachment_document_role_clause,
)
from app.backend.persistence.registration_schema import paper_registration_references
from app.backend.persistence.schema import attachments


def replace_extracted_registration_references(
    conn: Connection,
    paper_id: int,
    attachment_id: int,
    references: Iterable[RegistrationReference],
) -> list[int]:
    """Replace machine-extracted rows for one attachment without touching manual evidence."""
    conn.execute(
        delete(paper_registration_references).where(
            paper_registration_references.c.paper_id == paper_id,
            paper_registration_references.c.attachment_id == attachment_id,
            paper_registration_references.c.extraction_method != "manual",
        )
    )
    ids: list[int] = []
    for reference in references:
        result = conn.execute(
            insert(paper_registration_references).values(
                paper_id=paper_id,
                attachment_id=attachment_id,
                **_values(reference, attachment_id=attachment_id),
            )
        )
        ids.append(int(result.inserted_primary_key[0]))
    return ids


def add_manual_registration_reference(conn: Connection, paper_id: int, reference: RegistrationReference) -> int:
    existing = conn.execute(
        select(paper_registration_references.c.id).where(
            paper_registration_references.c.paper_id == paper_id,
            paper_registration_references.c.attachment_id.is_(None),
            paper_registration_references.c.provider == reference.provider,
            paper_registration_references.c.external_id == reference.external_id,
            paper_registration_references.c.extraction_method == "manual",
        )
    ).scalar_one_or_none()
    if existing is not None:
        conn.execute(
            update(paper_registration_references)
            .where(paper_registration_references.c.id == existing)
            .values(**_values(reference, attachment_id=None))
        )
        return int(existing)
    result = conn.execute(
        insert(paper_registration_references).values(
            paper_id=paper_id,
            attachment_id=None,
            **_values(reference, attachment_id=None),
        )
    )
    return int(result.inserted_primary_key[0])


def list_registration_references(conn: Connection, paper_id: int) -> list:
    return list(
        conn.execute(
            select(paper_registration_references)
            .select_from(
                paper_registration_references.outerjoin(
                    attachments, attachments.c.id == paper_registration_references.c.attachment_id
                )
            )
            .where(
                paper_registration_references.c.paper_id == paper_id,
                or_(
                    paper_registration_references.c.attachment_id.is_(None),
                    attachment_document_role_clause(ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES),
                ),
            )
            .order_by(paper_registration_references.c.id)
        ).mappings()
    )


def set_attachment_document_role(conn: Connection, paper_id: int, attachment_id: int, role: str) -> bool:
    result = conn.execute(
        update(attachments)
        .where(attachments.c.id == attachment_id, attachments.c.paper_id == paper_id)
        .values(role=role)
    )
    if result.rowcount and role not in ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES:
        conn.execute(
            delete(paper_registration_references).where(
                paper_registration_references.c.paper_id == paper_id,
                paper_registration_references.c.attachment_id == attachment_id,
                paper_registration_references.c.extraction_method != "manual",
            )
        )
    return bool(result.rowcount)


def _values(reference: RegistrationReference, *, attachment_id: int | None) -> dict:
    return {
        "provider": reference.provider,
        "external_id": reference.external_id,
        "canonical_url": reference.canonical_url,
        "visible_text": reference.visible_text,
        "evidence_snippet": reference.evidence_snippet,
        "page": reference.page,
        "extraction_method": reference.extraction_method,
        "evidence_class": reference.evidence_class,
        "explicitly_printed": reference.explicitly_printed,
    }
