"""Paper lifecycle / state data-access — extracted from repository.py (inc 220, to keep it under the 600-line cap).

A cohesive cluster: the generic metadata update, the Trash lifecycle (soft-delete / restore / permanent purge +
its embedding/vector cleanup), the user reading-state mutators (read/priority, inc 220), and the processing-tier
recompute. Re-exported from ``repository`` so existing ``from …repository import soft_delete_paper`` call sites are
unchanged (the inc-137 schema_findings / inc-67 dedup_repo pattern). Bound-param SQLAlchemy Core (rule #3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Connection, and_, delete, exists, func, or_, select, update

from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import attachments, chunks, embeddings, merge_operations, papers
from app.backend.persistence.sqlite_retry import retry_sqlite_locked

if TYPE_CHECKING:  # avoid coupling persistence to the embeddings package at import time
    from app.backend.embeddings.vector_store import VectorStore


def update_paper_metadata(conn: Connection, paper_id: int, **values: Any) -> None:
    if not values:
        return
    _write(conn, update(papers).where(papers.c.id == paper_id).values(**values))


def soft_delete_paper(conn: Connection, paper_id: int) -> bool:
    """Soft-delete (move to Trash): stamp deleted_at. Returns False if the paper is missing or already
    trashed. Nothing is removed — rows are kept so it's fully restorable and nothing orphans (inc 54)."""
    result = _write(
        conn,
        update(papers)
        .where(and_(papers.c.id == paper_id, papers.c.deleted_at.is_(None)))
        .values(deleted_at=func.current_timestamp()),
    )
    return bool(result.rowcount)


def restore_paper(conn: Connection, paper_id: int) -> bool:
    """Restore from Trash: clear deleted_at. Returns False if the paper is missing or not trashed."""
    result = _write(
        conn,
        update(papers).where(and_(papers.c.id == paper_id, papers.c.deleted_at.is_not(None))).values(deleted_at=None),
    )
    return bool(result.rowcount)


def set_paper_read(conn: Connection, paper_id: int, read: bool) -> bool:
    """Mark a paper read (stamp read_at = now) or unread (clear it) — a manual user toggle (inc 220). Returns
    False if the paper doesn't exist. Caller commits."""
    result = _write(
        conn,
        update(papers).where(papers.c.id == paper_id).values(read_at=func.current_timestamp() if read else None),
    )
    return bool(result.rowcount)


def set_paper_priority(conn: Connection, paper_id: int, priority: str | None) -> bool:
    """Set the user's reading priority ("high"/"normal"/"low") or clear it (None) — a hand-set triage label,
    never an AI score (inc 220). The caller validates ``priority`` against PRIORITY_LEVELS. Returns False if the
    paper doesn't exist. Caller commits."""
    result = _write(conn, update(papers).where(papers.c.id == paper_id).values(priority=priority))
    return bool(result.rowcount)


def purge_paper(conn: Connection, paper_id: int, *, vector_store: "VectorStore") -> bool:
    """Permanently delete a TRASHED paper and everything it owns. Irreversible (inc 65).

    Only acts on a soft-deleted (in-Trash) paper — returns False if the paper is missing or still live, so a
    live paper can never be purged in one step. Deletes the paper's `embeddings` rows AND their vectors first
    (those have no FK and would otherwise orphan and crash `retrieval._resolve_hit`), then deletes the paper
    row, whose FK CASCADE removes chunks/annotations/attachments/cluster_node_papers/dismissed pairs/etc.
    Caller commits.
    """
    row = conn.execute(select(papers.c.deleted_at, papers.c.merged_into).where(papers.c.id == paper_id)).first()
    if row is None or row[0] is None or row[1] is not None:
        return False  # missing, not in Trash, or merged-away (un-merge first — never orphan the undo record, #17)
    active_canonical = conn.execute(
        select(func.count())
        .select_from(merge_operations)
        .where(merge_operations.c.canonical_paper_id == paper_id, merge_operations.c.status == "active")
    ).scalar_one()
    if active_canonical:
        return False  # survivor of an active merge — un-merge before purging (no dangling merged_into on #17)
    _purge_paper_embeddings(conn, paper_id, vector_store=vector_store)
    _write(conn, delete(papers).where(papers.c.id == paper_id))
    return True


