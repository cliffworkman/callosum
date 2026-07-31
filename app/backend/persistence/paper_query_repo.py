"""Read-only paper list/query helpers extracted from ``repository.py`` to hold it under the 600-line cap (inc 301;
the inc-137/220/262 leaf-extraction pattern). Re-exported from ``repository`` so existing call sites are unchanged.
Bound-param SQLAlchemy Core only (rule #3).

inc 319 folded the library listing/filter/sort/rank cluster in here too (`list_papers`, `_paper_filter_clauses`,
`_paper_sort_order`, `_search_clause`, the signal/finding allowlists, and the new `get_paper_rank`) -- it was about
to push `repository.py` over the cap again, and it belongs with the other read-only paper-query helpers.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Connection, RowMapping, String, and_, case, cast, func, or_, select

from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import (
    attachments,
    axes,
    chunks,
    cluster_node_papers,
    cluster_nodes,
    open_science_signals,
    paper_citation_counts,
    paper_findings,
    paper_tags,
    papers,
    tags,
)

# User-set reading priority (inc 220). A personal triage label the user sets BY HAND -- never an AI score/rank
# (the inc-207 declined-ratings logic: a user dimension, like a color tag, not a composite). Allowlist (rule #3);
# NULL = unset. The CASE ranks high->low->unset for the explicit "By priority" sort.
PRIORITY_LEVELS = ("high", "normal", "low")
_PRIORITY_RANK = case(
    (papers.c.priority == "high", 0), (papers.c.priority == "normal", 1), (papers.c.priority == "low", 2), else_=3
)

# Papers needing bibliographic review ("Unsorted"): raw PDF scaffolds + Crossref-unresolved + no source
# recorded. Mirrors ingest.py's "pdf-scaffold" + enrichment.py's CROSSREF_UNRESOLVED_SOURCE (kept as a local
# literal allowlist to avoid an enrichment->repository import cycle; rule #3 -- never interpolated). (inc 79)
NEEDS_REVIEW_SOURCES = ("pdf-scaffold", "crossref-unresolved")

# Search scopes (inc 89). The key is an allowlist (never interpolated into SQL -- rule #3); unknown -> "all".
SEARCH_FIELDS = ("all", "title", "author", "journal")

# Library signal filters (inc 97). The `signal` param value indexes this allowlist (never interpolated -- rule #3)
# -> a fixed (signal_type, source|None, status) subquery against open_science_signals. A *filter* (papers to review),
# NOT a rank or score; unknown values are ignored. `source=None` matches any source (the inc-97/131 one-row-per-paper
# producers); a per-disclosure producer (transparency, inc 251 -- one row per (paper, disclosure)) pins the source.
SIGNAL_FILTERS = {
    "statcheck-inconsistent": ("statcheck", None, "inconsistent"),
    "retraction-retracted": ("retraction", None, "retracted"),  # inc 131: papers a registry records retracted
    # Positive transparency signal: papers where the auditor detected a data-availability disclosure. This is a
    # checkable evidence list, not a score or openness verdict.
    "transparency-data-detected": ("transparency", "data_availability", "detected"),
    # inc 251 (#44): transparency review queues -- papers where the auditor RAN but didn't detect a disclosure in
    # the text ("not detected -- go look"), NEVER "papers that hide their data" (the A-A no-accusation boundary).
    # Each pins (signal_type, disclosure_key, status). A `not-applicable` row (e.g. registration for a non-trial
    # paper) is never in a `not-detected` queue -- precondition-scoping for free.
    "transparency-data-not-detected": ("transparency", "data_availability", "not-detected"),
    "transparency-code-not-detected": ("transparency", "code_availability", "not-detected"),
    "transparency-coi-not-detected": ("transparency", "conflict_of_interest", "not-detected"),
    "transparency-funding-not-detected": ("transparency", "funding", "not-detected"),
    "transparency-registration-not-detected": ("transparency", "registration", "not-detected"),
    "transparency-preregistration-not-detected": ("transparency", "preregistration", "not-detected"),
    # upon_request has no "not detected" meaning (its absence is the norm) -- the review signal is its PRESENCE
    # ("data/code offered only upon request", a weaker-openness prompt to review), not an accusation.
    "transparency-upon-request": ("transparency", "upon_request", "detected"),
    # backlog #23 (F1): a detected mixed-model paper missing ≥1 reporting item — a completeness gap, never a
    # verdict on the modelling itself.
    "lmm-incomplete": ("lmm", None, "incomplete"),
    "meta-incomplete": ("meta", None, "incomplete"),
    # backlog #23 (F1): a detectably-Bayesian paper with ≥1 BF-reproduction mismatch or reporting-completeness
    # gap — combines two independent signals from the one auditor (methods/bayes.py::apply_bayes).
    "bayes-flagged": ("bayes", None, "flagged"),
}

# Findings review-queue filters (inc 133). `finding` value -> the paper_findings.review_state to match. A *work
# state* (papers with findings the user hasn't reviewed), never a quality rank. Allowlist (rule #3).
FINDING_FILTERS = {"needs-review": "unreviewed"}

# The default axis assignment cutoff (inc 45; mirrors routers/axes.py + discovery/relevance.py). A NULL
# axes.scoring_gain means "use this default". Used by the axis_hide_uncertain library filter (A10) so the
# library view matches the axis card's assigned-only view: shown in the card == filtered into the library.
DEFAULT_AXIS_CUTOFF = 0.35


def _cited_by_subquery():
    """Correlated scalar subquery: a paper's OpenAlex cited-by count (NULL if not fetched). Reused by the
    list projection (the card chip) and the explicit "Most cited" sort (inc 210, A2)."""
    return (
        select(paper_citation_counts.c.cited_by_count)
        .where(paper_citation_counts.c.paper_id == papers.c.id)
        .scalar_subquery()
    )


def _cited_by_as_of_subquery():
    return (
        select(paper_citation_counts.c.retrieved_at)
        .where(paper_citation_counts.c.paper_id == papers.c.id)
        .scalar_subquery()
    )


def _retraction_status_subquery():
    """Stored retraction check status for the card badge. A status is a registry signal, not a verdict."""
    return (
        select(open_science_signals.c.status)
        .where(open_science_signals.c.paper_id == papers.c.id, open_science_signals.c.signal_type == "retraction")
        .scalar_subquery()
    )


def _evidence_linked_correction_subquery():
    """Whether the correction producer projected its evidence-linked, read-only system tag."""
    return (
        select(paper_tags.c.paper_id)
        .select_from(paper_tags.join(tags, tags.c.id == paper_tags.c.tag_id))
        .where(
            paper_tags.c.paper_id == papers.c.id,
            tags.c.name == "system:self-correction:correction",
        )
        .exists()
    )


def _paper_sort_order(sort: str) -> list:
    """ORDER BY clause for a library `sort` key (inc 69). The key indexes an ALLOWLIST (rule #3 -- never
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
        # Most cited (inc 210, A2): an EXPLICIT, user-chosen sort by the OpenAlex cited-by count -- never the
        # default (no silent rank, Principles #2/#7). Papers without a fetched count sort last.
        "citations_desc": [_cited_by_subquery().is_(None), _cited_by_subquery().desc()],
        # By priority (inc 220): an EXPLICIT, user-chosen sort -- high -> normal -> low -> unset. The user's own
        # triage order, never the default and never an AI rank. Within each tier (esp. the unset bucket) fall back
        # to recency (id DESC, the same proxy "recent" uses) so a large unset tier isn't one oldest-first block
        # (inc 223 -- experience-pass finding #4); the global id ASC tail below stays as the pagination tiebreak.
        "priority": [_PRIORITY_RANK.asc(), papers.c.id.desc()],
        # Unread first (inc 220, experience-pass): the cap-free interim for "come back to what's unread" until the
        # header filter facet lands. read_at IS NULL (unread) sorts before read; a user-chosen order, never default.
        "unread": [papers.c.read_at.is_not(None)],
    }
    order = sorts.get(sort, sorts["added"])
    return order if sort in ("added", "recent") else [*order, papers.c.id.asc()]


