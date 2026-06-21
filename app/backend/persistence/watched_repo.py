"""Data access for `watched_folders` (inc 98) — folders callosum re-scans to pick up new PDFs (Zotero/Mendeley-
style watching). Scanning a folder registers it; auto-rescan-on-launch + a manual "Re-scan all" reconcile them.
Un-watching a folder drops the row only — never the papers it imported. Bound params (rule #3)."""

from __future__ import annotations

from sqlalchemy import Connection, RowMapping, delete, func, insert, select, update

from app.backend.persistence.schema import watched_folders


def add_watched_folder(conn: Connection, path: str) -> int:
    """Register a folder as watched (idempotent on the UNIQUE path — re-scanning the same folder is a no-op add).
    Returns the row id."""
    conn.execute(insert(watched_folders).prefix_with("OR IGNORE").values(path=path))
    row = conn.execute(select(watched_folders.c.id).where(watched_folders.c.path == path)).first()
    return int(row[0])


def list_watched_folders(conn: Connection) -> list[RowMapping]:
    return list(conn.execute(select(watched_folders).order_by(watched_folders.c.path)).mappings())


def remove_watched_folder(conn: Connection, folder_id: int) -> bool:
    """Stop watching a folder. Non-destructive — the papers it imported stay in the library."""
    result = conn.execute(delete(watched_folders).where(watched_folders.c.id == folder_id))
    return bool(result.rowcount)


def touch_last_scanned(conn: Connection, path: str) -> None:
    conn.execute(
        update(watched_folders).where(watched_folders.c.path == path).values(last_scanned_at=func.current_timestamp())
    )
