"""Per-paper saved GRIM/GRIMMER checks (inc 401) — an append-only, user-curated log, not a dedup'd set (unlike
paper_urls): a user may legitimately save the same mean/N combo twice under different labels (e.g. reported in
the abstract vs. a table). Split into its own file, mirroring schema_paper_urls.py's single-table shape."""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Table, func

from app.backend.persistence.schema_base import metadata

paper_grim_checks = Table(
    "paper_grim_checks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("label", String(120)),  # optional user note, e.g. "Table 2, Experiment 1 accuracy"
    Column("mean", String(40), nullable=False),  # verbatim reported string (GrimRequest.mean shape)
    Column("sd", String(40)),
    Column("n", Integer, nullable=False),
    Column("items", Integer, nullable=False, server_default="1"),
    Column("result_json", JSON, nullable=False),  # the server-recomputed GrimComputeResponse, frozen at save time
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_paper_grim_checks_paper_id", "paper_id"),
)