def _search_clause(field: str, pattern: str):
    """A WHERE clause for the q search, scoped by ``field``. The full bibliographic record lives in
    ``csl_json`` (every author, year, DOI, publisher, ISSN, ...), so searching its text surfaces non-first
    authors + fields the scalar columns don't project. Cast to text for LIKE; the pattern is bound (rule #3)."""
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
    return or_(title, venue, first_author, func.lower(papers.c.abstract).like(pattern), csl)  # "all" -- every field


def _paper_filter_clauses(
    conn: Connection,
    stmt,
    *,
    only_deleted: bool = False,
    q: str | None = None,
    search_field: str = "all",
    axis_id: int | None = None,
    axis_hide_uncertain: bool = False,
    tag_id: int | None = None,
    item_type: str | None = None,
    needs_review: bool = False,
    signal: str | None = None,
    finding: str | None = None,
    read_status: str | None = None,
    priority: str | None = None,
    missing_pdf: bool = False,
):
    """Apply the library's full filter contract to any base ``stmt`` selecting from ``papers`` -- the deleted-scope
    condition plus every conditional facet (q/axis/tag/item_type/needs_review/signal/finding/read_status/priority/
    missing_pdf). Shared by `list_papers` (adds order_by + limit/offset) and `get_paper_rank` (adds a row_number()
    window) so the two can never drift apart -- correctness-critical, not just DRY: the library's "reveal the
    selected paper" feature (inc 319) depends on both answering the exact same "does this paper match" question."""
    stmt = stmt.where(
        # Trash view excludes merged-away papers (deleted_at + merged_into): restoring one must route through
        # un-merge, not a plain restore, so it never appears here as naively-restorable (#17).
        and_(papers.c.deleted_at.is_not(None), papers.c.merged_into.is_(None))
        if only_deleted
        else papers.c.deleted_at.is_(None)
    )
    if q:
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(_search_clause(search_field if search_field in SEARCH_FIELDS else "all", pattern))
    if axis_id is not None:
        # Filter to the papers assigned to this axis (across all its cluster nodes). Bound-param IN
        # subquery (rule #3); composes with the deleted/q filters above (trashed papers stay excluded).
        members = (
            select(cluster_node_papers.c.paper_id)
            .select_from(
                cluster_node_papers.join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
            )
            .where(cluster_nodes.c.axis_id == axis_id)
        )
        if axis_hide_uncertain:
            # Match the axis card's hide-uncertain (assigned-only) view (inc 45/A10): assigned = manual
            # (confidence NULL) OR confidence >= the axis's cutoff (axes.scoring_gain, else the default), so
            # the count and contents shown on the card == what lands in the library -- shown is summarized.
            gain = conn.execute(select(axes.c.scoring_gain).where(axes.c.id == axis_id)).scalar()
            cutoff = float(gain) if gain is not None else DEFAULT_AXIS_CUTOFF
            members = members.where(
                or_(cluster_node_papers.c.confidence.is_(None), cluster_node_papers.c.confidence >= cutoff)
            )
        stmt = stmt.where(papers.c.id.in_(members))
    if tag_id is not None:
        # Filter to the papers carrying this tag. Bound-param IN subquery (rule #3); composes with the
        # deleted/q/axis clauses above (trashed papers stay excluded).
        stmt = stmt.where(papers.c.id.in_(select(paper_tags.c.paper_id).where(paper_tags.c.tag_id == tag_id)))
    if item_type:
        # Filter to a single CSL item type (article-journal / book / posted-content / ...). The value is
        # bound (rule #3 -- never interpolated); the dropdown only offers types actually present (see
        # list_item_types), and this composes with the deleted/q/axis/tag clauses above.
        stmt = stmt.where(papers.c.item_type == item_type)
    if needs_review:
        # The "Unsorted" view: papers whose metadata still needs review -- raw scaffolds, Crossref-unresolved,
        # or no source recorded (NULL). Bound-param IN over a local allowlist (rule #3); composes with the
        # clauses above (trashed papers stay excluded).
        stmt = stmt.where(
            or_(
                papers.c.imported_source.in_(NEEDS_REVIEW_SOURCES),
                papers.c.imported_source.is_(None),
            )
        )
    if signal in SIGNAL_FILTERS:
        # Filter to papers carrying a Methods-producer signal of a given status (inc 97) -- e.g. statcheck
        # reporting inconsistencies. A bound IN-subquery (rule #3) over a fixed allowlisted (type, status) pair;
        # a *view of papers to review*, never a rank. Composes with the deleted/q/axis/tag clauses above.
        sig_type, sig_source, sig_status = SIGNAL_FILTERS[signal]
        conds = [
            open_science_signals.c.signal_type == sig_type,
            open_science_signals.c.status == sig_status,
        ]
        if sig_source is not None:  # a per-disclosure producer (transparency) pins the source; inc-97/131 don't
            conds.append(open_science_signals.c.source == sig_source)
        stmt = stmt.where(papers.c.id.in_(select(open_science_signals.c.paper_id).where(*conds)))
    if finding in FINDING_FILTERS:
        # The unified "to review" queue (inc 133): papers carrying a CANDIDATE finding in a given review state
        # (v1: 'unreviewed'). The user's *work state*, never a rank. Bound IN-subquery (rule #3); composes above.
        stmt = stmt.where(
            papers.c.id.in_(
                select(paper_findings.c.paper_id).where(paper_findings.c.review_state == FINDING_FILTERS[finding])
            )
        )
    if read_status == "read":
        stmt = stmt.where(papers.c.read_at.is_not(None))  # the user marked it read (inc 220)
    elif read_status == "unread":
        stmt = stmt.where(papers.c.read_at.is_(None))
    if priority in PRIORITY_LEVELS:
        stmt = stmt.where(papers.c.priority == priority)  # bound value over the allowlist (rule #3)
    if missing_pdf:
        # Papers with no local PDF to read/extract -- a factual "you still need the PDF" facet mirroring the
        # Text-Health `no_local_pdf` flag: NOT EXISTS a PDF attachment (content_type/attachment_type) with a resolved
        # local path. Bound/parameterized (rule #3); composes with the deleted/q/type/read/priority clauses above.
        pdf_present = select(attachments.c.id).where(
            attachments.c.paper_id == papers.c.id,
            or_(
                func.lower(attachments.c.content_type) == "application/pdf",
                func.lower(attachments.c.attachment_type) == "pdf",
            ),
            attachments.c.resolved_path.is_not(None),
        )
        stmt = stmt.where(~pdf_present.exists())
    return stmt


