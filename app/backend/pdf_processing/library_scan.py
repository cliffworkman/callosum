"""Scan a folder of PDFs and reconcile it into the library (inc 87).

The app-level orchestrator the validation harness never exposed: walk a folder, ingest **new** PDFs (linked,
in-place — nothing is copied), skip **unchanged** ones (checksum already in the library), and mark **removed**
ones (a previously-scanned file now gone) as ``availability="missing"``. Pure ingest + reconcile (extract +
chunk via ``attach_pdf_to_paper``); the caller enriches + embeds afterward. Reuses the existing primitives.

Scope (v1): new / unchanged / removed. A file changed **in place** (same path, new content) is added as a new
paper (its stale copy can be trashed); true changed-file re-ingest is deferred — it needs the inc-65 vector
cleanup to avoid orphaned chunk embeddings.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, and_, select, update

from app.backend.pdf_processing.extraction import file_sha256
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import attachments

LIBRARY_SCAN_SOURCE = "library-scan"
MAX_SCAN_PDF_BYTES = 80 * 1024 * 1024  # 80 MiB/file — mirrors the inc-74 OA cap (rule #4: untrusted PDFs)
_log = logging.getLogger("callosum.library_scan")


def scan_library_folder(
    conn: Connection,
    folder: str | Path,
    *,
    import_source: str = LIBRARY_SCAN_SOURCE,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Reconcile ``folder``'s ``*.pdf`` files with the library. Returns
    ``{added:[{paper_id, chunk_ids}], unchanged:[…], removed:[…], errors:[…]}``. Per-file failures are isolated
    (a savepoint per new file; the bad file is recorded and the scan continues). ``on_progress(current, total,
    filename)`` (inc 142 / 214) is called once per file — the basename lets the UI show "Reading <file> (X / N)"."""
    folder = Path(folder)
    result: dict[str, Any] = {"added": [], "unchanged": [], "removed": [], "errors": []}
    current = {str(p.resolve()): p for p in sorted(folder.glob("*.pdf")) if p.is_file()}

    # Every library checksum (any source) — for content-dedup (don't re-add a file already imported from Zotero,
    # a bundle, acquisition, or an earlier scan with different source-path provenance).
    existing_by_checksum: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        select(
            attachments.c.id,
            attachments.c.paper_id,
            attachments.c.checksum,
            attachments.c.import_source,
            attachments.c.availability,
            attachments.c.resolved_path,
        ).where(attachments.c.checksum.is_not(None))
    ).mappings():
        checksum = str(row["checksum"])
        existing_by_checksum.setdefault(
            checksum,
            {
                "attachment_id": int(row["id"]),
                "paper_id": int(row["paper_id"]),
                "import_source": row["import_source"],
                "availability": row["availability"],
                "resolved_path": row["resolved_path"],
            },
        )
    # Live scan-sourced attachments keyed by resolved path — for removed-detection.
    tracked: dict[str, tuple[int, int]] = {}
    for row in conn.execute(
        select(attachments.c.id, attachments.c.paper_id, attachments.c.resolved_path).where(
            and_(attachments.c.import_source == import_source, attachments.c.availability != "missing")
        )
    ).mappings():
        if row["resolved_path"]:
            tracked[str(row["resolved_path"])] = (int(row["id"]), int(row["paper_id"]))

    total = len(current)
    for index, (resolved, path) in enumerate(current.items(), start=1):
        if on_progress:
            # inc 142/214: determinate per-file progress + the basename (extraction is the slow per-file step).
            on_progress(index, total, path.name)
        try:
            if path.stat().st_size > MAX_SCAN_PDF_BYTES:
                result["errors"].append({"path": resolved, "error": "exceeds the per-file size cap"})
                continue
            checksum = file_sha256(path)
            existing = existing_by_checksum.get(checksum)
            if existing:
                result["unchanged"].append({"path": resolved, "matched_by": "checksum", **existing})
                continue
            with conn.begin_nested():  # isolate a corrupt-PDF failure to this file
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
            existing_by_checksum[checksum] = {
                "attachment_id": int(res["attachment_id"]),
                "paper_id": int(paper_id),
                "import_source": import_source,
                "availability": "available",
                "resolved_path": str(path.resolve()),
            }
            result["added"].append({"paper_id": paper_id, "chunk_ids": res["chunk_ids"]})
        except Exception as exc:  # corrupt/unreadable PDF → record + keep scanning
            _log.warning("library scan: failed on %s: %s", resolved, exc)
            result["errors"].append({"path": resolved, "error": f"{type(exc).__name__}: {exc}"})

    # Removed: a previously-scanned file no longer on disk → mark its attachment missing (non-destructive).
    for resolved, (attachment_id, paper_id) in tracked.items():
        if resolved not in current:
            conn.execute(update(attachments).where(attachments.c.id == attachment_id).values(availability="missing"))
            result["removed"].append({"paper_id": paper_id, "path": resolved})

    return result
