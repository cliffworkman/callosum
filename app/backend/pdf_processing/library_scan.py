"""Scan a folder of PDFs and reconcile it into the library (inc 87).

The app-level orchestrator the validation harness never exposed: walk a folder, ingest **new** PDFs (linked,
in-place — nothing is copied), skip **unchanged** ones (checksum already in the library), and mark **removed**
ones (a previously-scanned file now gone) as ``availability="missing"``. Pure ingest + reconcile (extract +
chunk via ``attach_pdf_to_paper``); the caller enriches + embeds afterward. Reuses the existing primitives.

Scope (v1): new / reconnected / unchanged / removed. A missing attachment is reconnected only when a scanned
file has the exact stored checksum; its paper/chunks/annotations are preserved. A file changed **in place** (same
path, new content) is added as a new paper (its stale copy can be trashed); true changed-file re-ingest is deferred
— it needs the inc-65 vector cleanup to avoid orphaned chunk embeddings.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, and_, select, update

from app.backend.pdf_processing.extraction import file_sha256
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import attachments
from app.backend.persistence.sqlite_retry import run_write

LIBRARY_SCAN_SOURCE = "library-scan"
MAX_SCAN_PDF_BYTES = 80 * 1024 * 1024  # 80 MiB/file — mirrors the inc-74 OA cap (rule #4: untrusted PDFs)
_log = logging.getLogger("callosum.library_scan")


def _path_key(path: str | Path) -> str:
    """Platform-appropriate absolute key for path identity comparisons."""
    value = Path(path)
    try:
        value = value.resolve()
    except OSError:
        value = value.absolute()
    return os.path.normcase(str(value))


def _row_has_local_file(row: dict[str, Any]) -> bool:
    if row["storage_mode"] == "url" or row["availability"] != "available":
        return False
    raw_path = row["resolved_path"] or row["original_path"]
    try:
        return bool(raw_path and Path(raw_path).is_file())
    except OSError:
        return False


def scan_library_folder(
    engine: Engine,
    folder: str | Path,
    *,
    import_source: str = LIBRARY_SCAN_SOURCE,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Reconcile ``folder``'s ``*.pdf`` files with the library. Returns
    ``{added:[{paper_id, chunk_ids}], relinked:[…], unchanged:[…], removed:[…], errors:[…]}``. **Each new file is ingested +
    committed in its OWN transaction (inc A2)** — via ``run_write`` — so the write lock is released between files
    during the (slow) extraction phase; a corrupt-PDF failure rolls back just that file's transaction and the scan
    continues. ``on_progress(current, total, filename)`` (inc 142 / 214) is called once per file — the basename
    lets the UI show "Reading <file> (X / N)"."""
    folder = Path(folder)
    result: dict[str, Any] = {"added": [], "relinked": [], "unchanged": [], "removed": [], "errors": []}
    current = {_path_key(p): (str(p.resolve()), p) for p in sorted(folder.glob("*.pdf")) if p.is_file()}

    # Upfront reads (one read snapshot): every library checksum (any source) for content-dedup — don't re-add a
    # file already imported from Zotero, a bundle, acquisition, or an earlier scan with different source-path
    # provenance — plus the live scan-sourced attachments keyed by resolved path, for removed-detection.
    existing_by_checksum: dict[str, list[dict[str, Any]]] = {}
    tracked: dict[str, list[tuple[int, int, str]]] = {}
    folder_key = _path_key(folder)
    with engine.connect() as conn:
        for row in conn.execute(
            select(
                attachments.c.id,
                attachments.c.paper_id,
                attachments.c.checksum,
                attachments.c.import_source,
                attachments.c.availability,
                attachments.c.storage_mode,
                attachments.c.original_path,
                attachments.c.resolved_path,
                attachments.c.file_size,
            ).where(attachments.c.checksum.is_not(None))
        ).mappings():
            existing_by_checksum.setdefault(str(row["checksum"]), []).append(
                {
                    "attachment_id": int(row["id"]),
                    "paper_id": int(row["paper_id"]),
                    "import_source": row["import_source"],
                    "availability": row["availability"],
                    "storage_mode": row["storage_mode"],
                    "original_path": row["original_path"],
                    "resolved_path": row["resolved_path"],
                    "file_size": row["file_size"],
                },
            )
        for row in conn.execute(
            select(
                attachments.c.id,
                attachments.c.paper_id,
                attachments.c.original_path,
                attachments.c.resolved_path,
            ).where(and_(attachments.c.import_source == import_source, attachments.c.availability != "missing"))
        ).mappings():
            raw_path = row["resolved_path"] or row["original_path"]
            if raw_path and _path_key(Path(raw_path).parent) == folder_key:
                tracked.setdefault(_path_key(raw_path), []).append(
                    (int(row["id"]), int(row["paper_id"]), str(raw_path))
                )

    total = len(current)
    relinked_ids: set[int] = set()
    for index, (path_key, (resolved, path)) in enumerate(current.items(), start=1):
        if on_progress:
            # inc 142/214: determinate per-file progress + the basename (extraction is the slow per-file step).
            on_progress(index, total, path.name)
        try:
            if path.stat().st_size > MAX_SCAN_PDF_BYTES:
                result["errors"].append({"path": resolved, "error": "exceeds the per-file size cap"})
                continue
            checksum = file_sha256(path)
            matches = existing_by_checksum.get(checksum)
            if matches:
                inaccessible = [row for row in matches if not _row_has_local_file(row)]
                if inaccessible:
                    file_size = path.stat().st_size

                    def _relink(
                        conn,
                        rows=inaccessible,
                        new_path=resolved,
                        new_path_key=path_key,
                        new_file_size=file_size,
                    ):
                        for row in rows:
                            old_path = row["resolved_path"] or row["original_path"]
                            keep_mode = bool(old_path and _path_key(old_path) == new_path_key)
                            storage_mode = row["storage_mode"] if keep_mode else "linked"
                            conn.execute(
                                update(attachments)
                                .where(attachments.c.id == row["attachment_id"])
                                .values(
                                    storage_mode=storage_mode,
                                    availability="available",
                                    original_path=new_path,
                                    resolved_path=new_path,
                                    file_size=new_file_size,
                                )
                            )
                            row.update(
                                storage_mode=storage_mode,
                                availability="available",
                                original_path=new_path,
                                resolved_path=new_path,
                                file_size=new_file_size,
                            )

                    run_write(engine, _relink)
                    for row in inaccessible:
                        relinked_ids.add(row["attachment_id"])
                        result["relinked"].append(
                            {
                                "path": resolved,
                                "matched_by": "checksum",
                                "attachment_id": row["attachment_id"],
                                "paper_id": row["paper_id"],
                                "import_source": row["import_source"],
                            }
                        )
                else:
                    # A physical file is counted once even if duplicate attachment records share its checksum.
                    result["unchanged"].append({"path": resolved, "matched_by": "checksum", **matches[0]})
                continue

            def _ingest(conn, path=path, checksum=checksum):  # one committed transaction per new file
                paper_id = create_paper(
                    conn,
                    title=path.stem,
                    csl_json={"id": f"local-{checksum[:12]}", "type": "document", "title": path.stem},
                    imported_source="pdf-scaffold",
                    processing_tier="metadata-only",
                )
                res = attach_pdf_to_paper(
                    conn,
                    paper_id,
                    path,
                    storage_mode="linked",
                    original_path=str(path),
                    import_source=import_source,
                    role="primary",
                )
                return paper_id, res

            paper_id, res = run_write(engine, _ingest)
            existing_by_checksum[checksum] = [
                {
                    "attachment_id": int(res["attachment_id"]),
                    "paper_id": int(paper_id),
                    "import_source": import_source,
                    "availability": "available",
                    "storage_mode": "linked",
                    "original_path": str(path),
                    "resolved_path": str(path.resolve()),
                    "file_size": path.stat().st_size,
                }
            ]
            result["added"].append({"paper_id": paper_id, "chunk_ids": res["chunk_ids"]})
        except Exception as exc:  # corrupt/unreadable PDF → record + keep scanning (its transaction rolled back)
            _log.warning("library scan: failed on %s: %s", resolved, exc)
            result["errors"].append({"path": resolved, "error": f"{type(exc).__name__}: {exc}"})

    # Removed: previously-scanned files no longer on disk → mark their attachments missing (non-destructive), in
    # one short transaction.
    gone = [
        (aid, pid, resolved)
        for key, rows in tracked.items()
        if key not in current
        for aid, pid, resolved in rows
        if aid not in relinked_ids
    ]
    if gone:

        def _mark_missing(conn):
            for aid, _pid, _resolved in gone:
                conn.execute(update(attachments).where(attachments.c.id == aid).values(availability="missing"))

        run_write(engine, _mark_missing)
        for _aid, pid, resolved in gone:
            result["removed"].append({"paper_id": pid, "path": resolved})

    return result