def list_papers(
    conn: Connection,
    *,
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    search_field: str = "all",
    only_deleted: bool = False,
    axis_id: int | None = None,
    axis_hide_uncertain: bool = False,
    tag_id: int | None = None,
    item_type: str | None = None,
    needs_review: bool = False,
    signal: str | None = None,
    finding: str | None = None,
    read_status: str | None = None,
    priority: str | None = None,
    missing_pdf: bool = False,
    sort: str = "added",
) -> list[RowMapping]:
    attachment_count = (
        select(func.count()).select_from(attachments).where(attachments.c.paper_id == papers.c.id).scalar_subquery()
    )
    chunk_count = (
        select(func.count())
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(chunks.c.paper_id == papers.c.id, attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
        .scalar_subquery()
    )
    stmt = select(
        papers,
        attachment_count.label("attachment_count"),
        chunk_count.label("chunk_count"),
        _cited_by_subquery().label("cited_by_count"),  # inc 210, A2 -- verbatim OpenAlex count + as-of for the chip
        _cited_by_as_of_subquery().label("cited_by_as_of"),
        _retraction_status_subquery().label("retraction_status"),
        _evidence_linked_correction_subquery().label("correction_evidence_linked"),
    )
    stmt = _paper_filter_clauses(
        conn,
        stmt,
        only_deleted=only_deleted,
        q=q,
        search_field=search_field,
        axis_id=axis_id,
        axis_hide_uncertain=axis_hide_uncertain,
        tag_id=tag_id,
        item_type=item_type,
        needs_review=needs_review,
        signal=signal,
        finding=finding,
        read_status=read_status,
        priority=priority,
        missing_pdf=missing_pdf,
    )
    stmt = stmt.order_by(*_paper_sort_order(sort))
    return list(conn.execute(stmt.limit(limit).offset(offset)).mappings())


def get_paper_rank(
    conn: Connection,
    paper_id: int,
    *,
    q: str | None = None,
    search_field: str = "all",
    only_deleted: bool = False,
    axis_id: int | None = None,
    axis_hide_uncertain: bool = False,
    tag_id: int | None = None,
    item_type: str | None = None,
    needs_review: bool = False,
    signal: str | None = None,
    finding: str | None = None,
    read_status: str | None = None,
    priority: str | None = None,
    missing_pdf: bool = False,
    sort: str = "added",
) -> int | None:
    """0-based rank of ``paper_id`` within the exact filtered+sorted set `list_papers` would return for these same
    params, or None if it doesn't match (excluded by a filter, or trashed when `only_deleted` isn't set). Drives
    the library's "reveal the selected paper" jump (inc 319) -- answers "which page is it on" via one window-
    function query, without the caller ever walking pages or relaxing its own filters to find out. Cheap: unlike
    `list_papers` this selects only `id` + the rank, skipping the attachment/chunk/cited-by/retraction subqueries
    the display list needs."""
    row_number = func.row_number().over(order_by=_paper_sort_order(sort)).label("rn")
    stmt = _paper_filter_clauses(
        conn,
        select(papers.c.id, row_number),
        only_deleted=only_deleted,
        q=q,
        search_field=search_field,
        axis_id=axis_id,
        axis_hide_uncertain=axis_hide_uncertain,
        tag_id=tag_id,
        item_type=item_type,
        needs_review=needs_review,
        signal=signal,
        finding=finding,
        read_status=read_status,
        priority=priority,
        missing_pdf=missing_pdf,
    )
    sub = stmt.subquery()
    rank = conn.execute(select(sub.c.rn).where(sub.c.id == paper_id)).scalar()
    return (int(rank) - 1) if rank is not None else None


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


def titles_for_ids(conn: Connection, paper_ids: Sequence[int]) -> dict[int, str]:
    """Map paper id -> title for a set of ids (inc 304 -- per-item progress labels for import/embed jobs). Bound IN
    (rule #3); a missing/empty title falls back to ``paper <id>``."""
    if not paper_ids:
        return {}
    rows = conn.execute(select(papers.c.id, papers.c.title).where(papers.c.id.in_({int(p) for p in paper_ids})))
    return {int(r[0]): (r[1] or f"paper {r[0]}") for r in rows}


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
