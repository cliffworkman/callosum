"""Thin SQLAlchemy Core data-access helpers for initial persistence tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Connection,
    RowMapping,
    String,
    and_,
    cast,
    delete,
    exists,
    func,
    insert,
    not_,
    or_,
    select,
    update,
)

from app.backend.persistence.schema import (
    attachments,
    axes,
    chunks,
    citation_mappings,
    cluster_node_papers,
    cluster_nodes,
    embeddings,
    open_science_signals,
    paper_findings,
    paper_tags,
    papers,
    summaries,
    summary_sentences,
)

if TYPE_CHECKING:  # avoid coupling persistence to the embeddings package at import time
    from app.backend.embeddings.vector_store import VectorStore


def _paper_sort_order(sort: str) -> list:
    """ORDER BY clause for a library `sort` key (inc 69). The key indexes an ALLOWLIST (rule #3 — never
    interpolate request data into SQL); unknown keys fall back to "added". NULL year/author sort last;
    `papers.id` is always the final, stable tiebreak for deterministic pagination."""
    sorts = {
        "added": [papers.c.id.asc()],  # import order (default)
        "recent": [papers.c.id.desc()],  # most recently added first
        "title": [func.lower(papers.c.title).asc()],
        "title_desc": [func.lower(papers.c.title).desc()],
        "year_desc": [papers.c.year.is_(None), papers.c.year.desc()],  # newest publication year first
        "year_asc": [papers.c.year.is_(None), papers.c.year.asc()],
        "author": [papers.c.first_author_family_name.is_(None), func.lower(papers.c.first_author_family_name).asc()],
        "author_desc": [
            papers.c.first_author_family_name.is_(None),
            func.lower(papers.c.first_author_family_name).desc(),
        ],
    }
    order = sorts.get(sort, sorts["added"])
    return order if sort in ("added", "recent") else [*order, papers.c.id.asc()]


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


# Papers needing bibliographic review ("Unsorted"): raw PDF scaffolds + Crossref-unresolved + no source
# recorded. Mirrors ingest.py's "pdf-scaffold" + enrichment.py's CROSSREF_UNRESOLVED_SOURCE (kept as a local
# literal allowlist to avoid an enrichment→repository import cycle; rule #3 — never interpolated). (inc 79)
NEEDS_REVIEW_SOURCES = ("pdf-scaffold", "crossref-unresolved")

# Search scopes (inc 89). The key is an allowlist (never interpolated into SQL — rule #3); unknown → "all".
SEARCH_FIELDS = ("all", "title", "author", "journal")

# Library signal filters (inc 97). The `signal` param value indexes this allowlist (never interpolated — rule #3)
# → a fixed (signal_type, status) subquery against open_science_signals. A *filter* (papers to review), NOT a
# rank or score; unknown values are ignored.
SIGNAL_FILTERS = {
    "statcheck-inconsistent": ("statcheck", "inconsistent"),
    "retraction-retracted": ("retraction", "retracted"),  # inc 131: filter to papers a registry records retracted
}

# Findings review-queue filters (inc 133). `finding` value → the paper_findings.review_state to match. A *work
# state* (papers with findings the user hasn't reviewed), never a quality rank. Allowlist (rule #3).
FINDING_FILTERS = {"needs-review": "unreviewed"}


def _search_clause(field: str, pattern: str):
    """A WHERE clause for the q search, scoped by ``field``. The full bibliographic record lives in
    ``csl_json`` (every author, year, DOI, publisher, ISSN, …), so searching its text surfaces non-first
    authors + fields the scalar columns don't project — fixing the old title+first-author-only search. Cast to
    text for LIKE; the pattern is bound (rule #3)."""
    title = func.lower(papers.c.title).like(pattern)
    venue = func.lower(papers.c.venue).like(pattern)
    first_author = func.lower(papers.c.first_author_family_name).like(pattern)
    csl = func.lower(cast(papers.c.csl_json, String)).like(pattern)  # the whole record (all authors incl.)
    if field == "title":
        return title
    if field == "author":
        return or_(first_author, csl)  # csl_json["author"] has every author; the scalar is the belt-and-suspenders
    if field == "journal":
        return venue
    return or_(title, venue, first_author, func.lower(papers.c.abstract).like(pattern), csl)  # "all" — every field


def list_papers(
    conn: Connection,
    *,
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    search_field: str = "all",
    only_deleted: bool = False,
    axis_id: int | None = None,
    tag_id: int | None = None,
    item_type: str | None = None,
    needs_review: bool = False,
    signal: str | None = None,
    finding: str | None = None,
    sort: str = "added",
) -> list[RowMapping]:
    attachment_count = (
        select(func.count()).select_from(attachments).where(attachments.c.paper_id == papers.c.id).scalar_subquery()
    )
    chunk_count = select(func.count()).select_from(chunks).where(chunks.c.paper_id == papers.c.id).scalar_subquery()
    stmt = (
        select(
            papers,
            attachment_count.label("attachment_count"),
            chunk_count.label("chunk_count"),
        )
        .where(papers.c.deleted_at.is_not(None) if only_deleted else papers.c.deleted_at.is_(None))
        .order_by(*_paper_sort_order(sort))
    )
    if q:
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(_search_clause(search_field if search_field in SEARCH_FIELDS else "all", pattern))
    if axis_id is not None:
        # Filter to the papers assigned to this axis (across all its cluster nodes). Bound-param IN
        # subquery (rule #3); composes with the deleted/q filters above (trashed papers stay excluded).
        stmt = stmt.where(
            papers.c.id.in_(
                select(cluster_node_papers.c.paper_id)
                .select_from(
                    cluster_node_papers.join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
                )
                .where(cluster_nodes.c.axis_id == axis_id)
            )
        )
    if tag_id is not None:
        # Filter to the papers carrying this tag. Bound-param IN subquery (rule #3); composes with the
        # deleted/q/axis clauses above (trashed papers stay excluded).
        stmt = stmt.where(papers.c.id.in_(select(paper_tags.c.paper_id).where(paper_tags.c.tag_id == tag_id)))
    if item_type:
        # Filter to a single CSL item type (article-journal / book / posted-content / …). The value is
        # bound (rule #3 — never interpolated); the dropdown only offers types actually present (see
        # list_item_types), and this composes with the deleted/q/axis/tag clauses above.
        stmt = stmt.where(papers.c.item_type == item_type)
    if needs_review:
        # The "Unsorted" view: papers whose metadata still needs review — raw scaffolds, Crossref-unresolved,
        # or no source recorded (NULL). Bound-param IN over a local allowlist (rule #3); composes with the
        # clauses above (trashed papers stay excluded).
        stmt = stmt.where(
            or_(
                papers.c.imported_source.in_(NEEDS_REVIEW_SOURCES),
                papers.c.imported_source.is_(None),
            )
        )
    if signal in SIGNAL_FILTERS:
        # Filter to papers carrying a Methods-producer signal of a given status (inc 97) — e.g. statcheck
        # reporting inconsistencies. A bound IN-subquery (rule #3) over a fixed allowlisted (type, status) pair;
        # a *view of papers to review*, never a rank. Composes with the deleted/q/axis/tag clauses above.
        sig_type, sig_status = SIGNAL_FILTERS[signal]
        stmt = stmt.where(
            papers.c.id.in_(
                select(open_science_signals.c.paper_id).where(
                    open_science_signals.c.signal_type == sig_type,
                    open_science_signals.c.status == sig_status,
                )
            )
        )
    if finding in FINDING_FILTERS:
        # The unified "to review" queue (inc 133): papers carrying a CANDIDATE finding in a given review state
        # (v1: 'unreviewed'). The user's *work state*, never a rank. Bound IN-subquery (rule #3); composes above.
        stmt = stmt.where(
            papers.c.id.in_(
                select(paper_findings.c.paper_id).where(paper_findings.c.review_state == FINDING_FILTERS[finding])
            )
        )
    return list(conn.execute(stmt.limit(limit).offset(offset)).mappings())


def get_papers_for_export(conn: Connection, paper_ids: Sequence[int]) -> list[RowMapping]:
    """Full rows (incl. csl_json) for the given LIVE paper ids, ordered by id, for citation export (inc 70).
    Bound-param IN (rule #3); trashed papers are never exported."""
    if not paper_ids:
        return []
    stmt = (
        select(papers)
        .where(papers.c.id.in_(set(int(pid) for pid in paper_ids)), papers.c.deleted_at.is_(None))
        .order_by(papers.c.id)
    )
    return list(conn.execute(stmt).mappings())


def list_item_types(conn: Connection) -> list[RowMapping]:
    """Distinct CSL item types present among LIVE papers + a per-type count, most-common first (inc 91).
    Drives the library Type-filter dropdown so it only offers types that actually exist (honest facets)."""
    stmt = (
        select(papers.c.item_type, func.count().label("count"))
        .where(papers.c.deleted_at.is_(None), papers.c.item_type.is_not(None))
        .group_by(papers.c.item_type)
        .order_by(func.count().desc(), papers.c.item_type)
    )
    return list(conn.execute(stmt).mappings())


def list_live_paper_ids(conn: Connection) -> list[int]:
    """All live (non-trashed) paper ids — for batch Methods producers (inc 97). A light ids-only query."""
    return [int(r[0]) for r in conn.execute(select(papers.c.id).where(papers.c.deleted_at.is_(None)))]


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


def update_paper_metadata(conn: Connection, paper_id: int, **values: Any) -> None:
    if not values:
        return
    conn.execute(update(papers).where(papers.c.id == paper_id).values(**values))


def soft_delete_paper(conn: Connection, paper_id: int) -> bool:
    """Soft-delete (move to Trash): stamp deleted_at. Returns False if the paper is missing or already
    trashed. Nothing is removed — rows are kept so it's fully restorable and nothing orphans (inc 54)."""
    result = conn.execute(
        update(papers)
        .where(and_(papers.c.id == paper_id, papers.c.deleted_at.is_(None)))
        .values(deleted_at=func.current_timestamp())
    )
    return bool(result.rowcount)


def restore_paper(conn: Connection, paper_id: int) -> bool:
    """Restore from Trash: clear deleted_at. Returns False if the paper is missing or not trashed."""
    result = conn.execute(
        update(papers).where(and_(papers.c.id == paper_id, papers.c.deleted_at.is_not(None))).values(deleted_at=None)
    )
    return bool(result.rowcount)


def purge_paper(conn: Connection, paper_id: int, *, vector_store: "VectorStore") -> bool:
    """Permanently delete a TRASHED paper and everything it owns. Irreversible (inc 65).

    Only acts on a soft-deleted (in-Trash) paper — returns False if the paper is missing or still live, so a
    live paper can never be purged in one step. Deletes the paper's `embeddings` rows AND their vectors first
    (those have no FK and would otherwise orphan and crash `retrieval._resolve_hit`), then deletes the paper
    row, whose FK CASCADE removes chunks/annotations/attachments/cluster_node_papers/dismissed pairs/etc.
    Caller commits.
    """
    row = conn.execute(select(papers.c.deleted_at).where(papers.c.id == paper_id)).first()
    if row is None or row[0] is None:
        return False  # missing or not in Trash — never purge a live paper
    _purge_paper_embeddings(conn, paper_id, vector_store=vector_store)
    conn.execute(delete(papers).where(papers.c.id == paper_id))
    return True


def purge_all_trashed(conn: Connection, *, vector_store: "VectorStore") -> int:
    """Empty the Trash: permanently delete every soft-deleted paper. Returns the count purged. Caller commits."""
    ids = [int(r[0]) for r in conn.execute(select(papers.c.id).where(papers.c.deleted_at.is_not(None)))]
    for paper_id in ids:
        purge_paper(conn, paper_id, vector_store=vector_store)  # each is trashed → True
    return len(ids)


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
        conn.execute(delete(embeddings).where(embeddings.c.id.in_([int(r[0]) for r in rows])))


def compute_processing_tier(conn: Connection, paper_id: int) -> str:
    chunk_count = int(
        conn.execute(select(func.count()).select_from(chunks).where(chunks.c.paper_id == paper_id)).scalar_one()
    )
    if chunk_count > 0:
        return "fully-chunked"
    paper = get_paper(conn, paper_id)
    if paper["abstract"] or paper["doi"] or paper["year"] or paper["venue"] or paper["first_author_family_name"]:
        return "abstract-embedded"
    return "metadata-only"


def refresh_processing_tier(conn: Connection, paper_id: int) -> str:
    tier = compute_processing_tier(conn, paper_id)
    conn.execute(update(papers).where(papers.c.id == paper_id).values(processing_tier=tier))
    return tier


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
            )
            .select_from(cluster_node_papers.join(papers, papers.c.id == cluster_node_papers.c.paper_id))
            .where(cluster_node_papers.c.cluster_node_id == cluster_node_id, papers.c.deleted_at.is_(None))
            .order_by(papers.c.id)
        ).mappings()
    )


