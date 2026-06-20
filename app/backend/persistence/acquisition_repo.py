"""Data access for OA-acquisition attachment labels (split out to keep repository.py under the 600-line cap)."""

from __future__ import annotations

from sqlalchemy import Connection, update

from app.backend.persistence.schema import attachments


def set_attachment_oa_labels(
    conn: Connection,
    attachment_id: int,
    *,
    oa_color: str,
    oa_version: str,
    oa_source: str,
    oa_landing_page_url: str | None = None,
    oa_license: str | None = None,
) -> None:
    """Label a fetched attachment with its open-access provenance. ``oa_bronze_unstable`` is derived from the
    color (bronze = free-to-read without a license → may revert to paywalled; never presented as durable)."""
    conn.execute(
        update(attachments)
        .where(attachments.c.id == attachment_id)
        .values(
            oa_color=oa_color,
            oa_version=oa_version,
            oa_source=oa_source,
            oa_landing_page_url=oa_landing_page_url,
            oa_license=oa_license,
            oa_bronze_unstable=1 if oa_color == "bronze" else 0,
        )
    )
