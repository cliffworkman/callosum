"""Data access for paper tags — lightweight free-form labels (inc 71).

Distinct from the heavyweight semantic axes: a tag is just a name attached to papers (many-to-many via
`paper_tags`). The Zotero importer already populates these tables (`_upsert_tags`), so imported papers may
carry tags. Extracted to its own module (mirroring `dedup_repo.py`) to keep `repository.py` under the
600-line cap. All bound-param SQLAlchemy Core (rule #3).
"""

from __future__ import annotations

from sqlalchemy import Connection, RowMapping, delete, func, insert, select

from app.backend.persistence.schema import paper_tags, tags

TAG_NAME_MAX = 100


def get_tags_for_paper(conn: Connection, paper_id: int) -> list[RowMapping]:
    """The paper's tags as ``{id, name, import_source}``, ordered case-insensitively by name. `import_source`
    (inc 100) lets the UI distinguish imported author/index keywords from tags you added."""
    stmt = (
        select(tags.c.id, tags.c.name, tags.c.import_source)
        .select_from(paper_tags.join(tags, tags.c.id == paper_tags.c.tag_id))
        .where(paper_tags.c.paper_id == paper_id)
        .order_by(func.lower(tags.c.name))
    )
    return list(conn.execute(stmt).mappings())


def list_tags(conn: Connection) -> list[RowMapping]:
    """Every tag as ``{id, name, import_source, paper_count}`` (counts via LEFT JOIN), ordered by name."""
    stmt = (
        select(tags.c.id, tags.c.name, tags.c.import_source, func.count(paper_tags.c.paper_id).label("paper_count"))
        .select_from(tags.outerjoin(paper_tags, paper_tags.c.tag_id == tags.c.id))
        .group_by(tags.c.id, tags.c.name, tags.c.import_source)
        .order_by(func.lower(tags.c.name))
    )
    return list(conn.execute(stmt).mappings())


def add_tag_to_paper(conn: Connection, paper_id: int, name: str, *, import_source: str = "user") -> RowMapping:
    """Get-or-create the tag by name (UNIQUE), then link it to the paper. Idempotent (already-linked → no-op).
    `import_source` provenance is set only when the tag is **created** — an existing tag keeps its original
    source (so a user-named tag is never relabeled by a later keyword import). Returns ``{id, name}``."""
    clean = name.strip()[:TAG_NAME_MAX]
    row = (
        conn.execute(select(tags.c.id, tags.c.name, tags.c.import_source).where(tags.c.name == clean))
        .mappings()
        .first()
    )
    if row is None:
        tag_id = int(conn.execute(insert(tags).values(name=clean, import_source=import_source)).inserted_primary_key[0])
        row = (
            conn.execute(select(tags.c.id, tags.c.name, tags.c.import_source).where(tags.c.id == tag_id))
            .mappings()
            .one()
        )
    conn.execute(insert(paper_tags).prefix_with("OR IGNORE").values(paper_id=paper_id, tag_id=int(row["id"])))
    return row


def add_tags_to_paper(conn: Connection, paper_id: int, names, *, import_source: str = "user") -> list[RowMapping]:
    """Add several tags to a paper from one source (e.g. imported keywords). Caller commits."""
    return [add_tag_to_paper(conn, paper_id, name, import_source=import_source) for name in names if str(name).strip()]


def remove_tag_from_paper(conn: Connection, paper_id: int, tag_id: int) -> bool:
    """Unlink a tag from the paper; prune the tag if it now has no papers. False if it wasn't linked.
    Caller commits."""
    result = conn.execute(delete(paper_tags).where(paper_tags.c.paper_id == paper_id, paper_tags.c.tag_id == tag_id))
    if not result.rowcount:
        return False
    still_used = conn.execute(
        select(func.count()).select_from(paper_tags).where(paper_tags.c.tag_id == tag_id)
    ).scalar_one()
    if not still_used:  # orphaned → prune so the tag list stays meaningful
        conn.execute(delete(tags).where(tags.c.id == tag_id))
    return True
