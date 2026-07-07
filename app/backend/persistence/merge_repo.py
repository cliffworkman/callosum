"""Library merge + reversible un-merge (backlog #17/#16). Bound-param SQLAlchemy Core (rule #3); every table it
touches comes from the hardcoded ``merge_allowlist`` — never from request data. One transaction per operation
(the caller commits). The reversal snapshot stored on ``merge_operations`` is self-contained: un-merge replays
it without re-reading derived state.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Connection, and_, func, insert, select, update

from app.backend.persistence import merge_allowlist as al
from app.backend.persistence.schema import merge_operations, papers

# The paper metadata columns a merge snapshots (so un-merge restores A exactly) — the set build_paper_update touches.
_METADATA_COLUMNS = (
    "title",
    "abstract",
    "year",
    "venue",
    "item_type",
    "language",
    "publication_date",
    "doi",
    "first_author_family_name",
    "citation_key",
    "csl_json",
    "imported_source",
)

# Fields shown in the field-by-field picker → the papers column each reads from.
_PREVIEW_FIELDS = (
    "title",
    "year",
    "doi",
    "venue",
    "item_type",
    "abstract",
    "language",
    "publication_date",
    "first_author_family_name",
)


def merge_preview(conn: Connection, canonical_id: int, merged_id: int) -> dict[str, Any]:
    a = conn.execute(select(papers).where(papers.c.id == canonical_id)).mappings().first()
    b = conn.execute(select(papers).where(papers.c.id == merged_id)).mappings().first()
    if a is None or b is None:
        raise ValueError("both papers must exist")
    fields = []
    for name in _PREVIEW_FIELDS:
        va, vb = a[name], b[name]
        fields.append({"field": name, "value_a": va, "value_b": vb, "agree": va == vb})

    counts: dict[str, int] = {}
    for table_name, paper_col, _key in (*al.UNION_TABLES, *al.DEDUP_TABLES):
        counts[table_name] = _count(conn, table_name, paper_col, merged_id)

    warnings = _conflict_warnings(conn, canonical_id, merged_id)
    return {"fields": fields, "association_counts": counts, "warnings": warnings}


def _count(conn: Connection, table_name: str, paper_col: str, paper_id: int) -> int:
    from app.backend.persistence.schema import metadata

    table = metadata.tables[table_name]
    return int(conn.execute(select(func.count()).select_from(table).where(table.c[paper_col] == paper_id)).scalar_one())


def _conflict_warnings(conn: Connection, a: int, b: int) -> list[dict[str, str]]:
    from app.backend.persistence.schema import my_publication_decisions, reading_queue

    warnings: list[dict[str, str]] = []
    for table, label in ((reading_queue, "reading queue"), (my_publication_decisions, "My Publications")):
        both = conn.execute(select(func.count()).select_from(table).where(table.c.paper_id.in_([a, b]))).scalar_one()
        if both and both >= 2:
            warnings.append({"kind": "membership", "detail": f"both papers are in the {label}; kept once"})
    warnings.append(
        {"kind": "derived", "detail": "the survivor's methods signals won't auto-recompute — re-run Methods to refresh"}
    )
    return warnings


def merge_papers(conn: Connection, *, canonical_id: int, merged_id: int, resolved_metadata: dict[str, Any]) -> int:
    """Merge paper ``merged_id`` (B) into ``canonical_id`` (A): apply the resolved metadata to A, re-point every
    association off the allowlist (union + set-membership dedup + — added in the derived/special/JSON walk — the
    rest), soft-hide B (deleted_at + merged_into), and record a self-contained reversal snapshot on a new
    merge_operations row. One transaction (caller commits). Returns the merge_operation id.
    """
    from app.backend.persistence.schema import metadata

    if canonical_id == merged_id:
        raise ValueError("cannot merge a paper into itself")
    a = conn.execute(select(papers).where(papers.c.id == canonical_id)).mappings().first()
    b = conn.execute(select(papers).where(papers.c.id == merged_id)).mappings().first()
    if a is None or b is None:
        raise ValueError("both papers must exist")
    if a["merged_into"] is not None or b["merged_into"] is not None:
        raise ValueError("cannot merge an already-merged paper")
    if a["deleted_at"] is not None or b["deleted_at"] is not None:
        raise ValueError("cannot merge a trashed paper")

    snapshot: dict[str, Any] = {
        "canonical_metadata_before": {c: a[c] for c in _METADATA_COLUMNS},
        "repoints": [],
        "drops": [],
        "json_edits": [],
    }

    # (1) Apply the field-by-field resolved metadata to A (reuse the Details-editor merge — same validation surface).
    if resolved_metadata:
        from app.backend.metadata.paper_edits import build_paper_update
        from app.backend.persistence.paper_lifecycle_repo import update_paper_metadata

        update_paper_metadata(conn, canonical_id, **build_paper_update(a, resolved_metadata))

    # (2) Union + (3) dedup tables: re-point every B row; drop on a key collision with A (recorded for un-merge).
    for table_name, paper_col, key in (*al.UNION_TABLES, *al.DEDUP_TABLES):
        _repoint_or_drop(conn, metadata.tables[table_name], paper_col, canonical_id, merged_id, key, snapshot)

    # (4) Derived caches: snapshot B's rows then drop them (A's stand; user re-runs Methods to refresh).
    for table_name, paper_col in al.DERIVED_DROP_TABLES:
        table = metadata.tables[table_name]
        for row in conn.execute(select(table).where(table.c[paper_col] == merged_id)).mappings().all():
            snapshot["drops"].append({"table": table.name, "row": dict(row)})
            conn.execute(_pk_where(table, row))

    # (5) Special cases (bespoke rules the uniform walk can't express).
    _merge_findings(conn, canonical_id, merged_id, snapshot)
    _merge_my_pubs(conn, canonical_id, merged_id, snapshot)
    _merge_agent_writes(conn, canonical_id, merged_id, snapshot)
    _merge_dismissed_pairs(conn, canonical_id, merged_id, snapshot)

    # (6) JSON-scoped id rewrites (paper ids embedded in JSON blobs): B -> A.
    _rewrite_json_scopes(conn, canonical_id, merged_id, snapshot)

    # Hide B: soft-delete (every live-paper query already filters deleted_at) + flag it merged.
    conn.execute(
        update(papers)
        .where(papers.c.id == merged_id)
        .values(deleted_at=func.current_timestamp(), merged_into=canonical_id)
    )
    op_id = conn.execute(
        insert(merge_operations).values(
            canonical_paper_id=canonical_id,
            merged_paper_id=merged_id,
            snapshot_json=json.dumps(snapshot, default=str),
            status="active",
        )
    ).inserted_primary_key[0]
    return int(op_id)


def _repoint_or_drop(conn, table, paper_col, a_id, b_id, key, snapshot):
    """Move B's rows in ``table`` onto A. With a dedup ``key``, a B-row that would duplicate one of A's rows is
    DROPPED (recorded) instead of re-pointed. Handles single-``id``-PK and composite-PK tables alike."""
    single_id_pk = _has_single_id_pk(table)
    for row in conn.execute(select(table).where(table.c[paper_col] == b_id)).mappings().all():
        if key and _collides(conn, table, key, row, a_id, paper_col):
            conn.execute(_pk_where(table, row))
            snapshot["drops"].append({"table": table.name, "row": dict(row)})
        else:
            conn.execute(_pk_where(table, row, update_values={paper_col: a_id}))
            snapshot["repoints"].append(
                {"table": table.name, "id": _identity_after(table, row, paper_col, a_id, single_id_pk)}
            )


def _collides(conn, table, key, row, a_id, paper_col) -> bool:
    """True iff A already has a row that this B-row would duplicate — i.e. a row belonging to A matching the
    non-paper key columns. Scoping to A auto-excludes B's own row even when the key doesn't include paper_col
    (e.g. the globally-unique (provider, identifier) on paper_external_identifiers)."""
    conds = [table.c[paper_col] == a_id]
    for col in key:
        if col == paper_col:
            continue
        conds.append(table.c[col] == row[col])
    return conn.execute(select(func.count()).select_from(table).where(and_(*conds))).scalar_one() > 0


def _has_single_id_pk(table) -> bool:
    return [c.name for c in table.primary_key.columns] == ["id"]


def _identity_after(table, row, paper_col, a_id, single_id_pk):
    """The row's identity AFTER re-pointing paper_col to A — an int for id-PK tables, else the PK dict with
    paper_col set to a_id (so un-merge can find the moved row and send it back to B)."""
    if single_id_pk:
        return row["id"]
    return {c.name: (a_id if c.name == paper_col else row[c.name]) for c in table.primary_key.columns}


def _pk_where(table, row, update_values: dict | None = None):
    """A composite-PK-safe UPDATE (with ``update_values``) or DELETE targeting exactly ``row`` by its PK."""
    conds = and_(*[table.c[c.name] == row[c.name] for c in table.primary_key.columns])
    if update_values is not None:
        return table.update().where(conds).values(**update_values)
    return table.delete().where(conds)


def _merge_findings(conn, a_id, b_id, snapshot):
    """paper_findings: dedup on (paper_id, source, content_key), but KEEP the reviewed row on a collision — a
    human review decision is never silently discarded (Principles: a human value survives)."""
    from app.backend.persistence.schema import paper_findings as pf

    for row in conn.execute(select(pf).where(pf.c.paper_id == b_id)).mappings().all():
        clash = (
            conn.execute(
                select(pf).where(
                    pf.c.paper_id == a_id, pf.c.source == row["source"], pf.c.content_key == row["content_key"]
                )
            )
            .mappings()
            .first()
        )
        if clash is None:
            conn.execute(pf.update().where(pf.c.id == row["id"]).values(paper_id=a_id))
            snapshot["repoints"].append({"table": "paper_findings", "id": row["id"]})
        else:
            # If B's row is reviewed and A's isn't, promote A's review from B's before dropping B's.
            if row["review_state"] is not None and clash["review_state"] is None:
                conn.execute(
                    pf.update()
                    .where(pf.c.id == clash["id"])
                    .values(
                        review_state=row["review_state"],
                        review_reason=row["review_reason"],
                        reviewed_at=row["reviewed_at"],
                    )
                )
                snapshot["json_edits"].append(
                    {
                        "table": "paper_findings",
                        "column": "review_state",
                        "id": clash["id"],
                        "before": clash["review_state"],
                    }
                )
            snapshot["drops"].append({"table": "paper_findings", "row": dict(row)})
            conn.execute(pf.delete().where(pf.c.id == row["id"]))


def _merge_my_pubs(conn, a_id, b_id, snapshot):
    """my_publication_decisions: UNIQUE(paper_id). On a collision, "confirmed" beats "rejected"; else keep A's."""
    from app.backend.persistence.schema import my_publication_decisions as mpd

    b_row = conn.execute(select(mpd).where(mpd.c.paper_id == b_id)).mappings().first()
    if b_row is None:
        return
    a_row = conn.execute(select(mpd).where(mpd.c.paper_id == a_id)).mappings().first()
    if a_row is None:
        conn.execute(mpd.update().where(mpd.c.id == b_row["id"]).values(paper_id=a_id))
        snapshot["repoints"].append({"table": "my_publication_decisions", "id": b_row["id"]})
    else:
        if b_row["decision"] == "confirmed" and a_row["decision"] != "confirmed":
            conn.execute(mpd.update().where(mpd.c.id == a_row["id"]).values(decision="confirmed"))
            snapshot["json_edits"].append(
                {
                    "table": "my_publication_decisions",
                    "column": "decision",
                    "id": a_row["id"],
                    "before": a_row["decision"],
                }
            )
        snapshot["drops"].append({"table": "my_publication_decisions", "row": dict(b_row)})
        conn.execute(mpd.delete().where(mpd.c.id == b_row["id"]))


