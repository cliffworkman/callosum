"""Data access for paper tags — lightweight free-form labels (inc 71).

Distinct from the heavyweight semantic axes: a tag is just a name attached to papers (many-to-many via
`paper_tags`). The Zotero importer already populates these tables (`_upsert_tags`), so imported papers may
carry tags. Extracted to its own module (mirroring `dedup_repo.py`) to keep `repository.py` under the
600-line cap. All bound-param SQLAlchemy Core (rule #3).
"""

from __future__ import annotations

from sqlalchemy import Connection, RowMapping, delete, func, insert, select, update

from app.backend.persistence.schema import paper_tags, suppressed_paper_tags, tags

TAG_NAME_MAX = 100

# inc 207 (A5): the fixed tag-color palette. A tag stores a palette KEY (not arbitrary hex) — the frontend maps the
# key to a theme-aware token, so colors stay legible in light + dark. An allowlist (rule #3/#4); NULL = uncolored.
TAG_COLORS = ("red", "orange", "amber", "green", "teal", "blue", "purple", "gray")

# --- Tag provenance vocabulary (backlog #9 formalization) ---
# `tags.import_source` is a free-text String(100) column, but every producer — present or future — writes a
# value of the shape ``{namespace}:{origin}``, with exactly one bare exception: the literal ``"user"`` (a human
# typed the tag; there is no origin to disambiguate, and it's the `add_tag_to_paper` default). Namespaces:
#   user                — the sole bare value; a human-typed tag.
#   import:{system}      — a tag carried over from a bulk reference-manager import (e.g. ``import:zotero``).
#   keyword:{system}     — an auto-derived subject/topic keyword from a metadata source (e.g. ``keyword:crossref``,
#                          ``keyword:openalex``, ``keyword:pubmed`` — inc 73/306).
#   agent:{system}       — written by an autonomous agent action (e.g. ``agent:mcp`` — the MCP agent, B1 SP2).
#   system:{fact}        — read-only per-paper system-facts (e.g. retraction / evidence-linked correction).
# A new producer must pick an existing namespace or, if none fits, propose a new one here rather than writing a
# bare/ad-hoc string — that's the "future producers must follow this" contract.
TAG_SOURCE_NAMESPACES = ("user", "import", "keyword", "agent", "system")


def tag_source_namespace(source: str | None) -> str:
    """The formal namespace of a tag's `import_source`: `"user"` for the bare sentinel (or anything falsy), the
    parsed prefix for a conformant `{namespace}:{origin}` value, or `"other"` for anything that doesn't conform
    (defensive only — every in-tree producer conforms; this guards stray/legacy data, never silently reads it
    as user-authored)."""
    if not source or source == "user":
        return "user"
    namespace = source.split(":", 1)[0]
    return namespace if namespace in TAG_SOURCE_NAMESPACES else "other"


def suppress_paper_tag(conn: Connection, paper_id: int, name: str) -> None:
    """Remember that the user deleted this (imported keyword) tag from this paper (inc 143) — so a later
    re-resolve / backfill won't silently re-add it. Idempotent. Caller commits."""
    conn.execute(
        insert(suppressed_paper_tags).prefix_with("OR IGNORE").values(paper_id=paper_id, tag_name=name.strip())
    )


def unsuppress_paper_tag(conn: Connection, paper_id: int, name: str) -> None:
    """Clear a suppression (inc 143) — re-adding a tag by that name means the user wants it again. Caller commits."""
    conn.execute(
        delete(suppressed_paper_tags).where(
            suppressed_paper_tags.c.paper_id == paper_id, suppressed_paper_tags.c.tag_name == name.strip()
        )
    )


def suppressed_tag_names(conn: Connection, paper_id: int) -> set[str]:
    """The tag names the user has deleted for this paper that enrich must not re-add (inc 143)."""
    return {
        r[0]
        for r in conn.execute(
            select(suppressed_paper_tags.c.tag_name).where(suppressed_paper_tags.c.paper_id == paper_id)
        )
    }


def get_tag(conn: Connection, tag_id: int) -> RowMapping | None:
    """A single tag row as ``{id, name, import_source, color}``, or None if no such tag."""
    return (
        conn.execute(select(tags.c.id, tags.c.name, tags.c.import_source, tags.c.color).where(tags.c.id == tag_id))
        .mappings()
        .first()
    )


def get_tags_for_paper(conn: Connection, paper_id: int) -> list[RowMapping]:
    """The paper's tags as ``{id, name, import_source, color, locked}``, ordered case-insensitively by name.
    `import_source` (inc 100) distinguishes imported keywords from your tags; `color` (inc 207) is the optional
    user-chosen palette key (NULL = uncolored); `locked` is per-paper, not global."""
    stmt = (
        select(tags.c.id, tags.c.name, tags.c.import_source, tags.c.color, paper_tags.c.locked)
        .select_from(paper_tags.join(tags, tags.c.id == paper_tags.c.tag_id))
        .where(paper_tags.c.paper_id == paper_id)
        .order_by(func.lower(tags.c.name))
    )
    return list(conn.execute(stmt).mappings())


def list_tags(conn: Connection) -> list[RowMapping]:
    """Every tag as ``{id, name, import_source, color, paper_count}`` (counts via LEFT JOIN), ordered by name."""
    stmt = (
        select(
            tags.c.id,
            tags.c.name,
            tags.c.import_source,
            tags.c.color,
            func.count(paper_tags.c.paper_id).label("paper_count"),
        )
        .select_from(tags.outerjoin(paper_tags, paper_tags.c.tag_id == tags.c.id))
        .group_by(tags.c.id, tags.c.name, tags.c.import_source, tags.c.color)
        .order_by(func.lower(tags.c.name))
    )
    return list(conn.execute(stmt).mappings())


