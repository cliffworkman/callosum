"""Deterministic PDF source structure (inc 578, H1b) -- sibling tables, never a retrofit.

Callosum's extractor observes far more structure than it keeps. ``extract_pdf`` walks a full
page -> block -> line -> span tree, then flattens it: page width/height are computed and
dropped, page rotation is never read, block bbox survives only long enough to associate link
annotations, every span's font/size/flags are discarded, and image blocks are skipped whole.
What reaches ``chunks`` is one whitespace-collapsed string per text block plus per-span
rectangles. Two independent studies (``.claude/docs/research/2026-09-05_proposition-preserving-
evidence-units.md`` and ``..._codex-evidence-unit-replication.md``) converged on the same
finding: that flattening is why a current chunk is an *extraction* unit rather than an
*evidence* unit, and why the reconstruction those studies tested could not be made safe. These
tables preserve the discarded structure so the H1c study can run without repeated forensic
PDF rereads.

**Non-load-bearing, deliberately.** Nothing on the retrieval path reads these tables. Dropping
them would return the app to its exact prior behaviour. ``chunks``, embeddings, prompts, the
verifier and quote semantics remain authoritative and unchanged; this is observational
substrate, recorded to be *observed*, not obeyed -- the same posture H1a took.

Three shape decisions worth stating, because each closes a trap the studies found:

* **Native and sorted order are separate columns, and neither is "reading order".**
  ``extract_pdf`` calls ``get_text("dict", sort=True)``, which reorders blocks by
  (bottom-y, left-x) *without* renumbering MuPDF's own ``block["number"]``.
  ``chunks.bbox_json["block"]`` is therefore the post-sort enumerate ordinal -- and it counts
  image blocks that are then dropped, so it has gaps. ``quote_matching.py`` separately stores
  MuPDF's *native* number. The two integers are different numbering schemes that share a key
  name. Measured over 30 PDFs, stored order disagrees with native order on 70% of pages by more
  than 25%; on a 12-PDF probe 117 of 184 pages had the two out of sequence. Both are recorded
  here under distinct names, and **neither establishes paragraph continuity** -- adjacency is
  not semantic relation.
* **Style signals are recorded, never interpreted.** Font name, size and flags are preserved
  because they are deterministic extractor output. Larger or bold text may help a future
  heading detector; this layer does not assert that larger/bold *is* a heading.
* **A pure heading is a component, not evidence.** ``make_chunk_drafts`` recognizes a
  single-line heading block, advances its section tracker, and emits no chunk at all -- the
  heading text is lost outright today. It is preserved here as a ``heading`` component and is
  deliberately not bound to any neighbouring prose; heading/body scope is an H1c question.

Staleness is decided by (``source_checksum``, ``derivation_version``) against the live
attachment, so a replaced or re-ingested PDF invalidates these rows rather than letting them
masquerade as current.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    func,
)

from app.backend.persistence.schema_base import metadata, non_empty_check

# What the extractor structurally observed. NOT a semantic classification -- `chunk_structure`'s
# `chunk_type` is a separate, later observation *about a chunk*; these are the raw layers of the
# extractor's own tree. `heading` is a text block that `make_chunk_drafts` consumes for section
# tracking and never turns into a chunk. `image` is a raster block dropped at ingest today.
SOURCE_COMPONENT_KINDS = ("text_block", "line", "span", "heading", "image")

# Where a figure/table record came from. Only GROBID supplies these today.
FIGURE_SOURCES = ("grobid",)

# Bump to invalidate every derived row; the next backfill re-derives with no migration.
SOURCE_DERIVATION_VERSION = "source-components-v1"

source_pages = Table(
    "source_pages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("attachment_id", ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False),
    Column("page_number", Integer, nullable=False),
    Column("width", Float, nullable=False),
    Column("height", Float, nullable=False),
    # PDF page rotation in degrees (0/90/180/270). Never read at ingest today; the viewer
    # re-derives it from pdf.js and refuses an exact overlay when it is non-zero.
    Column("rotation", Integer, nullable=False),
    Column("coordinate_system", Text, nullable=False),
    Column("extraction_tool", Text, nullable=False),
    Column("extraction_version", Text, nullable=False),
    Column("derivation_version", Text, nullable=False),
    # The owning attachment's checksum at derivation time; with derivation_version it decides
    # staleness.
    Column("source_checksum", Text, nullable=False),
    Column("created_at", Text, server_default=func.current_timestamp(), nullable=False),
    CheckConstraint("page_number >= 1", name="page_number_positive"),
    CheckConstraint("width > 0 AND height > 0", name="dimensions_positive"),
    CheckConstraint("rotation IN (0, 90, 180, 270)", name="rotation_known"),
    non_empty_check("coordinate_system", "coordinate_system_non_empty"),
    non_empty_check("source_checksum", "source_checksum_non_empty"),
    UniqueConstraint("attachment_id", "page_number", name="uq_source_pages_attachment_id_page_number"),
)

source_components = Table(
    "source_components",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_page_id", ForeignKey("source_pages.id", ondelete="CASCADE"), nullable=False),
    # Self-referencing hierarchy: span -> line -> text_block/heading. NULL for a top-level block.
    Column("parent_id", ForeignKey("source_components.id", ondelete="CASCADE")),
    Column("kind", Text, nullable=False),
    # MuPDF's own block["number"], preserved verbatim. Survives sort=True un-renumbered.
    # NOT reading order, NOT comparable to `sorted_order`, NOT a continuity claim.
    Column("native_order", Integer),
    # Position in the geometrically sorted (bottom-y, left-x) block list -- the same ordinal
    # `chunks.bbox_json["block"]` carries, including the image blocks ingest then drops.
    Column("sorted_order", Integer),
    # Ordinal within the parent: line index within its block, span index within its line.
    Column("child_order", Integer),
    Column("x0", Float),
    Column("y0", Float),
    Column("x1", Float),
    Column("y1", Float),
    # Exact extractor text, NOT whitespace-normalized: this is structural provenance, not display
    # text. Only spans and headings carry it; block/line text is reconstructable from its spans
    # and is deliberately not duplicated at every level.
    Column("text", Text),
    Column("font", Text),
    Column("font_size", Float),
    # PyMuPDF span flags bitfield (bold/italic/serif/superscript). Recorded, never interpreted.
    Column("flags", Integer),
    # Line writing-direction cosine pair, and wmode. Preserved where exposed; rotated/vertical
    # text is silently flattened today.
    Column("dir_x", Float),
    Column("dir_y", Float),
    Column("wmode", Integer),
    CheckConstraint(
        "kind IN ('text_block', 'line', 'span', 'heading', 'image')",
        name="kind_known",
    ),
    # Two indexes only. The composite serves both page-scoped and (page, kind) reads because
    # source_page_id is its leftmost column, so a separate single-column index would be dead
    # weight on ~1.15M rows. parent_id earns its own: walking span -> line -> block is the
    # hierarchy read H1c needs. Deliberately no index on text/font/geometry, and deliberately
    # no full-text index over spans -- neither is justified until a study asks for it.
    Index("ix_source_components_parent_id", "parent_id"),
    Index("ix_source_components_page_kind", "source_page_id", "kind"),
)

# GROBID's own figure/table records. Structural metadata only: a caption and, where the pinned
# GROBID build supplies coordinates, a region. It is never proof of scientific meaning, is never
# retrieval-facing, and no plotted value is ever interpreted from it.
paper_figures = Table(
    "paper_figures",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("attachment_id", ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False),
    Column("source", Text, nullable=False),
    # GROBID's own xml:id (e.g. "fig_0", "tab_0") -- body <ref target="#fig_0"> points at it.
    Column("xml_id", Text),
    # GROBID's explicit @type ("table") when present; NULL for an ordinary figure. Never inferred.
    Column("figure_type", Text),
    Column("label", Text),
    # <head> -- the short label line ("Fig 1 ."). For tables GROBID puts the caption here.
    Column("head", Text),
    # <figDesc> -- the caption body. Empty for table figures.
    Column("description", Text),
    # GROBID's own <table><row><cell> grid, verbatim and bounded, as JSON rows-of-cells. This is
    # GROBID's supplied structure, NOT a reconstruction by us; `document_tables.py`'s PyMuPDF row
    # evidence is a separate, unrelated system that H1b does not touch or persist.
    Column("table_grid_json", Text),
    # Page/region from a nested <graphic coords>, or from the figure's own @coords once the
    # request asks for them. NULL is an honest, permanent state for a pre-H1b parse and for any
    # figure the pinned GROBID build does not locate -- it is never a staleness or error signal.
    Column("page_number", Integer),
    Column("x0", Float),
    Column("y0", Float),
    Column("x1", Float),
    Column("y1", Float),
    Column("order_index", Integer, nullable=False),
    Column("created_at", Text, server_default=func.current_timestamp(), nullable=False),
    CheckConstraint("source IN ('grobid')", name="source_known"),
    CheckConstraint("page_number IS NULL OR page_number >= 1", name="page_number_positive"),
    Index("ix_paper_figures_paper_id", "paper_id"),
    Index("ix_paper_figures_attachment_id", "attachment_id"),
)

__all__ = [
    "FIGURE_SOURCES",
    "SOURCE_COMPONENT_KINDS",
    "SOURCE_DERIVATION_VERSION",
    "paper_figures",
    "source_components",
    "source_pages",
]
