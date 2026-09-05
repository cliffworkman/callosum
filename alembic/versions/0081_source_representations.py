"""Source-representation completeness + stable logical locators (inc 579, H1b.1).

One additive sibling table plus two additive columns. No column on ``chunks``, ``attachments`` or
``source_pages`` is added or altered, and no existing H1b row changes meaning, so no
``op.batch_alter_table`` copy-and-move is needed. SQLite's ``ALTER TABLE ADD COLUMN`` with no
default is a metadata-only operation, so the two column adds are O(1) even against the ~1.09M
component rows a real library holds.

**This migration deliberately promotes nothing.** A pre-existing H1b attachment gets no
``source_representations`` row, so it is not current until ``tools/backfill_source_components.py``
re-derives it and passes the same completeness checks a new write passes. That is the conservative
choice, and it is also the necessary one: ``component_path`` and ``geometry_state`` are NULL on
every pre-H1b.1 row, so a full re-derivation is required regardless.

Revision ID: 0081_source_representations
Revises: 0080_source_components
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0081_source_representations"
down_revision = "0080_source_components"
branch_labels = None
depends_on = None

# Re-declared literally rather than imported from the schema module, so this migration stays frozen
# against future vocabulary edits (the 0079/0080 convention).
_REPRESENTATION_STATES = ("complete", "truncated", "incomplete", "failed")
_GEOMETRY_STATES = ("valid", "invalid", "unknown")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "source_representations" not in set(inspector.get_table_names()):
        op.create_table(
            "source_representations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "attachment_id",
                sa.Integer(),
                sa.ForeignKey("attachments.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("source_checksum", sa.Text(), nullable=False),
            sa.Column("extraction_tool", sa.Text(), nullable=False),
            sa.Column("extraction_version", sa.Text(), nullable=False),
            sa.Column("derivation_version", sa.Text(), nullable=False),
            # No expected component count: production cannot know one reliably before persistence.
            sa.Column("expected_pages", sa.Integer(), nullable=False),
            sa.Column("written_pages", sa.Integer(), nullable=False),
            sa.Column("skipped_pages", sa.Integer(), nullable=False),
            sa.Column("written_components", sa.Integer(), nullable=False),
            sa.Column("state", sa.Text(), nullable=False),
            sa.Column("state_reason", sa.Text()),
            sa.Column("created_at", sa.Text(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("updated_at", sa.Text(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.CheckConstraint(
                f"state IN ({_quoted(_REPRESENTATION_STATES)})",
                name="ck_source_representations_state_known",
            ),
            sa.CheckConstraint(
                "expected_pages >= 0 AND written_pages >= 0 AND skipped_pages >= 0 AND written_components >= 0",
                name="ck_source_representations_counts_non_negative",
            ),
            sa.CheckConstraint(
                "length(trim(source_checksum)) > 0",
                name="ck_source_representations_source_checksum_non_empty",
            ),
        )

    existing_columns = {column["name"] for column in inspector.get_columns("source_components")}
    if "component_path" not in existing_columns:
        op.add_column("source_components", sa.Column("component_path", sa.Text()))
    if "geometry_state" not in existing_columns:
        # The CHECK travels with the column so a value outside the vocabulary cannot be written even
        # by a hand-run statement. SQLite accepts a table-level CHECK only at CREATE time, so this
        # is expressed as a column constraint rather than a separate ALTER.
        op.add_column(
            "source_components",
            sa.Column(
                "geometry_state",
                sa.Text(),
                sa.CheckConstraint(
                    f"geometry_state IS NULL OR geometry_state IN ({_quoted(_GEOMETRY_STATES)})",
                    name="ck_source_components_geometry_state_known",
                ),
            ),
        )


def downgrade() -> None:
    # Additive, like 0052/0054-0057/0070-0074/0079/0080 -- 0001 owns eventual metadata teardown.
    pass
