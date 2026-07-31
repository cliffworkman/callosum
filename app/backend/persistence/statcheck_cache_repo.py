"""Per-paper statcheck result cache (inc 400) — the METHODS "Statistics" per-paper cache-then-explicit-rescan
store. Content-fingerprint staleness detection: since the paper's chunks/attachments are exactly what
_run_statcheck_for_paper reads, a change to either set (a reprocess mints new chunk ids; an attachment's
checksum/availability changes) means the fingerprint no longer matches, and the read path can flag the cached
result as possibly stale without ever recomputing it itself."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import Connection, insert, select
from sqlalchemy.engine import RowMapping

from app.backend.persistence.document_roles import (
    ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES,
    normalized_document_role,
)
from app.backend.persistence.repository import get_attachments_for_paper, get_chunks_for_paper
from app.backend.persistence.schema import paper_statcheck_cache


def compute_content_fingerprint(conn: Connection, paper_id: int) -> str:
    chunks = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES)
    chunk_sig = "\x1e".join(f"{c['id']}:{c['source_attachment_checksum']}" for c in chunks)
    attachments = sorted(
        (
            row
            for row in get_attachments_for_paper(conn, paper_id)
            if normalized_document_role(row) in ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES
        ),
        key=lambda a: a["id"],
    )
    attach_sig = "\x1e".join(f"{a['id']}:{a['checksum'] or ''}:{a['availability']}" for a in attachments)
    return hashlib.sha256(f"{chunk_sig}\x00{attach_sig}".encode()).hexdigest()


def store_statcheck_cache(
    conn: Connection,
    paper_id: int,
    *,
    checked: int,
    inconsistent: int,
    decision_errors: int,
    results_json: list[dict[str, Any]],
    coverage_json: dict[str, Any],
    content_fingerprint: str,
) -> None:
    conn.execute(
        insert(paper_statcheck_cache)
        .prefix_with("OR REPLACE")
        .values(
            paper_id=paper_id,
            checked=checked,
            inconsistent=inconsistent,
            decision_errors=decision_errors,
            results_json=results_json,
            coverage_json=coverage_json,
            content_fingerprint=content_fingerprint,
        )
    )


def get_statcheck_cache(conn: Connection, paper_id: int) -> RowMapping | None:
    return (
        conn.execute(select(paper_statcheck_cache).where(paper_statcheck_cache.c.paper_id == paper_id))
        .mappings()
        .first()
    )
