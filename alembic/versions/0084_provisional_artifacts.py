"""Provisional direct-PDF capture (#61): ``provisional_artifacts`` + ``capture_events``.

A direct-PDF browser capture with no resolvable canonical identity used to be either fabricated into
an anonymous Paper or terminally refused (f03b242c). Neither preserves the user's artifact correctly.
This adds the two tables the provisional-ingestion workflow needs: one row per distinct PDF object
(``provisional_artifacts``, keyed by content hash) and one row per encounter with that object
(``capture_events``) — kept separate so re-capturing already-known bytes records new provenance
without ever creating a second physical file.

Additive and idempotent (like 0002-0083): a *fresh* database already has both tables from 0001's
``metadata.create_all``, so the create is guarded and skipped there; an existing database gets it here.

Revision ID: 0084_provisional_artifacts
Revises: 0083_critical_read_snapshots
Create Date: 2026-09-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0084_provisional_artifacts"
down_revision = "0083_critical_read_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    if "provisional_artifacts" not in existing:
        op.create_table(
            "provisional_artifacts",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("content_hash", sa.Text(), nullable=False),
            sa.Column("pdf_path", sa.Text(), nullable=False),
            sa.Column("identity_state", sa.Text(), nullable=False, server_default="unresolved"),
            sa.Column("promotion_state", sa.Text(), nullable=False, server_default="pending_review"),
            sa.Column("resolved_paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="SET NULL")),
            sa.Column("evidence_json", sa.Text()),
            sa.Column("provenance_sidecar_state", sa.Text(), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.UniqueConstraint("content_hash", name="uq_provisional_artifacts_content_hash"),
            sa.CheckConstraint(
                "identity_state IN ('unresolved', 'resolved')",
                name="ck_provisional_artifacts_identity_state_valid",
            ),
            sa.CheckConstraint(
                "promotion_state IN "
                "('pending_review', 'attachment_conflict', 'processing_failed', 'indexing_unavailable', 'promoted')",
                name="ck_provisional_artifacts_promotion_state_valid",
            ),
            sa.CheckConstraint(
                "provenance_sidecar_state IN ('ok', 'pending', 'error')",
                name="ck_provisional_artifacts_provenance_sidecar_state_valid",
            ),
        )

    if "capture_events" not in existing:
        op.create_table(
            "capture_events",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column(
                "artifact_id", sa.Text(), sa.ForeignKey("provisional_artifacts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("source_url", sa.Text()),
            sa.Column("captured_at_client", sa.Text()),
            sa.Column("received_at_server", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("original_filename", sa.Text()),
            sa.Column("producer_kind", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
