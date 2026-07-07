"""Library merge + reversible un-merge (backlog #17/#16). Bound-param SQLAlchemy Core (rule #3); every table it
touches comes from the hardcoded ``merge_allowlist`` — never from request data. One transaction per operation
(the caller commits). The reversal snapshot stored on ``merge_operations`` is self-contained: un-merge replays
it without re-reading derived state.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, func, select

from app.backend.persistence import merge_allowlist as al
from app.backend.persistence.schema import papers

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
