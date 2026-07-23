"""Watched library-folder persistence, split from ``schema.py`` for the application-source line budget."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, Table, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.backend.persistence.schema_base import metadata

watched_folders = Table(
    "watched_folders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("path", Text, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("last_scanned_at", DateTime),
    UniqueConstraint("path", name="uq_watched_folders_path"),
)
