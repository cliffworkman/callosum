"""Merge duplicate papers into one surviving record — non-destructive (inc 161).

The researcher's case: a preprint + a published copy of the same paper. Rather than deleting the redundant copy
(today's only option — lossy: it discards whatever that copy held the survivor lacked), this folds every copy's
**source data** onto a chosen survivor and moves the others to Trash:

  * attachments (both PDFs are kept), chunks, annotations, notes, external identifiers → re-pointed to the survivor;
  * tags / collection memberships / manual axis assignments → unioned (idempotent);
  * a "Merged from …" lineage note captures every merged copy's identifiers (DOI, URL/OSF, PMID, arXiv) verbatim,
    so a link can never be silently lost even if Trash is later emptied;
  * the surviving record's scalar metadata is composed from the user's per-field picks (reusing the Details-editor
    `build_paper_update`); the merged-away copies are soft-deleted (a restorable husk that keeps its own csl_json
    as an audit trail).

The merged husks' UNIQUE non-DOI identifier columns (openalex_work_id / semantic_scholar_paper_id / Zotero key) are
nulled first so the survivor can adopt them without colliding (soft-delete keeps the row, so the UNIQUE constraint
would otherwise block it); the husk's
`csl_json` retains the values for audit. Chunk embeddings need no surgery — a chunk's `paper_id` re-point keeps its
`id`, so its embedding still resolves (now attributed to the survivor); the merged copy's paper-level embedding
stays harmlessly on the trashed husk (excluded from retrieval, inc 66). Entirely local; bound-param SQL (rule #3);
no migration. Runs inside the caller's transaction (the endpoint commits).

Derived signals/findings are intentionally NOT migrated — they regenerate from the now-migrated source by their
producers (retraction/statcheck), and the husk retains its copies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection, insert, select, update

from app.backend.metadata.enrichment import MERGED_SOURCE
from app.backend.metadata.paper_edits import build_paper_update
from app.backend.persistence import profile_repo, tags_repo
from app.backend.persistence.repository import get_paper, soft_delete_paper, update_paper_metadata
from app.backend.persistence.schema import (
    annotations,
    attachments,
    chunks,
    cluster_node_papers,
    collection_papers,
    merge_operations,
    notes,
    paper_external_identifiers,
    paper_tags,
    papers,
)

MAX_MERGE_PAPERS = 20

# Re-pointed wholesale (no per-paper UNIQUE on these — verified): a plain UPDATE paper_id is safe. external
# identifiers are globally UNIQUE on (provider, identifier), so two rows can't share one → no collision on move.
_REPOINT_TABLES = (attachments, chunks, annotations, notes, paper_external_identifiers)
# UNIQUE non-DOI identifier columns on `papers`. DOI is intentionally not unique: it can temporarily mark duplicate
# records that need merging. The husk's csl_json keeps all identifier values for audit. (zotero_* are a UNIQUE pair.)
_UNIQUE_ID_COLS = ("openalex_work_id", "semantic_scholar_paper_id", "zotero_library_id", "zotero_item_key")
# Matching ids auto-adopted onto the survivor when it lacks them (column-only, not user-facing csl fields).
_ADOPT_COLS = ("openalex_work_id", "semantic_scholar_paper_id")
# The survivor columns a merge mutates → snapshotted before, so un-merge (#16) restores the survivor's record exactly.
_SURVIVOR_SNAPSHOT_COLS = (
    "title",
    "abstract",
    "year",
    "venue",
    "item_type",
    "language",
    "publication_date",
    "citation_key",
    "first_author_family_name",
    "csl_json",
    "imported_source",
    *_UNIQUE_ID_COLS,
)


class MergeError(ValueError):
    """Base for merge failures."""


class MergeValidationError(MergeError):
    """Bad merge request (→ 422)."""


class MergeConflictError(MergeError):
    """Merge would conflict with an external unique identifier (→ 409)."""


@dataclass(frozen=True)
class MergeResult:
    survivor_id: int
    merged_ids: list[int]
    trashed: list[int]
    merge_operation_id: int  # the undo handle (#16) — reverse with paper_unmerge.unmerge


def _survivor_tag_ids(conn: Connection, survivor_id: int) -> set[int]:
    return {int(r[0]) for r in conn.execute(select(paper_tags.c.tag_id).where(paper_tags.c.paper_id == survivor_id))}


def _survivor_collection_ids(conn: Connection, survivor_id: int) -> set[int]:
    return {
        int(r[0])
        for r in conn.execute(
            select(collection_papers.c.collection_id).where(collection_papers.c.paper_id == survivor_id)
        )
    }


def _survivor_manual_axis_ids(conn: Connection, survivor_id: int) -> set[int]:
    return {
        int(r[0])
        for r in conn.execute(
            select(cluster_node_papers.c.cluster_node_id).where(
                cluster_node_papers.c.paper_id == survivor_id, cluster_node_papers.c.confidence.is_(None)
            )
        )
    }


def _profile_refs_any(prof: dict[str, Any], ids: list[int]) -> bool:
    idset = set(ids)
    if idset & {int(x) for x in (prof.get("starred_paper_ids") or [])}:
        return True
    for d in prof.get("research_domains") or []:
        if idset & {int(x) for x in (d.get("paper_ids") or [])}:
            return True
    return False


def merge_papers(
    conn: Connection,
    *,
    survivor_id: int,
    merged_ids: list[int],
    metadata: dict[str, Any] | None = None,
    primary_attachment_id: int | None = None,
) -> MergeResult:
    """Fold ``merged_ids`` into ``survivor_id``. See the module docstring. Caller commits."""
    metadata = metadata or {}
    survivor_id = int(survivor_id)
    merged_ids = [int(m) for m in merged_ids]

    # --- fail-fast validation (before any write) ---
    if not merged_ids:
        raise MergeValidationError("No papers to merge into the survivor.")
    if len(merged_ids) > MAX_MERGE_PAPERS:
        raise MergeValidationError(f"Too many papers to merge at once (max {MAX_MERGE_PAPERS}).")
    if len(set(merged_ids)) != len(merged_ids):
        raise MergeValidationError("Duplicate ids in the merge set.")
    if survivor_id in merged_ids:
        raise MergeValidationError("The survivor cannot also be a merged-away copy.")
    all_ids = [survivor_id, *merged_ids]
    live = {
        int(r[0])
        for r in conn.execute(select(papers.c.id).where(papers.c.id.in_(all_ids), papers.c.deleted_at.is_(None)))
    }
    missing = [i for i in all_ids if i not in live]
    if missing:
        raise MergeValidationError(f"Every paper must exist and be live; not so for: {missing}")

    survivor_row = get_paper(conn, survivor_id)
    merged_rows = [get_paper(conn, mid) for mid in merged_ids]

    # Compose the survivor's metadata up front (pure) before mutating.
    update_kwargs = build_paper_update(survivor_row, metadata)

    if primary_attachment_id is not None:
        owner = conn.execute(
            select(attachments.c.paper_id).where(attachments.c.id == int(primary_attachment_id))
        ).first()
        if owner is None or int(owner[0]) not in set(all_ids):
            raise MergeValidationError("primary_attachment_id must be an attachment of one of the merged papers.")

    # --- mutations (recording an un-merge reversal snapshot as we go, #16) ---
    # Union-link additions are captured by diffing the survivor's membership sets before vs. after (cleaner than
    # instrumenting each OR-IGNORE insert); everything moved/nulled is snapshotted before the write.
    snapshot: dict[str, Any] = {
        "survivor_id": survivor_id,
        "survivor_before": {c: survivor_row[c] for c in _SURVIVOR_SNAPSHOT_COLS},
        "husks": [],
        "repoints": [],
        "primary_before": [],
        "profile_before": None,
    }
    tags_before = _survivor_tag_ids(conn, survivor_id)
    colls_before = _survivor_collection_ids(conn, survivor_id)
    axes_before = _survivor_manual_axis_ids(conn, survivor_id)
    prof = profile_repo.get_profile(conn)
    if prof is not None and _profile_refs_any(prof, merged_ids):
        snapshot["profile_before"] = {
            "starred_paper_ids": prof.get("starred_paper_ids"),
            "research_domains": prof.get("research_domains"),
        }

    merged_by_id = {int(r["id"]): r for r in merged_rows}
    for mid in merged_ids:
        # Snapshot the husk's UNIQUE id columns, then free them so the survivor can adopt them (csl_json retains them).
        snapshot["husks"].append({"id": mid, "id_cols_before": {c: merged_by_id[mid][c] for c in _UNIQUE_ID_COLS}})
        conn.execute(update(papers).where(papers.c.id == mid).values(**dict.fromkeys(_UNIQUE_ID_COLS, None)))
        # Re-point source rows (record each moved row's id so un-merge sends it home).
        for table in _REPOINT_TABLES:
            for rid in conn.execute(select(table.c.id).where(table.c.paper_id == mid)).scalars():
                snapshot["repoints"].append({"table": table.name, "id": int(rid), "from": mid})
            conn.execute(update(table).where(table.c.paper_id == mid).values(paper_id=survivor_id))
        # Tags → union onto the survivor (idempotent get-or-create + OR IGNORE link; provenance preserved).
        for tag in tags_repo.get_tags_for_paper(conn, mid):
            tags_repo.add_tag_to_paper(conn, survivor_id, tag["name"], import_source=tag["import_source"] or "user")
        # Collection memberships → union (composite-PK safe).
        for cid in [
            int(r[0])
            for r in conn.execute(select(collection_papers.c.collection_id).where(collection_papers.c.paper_id == mid))
        ]:
            conn.execute(
                insert(collection_papers).prefix_with("OR IGNORE").values(collection_id=cid, paper_id=survivor_id)
            )
        # Manual axis assignments (confidence IS NULL) → union; scored rows recompute on the next re-score (inc 43).
        for node_id in [
            int(r[0])
            for r in conn.execute(
                select(cluster_node_papers.c.cluster_node_id).where(
                    cluster_node_papers.c.paper_id == mid, cluster_node_papers.c.confidence.is_(None)
                )
            )
        ]:
            conn.execute(
                insert(cluster_node_papers)
                .prefix_with("OR IGNORE")
                .values(cluster_node_id=node_id, paper_id=survivor_id, confidence=None)
            )
        # My-Publications references → repoint (no phantom/trashed star or domain entry).
        profile_repo.replace_paper_id(conn, mid, survivor_id)

    # Only the links this merge ADDED to the survivor (husks keep their own) — un-merge removes exactly these.
    snapshot["tag_links_added"] = sorted(_survivor_tag_ids(conn, survivor_id) - tags_before)
    snapshot["collection_links_added"] = sorted(_survivor_collection_ids(conn, survivor_id) - colls_before)
    snapshot["axis_links_added"] = sorted(_survivor_manual_axis_ids(conn, survivor_id) - axes_before)

    # Adopt matching ids the survivor lacks (from the first merged copy that has each).
    for col in _ADOPT_COLS:
        if not survivor_row[col]:
            for mrow in merged_rows:
                if mrow[col]:
                    update_kwargs[col] = mrow[col]
                    break

    # Lineage note + provenance, then one write for the survivor's record.
    csl = update_kwargs["csl_json"]
    lineage = "\n".join(_lineage_line(r) for r in merged_rows)
    existing_note = (csl.get("note") or "").strip()
    csl["note"] = f"{existing_note}\n{lineage}".strip() if existing_note else lineage
    update_kwargs["csl_json"] = csl
    update_kwargs["imported_source"] = MERGED_SOURCE
    update_paper_metadata(conn, survivor_id, **update_kwargs)

    # Primary attachment (both PDFs are kept; the user picks which leads). Record every role we change.
    if primary_attachment_id is not None:
        for aid, role in conn.execute(
            select(attachments.c.id, attachments.c.role).where(
                attachments.c.paper_id == survivor_id, attachments.c.role == "primary"
            )
        ):
            snapshot["primary_before"].append({"attachment_id": int(aid), "role": role})
        chosen_role = conn.execute(
            select(attachments.c.role).where(attachments.c.id == int(primary_attachment_id))
        ).scalar_one()
        snapshot["primary_before"].append({"attachment_id": int(primary_attachment_id), "role": chosen_role})
        conn.execute(
            update(attachments)
            .where(attachments.c.paper_id == survivor_id, attachments.c.role == "primary")
            .values(role=None)
        )
        conn.execute(update(attachments).where(attachments.c.id == int(primary_attachment_id)).values(role="primary"))

    # Retire the husks: Trash + mark merged-away (so they leave the live library AND the plain Trash list; they
    # come back only via un-merge, which restores their moved data — a plain restore would give an empty husk).
    for mid in merged_ids:
        soft_delete_paper(conn, mid)
        conn.execute(update(papers).where(papers.c.id == mid).values(merged_into=survivor_id))

    op_id = int(
        conn.execute(
            insert(merge_operations).values(
                canonical_paper_id=survivor_id,
                merged_paper_id=merged_ids[0],  # representative; snapshot["husks"] is the full N-way list
                snapshot_json=json.dumps(snapshot, default=str),
                status="active",
            )
        ).inserted_primary_key[0]
    )
    return MergeResult(
        survivor_id=survivor_id, merged_ids=merged_ids, trashed=list(merged_ids), merge_operation_id=op_id
    )


def _lineage_line(row: Any) -> str:
    """One 'Merged from "<title>" (<year>) — DOI: …; URL: …' line capturing a merged copy's identifiers verbatim."""
    csl = row["csl_json"] or {}
    title = (row["title"] or csl.get("title") or "Untitled").strip()
    parts: list[str] = []
    doi = csl.get("DOI") or row["doi"]
    if doi:
        parts.append(f"DOI: {doi}")
    if csl.get("URL"):
        parts.append(f"URL: {csl['URL']}")
    if csl.get("PMID"):
        parts.append(f"PMID: {csl['PMID']}")
    if csl.get("arxiv"):
        parts.append(f"arXiv: {csl['arxiv']}")
    head = f'Merged from "{title}"'
    if row["year"]:
        head += f" ({row['year']})"
    return head + (" — " + "; ".join(parts) if parts else "")
