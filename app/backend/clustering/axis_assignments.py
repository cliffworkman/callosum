"""Axis manual-assignment + read-state helpers.

Split from ``axis_scoring.py`` (release-readiness Phase 5) to keep the scoring engine under the
600-line cap. These manage HUMAN overrides (``confidence IS NULL``), assignment removal, and the
read-time scored/stale state — they do NOT score. ``score_axis`` (in ``axis_scoring``) remains the
only path that embeds + compares the library and writes scored assignments.

Depends on ``axis_scoring`` for the shared cluster-node + axis-text helpers (one direction only;
``axis_scoring`` does not import this module)."""

from __future__ import annotations

from sqlalchemy import Connection, and_, delete, func, insert, select, update

from app.backend.clustering.axis_scoring import _axis_text, _axis_text_version, _ensure_cluster_node
from app.backend.embeddings.models import strip_punctuation
from app.backend.persistence.schema import axes, cluster_node_papers, cluster_nodes, embeddings

CURATED_KIND = "curated"  # A7 (inc 211): a hand-populated, hand-ordered axis (members all manual; never scored)
CREATABLE_KINDS = {"standard", CURATED_KIND}  # kinds a user can create/switch to (my_publications is resolver-only)


def ensure_axis_node(conn: Connection, axis_id: int) -> int:
    """Find or create the axis's single top-level cluster_node (so manual assignment works
    before the first score). Caller must have validated the axis exists."""
    axis = conn.execute(select(axes).where(axes.c.id == axis_id)).mappings().first()
    if axis is None:
        raise ValueError(f"axis {axis_id} not found")
    return _ensure_cluster_node(conn, axis=axis, parent_cluster_node_id=None)


def add_manual_assignment(conn: Connection, *, axis_id: int, paper_id: int) -> int:
    """Manually assign a paper to an axis (human override). Stored with confidence=NULL to mark
    it manual vs a scored float. **Upsert to NULL:** a new paper is inserted; an existing SCORED
    row is updated to confidence=NULL — this is how "confirm an uncertain paper → assigned" works
    (the human overrides the embedding). An already-manual row is left as-is. Returns the node id."""
    node_id = ensure_axis_node(conn, axis_id)
    existing = conn.execute(
        select(cluster_node_papers.c.confidence).where(
            and_(
                cluster_node_papers.c.cluster_node_id == node_id,
                cluster_node_papers.c.paper_id == paper_id,
            )
        )
    ).first()
    if existing is None:
        conn.execute(insert(cluster_node_papers).values(cluster_node_id=node_id, paper_id=paper_id, confidence=None))
    elif existing[0] is not None:  # a scored row → demote to a manual (human-asserted) override
        conn.execute(
            update(cluster_node_papers)
            .where(
                and_(
                    cluster_node_papers.c.cluster_node_id == node_id,
                    cluster_node_papers.c.paper_id == paper_id,
                )
            )
            .values(confidence=None)
        )
    return node_id


def append_member_position(conn: Connection, *, axis_id: int, paper_id: int) -> None:
    """Place a freshly-added member at the END of a curated axis's manual order (position = max+1). Called
    after add_manual_assignment when the axis is curated; keyword axes leave position NULL (A7, inc 211)."""
    node_id = ensure_axis_node(conn, axis_id)
    next_pos = conn.execute(
        select(func.coalesce(func.max(cluster_node_papers.c.position), -1) + 1).where(
            cluster_node_papers.c.cluster_node_id == node_id
        )
    ).scalar_one()
    conn.execute(
        update(cluster_node_papers)
        .where(
            and_(
                cluster_node_papers.c.cluster_node_id == node_id,
                cluster_node_papers.c.paper_id == paper_id,
            )
        )
        .values(position=int(next_pos))
    )