def _merge_agent_writes(conn, a_id, b_id, snapshot):
    """agent_writes: a non-FK audit log keyed by target_paper_id; re-point B -> A so the revert log stays coherent."""
    from app.backend.persistence.schema import agent_writes as aw

    for row in conn.execute(select(aw.c.id).where(aw.c.target_paper_id == b_id)).mappings().all():
        conn.execute(aw.update().where(aw.c.id == row["id"]).values(target_paper_id=a_id))
        snapshot["repoints"].append({"table": "agent_writes", "id": row["id"]})


def _merge_dismissed_pairs(conn, a_id, b_id, snapshot):
    """dismissed_duplicate_pairs (two paper columns, canonical low<high): drop the A-B pair itself; re-canonicalize
    a (B, X) pair to (min(A,X), max(A,X)); drop a pair that would collide or become a self-pair."""
    from app.backend.persistence.schema import dismissed_duplicate_pairs as ddp

    rows = (
        conn.execute(
            select(ddp).where((ddp.c.paper_id_low.in_([a_id, b_id])) | (ddp.c.paper_id_high.in_([a_id, b_id])))
        )
        .mappings()
        .all()
    )
    for row in rows:
        lo, hi = row["paper_id_low"], row["paper_id_high"]
        other = None if {lo, hi} == {a_id, b_id} else (hi if b_id == lo else lo if b_id == hi else None)
        # Drop the existing row (it involves B, or is the A-B pair itself); snapshotted so un-merge restores it.
        snapshot["drops"].append({"table": "dismissed_duplicate_pairs", "row": dict(row)})
        conn.execute(ddp.delete().where(ddp.c.id == row["id"]))
        if other is None or other == a_id:
            continue  # the A-B pair (or a self pair) simply disappears
        nlo, nhi = sorted((a_id, other))
        exists = conn.execute(
            select(func.count()).select_from(ddp).where(ddp.c.paper_id_low == nlo, ddp.c.paper_id_high == nhi)
        ).scalar_one()
        if not exists:
            conn.execute(insert(ddp).values(paper_id_low=nlo, paper_id_high=nhi))
            # a NEW re-canonicalized row: record it so un-merge deletes it back out
            snapshot.setdefault("inserts", []).append(
                {"table": "dismissed_duplicate_pairs", "key": {"paper_id_low": nlo, "paper_id_high": nhi}}
            )


