"""Reads and writes for derived chunk structure (inc 577, H1a).

Idempotent by construction: a row is keyed by ``chunk_id`` and carries the ``(raw_sha,
chunk_version)`` it was derived from, so re-running the backfill replaces rather than duplicates,
and a row whose source text has changed is recognisably stale instead of silently masquerading as
current.

Read on the retrieval path only as a deprioritization/disagreement signal (inc 581 faceted seam; the
reference-eligibility repair via ``structure_role_states``) -- never as a hard exclusion.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.engine import Connection
from sqlalchemy.sql.elements import ColumnElement

from app.backend.pdf_processing.chunk_structure import ChunkStructure
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import attachments, chunks
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION, chunk_structure
from app.backend.persistence.sql_batch import in_batches

# The population the source-role derivation is responsible for (inc 425/613): article full-text chunks only.
# Preregistration, protocol, supplement and other attachments are never classified, so they must never count
# towards currentness either (inc 614) -- otherwise a paper with such an attachment can never become current.
CLASSIFIED_DOCUMENT_ROLES = ARTICLE_DOCUMENT_ROLES


def classified_chunks_clause() -> ColumnElement[bool]:
    """Predicate over ``chunks JOIN attachments`` selecting exactly the chunks the derivation classifies.

    Shared by the derivation's row selection and by ``papers_with_current_structure`` so the two
    populations cannot drift apart.
    """
    return attachment_document_role_clause(CLASSIFIED_DOCUMENT_ROLES)


def raw_sha(text: str) -> str:
    """FULL sha256 of the chunk text. Not a prefix: this decides staleness, and a full digest costs
    nothing here while removing the collision argument outright."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredStructure:
    chunk_id: int
    chunk_type: str
    evidence_role: str
    reason_codes: list[str]
    confidence: float | None
    derivation_version: str
    raw_sha: str
    chunk_version: str
    reference_region: bool | None
    reference_region_source: str | None
    repeated_boilerplate: bool | None
    is_stale: bool


def replace_paper_structure(
    conn: Connection,
    *,
    paper_id: int,
    results: Iterable[ChunkStructure],
    source: dict[int, tuple[str, str]],
) -> int:
    """Replace one paper's derived rows. ``source`` maps chunk_id -> (raw_sha, chunk_version).

    Scoped to the paper so an interrupted backfill leaves every other paper untouched, and so a
    re-run is a clean replace rather than an accumulating merge.
    """
    rows = []
    for result in results:
        if result.chunk_id not in source:
            continue
        sha, version = source[result.chunk_id]
        rows.append(
            {
                "chunk_id": result.chunk_id,
                "chunk_type": result.chunk_type,
                "evidence_role": result.evidence_role,
                "reason_codes_json": json.dumps(result.reason_codes),
                "confidence": result.confidence,
                "derivation_version": result.derivation_version,
                "raw_sha": sha,
                "chunk_version": version,
                "reference_region": None if result.reference_region is None else int(result.reference_region),
                "reference_region_source": result.reference_region_source,
                "repeated_boilerplate": (
                    None if result.repeated_boilerplate is None else int(result.repeated_boilerplate)
                ),
            }
        )
    if not rows:
        return 0
    existing = select(chunks.c.id).where(chunks.c.paper_id == paper_id)
    conn.execute(delete(chunk_structure).where(chunk_structure.c.chunk_id.in_(existing)))
    conn.execute(chunk_structure.insert(), rows)
    return len(rows)


