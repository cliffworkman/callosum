from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from sqlalchemy import Connection, insert, select, update

from app.backend.persistence.registration_schema import (
    paper_registration_links,
    registration_comparison_rows,
    registration_comparison_runs,
)
from app.backend.persistence.schema import attachments
from app.backend.registration_comparison.domain import ComparisonProposal


def source_snapshot(conn: Connection, chunks: Sequence[Mapping]) -> tuple[str, list[dict]]:
    attachment_ids = sorted({int(row["attachment_id"]) for row in chunks})
    attachment_rows = {
        int(row["id"]): row
        for row in conn.execute(select(attachments).where(attachments.c.id.in_(attachment_ids))).mappings()
    }
    snapshot = []
    for attachment_id in attachment_ids:
        attachment = attachment_rows[attachment_id]
        related = [row for row in chunks if int(row["attachment_id"]) == attachment_id]
        snapshot.append(
            {
                "attachment_id": attachment_id,
                "checksum": attachment["checksum"],
                "role": attachment["role"],
                "extraction_versions": sorted({str(row["extraction_version"]) for row in related}),
                "chunk_versions": sorted({str(row["chunk_version"]) for row in related}),
                "chunk_count": len(related),
            }
        )
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest(), snapshot


def create_comparison_run(
    conn: Connection,
    *,
    paper_id: int,
    link_id: int,
    registration_version_id: int,
    registration_content_hash: str,
    article_fingerprint: str,
    supplement_fingerprint: str | None,
    article_source: list[dict],
    supplement_source: list[dict],
    commitment_extraction_version: str,
    retrieval_version: str,
    comparison_version: str,
    configuration: dict,
    model_versions: dict,
    proposals: Sequence[ComparisonProposal],
) -> int:
    now = datetime.now(timezone.utc)
    run_id = int(
        conn.execute(
            insert(registration_comparison_runs).values(
                paper_id=paper_id,
                link_id=link_id,
                registration_version_id=registration_version_id,
                status="completed",
                registration_content_hash=registration_content_hash,
                article_fingerprint=article_fingerprint,
                supplement_fingerprint=supplement_fingerprint,
                article_source_json=article_source,
                supplement_source_json=supplement_source,
                commitment_extraction_version=commitment_extraction_version,
                retrieval_version=retrieval_version,
                comparison_version=comparison_version,
                configuration_json=configuration,
                model_versions_json=model_versions,
                stale_reasons_json=[],
                completed_at=now,
                updated_at=now,
            )
        ).inserted_primary_key[0]
    )
    for proposal in proposals:
        conn.execute(
            insert(registration_comparison_rows).values(
                run_id=run_id,
                commitment_id=proposal.commitment_id,
                field_type=proposal.field_type,
                registration_value_json=proposal.registration_value,
                registration_evidence_text=proposal.registration_evidence_text,
                registration_source_locator_json=proposal.registration_source_locator,
                publication_value_json=proposal.publication_value,
                publication_evidence_text=proposal.publication_evidence_text,
                publication_source_locator_json=proposal.publication_source_locator,
                comparison_status=proposal.comparison_status,
                timing_status=proposal.timing_status,
                explanation=proposal.explanation,
                uncertainty=proposal.uncertainty,
                search_scope_json=proposal.search_scope,
                registration_version_id=registration_version_id,
                registration_content_hash=registration_content_hash,
                publication_attachment_id=proposal.publication_attachment_id,
                publication_attachment_checksum=proposal.publication_attachment_checksum,
            )
        )
    return run_id


def list_comparison_runs(conn: Connection, paper_id: int) -> list:
    return list(
        conn.execute(
            select(registration_comparison_runs)
            .where(registration_comparison_runs.c.paper_id == paper_id)
            .order_by(registration_comparison_runs.c.created_at.desc(), registration_comparison_runs.c.id.desc())
        ).mappings()
    )


def get_comparison_run(conn: Connection, paper_id: int, run_id: int):
    return (
        conn.execute(
            select(registration_comparison_runs).where(
                registration_comparison_runs.c.id == run_id,
                registration_comparison_runs.c.paper_id == paper_id,
            )
        )
        .mappings()
        .first()
    )


def list_comparison_rows(conn: Connection, run_id: int) -> list:
    return list(
        conn.execute(
            select(registration_comparison_rows)
            .where(registration_comparison_rows.c.run_id == run_id)
            .order_by(registration_comparison_rows.c.id)
        ).mappings()
    )


def set_comparison_review(conn: Connection, row_id: int, review_state: str, note: str | None):
    now = datetime.now(timezone.utc)
    result = conn.execute(
        update(registration_comparison_rows)
        .where(registration_comparison_rows.c.id == row_id)
        .values(review_state=review_state, note=note, updated_at=now)
    )
    if not result.rowcount:
        return None
    return (
        conn.execute(select(registration_comparison_rows).where(registration_comparison_rows.c.id == row_id))
        .mappings()
        .one()
    )


def current_link_hash(conn: Connection, link_id: int) -> str | None:
    return conn.scalar(select(paper_registration_links.c.content_hash).where(paper_registration_links.c.id == link_id))


def mark_comparison_stale(conn: Connection, run_id: int, reasons: list[str]) -> None:
    if not reasons:
        return
    conn.execute(
        update(registration_comparison_runs)
        .where(registration_comparison_runs.c.id == run_id)
        .values(
            status="stale",
            stale_reasons_json=reasons,
            updated_at=datetime.now(timezone.utc),
        )
    )
