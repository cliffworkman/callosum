from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, insert, select, update

from app.backend.persistence.registration_schema import paper_registration_links, registration_document_versions
from app.backend.persistence.schema import attachments
from app.backend.registration_acquisition.domain import AcquiredRegistration


def get_registration_link(conn: Connection, paper_id: int, link_id: int):
    return (
        conn.execute(
            select(paper_registration_links).where(
                paper_registration_links.c.id == link_id,
                paper_registration_links.c.paper_id == paper_id,
            )
        )
        .mappings()
        .first()
    )


def get_registration_version_by_hash(conn: Connection, link_id: int, content_hash: str):
    return (
        conn.execute(
            select(registration_document_versions).where(
                registration_document_versions.c.link_id == link_id,
                registration_document_versions.c.content_hash == content_hash,
            )
        )
        .mappings()
        .first()
    )


def list_registration_versions(conn: Connection, paper_id: int) -> list:
    return list(
        conn.execute(
            select(registration_document_versions)
            .where(registration_document_versions.c.paper_id == paper_id)
            .order_by(registration_document_versions.c.retrieved_at.desc(), registration_document_versions.c.id.desc())
        ).mappings()
    )


def record_acquired_registration_version(
    conn: Connection,
    paper_id: int,
    link_id: int,
    attachment_id: int,
    acquired: AcquiredRegistration,
) -> tuple[int, bool]:
    existing = get_registration_version_by_hash(conn, link_id, acquired.content_hash)
    now = datetime.now(timezone.utc)
    if existing is not None:
        restored_attachment_id = existing["attachment_id"] or attachment_id
        if existing["attachment_id"] is None:
            conn.execute(
                update(registration_document_versions)
                .where(registration_document_versions.c.id == existing["id"])
                .values(attachment_id=restored_attachment_id, retrieved_at=now)
            )
        conn.execute(
            update(paper_registration_links)
            .where(paper_registration_links.c.id == link_id, paper_registration_links.c.paper_id == paper_id)
            .values(
                attachment_id=restored_attachment_id,
                content_hash=acquired.content_hash,
                retrieved_at=now,
                source_metadata_json=acquired.source_metadata,
                updated_at=now,
            )
        )
        return int(existing["id"]), False
    result = conn.execute(
        insert(registration_document_versions).values(
            link_id=link_id,
            paper_id=paper_id,
            attachment_id=attachment_id,
            provider=acquired.provider,
            external_id=acquired.external_id,
            content_hash=acquired.content_hash,
            canonical_url=acquired.canonical_url,
            registered_at=acquired.registered_at,
            registration_status=acquired.registration_status,
            schema_name=acquired.schema_name,
            schema_version=acquired.schema_version,
            structured_json=acquired.structured,
            rendered_text=acquired.rendered_text,
            source_metadata_json=acquired.source_metadata,
            retrieved_at=now,
        )
    )
    conn.execute(
        update(paper_registration_links)
        .where(paper_registration_links.c.id == link_id, paper_registration_links.c.paper_id == paper_id)
        .values(
            attachment_id=attachment_id,
            canonical_url=acquired.canonical_url,
            registered_at=acquired.registered_at,
            registration_status=acquired.registration_status,
            schema_name=acquired.schema_name,
            content_hash=acquired.content_hash,
            retrieved_at=now,
            source_metadata_json=acquired.source_metadata,
            updated_at=now,
        )
    )
    return int(result.inserted_primary_key[0]), True


def record_local_registration_version(conn: Connection, paper_id: int, link_id: int, attachment_id: int) -> int:
    attachment = (
        conn.execute(select(attachments).where(attachments.c.id == attachment_id, attachments.c.paper_id == paper_id))
        .mappings()
        .one()
    )
    content_hash = str(attachment["checksum"] or f"attachment:{attachment_id}")
    existing = get_registration_version_by_hash(conn, link_id, content_hash)
    now = datetime.now(timezone.utc)
    if existing is None:
        result = conn.execute(
            insert(registration_document_versions).values(
                link_id=link_id,
                paper_id=paper_id,
                attachment_id=attachment_id,
                provider="manual-local",
                external_id=f"attachment:{attachment_id}",
                content_hash=content_hash,
                registration_status="local",
                structured_json={
                    "format": "callosum-registration-v1",
                    "provider": "manual-local",
                    "attachment_id": attachment_id,
                    "checksum": attachment["checksum"],
                    "content_type": attachment["content_type"],
                },
                rendered_text=None,
                source_metadata_json={
                    "network_request": False,
                    "original_path": attachment["original_path"],
                    "resolved_path": attachment["resolved_path"],
                },
                retrieved_at=now,
            )
        )
        version_id = int(result.inserted_primary_key[0])
    else:
        version_id = int(existing["id"])
    conn.execute(
        update(paper_registration_links)
        .where(paper_registration_links.c.id == link_id, paper_registration_links.c.paper_id == paper_id)
        .values(attachment_id=attachment_id, content_hash=content_hash, retrieved_at=now, updated_at=now)
    )
    return version_id


def registration_version_summary(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "link_id": row["link_id"],
        "paper_id": row["paper_id"],
        "attachment_id": row["attachment_id"],
        "provider": row["provider"],
        "external_id": row["external_id"],
        "content_hash": row["content_hash"],
        "canonical_url": row["canonical_url"],
        "registered_at": row["registered_at"],
        "registration_status": row["registration_status"],
        "schema_name": row["schema_name"],
        "schema_version": row["schema_version"],
        "retrieved_at": row["retrieved_at"],
    }
