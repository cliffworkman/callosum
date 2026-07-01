"""Portable library bundle (B2 SP1): export/import metadata + tags + annotations + axis definitions — NO PDFs.

A versioned JSON file the user hands off — **no server, no automatic egress**; copyright-safe (no PDF bytes; the
recipient re-acquires their own copies via the OA lane). Reuses the cross-library identity primitive
(`find_existing_paper_by_identity`, keeping the matched row) + `create_paper` + the tags/annotations repos + the
inc-211 curated-axis machinery. Merge on import is **additive & non-destructive** — an existing paper (matched by
identity) keeps its own metadata and only *gains* the bundle's tags + annotations. Syntheses + PDFs are SP2/never
(see the design spec). No new dependency, no migration.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, select

from app.backend.clustering.axis_assignments import CURATED_KIND, add_manual_assignment, append_member_position
from app.backend.clustering.axis_scoring import create_axis
from app.backend.metadata.citation_import import csl_record_to_paper_fields
from app.backend.persistence import annotations_repo, tags_repo
from app.backend.persistence.repository import create_paper, find_existing_paper_by_identity
from app.backend.persistence.schema import axes, cluster_node_papers, cluster_nodes, papers

BUNDLE_VERSION = 1
MAX_BUNDLE_BYTES = 20_000_000  # ~20 MB — annotations add bulk vs. the 5 MB citation-import cap (rule #4)
MAX_BUNDLE_PAPERS = 20_000
MAX_TAGS_PER_PAPER = 200
MAX_ANNOTATIONS_PER_PAPER = 500
BUNDLE_SOURCE = "bundle-import"  # kept out of the enrich-clobber allowlist, like user-edited/discovery-import
_SHAREABLE_AXIS_KINDS = ("standard", CURATED_KIND)  # never export my_publications (authorship, resolver-only)
_IDENTITY_FIELDS = ("doi", "openalex_work_id", "semantic_scholar_paper_id", "title", "year", "first_author_family_name")


class BundleError(ValueError):
    """A malformed / unsupported bundle (bad JSON, unknown version, wrong shape)."""


# ── export ──────────────────────────────────────────────────────────────────


def _identity(row: Any) -> dict[str, Any]:
    """The dedup keys, omitting nulls."""
    return {f: row[f] for f in _IDENTITY_FIELDS if row[f] is not None}


def _paper_entry(conn: Connection, row: Any) -> dict[str, Any]:
    pid = int(row["id"])
    return {
        "identity": _identity(row),
        "csl_json": dict(row["csl_json"]) if row["csl_json"] else {},
        "item_type": row["item_type"],
        "abstract": row["abstract"],
        "tags": [
            {"name": t["name"], "color": t["color"], "source": t["import_source"]}
            for t in tags_repo.get_tags_for_paper(conn, pid)
        ],
        "annotations": [
            {
                "page": a["page"],
                "bboxes_json": a["bboxes_json"],
                "note": a["note"],
                "color": a["color"],
                "anchor_text": a["anchor_text"],
                "prefix": a["prefix"],
                "suffix": a["suffix"],
                "source": a["source"],
            }
            for a in annotations_repo.list_annotations_for_paper(conn, pid)
        ],
    }


def _axis_entries(conn: Connection) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ax in conn.execute(select(axes).where(axes.c.kind.in_(_SHAREABLE_AXIS_KINDS))).mappings():
        entry: dict[str, Any] = {
            "label": ax["label"],
            "description": ax["description"],
            "scoring_gain": ax["scoring_gain"],
            "kind": ax["kind"],
            "members": [],
        }
        if ax["kind"] == CURATED_KIND:  # curated members are hand-picked (manual) + hand-ordered → they travel
            node = (
                conn.execute(select(cluster_nodes.c.id).where(cluster_nodes.c.axis_id == ax["id"]).limit(1))
                .scalars()
                .first()
            )
            if node is not None:
                rows = conn.execute(
                    select(papers, cluster_node_papers.c.position)
                    .select_from(cluster_node_papers.join(papers, papers.c.id == cluster_node_papers.c.paper_id))
                    .where(
                        cluster_node_papers.c.cluster_node_id == node,
                        cluster_node_papers.c.confidence.is_(None),  # manual members only
                        papers.c.deleted_at.is_(None),
                    )
                    .order_by(cluster_node_papers.c.position, papers.c.id)
                ).mappings()
                for i, r in enumerate(rows):
                    pos = r["position"]
                    entry["members"].append({"identity": _identity(r), "position": int(pos) if pos is not None else i})
        out.append(entry)
    return out


def build_bundle(conn: Connection, *, scope: str, paper_ids: list[int] | None = None) -> dict[str, Any]:
    """Serialize the library (or a selection) to a bundle dict. Whole-library carries axis definitions; a selection
    carries only its papers + tags + annotations."""
    if scope == "selection":
        ids = [int(p) for p in (paper_ids or [])]
        rows = (
            list(conn.execute(select(papers).where(papers.c.id.in_(ids), papers.c.deleted_at.is_(None))).mappings())
            if ids
            else []
        )
    else:
        rows = list(conn.execute(select(papers).where(papers.c.deleted_at.is_(None)).order_by(papers.c.id)).mappings())
    bundle: dict[str, Any] = {
        "callosum_bundle": BUNDLE_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "generator": "callosum",
        "scope": "selection" if scope == "selection" else "library",
        "papers": [_paper_entry(conn, r) for r in rows],
    }
    if scope != "selection":
        bundle["axes"] = _axis_entries(conn)
    return bundle


# ── import ──────────────────────────────────────────────────────────────────


def parse_bundle(content: str) -> dict[str, Any]:
    """Validate + parse the bundle text (bounded; unknown/absent version → BundleError). Caller catches."""
    if len(content.encode("utf-8", "ignore")) > MAX_BUNDLE_BYTES:
        raise BundleError("Bundle file too large to import.")
    try:
        data = json.loads(content)
    except Exception as exc:
        raise BundleError("Not a valid callosum bundle (could not parse JSON).") from exc
    if not isinstance(data, dict) or data.get("callosum_bundle") != BUNDLE_VERSION:
        raise BundleError("Not a callosum library bundle (missing or unsupported version).")
    if not isinstance(data.get("papers"), list):
        raise BundleError("Bundle has no papers list.")
    return data


def _fields_from_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Build create_paper kwargs from an entry's csl_json (else a minimal record from its identity). None → skip."""
    csl = entry.get("csl_json") if isinstance(entry.get("csl_json"), dict) else {}
    ident = entry.get("identity") if isinstance(entry.get("identity"), dict) else {}
    if not csl:
        title = ident.get("title")
        if not title and not ident.get("doi"):
            return None
        csl = {"title": title, "DOI": ident.get("doi")}
    fields = csl_record_to_paper_fields(csl)
    if entry.get("item_type"):
        fields["item_type"] = str(entry["item_type"])
    if not fields.get("abstract") and entry.get("abstract"):
        fields["abstract"] = str(entry["abstract"])
    return fields


