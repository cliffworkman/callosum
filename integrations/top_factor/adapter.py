"""TOP Factor database download + parse (backlog #40).

Downloads the Center for Open Science's TOP Factor CSV snapshot (public, no auth) and parses it into rows for
the local `top_factor_records` mirror. No live per-journal query API exists for TOP Factor -- COS publishes it
only as a periodically-updated bulk CSV on OSF, so this mirrors `integrations/retraction_watch/adapter.py`'s
download-parse-replace shape exactly rather than DOAJ/SciELO's live-per-request shape. The fetcher is injectable
(size-capped streaming GET) so tests run offline.

Public metadata (a third-party rubric COS itself defines and publishes) -- not the Gemini library-text egress
gate.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from app.backend.persistence.top_factor_repo import replace_top_factor_records

TOP_FACTOR_DOWNLOAD_URL = "https://osf.io/download/qatkz/"
MAX_TOP_FACTOR_BYTES = 20 * 1024 * 1024  # ~5x the confirmed ~4.2 MiB file, generous headroom
MAX_TOP_FACTOR_ROWS = 50_000  # bound the parse (rule #4); TOP Factor covers a few thousand journals

# (CSV column-name prefix, max score) -- confirmed verbatim against the real published header. Every category
# has a "<name> score" + "<name> justification" column pair; Total is COS's own defined sum of the 10 scores.
TOP_FACTOR_CATEGORIES: list[tuple[str, int]] = [
    ("Data citation", 3),
    ("Data transparency", 3),
    ("Analysis code transparency", 3),
    ("Materials transparency", 3),
    ("Design & analysis reporting guidelines", 3),
    ("Study preregistration", 3),
    ("Analysis plan preregistration", 3),
    ("Replication", 3),
    ("Registered reports & publication bias", 3),
    ("Open science badges", 2),
]


class TopFactorUnavailable(RuntimeError):
    """The TOP Factor CSV could not be downloaded (oversize or network error)."""


class TopFactorFetcher(Protocol):
    def __call__(self, url: str, *, timeout: float, max_bytes: int) -> str:
        """Return the CSV text for an https GET, enforcing max_bytes; raise on error/oversize."""


class TopFactorClient:
    def __init__(self, *, fetcher: TopFactorFetcher | None = None, timeout: float = 60.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout

    def fetch_csv(self) -> str:
        return self.fetcher(TOP_FACTOR_DOWNLOAD_URL, timeout=self.timeout, max_bytes=MAX_TOP_FACTOR_BYTES)


def _httpx_fetcher(url: str, *, timeout: float, max_bytes: int) -> str:
    # Streaming + follow_redirects=True + a size cap -- OSF's real download URL redirects twice (files.osf.io,
    # then a signed storage.googleapis.com URL) before the actual CSV, confirmed live.
    chunks: list[bytes] = []
    total = 0
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise TopFactorUnavailable(f"TOP Factor download exceeds the {max_bytes}-byte cap")
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def parse_top_factor_csv(text: str) -> list[dict[str, Any]]:
    """Parse the TOP Factor CSV into record dicts. Rows with neither an ISSN nor an EISSN are unreachable by our
    ISSN-keyed matching and are skipped. A malformed/missing score cell omits that category rather than
    fabricating a 0; a malformed Total cell is derived from the sum of the parsed category scores."""
    out: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for i, row in enumerate(reader):
        if i >= MAX_TOP_FACTOR_ROWS:
            break
        low = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        issn = (low.get("Issn") or "").upper() or None
        eissn = (low.get("Eissn") or "").upper() or None
        if not issn and not eissn:
            continue
        categories: list[dict[str, Any]] = []
        for name, max_score in TOP_FACTOR_CATEGORIES:
            raw = low.get(f"{name} score", "")
            try:
                score = int(raw)
            except ValueError:
                continue
            categories.append(
                {
                    "name": name,
                    "score": score,
                    "max": max_score,
                    "justification": low.get(f"{name} justification") or None,
                }
            )
        try:
            total = int(low.get("Total", ""))
        except ValueError:
            total = sum(c["score"] for c in categories)
        out.append(
            {
                "issn": issn,
                "eissn": eissn,
                "journal": low.get("Journal") or None,
                "categories": categories,
                "total": total,
            }
        )
    return out


def download_top_factor_database(client: TopFactorClient, conn: Connection) -> int:
    """Download -> parse -> replace the local mirror. Returns the stored record count. Raises
    TopFactorUnavailable (oversize / network) -- the caller maps it to a job error."""
    text = client.fetch_csv()
    records = parse_top_factor_csv(text)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    replace_top_factor_records(conn, records, retrieved_at=retrieved_at)
    return len(records)
