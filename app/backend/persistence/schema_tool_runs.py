"""Generic deterministic/assisted tool-run provenance."""

from __future__ import annotations

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Index, Integer, String, Table, Text
from sqlalchemy.sql import func

from app.backend.persistence.schema_base import metadata

tool_runs = Table(
    "tool_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("uid", String(36), nullable=False, unique=True),
    Column("tool_id", String(100), nullable=False),
    Column("tool_version", String(80), nullable=False),
    Column("callosum_version", String(40), nullable=False),
    Column("parameters_json", JSON, nullable=False),
    Column("result_summary", Text, nullable=False),
    Column("structured_result_json", JSON, nullable=False),
    Column("coverage", Text, nullable=False),
    Column("status", String(20), nullable=False),
    Column("error_detail", Text),
    Column("executed_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("status IN ('running','complete','failed')", name="tool_runs_status"),
)
Index("ix_tool_runs_tool_time", tool_runs.c.tool_id, tool_runs.c.executed_at)