def _anno_key(a: Any) -> tuple:
    return (a["page"], json.dumps(a["bboxes_json"], sort_keys=True, default=str), a["note"])


def _axis_member_ids(conn: Connection, axis_id: int) -> set[int]:
    node = conn.execute(select(cluster_nodes.c.id).where(cluster_nodes.c.axis_id == axis_id).limit(1)).scalars().first()
    if node is None:
        return set()
    return {
        int(r)
        for r in conn.execute(
            select(cluster_node_papers.c.paper_id).where(cluster_node_papers.c.cluster_node_id == node)
        ).scalars()
    }


def _get_or_create_axis(conn: Connection, label: str, description: Any, kind: str, gain: Any) -> tuple[int, bool]:
    """Match a shareable-kind axis by label (reuse, definition left as-is — non-destructive); else create it."""
    existing = (
        conn.execute(select(axes.c.id).where(axes.c.label == label, axes.c.kind.in_(_SHAREABLE_AXIS_KINDS)).limit(1))
        .scalars()
        .first()
    )
    if existing is not None:
        return int(existing), False
    axis_id = create_axis(conn, label=label, description=str(description) if description else None, kind=kind)
    if isinstance(gain, (int, float)):
        conn.execute(axes.update().where(axes.c.id == axis_id).values(scoring_gain=float(gain)))
    return axis_id, True


