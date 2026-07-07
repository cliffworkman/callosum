"""Un-merge — reverse a non-destructive paper merge exactly from its stored snapshot (#16, pairs with inc-161
merge). The reversal safety net for the app's most destructive op: an app with no git needs a real undo.

``merge_papers`` (paper_merge.py) records a self-contained reversal snapshot on a ``merge_operations`` row as it
mutates. ``unmerge`` replays it: restore the survivor's record, remove only the union links the merge added
(husks kept their own), move every re-pointed source row home, restore each husk's freed UNIQUE id columns, and
un-hide the husks (clear deleted_at + merged_into). Every step is an UPDATE/DELETE (no row re-insertion), so
there is no autoincrement-id or timestamp-coercion hazard. One transaction (the endpoint commits).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import Connection, func, select, update

from app.backend.metadata.paper_merge import _REPOINT_TABLES
from app.backend.persistence import profile_repo
from app.backend.persistence.repository import update_paper_metadata
from app.backend.persistence.schema import (
    attachments,
    cluster_node_papers,
    collection_papers,
    merge_operations,
    paper_tags,
    papers,
    profile,
)

_REPOINT_BY_NAME = {t.name: t for t in _REPOINT_TABLES}


class UnmergeError(ValueError):
    """Bad un-merge request (→ 422)."""


@dataclass(frozen=True)
class UnmergeResult:
    survivor_id: int
    restored_ids: list[int]  # the husks brought back to live


def unmerge(conn: Connection, *, merge_operation_id: int) -> UnmergeResult:
    op = (
        conn.execute(select(merge_operations).where(merge_operations.c.id == int(merge_operation_id)))
        .mappings()
        .first()
    )
    if op is None:
        raise UnmergeError("Merge operation not found.")
    if op["status"] != "active":
        raise UnmergeError("This merge has already been un-merged.")
    snap = json.loads(op["snapshot_json"])
    survivor_id = int(snap["survivor_id"])
    husks = snap["husks"]

    # 1) Restore the survivor's record FIRST — this frees any UNIQUE id (e.g. a DOI) the survivor adopted, before a
    #    husk reclaims it in step 4, so the UNIQUE constraint can't trip. csl_json round-trips as a dict.
    update_paper_metadata(conn, survivor_id, **snap["survivor_before"])

    # 2) Remove exactly the union links this merge added to the survivor (husks kept their own copies).
    for tag_id in snap.get("tag_links_added", []):
        conn.execute(
            paper_tags.delete().where(paper_tags.c.paper_id == survivor_id, paper_tags.c.tag_id == int(tag_id))
        )
    for cid in snap.get("collection_links_added", []):
        conn.execute(
            collection_papers.delete().where(
                collection_papers.c.paper_id == survivor_id, collection_papers.c.collection_id == int(cid)
            )
        )
    for node_id in snap.get("axis_links_added", []):
        conn.execute(
            cluster_node_papers.delete().where(
                cluster_node_papers.c.paper_id == survivor_id, cluster_node_papers.c.cluster_node_id == int(node_id)
            )
        )

    # 3) Move every re-pointed source row back to its original husk.
    for entry in snap["repoints"]:
        table = _REPOINT_BY_NAME[entry["table"]]
        conn.execute(table.update().where(table.c.id == int(entry["id"])).values(paper_id=int(entry["from"])))

    # 4) Restore each husk's freed UNIQUE id columns, then bring it back to live.
    for husk in husks:
        conn.execute(
            update(papers)
            .where(papers.c.id == int(husk["id"]))
            .values(**husk["id_cols_before"], deleted_at=None, merged_into=None)
        )

    # 5) Restore My-Publications references (starred / research-domain paper ids) if the merge rewrote them.
    if snap.get("profile_before") is not None:
        prof = profile_repo.get_profile(conn)
        if prof is not None:
            conn.execute(
                update(profile)
                .where(profile.c.id == int(prof["id"]))
                .values(
                    starred_paper_ids=snap["profile_before"]["starred_paper_ids"],
                    research_domains=snap["profile_before"]["research_domains"],
                    updated_at=func.current_timestamp(),
                )
            )

    # 6) Restore any primary-attachment role the merge changed.
    for entry in snap.get("primary_before", []):
        conn.execute(
            update(attachments).where(attachments.c.id == int(entry["attachment_id"])).values(role=entry["role"])
        )

    # 7) Mark the operation undone.
    conn.execute(
        update(merge_operations)
        .where(merge_operations.c.id == int(merge_operation_id))
        .values(status="undone", undone_at=func.current_timestamp())
    )
    return UnmergeResult(survivor_id=survivor_id, restored_ids=[int(h["id"]) for h in husks])


def merge_origin(conn: Connection, paper_id: int) -> dict | None:
    """For the survivor's Detail "Merged from … — Un-merge" affordance: the active merge (if any) this paper is
    the survivor of, with the merged-away copies' titles read from the snapshot (N-way safe)."""
    op = (
        conn.execute(
            select(merge_operations)
            .where(merge_operations.c.canonical_paper_id == int(paper_id), merge_operations.c.status == "active")
            .order_by(merge_operations.c.created_at.desc())
        )
        .mappings()
        .first()
    )
    if op is None:
        return None
    husk_ids = [int(h["id"]) for h in json.loads(op["snapshot_json"])["husks"]]
    titles = [
        (r[0] or "Untitled")
        for r in conn.execute(select(papers.c.title).where(papers.c.id.in_(husk_ids)).order_by(papers.c.id))
    ]
    return {"merge_operation_id": int(op["id"]), "merged_from_titles": titles, "merged_at": op["created_at"]}
