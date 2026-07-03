"""Meta-analysis extraction workspace tables (workbench SP2a, inc 253).

A stateful "Extract" workspace: a **project** (a named dataset + an extraction template) has **rows** (one row = one
effect/comparison, optionally linked to a library paper) whose **cells** carry the hand-entered value + its exact
source provenance (page / quote / bbox). The row's cells feed the SP1 effect-size converter; the dataset exports to
metafor/JASP. Extract/structure/convert/export only — never pools/models (the SP1 boundary, extended).

Split out of ``schema.py`` (rule #1); registers on the shared ``metadata`` from ``schema_base`` (re-exported from
``schema.py``, so ``from app.backend.persistence.schema import ma_projects`` keeps working — the schema_findings /
schema_feed pattern).
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

from app.backend.persistence.schema_base import metadata

# A meta-analysis extraction project: a named dataset + a `design` (which converter family its rows target) + the
# `template_json` (the ordered columns, seeded from the design + user-added moderator/notes columns).
ma_projects = Table(
    "ma_projects",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(300), nullable=False),
    Column("protocol_note", Text),
    Column("design", String(40), nullable=False),
    Column("template_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)

# One extracted effect/comparison. `paper_id` references papers.id but is a PLAIN COLUMN (no FK) so a row survives a
# paper purge (the inc-216 agent_writes.target_paper_id pattern) — the dataset is the user's own extracted data.
# `converted_json` = the stored Conversion.to_dict() after a convert (g/var, exportable).
ma_rows = Table(
    "ma_rows",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("project_id", ForeignKey("ma_projects.id", ondelete="CASCADE"), nullable=False),
    Column("paper_id", Integer),
    Column("label", String(500)),
    Column("position", Integer, nullable=False),
    Column("converted_json", Text),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_ma_rows_project_id", "project_id"),
)

# One cell = a template field's value on a row + its exact source provenance (page / quote / bbox). UNIQUE(row, field)
# → one cell per field per row (upsert). bbox_json is set only by SP2a-2's select-in-PDF capture; SP2a-1 sets page +
# quote manually.
ma_cells = Table(
    "ma_cells",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("row_id", ForeignKey("ma_rows.id", ondelete="CASCADE"), nullable=False),
    Column("field_key", String(80), nullable=False),
    Column("value", Text),
    Column("page", Integer),
    Column("quote", Text),
    Column("bbox_json", Text),
    Column("origin", String(20)),  # SP2b: NULL = manual/capture; "assisted" = accepted from an AI proposal (provenance)
    UniqueConstraint("row_id", "field_key", name="uq_ma_cells_row_field"),
    Index("ix_ma_cells_row_id", "row_id"),
)

# SP2b (inc 259) — an AI-drafted CANDIDATE for a cell, physically isolated from the trusted `ma_cells` so convert +
# export stay candidate-safe with zero change. The model returns only value/quote/page; `anchor_state` is decided by
# the deterministic local locator (never the model). bbox_json is set only when `exact`. UNIQUE(row, field) → one live
# candidate per cell (a re-draft replaces it).
ma_proposals = Table(
    "ma_proposals",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("row_id", ForeignKey("ma_rows.id", ondelete="CASCADE"), nullable=False),
    Column("field_key", String(80), nullable=False),
    Column("value", Text),
    Column("quote", Text),
    Column("page", Integer),
    Column("bbox_json", Text),
    Column("anchor_state", String(20), nullable=False),  # exact | region | unanchored
    Column("reason", String(40)),  # value_not_in_quote | quote_not_found (why not exact)
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("row_id", "field_key", name="uq_ma_proposals_row_field"),
    Index("ix_ma_proposals_row_id", "row_id"),
)
