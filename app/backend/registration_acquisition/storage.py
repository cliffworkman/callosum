from __future__ import annotations

import re
import shutil
from pathlib import Path

from sqlalchemy import Connection

from app.backend.acquisition.fetch import library_dir
from app.backend.pdf_processing.ingest import attach_pdf_to_paper, attach_text_document_to_paper
from app.backend.registration_acquisition.domain import AcquiredRegistration


def managed_registration_path(acquired: AcquiredRegistration) -> Path:
    directory = library_dir()
    directory.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[^A-Za-z0-9_.-]+", "-", f"{acquired.provider}-{acquired.external_id}").strip("-.")[:120]
    stem = f"registration-{base or 'record'}-{acquired.content_hash[:12]}"
    candidate = directory / f"{stem}{acquired.file_suffix}"
    index = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{index}{acquired.file_suffix}"
        index += 1
    return candidate


def import_acquired_registration(
    conn: Connection,
    paper_id: int,
    acquired: AcquiredRegistration,
    temp_path: Path,
    managed_path: Path,
) -> dict:
    shutil.move(str(temp_path), str(managed_path))
    kwargs = {
        "storage_mode": "managed",
        "original_path": str(managed_path),
        "import_source": f"registration:{acquired.provider}",
        "role": "preregistration",
    }
    if acquired.file_suffix.casefold() == ".pdf":
        return attach_pdf_to_paper(conn, paper_id, managed_path, **kwargs)
    return attach_text_document_to_paper(
        conn,
        paper_id,
        managed_path,
        content_type=acquired.content_type,
        **kwargs,
    )
