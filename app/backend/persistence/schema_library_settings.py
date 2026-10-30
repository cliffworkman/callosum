"""Per-library settings: choices that describe THIS database rather than the user or machine.

The app-settings JSON file is per OS user and shared by every Callosum instance on the machine (installed app and
dev server alike), so a choice that depends on what a library contains -- e.g. which embedding profile retrieval
uses, which is only valid once that profile's index covers this library -- must live with the library itself.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Table, Text, func

from app.backend.persistence.schema_base import metadata

library_settings = Table(
    "library_settings",
    metadata,
    Column("key", String(80), primary_key=True),
    Column("value", Text, nullable=False),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)
