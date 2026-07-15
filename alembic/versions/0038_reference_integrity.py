"""reference_integrity — Meta Reference List review state.

Additive + guarded; no down-migration by design. Review state is scoped to citation instances and keyed by an
active signal-set fingerprint so materially new signals reopen review.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0038_reference_integrity"
down_revision = "0037_critical_review_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "reference_entities" not in tables:
        op.create_table(
            "reference_entities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("normalized_key", sa.String(length=255), nullable=False),
            sa.Column("doi", sa.String(length=255)),
            sa.Column("openalex_work_id", sa.String(length=255)),
            sa.Column("semantic_scholar_paper_id", sa.String(length=255)),
            sa.Column("title", sa.Text()),
            sa.Column("authors_json", sa.JSON()),
            sa.Column("year", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("normalized_key", name="uq_reference_entities_normalized_key"),
        )
        op.create_index("ix_reference_entities_doi", "reference_entities", ["doi"])

    if "reference_instances" not in tables:
        op.create_table(
            "reference_instances",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("citing_paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reference_entity_id", sa.Integer(), sa.ForeignKey("reference_entities.id", ondelete="SET NULL")),
            sa.Column("instance_key", sa.String(length=64), nullable=False),
            sa.Column("source", sa.String(length=60), nullable=False),
            sa.Column("source_ordinal", sa.Integer(), nullable=False),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("title", sa.Text()),
            sa.Column("authors_json", sa.JSON()),
            sa.Column("year", sa.Integer()),
            sa.Column("doi", sa.String(length=255)),
            sa.Column("context_json", sa.JSON()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("citing_paper_id", "instance_key", name="uq_reference_instances_paper_key"),
        )
        op.create_index("ix_reference_instances_paper", "reference_instances", ["citing_paper_id"])
        op.create_index("ix_reference_instances_entity", "reference_instances", ["reference_entity_id"])

    if "reference_signals" not in tables:
        op.create_table(
            "reference_signals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "citation_instance_id",
                sa.Integer(),
                sa.ForeignKey("reference_instances.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("detector_kind", sa.String(length=60), nullable=False),
            sa.Column("detector_status", sa.String(length=60), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=False),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("snapshot_marker", sa.String(length=255), nullable=False),
            sa.Column("signal_key", sa.String(length=64), nullable=False),
            sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint(
                "citation_instance_id",
                "detector_kind",
                "signal_key",
                name="uq_reference_signals_instance_kind_key",
            ),
        )
        op.create_index("ix_reference_signals_instance", "reference_signals", ["citation_instance_id"])

    if "reference_reviews" not in tables:
        op.create_table(
            "reference_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "citation_instance_id",
                sa.Integer(),
                sa.ForeignKey("reference_instances.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("signal_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("state", sa.String(length=30), nullable=False, server_default="unreviewed"),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("reference_entity_id", sa.Integer()),
            sa.Column("review_snapshot_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.CheckConstraint(
                "state IN ('unreviewed', 'dismissed', 'confirmed_problem')",
                name="reference_review_state_valid",
            ),
            sa.UniqueConstraint(
                "citation_instance_id",
                "signal_fingerprint",
                name="uq_reference_reviews_instance_fingerprint",
            ),
        )
        op.create_index("ix_reference_reviews_instance", "reference_reviews", ["citation_instance_id"])


def downgrade() -> None:
    return
