"""Deterministic PDF source structure (inc 578, H1b).

Three sibling tables in the 0074 ``paper_sections`` / 0079 ``chunk_structure`` mould -- additive,
never a retrofit. No column on ``chunks`` or ``attachments`` is added or altered, so no
``op.batch_alter_table`` copy-and-move is needed here.

Revision ID: 0080_source_components
Revises: 0079_chunk_structure
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0080_source_components"
down_revision = "0079_chunk_structure"
branch_labels = None
depends_on = None

# Re-declared literally rather than imported from the schema module, so this migration stays
# frozen against future vocabulary edits (the 0079 convention).
_COMPONENT_KINDS = ("text_block", "line", "span", "heading", "image")
_FIGURE_SOURCES = ("grobid",)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "source_pages" not in existing:
        op.create_table(
            "source_pages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "attachment_id",
                sa.Integer(),
                sa.ForeignKey("attachments.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("page_number", sa.Integer(), nullable=False),
            sa.Column("width", sa.Float(), nullable=False),
            sa.Column("height", sa.Float(), nullable=False),
            sa.Column("rotation", sa.Integer(), nullable=False),
            sa.Column("coordinate_system", sa.Text(), nullable=False),
            sa.Column("extraction_tool", sa.Text(), nullable=False),
            sa.Column("extraction_version", sa.Text(), nullable=False),
            sa.Column("derivation_version", sa.Text(), nullable=False),
            # With derivation_version this decides staleness against the live attachment.
            sa.Column("source_checksum", sa.Text(), nullable=False),
            sa.Column("created_at", sa.Text(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.CheckConstraint("page_number >= 1", name="ck_source_pages_page_number_positive"),
            sa.CheckConstraint("width > 0 AND height > 0", name="ck_source_pages_dimensions_positive"),
            sa.CheckConstraint("rotation IN (0, 90, 180, 270)", name="ck_source_pages_rotation_known"),
            sa.CheckConstraint(
                "length(trim(coordinate_system)) > 0", name="ck_source_pages_coordinate_system_non_empty"
            ),
            sa.CheckConstraint("length(trim(source_checksum)) > 0", name="ck_source_pages_source_checksum_non_empty"),
            # Declared inside create_table: SQLite's ALTER dialect cannot add a UNIQUE constraint
            # to an existing table (op.create_unique_constraint raises NotImplementedError).
            sa.UniqueConstraint("attachment_id", "page_number", name="uq_source_pages_attachment_id_page_number"),
        )

    if "source_components" not in existing:
        op.create_table(
            "source_components",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "source_page_id",
                sa.Integer(),
                sa.ForeignKey("source_pages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("source_components.id", ondelete="CASCADE")),
            sa.Column("kind", sa.Text(), nullable=False),
            # MuPDF's own block["number"] -- NOT the post-sort ordinal chunks.bbox_json carries.
            sa.Column("native_order", sa.Integer()),
            sa.Column("sorted_order", sa.Integer()),
            sa.Column("child_order", sa.Integer()),
            sa.Column("x0", sa.Float()),
            sa.Column("y0", sa.Float()),
            sa.Column("x1", sa.Float()),
            sa.Column("y1", sa.Float()),
            sa.Column("text", sa.Text()),
            sa.Column("font", sa.Text()),
            sa.Column("font_size", sa.Float()),
            sa.Column("flags", sa.Integer()),
            sa.Column("dir_x", sa.Float()),
            sa.Column("dir_y", sa.Float()),
            sa.Column("wmode", sa.Integer()),
            sa.CheckConstraint(f"kind IN ({_quoted(_COMPONENT_KINDS)})", name="ck_source_components_kind_known"),
        )
        op.create_index("ix_source_components_parent_id", "source_components", ["parent_id"])
        op.create_index("ix_source_components_page_kind", "source_components", ["source_page_id", "kind"])

    if "paper_figures" not in existing:
        op.create_table(
            "paper_figures",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "attachment_id",
                sa.Integer(),
                sa.ForeignKey("attachments.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("source", sa.Text(), nullable=False),
            sa.Column("xml_id", sa.Text()),
            sa.Column("figure_type", sa.Text()),
            sa.Column("label", sa.Text()),
            sa.Column("head", sa.Text()),
            sa.Column("description", sa.Text()),
            sa.Column("table_grid_json", sa.Text()),
            # NULL is an honest permanent state for a pre-H1b parse, never a staleness signal.
            sa.Column("page_number", sa.Integer()),
            sa.Column("x0", sa.Float()),
            sa.Column("y0", sa.Float()),
            sa.Column("x1", sa.Float()),
            sa.Column("y1", sa.Float()),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.Text(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.CheckConstraint(f"source IN ({_quoted(_FIGURE_SOURCES)})", name="ck_paper_figures_source_known"),
            sa.CheckConstraint("page_number IS NULL OR page_number >= 1", name="ck_paper_figures_page_number_positive"),
        )
        op.create_index("ix_paper_figures_paper_id", "paper_figures", ["paper_id"])
        op.create_index("ix_paper_figures_attachment_id", "paper_figures", ["attachment_id"])


def downgrade() -> None:
    # Additive tables, like 0052/0054-0057/0070-0074/0079 -- 0001 owns eventual metadata teardown.
    pass