def set_tag_color(conn: Connection, tag_id: int, color: str | None) -> RowMapping | None:
    """Set (or clear, with ``color=None``) a tag's palette color. `color` must be a key in ``TAG_COLORS`` or None
    (validated at the router boundary). Returns the updated ``{id, name, import_source, color}`` or None if no such
    tag. Caller commits."""
    result = conn.execute(update(tags).where(tags.c.id == tag_id).values(color=color))
    if not result.rowcount:
        return None
    return (
        conn.execute(select(tags.c.id, tags.c.name, tags.c.import_source, tags.c.color).where(tags.c.id == tag_id))
        .mappings()
        .one()
    )


def add_tag_to_paper(conn: Connection, paper_id: int, name: str, *, import_source: str = "user") -> RowMapping:
    """Get-or-create the tag by name (UNIQUE), then link it to the paper. Idempotent (already-linked → no-op).
    `import_source` provenance is set only when the tag is **created** — an existing tag keeps its original
    source (so a user-named tag is never relabeled by a later keyword import). Returns the per-paper tag row."""
    clean = name.strip()[:TAG_NAME_MAX]
    row = (
        conn.execute(select(tags.c.id, tags.c.name, tags.c.import_source, tags.c.color).where(tags.c.name == clean))
        .mappings()
        .first()
    )
    if row is None:
        tag_id = int(conn.execute(insert(tags).values(name=clean, import_source=import_source)).inserted_primary_key[0])
        row = (
            conn.execute(select(tags.c.id, tags.c.name, tags.c.import_source, tags.c.color).where(tags.c.id == tag_id))
            .mappings()
            .one()
        )
    conn.execute(insert(paper_tags).prefix_with("OR IGNORE").values(paper_id=paper_id, tag_id=int(row["id"])))
    unsuppress_paper_tag(conn, paper_id, clean)  # inc 143: re-adding a tag clears any prior deletion-suppression
    return (
        conn.execute(
            select(tags.c.id, tags.c.name, tags.c.import_source, tags.c.color, paper_tags.c.locked)
            .select_from(paper_tags.join(tags, tags.c.id == paper_tags.c.tag_id))
            .where(paper_tags.c.paper_id == paper_id, paper_tags.c.tag_id == int(row["id"]))
        )
        .mappings()
        .one()
    )


def set_paper_tag_locked(conn: Connection, paper_id: int, tag_id: int, locked: bool) -> RowMapping | None:
    """Set a per-paper lock on a tag link. Returns the tag row for this paper or None if it is not linked."""
    result = conn.execute(
        update(paper_tags).where(paper_tags.c.paper_id == paper_id, paper_tags.c.tag_id == tag_id).values(locked=locked)
    )
    if not result.rowcount:
        return None
    return (
        conn.execute(
            select(tags.c.id, tags.c.name, tags.c.import_source, tags.c.color, paper_tags.c.locked)
            .select_from(paper_tags.join(tags, tags.c.id == paper_tags.c.tag_id))
            .where(paper_tags.c.paper_id == paper_id, paper_tags.c.tag_id == tag_id)
        )
        .mappings()
        .one()
    )


def is_paper_tag_locked(conn: Connection, paper_id: int, tag_id: int) -> bool:
    row = conn.execute(
        select(paper_tags.c.locked).where(paper_tags.c.paper_id == paper_id, paper_tags.c.tag_id == tag_id)
    ).first()
    return bool(row and row[0])


def add_tags_to_paper(conn: Connection, paper_id: int, names, *, import_source: str = "user") -> list[RowMapping]:
    """Add several tags to a paper from one source (e.g. imported keywords). Caller commits."""
    return [add_tag_to_paper(conn, paper_id, name, import_source=import_source) for name in names if str(name).strip()]


def remove_tag_from_paper(conn: Connection, paper_id: int, tag_id: int) -> bool:
    """Unlink a tag from the paper; prune the tag if it now has no papers. False if it wasn't linked.
    Inc 143: if the removed tag was an imported ``keyword:*`` tag, record a suppression so a later re-resolve /
    backfill doesn't silently re-add it (read its name/source before the row is pruned). Caller commits."""
    tag = conn.execute(select(tags.c.name, tags.c.import_source).where(tags.c.id == tag_id)).mappings().first()
    result = conn.execute(delete(paper_tags).where(paper_tags.c.paper_id == paper_id, paper_tags.c.tag_id == tag_id))
    if not result.rowcount:
        return False
    if tag and tag_source_namespace(tag["import_source"]) == "keyword":
        suppress_paper_tag(conn, paper_id, str(tag["name"]))
    still_used = conn.execute(
        select(func.count()).select_from(paper_tags).where(paper_tags.c.tag_id == tag_id)
    ).scalar_one()
    if not still_used:  # orphaned → prune so the tag list stays meaningful
        conn.execute(delete(tags).where(tags.c.id == tag_id))
    return True


def remove_tag_from_paper_by_name(conn: Connection, paper_id: int, name: str) -> bool:
    """Unlink a tag from the paper by exact name (backlog #19: a `system:*` fact producer un-tags without ever
    holding a tag id — e.g. un-retraction). False if no such tag exists or it wasn't linked on this paper (the
    common case: a paper that was never flagged). Caller commits."""
    row = conn.execute(select(tags.c.id).where(tags.c.name == name)).mappings().first()
    if row is None:
        return False
    return remove_tag_from_paper(conn, paper_id, int(row["id"]))