def set_member_order(conn: Connection, *, axis_id: int, paper_ids: list[int]) -> None:
    """Write the manual member order of a curated axis: position = index in ``paper_ids`` (A7, inc 211).
    ``paper_ids`` must be EXACTLY the axis's current members (no partial / foreign ids), else ValueError."""
    node_id = ensure_axis_node(conn, axis_id)
    current = {
        int(r[0])
        for r in conn.execute(
            select(cluster_node_papers.c.paper_id).where(cluster_node_papers.c.cluster_node_id == node_id)
        )
    }
    if len(paper_ids) != len(current) or set(int(p) for p in paper_ids) != current:
        raise ValueError("paper_ids must be exactly the axis's current members")
    for index, pid in enumerate(paper_ids):
        conn.execute(
            update(cluster_node_papers)
            .where(
                and_(
                    cluster_node_papers.c.cluster_node_id == node_id,
                    cluster_node_papers.c.paper_id == int(pid),
                )
            )
            .values(position=index)
        )


def freeze_to_curated(conn: Connection, *, axis_id: int, cutoff: float) -> None:
    """Keyword → Curated ("freeze", A7 inc 211): snapshot the currently-SHOWN members — *assigned*
    (confidence >= cutoff) + *manual* (confidence IS NULL) — demote them all to manual, assign `position` by
    display order (assigned by confidence desc, then manual by id), DROP the below-cutoff uncertain rows, and
    set kind=curated. Idempotent for an already-curated axis (no scored rows → a no-op reorder)."""
    node_id = ensure_axis_node(conn, axis_id)
    rows = list(
        conn.execute(
            select(cluster_node_papers.c.paper_id, cluster_node_papers.c.confidence).where(
                cluster_node_papers.c.cluster_node_id == node_id
            )
        )
    )
    manual = sorted(int(r[0]) for r in rows if r[1] is None)
    assigned = sorted(
        ((int(r[0]), float(r[1])) for r in rows if r[1] is not None and float(r[1]) >= cutoff),
        key=lambda t: t[1],
        reverse=True,
    )
    uncertain = [int(r[0]) for r in rows if r[1] is not None and float(r[1]) < cutoff]
    ordered = [pid for pid, _ in assigned] + manual  # the card's pre-freeze display order
    for index, pid in enumerate(ordered):
        conn.execute(
            update(cluster_node_papers)
            .where(and_(cluster_node_papers.c.cluster_node_id == node_id, cluster_node_papers.c.paper_id == pid))
            .values(confidence=None, position=index)
        )
    for pid in uncertain:
        conn.execute(
            delete(cluster_node_papers).where(
                and_(cluster_node_papers.c.cluster_node_id == node_id, cluster_node_papers.c.paper_id == pid)
            )
        )
    conn.execute(update(axes).where(axes.c.id == axis_id).values(kind=CURATED_KIND))


def revert_to_keyword(conn: Connection, *, axis_id: int) -> None:
    """Curated → Keyword (warned, A7 inc 211): members are KEPT (the manual NULL rows survive); clear
    `position`; set kind=standard. The axis is then stale → a re-score replaces the manual order with fit order."""
    node_id = ensure_axis_node(conn, axis_id)
    conn.execute(
        update(cluster_node_papers).where(cluster_node_papers.c.cluster_node_id == node_id).values(position=None)
    )
    conn.execute(update(axes).where(axes.c.id == axis_id).values(kind="standard"))


def remove_assignment(conn: Connection, *, axis_id: int, paper_id: int) -> bool:
    """Remove a paper's assignment (scored or manual) from an axis. Returns True if a row was
    deleted, False if the axis had no node or no such assignment."""
    node_id = conn.execute(
        select(cluster_nodes.c.id)
        .where(and_(cluster_nodes.c.axis_id == axis_id, cluster_nodes.c.parent_id.is_(None)))
        .limit(1)
    ).scalar_one_or_none()
    if node_id is None:
        return False
    result = conn.execute(
        delete(cluster_node_papers).where(
            and_(
                cluster_node_papers.c.cluster_node_id == int(node_id),
                cluster_node_papers.c.paper_id == paper_id,
            )
        )
    )
    return bool(result.rowcount)


def manual_assignment_paper_ids(conn: Connection, axis_id: int) -> set[int]:
    """Paper ids manually assigned to the axis (confidence IS NULL) — used to preserve human
    overrides across a re-score."""
    node_id = conn.execute(
        select(cluster_nodes.c.id)
        .where(and_(cluster_nodes.c.axis_id == axis_id, cluster_nodes.c.parent_id.is_(None)))
        .limit(1)
    ).scalar_one_or_none()
    if node_id is None:
        return set()
    rows = conn.execute(
        select(cluster_node_papers.c.paper_id).where(
            and_(
                cluster_node_papers.c.cluster_node_id == int(node_id),
                cluster_node_papers.c.confidence.is_(None),
            )
        )
    )
    return {int(row[0]) for row in rows}