def structure_for_chunk(conn: Connection, chunk_id: int) -> StoredStructure | None:
    """One chunk's derived structure, with staleness resolved against the live chunk row."""
    row = (
        conn.execute(
            select(
                chunk_structure,
                chunks.c.text.label("live_text"),
                chunks.c.chunk_version.label("live_version"),
            )
            .select_from(chunk_structure.join(chunks, chunks.c.id == chunk_structure.c.chunk_id))
            .where(chunk_structure.c.chunk_id == chunk_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    stale = row["raw_sha"] != raw_sha(row["live_text"] or "") or row["chunk_version"] != (row["live_version"] or "")
    return StoredStructure(
        chunk_id=int(row["chunk_id"]),
        chunk_type=row["chunk_type"],
        evidence_role=row["evidence_role"],
        reason_codes=json.loads(row["reason_codes_json"] or "[]"),
        confidence=row["confidence"],
        derivation_version=row["derivation_version"],
        raw_sha=row["raw_sha"],
        chunk_version=row["chunk_version"],
        reference_region=None if row["reference_region"] is None else bool(row["reference_region"]),
        reference_region_source=row["reference_region_source"],
        repeated_boilerplate=(None if row["repeated_boilerplate"] is None else bool(row["repeated_boilerplate"])),
        is_stale=stale,
    )


def current_structure_roles(
    conn: Connection,
    chunk_ids: list[int],
    *,
    derivation_version: str = DERIVATION_VERSION,
) -> dict[int, tuple[str, str]]:
    """``{chunk_id: (chunk_type, evidence_role)}`` for chunks whose derived structure is present AND
    current (matching ``derivation_version`` and the live ``(raw_sha, chunk_version)``).

    Used ONLY by the broad-Ask evidence-hygiene seam (inc 581) as a **deprioritization** signal --
    the H1a study found no reason code clears the >=95% precision gate, so this is never a hard
    exclusion. A missing or stale row is simply omitted: the caller treats an absent chunk as
    ``unknown`` at full priority, so the seam degrades to a safe no-op on an un-backfilled library
    and can neither delete nor manufacture evidence. ``chunk_ids`` is bounded by the retrieval budget
    (a few dozen), well under any SQLite variable limit.
    """
    if not chunk_ids:
        return {}
    rows = conn.execute(
        select(
            chunk_structure.c.chunk_id,
            chunk_structure.c.chunk_type,
            chunk_structure.c.evidence_role,
            chunk_structure.c.raw_sha,
            chunk_structure.c.chunk_version.label("derived_version"),
            chunk_structure.c.derivation_version,
            chunks.c.text.label("live_text"),
            chunks.c.chunk_version.label("live_version"),
        )
        .select_from(chunk_structure.join(chunks, chunks.c.id == chunk_structure.c.chunk_id))
        .where(chunk_structure.c.chunk_id.in_(chunk_ids))
    ).mappings()
    out: dict[int, tuple[str, str]] = {}
    for row in rows:
        current = (
            row["derivation_version"] == derivation_version
            and row["raw_sha"] == raw_sha(row["live_text"] or "")
            and row["derived_version"] == (row["live_version"] or "")
        )
        if current:
            out[int(row["chunk_id"])] = (row["chunk_type"], row["evidence_role"])
    return out


@dataclass(frozen=True)
class RoleState:
    """One chunk's stored structure judged against its live text: ``state`` is ``current`` or ``stale``."""

    chunk_id: int
    state: str
    chunk_type: str
    evidence_role: str
    reference_region_source: str | None
    stale_reason: str | None
    raw_sha: str


def structure_role_states(
    conn: Connection,
    chunk_ids: Iterable[int],
    *,
    derivation_version: str = DERIVATION_VERSION,
) -> dict[int, RoleState]:
    """Like ``current_structure_roles`` but keeps stale rows, labelled with WHY they are stale.

    Used by the reference-eligibility seam, which must record (not silently reuse or drop) a classification
    whose text, chunk version or derivation version no longer matches. A chunk with no row is absent from the
    result. Batched through ``sql_batch`` so an arbitrarily large id set never exceeds SQLite's variable limit.
    """
    out: dict[int, RoleState] = {}
    for batch in in_batches(sorted({int(i) for i in chunk_ids})):
        rows = conn.execute(
            select(
                chunk_structure.c.chunk_id,
                chunk_structure.c.chunk_type,
                chunk_structure.c.evidence_role,
                chunk_structure.c.reference_region_source,
                chunk_structure.c.raw_sha,
                chunk_structure.c.chunk_version.label("derived_version"),
                chunk_structure.c.derivation_version,
                chunks.c.text.label("live_text"),
                chunks.c.chunk_version.label("live_version"),
            )
            .select_from(chunk_structure.join(chunks, chunks.c.id == chunk_structure.c.chunk_id))
            .where(chunk_structure.c.chunk_id.in_(batch))
        ).mappings()
        for row in rows:
            reason = None
            if row["derivation_version"] != derivation_version:
                reason = "derivation_version"
            elif row["raw_sha"] != raw_sha(row["live_text"] or ""):
                reason = "text_hash"
            elif row["derived_version"] != (row["live_version"] or ""):
                reason = "chunk_version"
            out[int(row["chunk_id"])] = RoleState(
                int(row["chunk_id"]),
                "stale" if reason else "current",
                row["chunk_type"],
                row["evidence_role"],
                row["reference_region_source"],
                reason,
                row["raw_sha"],
            )
    return out


def papers_with_classified_chunks(conn: Connection) -> set[int]:
    """Papers holding at least one chunk the derivation is responsible for (``classified_chunks_clause``)."""
    stmt = (
        select(chunks.c.paper_id)
        .distinct()
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(classified_chunks_clause())
    )
    return {int(r[0]) for r in conn.execute(stmt)}


def papers_with_current_structure(conn: Connection, derivation_version: str) -> set[int]:
    """Papers whose every *classified* chunk has a current row at this derivation version.

    A paper with any missing or stale row is absent, so the backfill re-derives it. This is what
    makes an interrupted run resumable without a cursor. Only the population the derivation
    classifies counts (``classified_chunks_clause``); a paper with no such chunk is never current
    and never a derivation target either (see ``papers_with_classified_chunks``).
    """
    rows = conn.execute(
        select(
            chunks.c.paper_id,
            chunks.c.id,
            chunks.c.text,
            chunks.c.chunk_version,
            chunk_structure.c.raw_sha,
            chunk_structure.c.chunk_version.label("derived_version"),
            chunk_structure.c.derivation_version,
        )
        .select_from(
            chunks.join(attachments, attachments.c.id == chunks.c.attachment_id).outerjoin(
                chunk_structure, chunk_structure.c.chunk_id == chunks.c.id
            )
        )
        .where(classified_chunks_clause())
    ).mappings()
    incomplete: set[int] = set()
    seen: set[int] = set()
    for row in rows:
        paper_id = int(row["paper_id"])
        seen.add(paper_id)
        current = (
            row["raw_sha"] is not None
            and row["derivation_version"] == derivation_version
            and row["raw_sha"] == raw_sha(row["text"] or "")
            and row["derived_version"] == (row["chunk_version"] or "")
        )
        if not current:
            incomplete.add(paper_id)
    return seen - incomplete