# Persistent "not a duplicate" dismissals (inc 64) live in `app/backend/persistence/dedup_repo.py`
# (extracted inc 67 to keep this module under the 600-line cap).


def list_summaries(conn: Connection, *, limit: int = 50, offset: int = 0) -> list[RowMapping]:
    sentence_count = (
        select(func.count())
        .select_from(summary_sentences)
        .where(summary_sentences.c.summary_id == summaries.c.id)
        .scalar_subquery()
    )
    verified_sentence_count = (
        select(func.count())
        .select_from(summary_sentences)
        .where(
            summary_sentences.c.summary_id == summaries.c.id,
            exists(
                select(citation_mappings.c.id).where(citation_mappings.c.summary_sentence_id == summary_sentences.c.id)
            ),
            not_(
                exists(
                    select(citation_mappings.c.id).where(
                        citation_mappings.c.summary_sentence_id == summary_sentences.c.id,
                        citation_mappings.c.status != "verified",
                    )
                )
            ),
        )
        .scalar_subquery()
    )
    stmt = (
        select(
            summaries,
            sentence_count.label("sentence_count"),
            verified_sentence_count.label("verified_sentence_count"),
            (sentence_count - verified_sentence_count).label("flagged_sentence_count"),
        )
        .order_by(summaries.c.created_at.desc(), summaries.c.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(conn.execute(stmt).mappings())


def get_summary(conn: Connection, summary_id: int) -> RowMapping:
    return _one_mapping(conn.execute(select(summaries).where(summaries.c.id == summary_id)))


def delete_summary(conn: Connection, summary_id: int) -> bool:
    result = conn.execute(delete(summaries).where(summaries.c.id == summary_id))
    return bool(result.rowcount)


def _normalize_doi(doi: str | None) -> str | None:
    if doi is None:
        return None
    normalized = doi.strip().lower()
    return normalized or None
