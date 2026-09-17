"""Provisional direct-PDF capture persistence (#61 provisional-ingestion increment).

Two tables, deliberately split, because they answer different questions (inc #61 steering: "dedupe
the object, not the encounter"):

* ``provisional_artifacts`` — one row per distinct PDF **object** (keyed by content hash). Its columns
  answer "what is this file, and what does Callosum currently believe about its identity/promotion."
* ``capture_events`` — one row per **encounter** with that object (a browser click that produced those
  exact bytes). Its columns answer "when/where/how was this object captured" — genuinely new
  provenance even when the bytes themselves were already known.

Collapsing these into one row would mean re-capturing already-known bytes either fabricates a second
physical file or silently discards the new encounter's provenance. Neither is acceptable.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Table, Text, UniqueConstraint, func

from app.backend.persistence.schema_base import enum_check, metadata

PROVISIONAL_IDENTITY_STATES = ("unresolved", "resolved")
PROVISIONAL_PROMOTION_STATES = (
    "pending_review",
    "attachment_conflict",
    "processing_failed",
    "indexing_unavailable",
    "promoted",
)
PROVENANCE_SIDECAR_STATES = ("ok", "pending", "error")

provisional_artifacts = Table(
    "provisional_artifacts",
    metadata,
    Column("id", Text, primary_key=True),  # the artifact_id — also the queue filename stem
    Column("content_hash", Text, nullable=False),
    Column("pdf_path", Text, nullable=False),
    Column("identity_state", Text, nullable=False, server_default="unresolved"),
    Column("promotion_state", Text, nullable=False, server_default="pending_review"),
    Column("resolved_paper_id", ForeignKey("papers.id", ondelete="SET NULL")),
    Column("evidence_json", Text),
    Column("provenance_sidecar_state", Text, nullable=False, server_default="pending"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("content_hash", name="uq_provisional_artifacts_content_hash"),
    enum_check("identity_state", PROVISIONAL_IDENTITY_STATES, "identity_state_valid"),
    enum_check("promotion_state", PROVISIONAL_PROMOTION_STATES, "promotion_state_valid"),
    enum_check("provenance_sidecar_state", PROVENANCE_SIDECAR_STATES, "provenance_sidecar_state_valid"),
)

capture_events = Table(
    "capture_events",
    metadata,
    Column("id", Text, primary_key=True),  # == the transport capture_id minted at POST /capture/item
    Column("artifact_id", ForeignKey("provisional_artifacts.id", ondelete="CASCADE"), nullable=False),
    Column("source_url", Text),  # sanitized — scheme+host+path only, see provisional.sanitize_source_url
    Column("captured_at_client", Text),  # browser-supplied ISO-8601 — evidence, never authoritative
    Column("received_at_server", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("original_filename", Text),  # display/provenance ONLY — never bibliographic identity
    Column("producer_kind", Text),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)