def purgeable_trashed_paper_ids(conn: Connection, *, paper_id: int | None = None) -> list[int]:
    """Return trashed, non-merged papers that are not the survivor of an active merge."""
    active_merge = exists(
        select(merge_operations.c.id).where(
            merge_operations.c.canonical_paper_id == papers.c.id,
            merge_operations.c.status == "active",
        )
    )
    conditions = [papers.c.deleted_at.is_not(None), papers.c.merged_into.is_(None), ~active_merge]
    if paper_id is not None:
        conditions.append(papers.c.id == paper_id)
    return [int(row[0]) for row in conn.execute(select(papers.c.id).where(and_(*conditions)))]


def _purge_paper_embeddings(conn: Connection, paper_id: int, *, vector_store: "VectorStore") -> None:
    # The polymorphic `embeddings` table has no FK: a paper's vectors are its own paper-embedding plus one per
    # chunk. Collect them, drop each vector from the store (by embedding id), then delete the embedding rows.
    chunk_ids = [int(r[0]) for r in conn.execute(select(chunks.c.id).where(chunks.c.paper_id == paper_id))]
    conditions = [and_(embeddings.c.target_type == "paper", embeddings.c.target_id == paper_id)]
    if chunk_ids:
        conditions.append(and_(embeddings.c.target_type == "chunk", embeddings.c.target_id.in_(chunk_ids)))
    rows = conn.execute(select(embeddings.c.id, embeddings.c.dimension).where(or_(*conditions))).all()
    for embedding_id, dimension in rows:
        vector_store.delete(conn, embedding_id=int(embedding_id), dimension=int(dimension))
    if rows:
        _write(conn, delete(embeddings).where(embeddings.c.id.in_([int(r[0]) for r in rows])))


def delete_chunks_for_attachment(
    conn: Connection, paper_id: int, attachment_id: int, *, vector_store: "VectorStore"
) -> list[int]:
    """Delete chunks owned by one attachment, including their non-FK embedding rows and vectors.

    Used by PDF text reprocessing: the paper, attachment, annotations, tags, notes, and metadata survive; only the
    stale extracted-text rows for the selected local PDF are replaced. Caller commits.
    """
    chunk_ids = [
        int(r[0])
        for r in conn.execute(
            select(chunks.c.id).where(and_(chunks.c.paper_id == paper_id, chunks.c.attachment_id == attachment_id))
        )
    ]
    if not chunk_ids:
        return []
    rows = conn.execute(
        select(embeddings.c.id, embeddings.c.dimension).where(
            and_(embeddings.c.target_type == "chunk", embeddings.c.target_id.in_(chunk_ids))
        )
    ).all()
    for embedding_id, dimension in rows:
        vector_store.delete(conn, embedding_id=int(embedding_id), dimension=int(dimension))
    if rows:
        _write(conn, delete(embeddings).where(embeddings.c.id.in_([int(r[0]) for r in rows])))
    _write(conn, delete(chunks).where(and_(chunks.c.paper_id == paper_id, chunks.c.attachment_id == attachment_id)))
    return chunk_ids


def compute_processing_tier(conn: Connection, paper_id: int) -> str:
    chunk_count = int(
        conn.execute(
            select(func.count())
            .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
            .where(chunks.c.paper_id == paper_id, attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
        ).scalar_one()
    )
    if chunk_count > 0:
        return "fully-chunked"
    paper = (
        conn.execute(
            select(
                papers.c.abstract, papers.c.doi, papers.c.year, papers.c.venue, papers.c.first_author_family_name
            ).where(papers.c.id == paper_id)
        )
        .mappings()
        .one()
    )
    if paper["abstract"] or paper["doi"] or paper["year"] or paper["venue"] or paper["first_author_family_name"]:
        return "abstract-embedded"
    return "metadata-only"


def refresh_processing_tier(conn: Connection, paper_id: int) -> str:
    tier = compute_processing_tier(conn, paper_id)
    _write(conn, update(papers).where(papers.c.id == paper_id).values(processing_tier=tier))
    return tier


def _write(conn: Connection, statement):
    return retry_sqlite_locked(lambda: conn.execute(statement))