def import_bundle(conn: Connection, bundle: dict[str, Any]) -> dict[str, Any]:
    """Merge a parsed bundle into the library (additive, non-destructive). Returns ``{summary, created}`` — the
    caller embeds ``created`` (the new paper ids). Each paper/axis runs in its own savepoint so a bad one is
    skipped, never fatal."""
    summary = {
        "papers_created": 0,
        "papers_merged": 0,
        "tags_applied": 0,
        "annotations_added": 0,
        "axes_created": 0,
        "axes_members_added": 0,
        "skipped": 0,
    }
    created: list[int] = []

    for entry in bundle["papers"][:MAX_BUNDLE_PAPERS]:
        try:
            with conn.begin_nested():
                if not isinstance(entry, dict):
                    summary["skipped"] += 1
                    continue
                ident = entry.get("identity") if isinstance(entry.get("identity"), dict) else {}
                fields = _fields_from_entry(entry)
                existing = find_existing_paper_by_identity(
                    conn,
                    doi=ident.get("doi") or (fields or {}).get("doi"),
                    openalex_work_id=ident.get("openalex_work_id"),
                    semantic_scholar_paper_id=ident.get("semantic_scholar_paper_id"),
                    title=ident.get("title") or (fields or {}).get("title"),
                    year=ident.get("year") or (fields or {}).get("year"),
                    first_author_family_name=ident.get("first_author_family_name")
                    or (fields or {}).get("first_author_family_name"),
                )
                if existing is not None:
                    paper_id = int(existing[1]["id"])  # merge target — metadata untouched
                    summary["papers_merged"] += 1
                elif fields is not None:
                    paper_id = create_paper(
                        conn,
                        imported_source=BUNDLE_SOURCE,
                        openalex_work_id=ident.get("openalex_work_id"),
                        semantic_scholar_paper_id=ident.get("semantic_scholar_paper_id"),
                        **fields,
                    )
                    created.append(paper_id)
                    summary["papers_created"] += 1
                else:
                    summary["skipped"] += 1
                    continue

                for t in (entry.get("tags") or [])[:MAX_TAGS_PER_PAPER]:
                    name = str((t or {}).get("name") or "").strip()
                    if not name:
                        continue
                    row = tags_repo.add_tag_to_paper(conn, paper_id, name, import_source=str(t.get("source") or "user"))
                    summary["tags_applied"] += 1
                    color = t.get("color")
                    if color and row.get("color") is None:  # additive: only color an uncolored tag
                        tags_repo.set_tag_color(conn, int(row["id"]), str(color))

                seen = {_anno_key(a) for a in annotations_repo.list_annotations_for_paper(conn, paper_id)}
                for a in (entry.get("annotations") or [])[:MAX_ANNOTATIONS_PER_PAPER]:
                    if not isinstance(a, dict):
                        continue
                    key = (a.get("page"), json.dumps(a.get("bboxes_json"), sort_keys=True, default=str), a.get("note"))
                    if key in seen:
                        continue
                    src = a.get("source") if a.get("source") in ("user", "synthesis") else "user"
                    annotations_repo.create_annotation(
                        conn,
                        paper_id=paper_id,
                        page=int(a.get("page") or 1),
                        color=str(a.get("color") or "yellow"),
                        bboxes_json=a.get("bboxes_json"),
                        anchor_text=str(a.get("anchor_text") or ""),
                        prefix=a.get("prefix"),
                        suffix=a.get("suffix"),
                        attachment_id=None,  # per-device PDF pointer dropped; the box renders once the same PDF exists
                        source=src,
                        note=a.get("note"),
                    )
                    seen.add(key)
                    summary["annotations_added"] += 1
        except Exception:
            summary["skipped"] += 1

    for ax in bundle.get("axes") or []:
        try:
            with conn.begin_nested():
                if not isinstance(ax, dict):
                    continue
                label = str(ax.get("label") or "").strip()
                if not label:
                    continue
                kind = ax.get("kind") if ax.get("kind") in _SHAREABLE_AXIS_KINDS else "standard"
                axis_id, is_new = _get_or_create_axis(conn, label, ax.get("description"), kind, ax.get("scoring_gain"))
                if is_new:
                    summary["axes_created"] += 1
                if kind == CURATED_KIND:
                    members = _axis_member_ids(conn, axis_id)
                    for m in ax.get("members") or []:
                        mi = (m or {}).get("identity") if isinstance(m, dict) else None
                        if not isinstance(mi, dict):
                            continue
                        found = find_existing_paper_by_identity(
                            conn,
                            doi=mi.get("doi"),
                            openalex_work_id=mi.get("openalex_work_id"),
                            semantic_scholar_paper_id=mi.get("semantic_scholar_paper_id"),
                            title=mi.get("title"),
                            year=mi.get("year"),
                            first_author_family_name=mi.get("first_author_family_name"),
                        )
                        if found is None:
                            continue
                        pid = int(found[1]["id"])
                        if pid in members:
                            continue
                        add_manual_assignment(conn, axis_id=axis_id, paper_id=pid)
                        append_member_position(conn, axis_id=axis_id, paper_id=pid)
                        members.add(pid)
                        summary["axes_members_added"] += 1
        except Exception:
            pass  # a bad axis never sinks the import

    return {"summary": summary, "created": created}