def restore_manual_assignments(conn: Connection, *, axis_id: int, paper_ids: set[int]) -> None:
    """Force the given paper ids back to manual (confidence=NULL) after a re-score, so a human's
    manual/confirmed picks survive re-scoring. **Upsert:** a re-inserted-as-scored paper is updated
    back to NULL (not just absent ones) — otherwise a manual pick that also scores above the floor
    would silently revert to scored. Absent papers are inserted as NULL."""
    if not paper_ids:
        return
    node_id = ensure_axis_node(conn, axis_id)
    present = {
        int(row[0])
        for row in conn.execute(
            select(cluster_node_papers.c.paper_id).where(cluster_node_papers.c.cluster_node_id == node_id)
        )
    }
    for paper_id in sorted(paper_ids):
        if paper_id in present:
            conn.execute(
                update(cluster_node_papers)
                .where(
                    and_(
                        cluster_node_papers.c.cluster_node_id == node_id,
                        cluster_node_papers.c.paper_id == paper_id,
                    )
                )
                .values(confidence=None)
            )
        else:
            conn.execute(
                insert(cluster_node_papers).values(cluster_node_id=node_id, paper_id=paper_id, confidence=None)
            )


def axis_score_state(conn: Connection, axis_id: int, *, cutoff: float | None = None) -> dict[str, object]:
    """Whether an axis has been scored, whether its assignments are stale, and — when ``cutoff`` is given —
    how many assignments are *uncertain* (scored but below the cutoff), for the count-badge subtraction
    (inc 79). Staleness compares the axis text-version recomputed with the stored embedding's normalization
    against its source_text_version."""
    axis = conn.execute(select(axes).where(axes.c.id == axis_id)).mappings().first()
    if axis is None:
        return {"scored": False, "stale": False, "assignment_count": 0, "uncertain_count": 0}
    count = int(
        conn.execute(
            select(func.count())
            .select_from(
                cluster_node_papers.join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
            )
            .where(cluster_nodes.c.axis_id == axis_id)
        ).scalar_one()
    )
    if axis["kind"] == CURATED_KIND:
        # A7 (inc 211): a curated axis is never scored / never stale; all members are manual, none uncertain.
        return {"scored": False, "stale": False, "assignment_count": count, "uncertain_count": 0}
    # Uncertain = scored (confidence NOT NULL) but below the display cutoff; manual (NULL) is never uncertain.
    # Mirrors the read-time tiering in routers/axes.py (assigned = confidence >= cutoff).
    uncertain = 0
    if cutoff is not None:
        uncertain = int(
            conn.execute(
                select(func.count())
                .select_from(
                    cluster_node_papers.join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
                )
                .where(
                    and_(
                        cluster_nodes.c.axis_id == axis_id,
                        cluster_node_papers.c.confidence.is_not(None),
                        cluster_node_papers.c.confidence < cutoff,
                    )
                )
            ).scalar_one()
        )
    # Fresh if ANY stored embedding matches the current text — NOT just newest-by-id. An axis accrues a
    # row per scored text version (never pruned), so a merge/edit cycle revisiting a prior version can
    # leave a stale higher-id row above the matching one (else: perpetually stale). score_axis embeds current.
    rows = (
        conn.execute(
            select(embeddings.c.source_text_version, embeddings.c.normalization).where(
                and_(embeddings.c.target_type == "axis", embeddings.c.target_id == axis_id)
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        return {"scored": False, "stale": False, "assignment_count": count, "uncertain_count": uncertain}
    current_text = strip_punctuation(_axis_text(axis))
    fresh = any(
        _axis_text_version(current_text, normalization=r["normalization"]) == r["source_text_version"] for r in rows
    )
    return {"scored": True, "stale": not fresh, "assignment_count": count, "uncertain_count": uncertain}
