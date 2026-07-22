"""Thin SQLAlchemy Core data-access helpers for initial persistence tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import (
    Connection,
    RowMapping,
    and_,
    func,
    insert,
    select,
)

# Paper lifecycle/state mutators (trash, purge, read/priority, tier) live in paper_lifecycle_repo.py (extracted
# inc 220 to keep this module under the 600-line cap); re-exported so existing import sites are unchanged.
from app.backend.persistence.paper_lifecycle_repo import (  # noqa: E402,F401
    compute_processing_tier,
    delete_chunks_for_attachment,
    purge_paper,
    refresh_processing_tier,
    restore_paper,
    set_paper_priority,
    set_paper_read,
    soft_delete_paper,
    update_paper_metadata,
)
from app.backend.persistence.schema import (
    attachments,
    axes,
    chunks,
    cluster_node_papers,
    cluster_nodes,
    paper_citation_counts,
    papers,
)

# Summary (synthesis) CRUD lives in summaries_repo.py (extracted inc 220); re-exported so call sites are unchanged.
from app.backend.persistence.summaries_repo import (  # noqa: E402,F401
    delete_summary,
    get_summary,
    list_summaries,
)


def _one_mapping(result: Any) -> RowMapping:
    return result.mappings().one()


def create_paper(
    conn: Connection,
    *,
    title: str,
    csl_json: Mapping[str, Any],
    abstract: str | None = None,
    year: int | None = None,
    doi: str | None = None,
    venue: str | None = None,
    item_type: str | None = None,
    language: str | None = None,
    publication_date: str | None = None,
    first_author_family_name: str | None = None,
    imported_source: str | None = None,
    openalex_work_id: str | None = None,
    semantic_scholar_paper_id: str | None = None,
    zotero_library_id: str | None = None,
    zotero_item_key: str | None = None,
    citation_key: str | None = None,
    processing_tier: str = "metadata-only",
) -> int:
    result = conn.execute(
        insert(papers).values(
            title=title,
            abstract=abstract,
            year=year,
            doi=_normalize_doi(doi),
            venue=venue,
            item_type=item_type,
            language=language,
            publication_date=publication_date,
            first_author_family_name=first_author_family_name,
            imported_source=imported_source,
            openalex_work_id=openalex_work_id,
            semantic_scholar_paper_id=semantic_scholar_paper_id,
            zotero_library_id=zotero_library_id,
            zotero_item_key=zotero_item_key,
            citation_key=citation_key,
            csl_json=dict(csl_json),
            processing_tier=processing_tier,
        )
    )
    return int(result.inserted_primary_key[0])


def get_paper(conn: Connection, paper_id: int) -> RowMapping:
    return _one_mapping(conn.execute(select(papers).where(papers.c.id == paper_id)))


# inc 301: get_papers_for_export + list_item_types moved to paper_query_repo.py to hold this file under the 600-line
# cap (rule #1; the inc-220/262 pattern). inc 319 folded the whole library listing/filter/sort/rank cluster
# (list_papers, PRIORITY_LEVELS, get_paper_rank) in there too, for the same reason. Re-exported so call sites
# (routers, tests) still import them from `repository`.
from app.backend.persistence.paper_query_repo import (  # noqa: E402,F401
    PRIORITY_LEVELS,
    get_paper_rank,
    get_papers_for_export,
    list_item_types,
    list_papers,
    titles_for_ids,
)


def list_live_paper_ids(conn: Connection) -> list[int]:
    """All live (non-trashed) paper ids — for batch Methods producers (inc 97). A light ids-only query."""
    return [int(r[0]) for r in conn.execute(select(papers.c.id).where(papers.c.deleted_at.is_(None)))]


def list_live_papers_with_doi(conn: Connection) -> list[RowMapping]:
    """(id, doi) for live papers that have a DOI — the bounded set the citation-count batch fetches (inc 210,
    A2). DOI only: it's the reliable OpenAlex identifier; a title-search cited-by count is unreliable + costly."""
    stmt = select(papers.c.id, papers.c.doi).where(papers.c.deleted_at.is_(None), papers.c.doi.is_not(None))
    return list(conn.execute(stmt).mappings())


def upsert_citation_count(conn: Connection, paper_id: int, cited_by_count: int, *, source: str = "openalex") -> None:
    """Store/replace one paper's cited-by count (inc 210, A2). OR-REPLACE on the paper_id PK → idempotent;
    `retrieved_at` server-defaults to now (the "as of <date>" attribution). Bound params (rule #3)."""
    conn.execute(
        insert(paper_citation_counts)
        .prefix_with("OR REPLACE")
        .values(paper_id=paper_id, cited_by_count=int(cited_by_count), source=source)
    )


def get_paper_counts(conn: Connection, paper_id: int) -> RowMapping:
    return _one_mapping(
        conn.execute(
            select(
                select(func.count())
                .select_from(attachments)
                .where(attachments.c.paper_id == paper_id)
                .scalar_subquery()
                .label("attachment_count"),
                select(func.count())
                .select_from(chunks)
                .where(chunks.c.paper_id == paper_id)
                .scalar_subquery()
                .label("chunk_count"),
            )
        )
    )


