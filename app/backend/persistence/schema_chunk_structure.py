"""Derived structural classification for chunks (inc 577, H1a) -- a sibling table, never a retrofit.

`chunks.text`, `chunks.section` and every other ingest-time column are untouched by this module and
by everything that writes it. This is additive, derived, and re-derivable: dropping the table would
return the app to its exact prior behavior, because **nothing on the retrieval path reads it**.

Two deliberate shape decisions, both from the evidence-hygiene study's FINAL VALIDATION section:

* **`evidence_role` is not a boolean.** A reference entry is not evidence for a scientific claim but
  is real evidence for "what did this paper cite?", so eligibility is *task-relative* and cannot be
  frozen into one global flag. The pair (`chunk_type`, `evidence_role`) records what a unit IS;
  which questions it may answer is computed per question, later.
* **`unknown` is a first-class value and never implies ineligibility.** Measured on the testing
  library, `unknown` holds real fragmentary statistics ("β = 0.086, SE = 0.015, z = 5.664,
  p < 0.00001"). Treating it as junk would delete evidence.

Staleness is decided by (`raw_sha`, `chunk_version`) against the live chunk row, so a re-ingest
invalidates a derived row rather than letting it silently masquerade as current.
"""

from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Index, Integer, Table, Text, func

from app.backend.persistence.schema_base import enum_check, metadata

# The validated closed vocabulary. `running_footer` stays distinct from `running_head` because the
# detector already separates them by page band; collapsing them would discard real information.
CHUNK_TYPES = (
    "body_prose",
    "abstract_prose",
    "caption",
    "reference_entry",
    "running_head",
    "running_footer",
    "table_cell_debris",
    "heading_fragment",
    "publication_metadata",
    "keyword_line",
    "citation_instruction",
    "math_or_symbol",
    "unknown",
)

# What KIND of evidence a unit can be -- not whether it is eligible for any particular question.
EVIDENCE_ROLES = ("scientific", "bibliographic", "structural", "unknown")

# How the reference region was established for this chunk's paper.
REFERENCE_REGION_SOURCES = ("anchored", "heuristic", "none")

DERIVATION_VERSION = "chunk-structure-v1"

chunk_structure = Table(
    "chunk_structure",
    metadata,
    Column("chunk_id", ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True),
    Column("chunk_type", Text, nullable=False),
    Column("evidence_role", Text, nullable=False),
    Column("reason_codes_json", Text),  # ordered rule ids that fired, for audit
    Column("confidence", Float),
    Column("derivation_version", Text, nullable=False),
    # FULL sha256 of chunks.text at derivation time (not a prefix): this decides staleness, so the
    # collision argument is worth removing outright.
    Column("raw_sha", Text, nullable=False),
    Column("chunk_version", Text, nullable=False),
    # Tri-state: 1 in region, 0 outside, NULL not determined. Region membership is strong structural
    # evidence, NOT final chunk identity -- real prose was measured inside imperfect inferred bounds.
    Column("reference_region", Integer),
    Column("reference_region_source", Text),
    Column("repeated_boilerplate", Integer),  # tri-state, same convention
    Column("created_at", Text, server_default=func.current_timestamp(), nullable=False),
    enum_check("chunk_type", CHUNK_TYPES, "chunk_type_known"),
    enum_check("evidence_role", EVIDENCE_ROLES, "evidence_role_known"),
    Index("ix_chunk_structure_chunk_type", "chunk_type"),
    Index("ix_chunk_structure_derivation_version", "derivation_version"),
)

__all__ = [
    "CHUNK_TYPES",
    "DERIVATION_VERSION",
    "EVIDENCE_ROLES",
    "REFERENCE_REGION_SOURCES",
    "chunk_structure",
]