def _rewrite_json_scopes(conn, a_id, b_id, snapshot):
    """Rewrite a merged-away paper id embedded in a JSON blob (summary scope, starred ids, research domains)."""
    from app.backend.persistence.schema import metadata

    for table_name, column in al.JSON_SCOPED:
        table = metadata.tables[table_name]
        for row in conn.execute(select(table.c.id, table.c[column])).mappings().all():
            before = row[column]
            after = _replace_paper_id_in_json(before, b_id, a_id)
            if after != before:
                conn.execute(table.update().where(table.c.id == row["id"]).values(**{column: after}))
                snapshot["json_edits"].append(
                    {"table": table_name, "column": column, "id": row["id"], "before": before}
                )


def _replace_paper_id_in_json(value, old_id, new_id):
    """Recursively replace ``old_id`` with ``new_id`` anywhere in a JSON structure; de-dups lists after replacing."""
    if isinstance(value, list):
        seen, out = set(), []
        for item in (_replace_paper_id_in_json(v, old_id, new_id) for v in value):
            marker = json.dumps(item, sort_keys=True, default=str)
            if marker not in seen:
                seen.add(marker)
                out.append(item)
        return out
    if isinstance(value, dict):
        return {k: _replace_paper_id_in_json(v, old_id, new_id) for k, v in value.items()}
    return new_id if value == old_id else value
