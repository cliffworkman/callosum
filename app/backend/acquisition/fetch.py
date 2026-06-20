"""Download + validate + import a fetched open-access PDF into the local library (the OA lane's import front).

All the validation `ingest_pdf_scaffold` lacks — https-only download, a size cap enforced mid-stream, a real
%PDF- + PyMuPDF check, and a sanitized managed filename — lives HERE, in front of the reusable attach path, so
OA fetching is fail-closed and the ingest scaffold is never weakened. `download_oa_pdf` takes an `OaLocation`
(never a bare URL): the structural guarantee that only database-asserted OA copies are ever fetched.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import fitz
import httpx
from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, _require_safe_https
from app.backend.metadata.enrichment import enrich_paper_metadata_from_crossref
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.persistence.acquisition_repo import set_attachment_oa_labels
from app.backend.persistence.repository import get_paper

# app/backend/acquisition/fetch.py → parents[3] == repo root (kept local to avoid importing app.backend.api,
# which would create an import cycle: api package __init__ imports app.py, which imports this via the router).
PROJECT_ROOT = Path(__file__).resolve().parents[3]

MAX_OA_PDF_BYTES = 80 * 1024 * 1024  # 80 MiB
_MAX_FILENAME_BASE = 180


class OaFetchError(RuntimeError):
    """A fetched OA copy could not be retrieved or validated (oversize, non-PDF, network, or unsafe URL)."""


class PdfFetcher(Protocol):
    def __call__(self, url: str, *, timeout: float, max_bytes: int) -> bytes:
        """Return the response body bytes for an https GET, enforcing max_bytes; raise on error/oversize."""


def download_oa_pdf(location: OaLocation, *, fetcher: PdfFetcher | None = None, timeout: float = 30.0) -> Path:
    """Download + validate an authorized OA PDF (by ``OaLocation``, never a bare URL) → a temp file path.

    Validates: https (already enforced on ``OaLocation``), the size cap mid-stream, the ``%PDF-`` magic, and
    that PyMuPDF opens it with >=1 page. Any failure raises ``OaFetchError`` and leaves no temp file behind.
    """
    fetch = fetcher or _httpx_pdf_fetcher
    data = fetch(location.pdf_url, timeout=timeout, max_bytes=MAX_OA_PDF_BYTES)
    if len(data) > MAX_OA_PDF_BYTES:  # defense-in-depth: the streaming fetcher also caps mid-download
        raise OaFetchError(f"downloaded PDF exceeds the {MAX_OA_PDF_BYTES}-byte cap")
    if not data.startswith(b"%PDF-"):
        raise OaFetchError("downloaded bytes are not a PDF (missing %PDF- header)")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        page_count = doc.page_count
        doc.close()
    except Exception as exc:  # corrupt / not actually a PDF
        raise OaFetchError(f"downloaded PDF did not open: {exc}") from exc
    if page_count < 1:
        raise OaFetchError("downloaded PDF has no pages")
    temp_dir = PROJECT_ROOT / ".local" / "acquire-tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"oa-{uuid4().hex}.pdf"  # name from uuid, never from metadata
    temp_path.write_bytes(data)
    return temp_path


def import_oa_pdf(
    conn: Connection,
    location: OaLocation,
    temp_pdf_path: Path,
    *,
    paper_id: int,
    crossref_client: Any | None = None,
) -> dict[str, Any]:
    """Move a validated OA PDF into the managed library dir (named per the library convention), attach it to
    the EXISTING paper, label its OA color/version/source, and enrich metadata. Returns a result dict."""
    paper = get_paper(conn, paper_id)
    library_dir = _library_dir()
    library_dir.mkdir(parents=True, exist_ok=True)
    managed_path = _unique_path(library_dir, library_filename_for(paper))
    shutil.move(str(temp_pdf_path), str(managed_path))
    result = attach_pdf_to_paper(
        conn,
        paper_id,
        managed_path,
        storage_mode="managed",
        original_path=str(managed_path),
        import_source=f"oa:{location.source}",
        role="primary",
    )
    set_attachment_oa_labels(
        conn,
        result["attachment_id"],
        oa_color=location.oa_color,
        oa_version=location.version,
        oa_source=location.source,
        oa_landing_page_url=location.landing_page_url,
        oa_license=location.license,
    )
    enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=crossref_client)
    return {
        "paper_id": paper_id,
        "attachment_id": result["attachment_id"],
        "oa_color": location.oa_color,
        "oa_version": location.version,
        "oa_source": location.source,
        "bronze_unstable": location.bronze_unstable,
        "filename": managed_path.name,
    }


def _library_dir() -> Path:
    configured = os.environ.get("CALLOSUM_LIBRARY_DIR")
    return Path(configured) if configured else (PROJECT_ROOT / "library")


# --- managed filename: mirror the existing library convention "Authors - Year - Venue.pdf" -----------------


def library_filename_for(paper) -> str:
    csl = paper["csl_json"] or {}
    base = f"{_author_label(csl, paper)} - {_year_label(csl, paper)} - {_venue_label(csl, paper)}"
    return _sanitize_filename(base) + ".pdf"


def _author_label(csl: dict, paper) -> str:
    families = []
    for author in csl.get("author") or []:
        if not isinstance(author, dict):
            continue
        family = (author.get("family") or author.get("literal") or "").strip()
        if family:
            families.append(family)
    if not families:
        return (paper["first_author_family_name"] or "").strip() or "Unknown"
    if len(families) == 1:
        return families[0]
    if len(families) == 2:
        return f"{families[0]} & {families[1]}"
    return f"{families[0]} et al."


def _year_label(csl: dict, paper) -> str:
    if paper["year"]:
        return str(paper["year"])
    parts = (csl.get("issued") or {}).get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        return str(parts[0][0])
    return "n.d."


def _venue_label(csl: dict, paper) -> str:
    venue = (csl.get("container-title-short") or csl.get("container-title") or paper["venue"] or "").strip()
    if not venue and csl.get("type") in {"book", "chapter"}:
        venue = (paper["title"] or "").strip()
    chapter = csl.get("chapter-number")
    if chapter and csl.get("type") == "chapter":
        venue = f"{venue} (Ch. {chapter})".strip()
    return venue or "Unknown"


_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_filename(base: str) -> str:
    cleaned = _ILLEGAL.sub(" ", base)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    if len(cleaned) > _MAX_FILENAME_BASE:
        cleaned = cleaned[:_MAX_FILENAME_BASE].rstrip()
    return cleaned or "acquired"


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    n = 2
    while True:
        candidate = directory / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def _httpx_pdf_fetcher(url: str, *, timeout: float, max_bytes: int) -> bytes:
    """Stream an https GET, following redirects manually so every hop is re-validated https + non-IP host
    (SSRF guard), and enforcing the byte cap mid-stream."""
    current = url
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        for _ in range(6):
            _require_safe_https(current)
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location_header = response.headers.get("location")
                    if not location_header:
                        raise OaFetchError("redirect without a Location header")
                    current = str(httpx.URL(current).join(location_header))
                    continue
                if response.status_code != 200:
                    raise OaFetchError(f"download returned HTTP {response.status_code}")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise OaFetchError(f"download exceeds the {max_bytes}-byte cap")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise OaFetchError("too many redirects")
