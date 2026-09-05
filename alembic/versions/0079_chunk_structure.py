"""Add chunk_structure: derived, inspectable structural classification for chunks (inc 577, H1a).

A sibling table to `chunks` in the 0074 `paper_sections` mould -- additive, never a retrofit. No
column on `chunks` is added or altered, so no `op.batch_alter_table` copy-and-move is needed here.

Nothing on the retrieval path reads this table in this increment: it is instrumentation, shipped so
the substrate can be observed and audited before any of it is trusted to change behavior.

Revision ID: 0079_chunk_structure
Revises: 0078_imported_collection_axes
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0079_chunk_structure"
down_revision = "0078_imported_collection_axes"
branch_labels = None
depends_on = None

_CHUNK_TYPES = (
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
_EVIDENCE_ROLES = ("scientific", "bibliographic", "structural", "unknown")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "chunk_structure" in inspector.get_table_names():
        return
    op.create_table(
        "chunk_structure",
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("chunk_type", sa.Text(), nullable=False),
        sa.Column("evidence_role", sa.Text(), nullable=False),
        sa.Column("reason_codes_json", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("derivation_version", sa.Text(), nullable=False),
        # FULL sha256 of chunks.text at derivation time; with chunk_version it decides staleness.
        sa.Column("raw_sha", sa.Text(), nullable=False),
        sa.Column("chunk_version", sa.Text(), nullable=False),
        sa.Column("reference_region", sa.Integer()),
        sa.Column("reference_region_source", sa.Text()),
        sa.Column("repeated_boilerplate", sa.Integer()),
        sa.Column("created_at", sa.Text(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint(f"chunk_type IN ({_quoted(_CHUNK_TYPES)})", name="ck_chunk_structure_chunk_type_known"),
        sa.CheckConstraint(
            f"evidence_role IN ({_quoted(_EVIDENCE_ROLES)})", name="ck_chunk_structure_evidence_role_known"
        ),
    )
    op.create_index("ix_chunk_structure_chunk_type", "chunk_structure", ["chunk_type"])
    op.create_index("ix_chunk_structure_derivation_version", "chunk_structure", ["derivation_version"])


def downgrade() -> None:
    # Additive table, like 0052/0054-0057/0070-0074 -- 0001 owns eventual metadata teardown.
    pass
