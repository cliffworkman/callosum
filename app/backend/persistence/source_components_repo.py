"""Read/write the deterministic source-component tables (inc 578, H1b).

The only module that writes ``source_pages`` / ``source_components`` / ``paper_figures``. Nothing
on the retrieval path reads any of them: Ask's chunk query joins ``chunks`` to ``attachments`` and
nothing else, and these tables are absent from ``SourceChunk``. Dropping all three would restore
the app's exact prior behaviour.

Writes are **replace-per-attachment**, so a re-ingest or a re-run of the backfill is idempotent and
an interrupted run resumes simply by re-running. Staleness is decided by
(``source_checksum``, ``derivation_version``) against the live attachment row, so a replaced PDF
invalidates its rows rather than letting them masquerade as current.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Connection

from app.backend.pdf_processing.source_components import SourcePage
from app.backend.persistence.schema import attachments
from app.backend.persistence.schema_source_components import (
    SOURCE_DERIVATION_VERSION,
    paper_figures,
    source_components,
    source_pages,
)

_log = logging.getLogger(__name__)

# Rule #4 bound on untrusted input: a pathological PDF must not be able to write unbounded rows.
# ~250k components is roughly a 380-page densely-typeset article at the measured 656 spans/page --
# far beyond any real paper. Truncation is reported, never silent.
MAX_COMPONENTS_PER_ATTACHMENT = 250_000

# Bounds for a GROBID-supplied table grid. GROBID's own output, not a reconstruction by us.
MAX_FIGURE_TABLE_ROWS = 200
MAX_FIGURE_TABLE_CELLS_PER_ROW = 50
MAX_FIGURE_CELL_CHARS = 2_000


@dataclass(frozen=True)
class StoredSourcePage:
    id: int
    attachment_id: int
    page_number: int
    width: float
    height: float
    rotation: int
    coordinate_system: str
    extraction_tool: str
    extraction_version: str
    derivation_version: str
    source_checksum: str
    is_stale: bool


def _flatten(page_id: int, page: SourcePage, next_id: int) -> tuple[list[dict[str, Any]], int]:
    """Depth-first rows with explicit, pre-allocated ids so children can name their parent.

    Ids are assigned in Python rather than round-tripping ``inserted_primary_key`` per row: a
    single 8-page article produces ~14.5k spans, so per-row inserts would dominate ingest. The
    allocation is safe because the caller has already written the page row inside this same
    transaction, which holds SQLite's write lock.
    """
    rows: list[dict[str, Any]] = []

    def emit(component: Any, parent_id: int | None, allocated: int) -> int:
        bbox = component.bbox or (None, None, None, None)
        rows.append(
            {
                "id": allocated,
                "source_page_id": page_id,
                "parent_id": parent_id,
                "kind": component.kind,
                "native_order": component.native_order,
                "sorted_order": component.sorted_order,
                "child_order": component.child_order,
                "x0": bbox[0],
                "y0": bbox[1],
                "x1": bbox[2],
                "y1": bbox[3],
                "text": component.text,
                "font": component.font,
                "font_size": component.font_size,
                "flags": component.flags,
                "dir_x": component.dir_x,
                "dir_y": component.dir_y,
                "wmode": component.wmode,
            }
        )
        cursor = allocated + 1
        for child in component.children:
            cursor = emit(child, allocated, cursor)
        return cursor

    cursor = next_id
    for component in page.components:
        cursor = emit(component, None, cursor)
    return rows, cursor


def replace_attachment_source(
    conn: Connection,
    *,
    attachment_id: int,
    pages: list[SourcePage],
    coordinate_system: str,
    extraction_tool: str,
    extraction_version: str,
    source_checksum: str,
    derivation_version: str = SOURCE_DERIVATION_VERSION,
) -> dict[str, int]:
    """Replace every source page/component for one attachment. Idempotent."""
    # CASCADE on source_pages removes the component rows; deleting the parent alone is enough.
    conn.execute(delete(source_pages).where(source_pages.c.attachment_id == attachment_id))

    written_pages = 0
    component_rows: list[dict[str, Any]] = []
    truncated = 0
    next_id = int(conn.execute(select(func.coalesce(func.max(source_components.c.id), 0))).scalar_one()) + 1

    for page in pages:
        if page.width <= 0 or page.height <= 0:
            # The schema requires positive dimensions; a degenerate page is skipped rather than
            # failing an ingest whose chunks are perfectly usable.
            continue
        result = conn.execute(
            source_pages.insert().values(
                attachment_id=attachment_id,
                page_number=page.page_number,
                width=page.width,
                height=page.height,
                rotation=page.rotation,
                coordinate_system=coordinate_system,
                extraction_tool=extraction_tool,
                extraction_version=extraction_version,
                derivation_version=derivation_version,
                source_checksum=source_checksum,
            )
        )
        written_pages += 1
        page_rows, next_id = _flatten(int(result.inserted_primary_key[0]), page, next_id)
        if len(component_rows) + len(page_rows) > MAX_COMPONENTS_PER_ATTACHMENT:
            truncated = 1
            _log.warning(
                "source components truncated at %d rows for attachment %s (page %d)",
                MAX_COMPONENTS_PER_ATTACHMENT,
                attachment_id,
                page.page_number,
            )
            break
        component_rows.extend(page_rows)

    if component_rows:
        conn.execute(source_components.insert(), component_rows)
    return {"pages": written_pages, "components": len(component_rows), "truncated": truncated}


def attachments_with_current_source(conn: Connection, derivation_version: str = SOURCE_DERIVATION_VERSION) -> set[int]:
    """Attachment ids whose source rows are present and match the live checksum + derivation version.

    This is what makes an interrupted backfill resumable without a cursor file. An attachment with
    no rows, stale rows, or rows from an older derivation version is simply absent from the set.
    """
    stmt = select(
        source_pages.c.attachment_id,
        attachments.c.checksum,
        source_pages.c.source_checksum,
        source_pages.c.derivation_version,
    ).select_from(source_pages.join(attachments, attachments.c.id == source_pages.c.attachment_id))
    seen: set[int] = set()
    incomplete: set[int] = set()
    for row in conn.execute(stmt).mappings():
        attachment_id = int(row["attachment_id"])
        seen.add(attachment_id)
        current = (
            row["derivation_version"] == derivation_version
            and (row["source_checksum"] or "") == (row["checksum"] or "")
            and bool(row["checksum"])
        )
        if not current:
            incomplete.add(attachment_id)
    return seen - incomplete


def source_page_for(conn: Connection, attachment_id: int, page_number: int) -> StoredSourcePage | None:
    """One page's identity, with staleness resolved against the live attachment checksum."""
    row = (
        conn.execute(
            select(source_pages, attachments.c.checksum.label("live_checksum"))
            .select_from(source_pages.join(attachments, attachments.c.id == source_pages.c.attachment_id))
            .where(source_pages.c.attachment_id == attachment_id, source_pages.c.page_number == page_number)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return StoredSourcePage(
        id=int(row["id"]),
        attachment_id=int(row["attachment_id"]),
        page_number=int(row["page_number"]),
        width=float(row["width"]),
        height=float(row["height"]),
        rotation=int(row["rotation"]),
        coordinate_system=row["coordinate_system"],
        extraction_tool=row["extraction_tool"],
        extraction_version=row["extraction_version"],
        derivation_version=row["derivation_version"],
        source_checksum=row["source_checksum"],
        is_stale=(row["source_checksum"] or "") != (row["live_checksum"] or ""),
    )


def components_for_page(conn: Connection, source_page_id: int) -> list[dict[str, Any]]:
    """Every component on one page, parents before children (id order is allocation order)."""
    return [
        dict(row)
        for row in conn.execute(
            select(source_components)
            .where(source_components.c.source_page_id == source_page_id)
            .order_by(source_components.c.id)
        ).mappings()
    ]


def _bounded_grid(grid: Any) -> str | None:
    """GROBID's own row/cell grid, bounded and serialized. Never a reconstruction of our own."""
    if not grid:
        return None
    rows: list[list[str]] = []
    for row in list(grid)[:MAX_FIGURE_TABLE_ROWS]:
        rows.append([str(cell)[:MAX_FIGURE_CELL_CHARS] for cell in list(row)[:MAX_FIGURE_TABLE_CELLS_PER_ROW]])
    return json.dumps(rows, ensure_ascii=False) if rows else None


def replace_paper_figures(conn: Connection, *, paper_id: int, attachment_id: int, figures: list[Any]) -> int:
    """Replace GROBID figure/caption records for one attachment. Structural metadata only.

    A figure with no coordinates is stored with NULL geometry. That is an honest permanent state --
    a pre-H1b parse never requested figure coordinates, and the pinned GROBID build does not locate
    every figure even when asked. It is never treated as stale or as an error.
    """
    conn.execute(delete(paper_figures).where(paper_figures.c.attachment_id == attachment_id))
    rows = []
    for order_index, figure in enumerate(figures):
        bbox = getattr(figure, "bbox", None) or (None, None, None, None)
        rows.append(
            {
                "paper_id": paper_id,
                "attachment_id": attachment_id,
                "source": "grobid",
                "xml_id": getattr(figure, "xml_id", None),
                "figure_type": getattr(figure, "figure_type", None),
                "label": getattr(figure, "label", None),
                "head": getattr(figure, "head", None),
                "description": getattr(figure, "description", None),
                "table_grid_json": _bounded_grid(getattr(figure, "table_grid", None)),
                "page_number": getattr(figure, "page_number", None),
                "x0": bbox[0],
                "y0": bbox[1],
                "x1": bbox[2],
                "y1": bbox[3],
                "order_index": order_index,
            }
        )
    if rows:
        conn.execute(paper_figures.insert(), rows)
    return len(rows)


def figures_for_paper(conn: Connection, paper_id: int) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            select(paper_figures).where(paper_figures.c.paper_id == paper_id).order_by(paper_figures.c.order_index)
        ).mappings()
    ]


__all__ = [
    "MAX_COMPONENTS_PER_ATTACHMENT",
    "StoredSourcePage",
    "attachments_with_current_source",
    "components_for_page",
    "figures_for_paper",
    "replace_attachment_source",
    "replace_paper_figures",
    "source_page_for",
]
