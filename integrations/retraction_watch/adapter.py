"""Retraction Watch Database download + parse (inc 132).

Downloads the Crossref-hosted Retraction Watch DB (CC0) as CSV and parses it into rows for the local
`retraction_records` mirror. Public bulk metadata (uses the existing ``CALLOSUM_CROSSREF_MAILTO`` polite contact)
— **not** the Gemini library-text egress gate. The fetcher is injectable (size-capped https GET) so tests run
offline. A **Reinstatement** (an un-retraction) and any unrecognized nature are skipped — never a finding.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import Connection

from app.backend.app_settings import resolved_mailto
from app.backend.persistence.retraction_repo import replace_retraction_records

RW_BASE_URL = "https://api.labs.crossref.org/data/retractionwatch"
MAX_RW_BYTES = 80 * 1024 * 1024  # 80 MiB cap on the download (the RW DB is ~tens of MB)
MAX_RW_ROWS = 500_000  # bound the parse (rule #4)

# Retraction Watch `RetractionNature` → our status. Anything not here (notably "Reinstatement") is SKIPPED.
RW_STATUS_BY_NATURE = {
    "retraction": "retracted",
    "withdrawal": "retracted",
    "removal": "retracted",
    "correction": "correction",
    "erratum": "correction",
    "expression of concern": "concern",
}


class RetractionWatchUnavailable(RuntimeError):
    """The Retraction Watch database could not be downloaded (no mailto, oversize, or network error)."""


class RetractionWatchFetcher(Protocol):
    def __call__(self, url: str, *, timeout: float, max_bytes: int) -> str:
        """Return the CSV text for an https GET, enforcing max_bytes; raise on error/oversize."""


class RetractionWatchClient:
    def __init__(
        self,
        *,
        fetcher: RetractionWatchFetcher | None = None,
        mailto: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        # UI contact email (Settings → Metadata access) overlays the CALLOSUM_CROSSREF_MAILTO env var (inc 158).
        self.mailto = mailto if mailto is not None else resolved_mailto("CALLOSUM_CROSSREF_MAILTO")
        self.timeout = timeout

    def fetch_csv(self) -> str:
        if not self.mailto:
            raise RetractionWatchUnavailable(
                "Set a contact email in Settings → Metadata access (or the CALLOSUM_CROSSREF_MAILTO env var) "
                "to download the Retraction Watch database."
            )
        url = f"{RW_BASE_URL}?{quote(self.mailto, safe='@.')}"
        return self.fetcher(url, timeout=self.timeout, max_bytes=MAX_RW_BYTES)


def _httpx_fetcher(url: str, *, timeout: float, max_bytes: int) -> str:
    chunks: list[bytes] = []
    total = 0
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise RetractionWatchUnavailable(f"Retraction Watch download exceeds the {max_bytes}-byte cap")
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def parse_retraction_csv(text: str) -> list[dict[str, Any]]:
    """Parse the RW CSV into record dicts. Tolerant (case-insensitive headers); skips rows with no original DOI
    or an unrecognized / reinstatement nature; maps nature → status; derives the notice URL from the notice DOI."""
    out: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for i, row in enumerate(reader):
        if i >= MAX_RW_ROWS:
            break
        low = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        original_doi = low.get("originalpaperdoi", "").lower()
        if not original_doi:
            continue
        nature_raw = low.get("retractionnature", "")
        status = RW_STATUS_BY_NATURE.get(nature_raw.lower())
        if status is None:  # reinstatement / unknown → never a finding
            continue
        notice_doi = low.get("retractiondoi", "").lower() or None
        out.append(
            {
                "original_doi": original_doi,
                "status": status,
                "nature": nature_raw or None,
                "date": low.get("retractiondate") or None,
                "reason": low.get("reason") or None,
                "notice_doi": notice_doi,
                "notice_url": f"https://doi.org/{notice_doi}" if notice_doi else None,
            }
        )
    return out


def download_retraction_database(client: RetractionWatchClient, conn: Connection) -> int:
    """Download → parse → replace the local mirror. Returns the stored record count. Raises
    RetractionWatchUnavailable (mailto absent / oversize / network) — the caller maps it to a job error."""
    text = client.fetch_csv()
    records = parse_retraction_csv(text)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    replace_retraction_records(conn, records, retrieved_at=retrieved_at)
    return len(records)
