"""WIP sections, tasks, and Library-reference relationships.

Revision ID: 0049_wip_workflow
Revises: 0048_wip_foundation
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "0049_wip_workflow"
down_revision = "0048_wip_foundation"
branch_labels = None
depends_on = None

DEFAULT_SECTIONS = (
    "Title page",
    "Abstract",
    "Introduction",
    "Method",
    "Results",
    "Discussion",
    "References",
    "Tables",
    "Figures",
    "Supplement",
    "Open practices statement",
    "Author contributions",
    "Data availability statement",
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "wip_sections" not in existing:
        op.create_table(
            "wip_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(36), nullable=False),
            sa.Column(
                "manuscript_id", sa.Integer(), sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="not-started"),
            sa.Column("notes", sa.Text()),
            sa.Column("content_detected", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("uid", name="uq_wip_sections_uid"),
            sa.UniqueConstraint("manuscript_id", "position", name="uq_wip_sections_position"),
            sa.CheckConstraint(
                "status IN ('not-started','outlined','drafting','complete','needs-revision','under-review','approved','not-applicable')",
                name="ck_wip_sections_wip_sections_status",
            ),
        )
        op.create_index("ix_wip_sections_manuscript_id", "wip_sections", ["manuscript_id"])
    if "wip_tasks" not in existing:
        op.create_table(
            "wip_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(36), nullable=False),
            sa.Column(
                "manuscript_id", sa.Integer(), sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("status", sa.String(30), nullable=False, server_default="open"),
            sa.Column("due_date", sa.Date()),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("wip_sections.id", ondelete="SET NULL")),
            sa.Column("file_id", sa.Integer(), sa.ForeignKey("wip_files.id", ondelete="SET NULL")),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="SET NULL")),
            sa.Column("finding_id", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("completed_at", sa.DateTime()),
            sa.UniqueConstraint("uid", name="uq_wip_tasks_uid"),
            sa.CheckConstraint(
                "status IN ('open','in-progress','blocked','complete','deferred','cancelled')",
                name="ck_wip_tasks_wip_tasks_status",
            ),
        )
        op.create_index("ix_wip_tasks_manuscript_status", "wip_tasks", ["manuscript_id", "status"])
    if "wip_references" not in existing:
        op.create_table(
            "wip_references",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "manuscript_id", sa.Integer(), sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("relationship_state", sa.String(30), nullable=False, server_default="possibly-cited"),
            sa.Column("notes", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("manuscript_id", "paper_id", name="uq_wip_references_manuscript_paper"),
            sa.CheckConstraint(
                "relationship_state IN ('cited','possibly-cited','background-reading','to-cite','rejected-for-use','needs-verification')",
                name="ck_wip_references_wip_references_state",
            ),
        )
        op.create_index("ix_wip_references_paper_id", "wip_references", ["paper_id"])

    section_count = bind.execute(sa.text("SELECT count(*) FROM wip_sections")).scalar_one()
    if section_count == 0:
        manuscript_ids = bind.execute(sa.text("SELECT id FROM wip_manuscripts")).scalars()
        for manuscript_id in manuscript_ids:
            for position, name in enumerate(DEFAULT_SECTIONS):
                bind.execute(
                    sa.text(
                        "INSERT INTO wip_sections (uid, manuscript_id, name, position) "
                        "VALUES (:uid, :manuscript_id, :name, :position)"
                    ),
                    {"uid": str(uuid4()), "manuscript_id": manuscript_id, "name": name, "position": position},
                )


def downgrade() -> None:
    pass