def find_existing_paper_by_identity(
    conn: Connection,
    *,
    doi: str | None = None,
    openalex_work_id: str | None = None,
    semantic_scholar_paper_id: str | None = None,
    zotero_library_id: str | None = None,
    zotero_item_key: str | None = None,
    title: str | None = None,
    year: int | None = None,
    first_author_family_name: str | None = None,
) -> tuple[str, RowMapping] | None:
    """Return the first matching paper using the documented identity precedence."""
    normalized_doi = _normalize_doi(doi)
    lookups = [
        ("doi", papers.c.doi == normalized_doi if normalized_doi else None),
        ("openalex_work_id", papers.c.openalex_work_id == openalex_work_id if openalex_work_id else None),
        (
            "semantic_scholar_paper_id",
            papers.c.semantic_scholar_paper_id == semantic_scholar_paper_id if semantic_scholar_paper_id else None,
        ),
        (
            "zotero_key",
            and_(
                papers.c.zotero_library_id == zotero_library_id,
                papers.c.zotero_item_key == zotero_item_key,
            )
            if zotero_library_id and zotero_item_key
            else None,
        ),
        (
            "title_year_author",
            and_(
                papers.c.title == title,
                papers.c.year == year,
                papers.c.first_author_family_name == first_author_family_name,
            )
            if title and year and first_author_family_name
            else None,
        ),
    ]

    for reason, predicate in lookups:
        if predicate is None:
            continue
        row = conn.execute(select(papers).where(predicate).limit(1)).mappings().first()
        if row is not None:
            return reason, row
    return None


def create_attachment(
    conn: Connection,
    *,
    paper_id: int,
    storage_mode: str,
    availability: str,
    content_type: str,
    original_path: str | None = None,
    resolved_path: str | None = None,
    checksum: str | None = None,
    file_size: int | None = None,
    import_source: str | None = None,
    attachment_type: str | None = None,
    role: str | None = None,
) -> int:
    result = conn.execute(
        insert(attachments).values(
            paper_id=paper_id,
            storage_mode=storage_mode,
            availability=availability,
            original_path=original_path,
            resolved_path=resolved_path,
            checksum=checksum,
            file_size=file_size,
            content_type=content_type,
            import_source=import_source,
            attachment_type=attachment_type,
            role=role,
        )
    )
    return int(result.inserted_primary_key[0])


def get_attachments_for_paper(conn: Connection, paper_id: int) -> list[RowMapping]:
    return list(conn.execute(select(attachments).where(attachments.c.paper_id == paper_id)).mappings())


def create_chunk(
    conn: Connection,
    *,
    paper_id: int,
    attachment_id: int,
    text: str,
    page_start: int,
    page_end: int,
    bbox_coordinate_system: str,
    extraction_tool: str,
    extraction_version: str,
    chunking_strategy: str,
    chunk_version: str,
    source_attachment_checksum: str,
    section: str | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
    bbox_json: Mapping[str, Any] | list[Any] | None = None,
) -> int:
    result = conn.execute(
        insert(chunks).values(
            paper_id=paper_id,
            attachment_id=attachment_id,
            text=text,
            section=section,
            page_start=page_start,
            page_end=page_end,
            char_start=char_start,
            char_end=char_end,
            bbox_json=bbox_json,
            bbox_coordinate_system=bbox_coordinate_system,
            extraction_tool=extraction_tool,
            extraction_version=extraction_version,
            chunking_strategy=chunking_strategy,
            chunk_version=chunk_version,
            source_attachment_checksum=source_attachment_checksum,
        )
    )
    return int(result.inserted_primary_key[0])


def get_chunks_for_paper(
    conn: Connection, paper_id: int, *, limit: int | None = None, offset: int = 0
) -> list[RowMapping]:
    stmt = select(chunks).where(chunks.c.paper_id == paper_id).order_by(chunks.c.id)
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return list(conn.execute(stmt).mappings())


def list_axes(conn: Connection) -> list[RowMapping]:
    return list(conn.execute(select(axes).order_by(axes.c.id)).mappings())


def get_axis(conn: Connection, axis_id: int) -> RowMapping | None:
    return conn.execute(select(axes).where(axes.c.id == axis_id)).mappings().first()


def get_cluster_nodes_for_axis(conn: Connection, axis_id: int) -> list[RowMapping]:
    return list(
        conn.execute(
            select(cluster_nodes)
            .where(cluster_nodes.c.axis_id == axis_id)
            .order_by(cluster_nodes.c.parent_id.is_not(None), cluster_nodes.c.parent_id, cluster_nodes.c.id)
        ).mappings()
    )


def get_papers_for_cluster_node(conn: Connection, cluster_node_id: int) -> list[RowMapping]:
    return list(
        conn.execute(
            select(
                papers.c.id,
                papers.c.title,
                cluster_node_papers.c.confidence,
                cluster_node_papers.c.position,  # A7 (inc 211): manual order on a curated axis (NULL on keyword axes)
            )
            .select_from(cluster_node_papers.join(papers, papers.c.id == cluster_node_papers.c.paper_id))
            .where(cluster_node_papers.c.cluster_node_id == cluster_node_id, papers.c.deleted_at.is_(None))
            # A7: curated axes order by `position`; keyword axes (all-NULL position) fall back to papers.id (unchanged).
            .order_by(cluster_node_papers.c.position.is_(None), cluster_node_papers.c.position, papers.c.id)
        ).mappings()
    )


# Persistent "not a duplicate" dismissals (inc 64) live in `app/backend/persistence/dedup_repo.py`
# (extracted inc 67 to keep this module under the 600-line cap).


def _normalize_doi(doi: str | None) -> str | None:
    if doi is None:
        return None
    normalized = doi.strip().lower()
    return normalized or None
