"""Sync bookkeeping tables (accounts SP3a): local change-tracking + surfaced conflicts.

E2E multi-device sync (design spec ``2026-06-29-accounts-sync-design.md``) tracks which syncable rows changed
*without* touching the domain tables — ``sync_state`` holds one row per ``(collection, record_id)`` with a content
hash + version + tombstone, so the change-set is a **hash-diff at sync time** (no per-write hooks). ``sync_conflicts``
keeps the **losing** side of a last-write-wins merge so a multi-device conflict is **surfaced + recoverable**, never
silently clobbered (value A4). Both are **local-only**: they never sync, and (SP3a) the foundation makes no network
call. ``received_shares`` (SP4c, backlog #15) is the recipient-side cross-user provenance log: one row per share
the local user has acted on (imported or dismissed) via the sharing feature (``sync/sharing.py``) — distinct from
``sync_state``/``sync_conflicts``, which are about the E2E backup/restore of the user's OWN records, not
someone else's data arriving via a share. Additive + guarded, registered on the shared ``metadata`` and
re-exported from ``schema.py`` (like ``schema_findings`` / ``schema_feed``).
"""

from __future__ import annotations

import sqlalchemy as sa

from app.backend.persistence.schema_base import metadata

# One row per syncable record. content_hash = sha256 of its canonical payload (NULL once tombstoned); the change-set
# is "rows whose current hash differs from here, plus rows gone from the domain table" (→ a tombstone).
sync_state = sa.Table(
    "sync_state",
    metadata,
    sa.Column("collection", sa.String(length=60), nullable=False),
    sa.Column("record_id", sa.String(length=120), nullable=False),
    sa.Column("content_hash", sa.String(length=64)),  # NULL for a tombstone
    sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("deleted", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
    sa.Column("last_synced_seq", sa.Integer()),  # SP3b: the server sequence this row was last pushed/pulled at
    sa.PrimaryKeyConstraint("collection", "record_id", name="pk_sync_state"),
)

# Local↔global identity map (SP3b): a stable `sync_uid` (UUID) per syncable row, so sync keys on a GLOBAL id instead
# of the device-local auto-increment ``id`` (which differs across devices). Keeps the domain tables untouched + is
# the layer FK-translation (the follow-on) reuses to resolve a referenced row's sync_uid → its local id. Local-only.
sync_identity = sa.Table(
    "sync_identity",
    metadata,
    sa.Column("collection", sa.String(length=60), nullable=False),
    sa.Column("local_id", sa.String(length=120), nullable=False),
    sa.Column("sync_uid", sa.String(length=64), nullable=False),
    sa.PrimaryKeyConstraint("collection", "local_id", name="pk_sync_identity"),
    sa.UniqueConstraint("collection", "sync_uid", name="uq_sync_identity_collection_uid"),
)

# The losing side of a last-write-wins merge — kept (local, plaintext, never synced) so the user can recover it; the
# Conflicts review (SP3c) reads here. Surfacing-not-clobbering is the A4 alignment for multi-device editing.
sync_conflicts = sa.Table(
    "sync_conflicts",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("collection", sa.String(length=60), nullable=False),
    sa.Column("record_id", sa.String(length=120), nullable=False),
    sa.Column("losing_version", sa.Integer()),
    sa.Column("losing_payload", sa.JSON()),  # the overwritten side, kept for recovery (local-only)
    sa.Column("detected_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
    sa.Column("resolved", sa.Integer(), nullable=False, server_default="0"),
    sa.Index("ix_sync_conflicts_unresolved", "resolved"),
)

# SP4c: one row per share the local user (the recipient) has acted on — the cross-user provenance log. `share_id`
# is the SERVER's share row id (unique per recipient's local DB, since a local DB has one identity). `status`
# distinguishes an explicit import from an explicit dismiss (never both); `summary_json` mirrors the same
# BundleImportSummary shape `POST /library/bundle/import` already returns, so the panel can show "what came in"
# without re-deriving it from the (by-then-merged) papers table.
RECEIVED_SHARE_STATUSES = ("imported", "dismissed")

received_shares = sa.Table(
    "received_shares",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("share_id", sa.Integer(), nullable=False, unique=True),
    sa.Column("sender_sub", sa.String(length=255), nullable=False),
    sa.Column("status", sa.String(length=20), nullable=False),
    sa.Column("acted_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
    sa.Column("summary_json", sa.JSON()),  # only set for status="imported"
    sa.CheckConstraint("status IN ('imported', 'dismissed')", name="received_share_status_valid"),
)
