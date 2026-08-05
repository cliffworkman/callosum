"""AJOL database download + parse (backlog #40, inc 451).

Downloads a third-party CC-BY-4.0 compiled snapshot of AJOL (African Journals Online) journal metadata --
Alonso-Álvarez, P. (2025). *AJOL dataset: structured metadata of articles and journals indexed in African
Journals Online.* Zenodo. DOI 10.5281/zenodo.14899380 -- and parses it into rows for the local `ajol_records`
mirror. This is NOT AJOL's own official feed: AJOL runs a live OAI-PMH endpoint
(https://www.ajol.info/index.php/index/oai, confirmed live), but it is organized as one "set" per journal
(article-level Dublin Core records) with no per-ISSN journal lookup and uncertain ISSN-field coverage across
~750 sets -- a heavy full-harvest build for an uncertain payoff. The Zenodo CSV is a directly-inspected,
immediately-usable alternative, so this mirrors `integrations/top_factor/adapter.py`'s download-parse-replace
shape rather than DOAJ/SciELO's live-per-request shape.

Honesty note (this is NOT like TOP Factor/Retraction Watch, which are periodically republished by their source
org): the Zenodo record is immutable and dated February 2024. Re-downloading will always fetch the byte-identical
snapshot -- there is no "fresher" version to refresh to unless a future increment re-pins AJOL_DOWNLOAD_URL to a
new Zenodo record. AJOL_SNAPSHOT_DATE is the data's own fixed vintage, never to be confused with the local
download timestamp (`retrieved_at`) -- see ajol_repo.py / methods_ajol.py / the frontend's "Download database"
(never "Refresh") framing.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from app.backend.persistence.ajol_repo import replace_ajol_records

AJOL_DOWNLOAD_URL = "https://zenodo.org/api/records/14899380/files/ajol_journals.csv/content"
MAX_AJOL_BYTES = 2 * 1024 * 1024  # ~20x the confirmed real ~98 KiB file, generous headroom
MAX_AJOL_ROWS = 10_000  # bound the parse (rule #4); the confirmed real file has 739 rows
AJOL_SNAPSHOT_DATE = "February 2024"  # the dataset's own stated vintage -- hand-update ONLY if a future
# increment re-pins AJOL_DOWNLOAD_URL to a newer Zenodo record version; never derive this from retrieved_at.
AJOL_JOURNAL_URL_PREFIX = "https://www.ajol.info/"  # rule #4: only source_url values under this prefix are
# ever stored/rendered -- the CSV is untrusted external data.


class AjolUnavailable(RuntimeError):
    """The AJOL CSV could not be downloaded (oversize or network error)."""


class AjolFetcher(Protocol):
    def __call__(self, url: str, *, timeout: float, max_bytes: int) -> str:
        """Return the CSV text for an https GET, enforcing max_bytes; raise on error/oversize."""


class AjolClient:
    def __init__(self, *, fetcher: AjolFetcher | None = None, timeout: float = 60.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout

    def fetch_csv(self) -> str:
        return self.fetcher(AJOL_DOWNLOAD_URL, timeout=self.timeout, max_bytes=MAX_AJOL_BYTES)


def _httpx_fetcher(url: str, *, timeout: float, max_bytes: int) -> str:
    chunks: list[bytes] = []
    total = 0
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise AjolUnavailable(f"AJOL download exceeds the {max_bytes}-byte cap")
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _clean_issn(raw: str) -> str | None:
    """Both "" and the literal string "NA" mean "no value" -- confirmed live: the real CSV encodes a missing
    ISSN as the string "NA", not an empty cell (11 of 739 real rows have BOTH issn_print and eissn == "NA"). A
    naive empty-string-only check would silently store "NA" as a bogus matchable ISSN key."""
    v = (raw or "").strip().upper()
    return None if v in ("", "NA") else v


def _clean_bool(raw: str) -> bool | None:
    """ "1"/"0" only; anything else (including blank or "NA") is unknown -- never silently coerced to False."""
    v = (raw or "").strip()
    if v == "1":
        return True
    if v == "0":
        return False
    return None


def _clean_url(raw: str) -> str | None:
    """Untrusted external data (rule #4): only a value that actually starts with AJOL's own domain is kept."""
    v = (raw or "").strip()
    return v if v.startswith(AJOL_JOURNAL_URL_PREFIX) else None


def parse_ajol_csv(text: str) -> list[dict[str, Any]]:
    """Parse the AJOL CSV into record dicts. Rows with neither an ISSN nor an EISSN (per _clean_issn's "" / "NA"
    predicate) are skipped -- unreachable by our ISSN-keyed matching. The real CSV's own column is the typo'd
    `jjps_status` (double-j); this is read in but stored/exposed under the correct term `jpps_status` (Journal
    Publishing Practices and Standards, AJOL's own official rubric name, confirmed live at ajol.info) so
    Callosum's public surface doesn't propagate the source file's typo."""
    out: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for i, row in enumerate(reader):
        if i >= MAX_AJOL_ROWS:
            break
        low = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        issn = _clean_issn(low.get("issn_print", ""))
        eissn = _clean_issn(low.get("eissn", ""))
        if not issn and not eissn:
            continue
        out.append(
            {
                "issn": issn,
                "eissn": eissn,
                "journal": low.get("source_title") or None,
                "country": low.get("country") or None,
                "jpps_status": low.get("jjps_status") or None,
                "is_diamond": _clean_bool(low.get("is_diamond", "")),
                "source_url": _clean_url(low.get("source_url", "")),
            }
        )
    return out


def download_ajol_database(client: AjolClient, conn: Connection) -> int:
    """Download -> parse -> replace the local mirror. Returns the stored record count. Raises AjolUnavailable
    (oversize / network) -- the caller maps it to a job error."""
    text = client.fetch_csv()
    records = parse_ajol_csv(text)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    replace_ajol_records(conn, records, retrieved_at=retrieved_at)
    return len(records)
