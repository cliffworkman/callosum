"""High-level axis operations composed over the scoring engine.

These live here (not in `axis_scoring.py`) so the scoring engine stays under the 600-line cap.
They do NOT reimplement scoring — `merge_axes` only rearranges metadata + manual assignments;
the caller re-scores the survivor so its scored tier is recomputed from the merged text.
"""

from __future__ import annotations

from sqlalchemy import Connection, update

from app.backend.clustering.axis_assignments import (
    add_manual_assignment,
    manual_assignment_paper_ids,
)
from app.backend.clustering.axis_scoring import delete_axis
from app.backend.persistence.schema import axes


def merge_axes(
    conn: Connection,
    *,
    keep_axis_id: int,
    merge_axis_ids: list[int],
    label: str,
    description: str | None,
) -> None:
    """Consolidate `merge_axis_ids` into the surviving axis `keep_axis_id`.

    The survivor absorbs every merged axis's **manual** (human-override, confidence-NULL)
    assignments as a union, and its label/description are set to exactly the user-composed
    strings (a parameterized UPDATE — sets the description even when empty/NULL, unlike
    `update_axis`, whose ``None`` means "leave unchanged"). The merged axes are then deleted;
    their cluster_nodes + assignments cascade via FK ``ondelete=CASCADE``.

    Scored assignments are intentionally NOT carried over — only human overrides survive a
    merge. The caller re-scores the survivor afterwards so the scored tier reflects the merged
    text. Caller must have validated that every id exists and that `merge_axis_ids` is non-empty
    and disjoint from `keep_axis_id`.
    """
    for source_id in merge_axis_ids:
        for paper_id in manual_assignment_paper_ids(conn, source_id):
            add_manual_assignment(conn, axis_id=keep_axis_id, paper_id=paper_id)
    conn.execute(update(axes).where(axes.c.id == keep_axis_id).values(label=label, description=description))
    for source_id in merge_axis_ids:
        delete_axis(conn, source_id)
