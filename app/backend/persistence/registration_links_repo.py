from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Connection, insert, select, update

from app.backend.persistence.registration_schema import paper_registration_links
from app.backend.registration_discovery.domain import RegistrationCandidate


def upsert_registration_candidates(
    conn: Connection, paper_id: int, candidates: list[RegistrationCandidate], *, fresh: bool = False
) -> list[int]:
    visible_ids: list[int] = []
    for candidate in candidates:
        existing = (
            conn.execute(
                select(paper_registration_links).where(
                    paper_registration_links.c.paper_id == paper_id,
                    paper_registration_links.c.provider == candidate.provider,
                    paper_registration_links.c.external_id == candidate.external_id,
                )
            )
            .mappings()
            .first()
        )
        values = _candidate_values(candidate)
        if existing is None:
            values["link_status"] = "withdrawn" if candidate.registration_status == "withdrawn" else "candidate"
            result = conn.execute(insert(paper_registration_links).values(paper_id=paper_id, **values))
            visible_ids.append(int(result.inserted_primary_key[0]))
            continue
        link_id = int(existing["id"])
        if existing["link_status"] == "confirmed":
            values["link_status"] = "confirmed"
            values["user_confirmed"] = True
        elif existing["link_status"] == "rejected" and not fresh:
            continue
        else:
            values["link_status"] = "withdrawn" if candidate.registration_status == "withdrawn" else "candidate"
            values["user_confirmed"] = False
        conn.execute(
            update(paper_registration_links)
            .where(paper_registration_links.c.id == link_id)
            .values(**values, updated_at=datetime.now(timezone.utc))
        )
        visible_ids.append(link_id)
    return visible_ids


def list_registration_links(conn: Connection, paper_id: int, *, include_rejected: bool = False) -> list:
    stmt = select(paper_registration_links).where(paper_registration_links.c.paper_id == paper_id)
    if not include_rejected:
        stmt = stmt.where(paper_registration_links.c.link_status != "rejected")
    return list(conn.execute(stmt.order_by(paper_registration_links.c.id)).mappings())


def set_registration_link_status(
    conn: Connection, paper_id: int, link_id: int, status: str, *, user_confirmed: bool
) -> bool:
    result = conn.execute(
        update(paper_registration_links)
        .where(paper_registration_links.c.id == link_id, paper_registration_links.c.paper_id == paper_id)
        .values(link_status=status, user_confirmed=user_confirmed, updated_at=datetime.now(timezone.utc))
    )
    return bool(result.rowcount)


def confirm_local_registration_attachment(conn: Connection, paper_id: int, attachment_id: int) -> int:
    external_id = f"attachment:{attachment_id}"
    existing = conn.execute(
        select(paper_registration_links.c.id).where(
            paper_registration_links.c.paper_id == paper_id,
            paper_registration_links.c.provider == "manual-local",
            paper_registration_links.c.external_id == external_id,
        )
    ).scalar_one_or_none()
    values = {
        "attachment_id": attachment_id,
        "canonical_url": None,
        "title": "Local registration attachment",
        "contributors_json": [],
        "registration_status": "local",
        "link_status": "confirmed",
        "linkage_class": "explicit-linkage",
        "match_method": "user-attached-local-file",
        "match_evidence_json": [{"kind": "user-confirmed-local-attachment", "attachment_id": attachment_id}],
        "user_confirmed": True,
        "source_metadata_json": {"network_request": False},
        "updated_at": datetime.now(timezone.utc),
    }
    if existing is not None:
        conn.execute(update(paper_registration_links).where(paper_registration_links.c.id == existing).values(**values))
        return int(existing)
    result = conn.execute(
        insert(paper_registration_links).values(
            paper_id=paper_id,
            provider="manual-local",
            external_id=external_id,
            **values,
        )
    )
    return int(result.inserted_primary_key[0])


def _candidate_values(candidate: RegistrationCandidate) -> dict:
    return {
        "provider": candidate.provider,
        "external_id": candidate.external_id,
        "attachment_id": candidate.attachment_id,
        "registration_doi": candidate.registration_doi,
        "canonical_url": candidate.canonical_url,
        "title": candidate.title,
        "contributors_json": list(candidate.contributors),
        "registered_at": candidate.registered_at,
        "registration_status": candidate.registration_status,
        "schema_name": candidate.schema_name,
        "linkage_class": candidate.linkage_class,
        "match_method": candidate.match_method,
        "match_evidence_json": list(candidate.match_evidence),
        "source_metadata_json": candidate.source_metadata,
        "retrieved_at": datetime.now(timezone.utc),
    }
