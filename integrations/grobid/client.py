"""GROBID HTTP client (backlog #30 Stage 2) -- an opt-in, loopback-by-default accuracy upgrade for
Suggest-Citation's section-scoping. See integrations/grobid/README.md and
.claude/backups/plans/2026-08-13_grobid-section-scoping-design.md for the full architecture.

GROBID is a separately-running Docker service the user opts into and configures a URL for (app_settings.py's
`stored_grobid_url`) -- this module only ever calls that URL, never assumes GROBID is running."""

from __future__ import annotations

import httpx


class GrobidError(Exception):
    """A GROBID request failed -- connection, timeout, or non-200. Fails closed; callers must never proceed
    with partial/assumed data on this exception."""


def parse_fulltext(
    pdf_bytes: bytes,
    base_url: str,
    *,
    timeout: float = 60.0,
    client: httpx.Client | None = None,
) -> bytes:
    """POST `pdf_bytes` to GROBID's processFulltextDocument endpoint, requesting bounding-box coordinates for
    divisions/headings/paragraphs. Returns the raw TEI-XML response body. Raises GrobidError on any failure --
    never returns a partial/best-effort result."""
    url = f"{base_url.rstrip('/')}/api/processFulltextDocument"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    try:
        resp = http_client.post(
            url,
            data={"teiCoordinates": ["div", "head", "p"]},
            files={"input": ("document.pdf", pdf_bytes, "application/pdf")},
        )
    except httpx.HTTPError as exc:
        raise GrobidError(f"GROBID request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()
    if resp.status_code != 200:
        raise GrobidError(f"GROBID returned HTTP {resp.status_code}: {resp.text[:500]}")
    return resp.content
