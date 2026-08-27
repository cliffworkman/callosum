"""GROBID HTTP client (backlog #30 Stage 2) -- an opt-in, loopback-by-default accuracy upgrade for
Suggest-Citation's section-scoping. See integrations/grobid/README.md and
.claude/backups/plans/2026-08-13_grobid-section-scoping-design.md for the full architecture.

GROBID is a separately-running Docker service the user opts into and configures a URL for (app_settings.py's
`stored_grobid_url`) -- this module only ever calls that URL, never assumes GROBID is running."""

from __future__ import annotations

import logging
import time

import httpx

from integrations.http_bounds import METADATA_RESPONSE_CAP, ResponseTooLargeError, bounded_post

_log = logging.getLogger("callosum.grobid")


class GrobidError(Exception):
    """A GROBID request failed -- connection, timeout, or non-200. Fails closed; callers must never proceed
    with partial/assumed data on this exception."""


def parse_fulltext(
    pdf_bytes: bytes,
    base_url: str,
    *,
    timeout: float = 60.0,
    client: httpx.Client | None = None,
    max_retries: int = 3,
    retry_backoff_seconds: float = 2.0,
) -> bytes:
    """POST `pdf_bytes` to GROBID's processFulltextDocument endpoint, requesting bounding-box coordinates for
    divisions/headings/paragraphs. Returns the raw TEI-XML response body. Raises GrobidError on any failure --
    never returns a partial/best-effort result.

    A 503 specifically means GROBID's own internal processing-engine pool is momentarily exhausted (observed
    live: a bulk parse run can 503 every paper if concurrent requests outpace the pool) -- retried with linear
    backoff, since it is a transient "try again shortly" signal, unlike every other non-200 status (404/500/etc,
    which fail immediately as likely-permanent)."""
    url = f"{base_url.rstrip('/')}/api/processFulltextDocument"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    try:
        attempt = 0
        while True:
            try:
                resp = bounded_post(
                    url,
                    max_bytes=METADATA_RESPONSE_CAP,
                    client=http_client,
                    # Ask GROBID not to compress the response at all. Observed live: under heavy load GROBID
                    # returned a response whose Content-Encoding claimed gzip but whose body was truncated/
                    # corrupted ("Error -3 while decompressing data: incorrect header check" from httpx's own
                    # streaming decoder in bounded_post). Refusing compression removes that whole failure class
                    # regardless of cause -- a TEI-XML response is already bounded by METADATA_RESPONSE_CAP, so
                    # the larger uncompressed transfer is an acceptable, bounded trade for correctness.
                    headers={"Accept-Encoding": "identity"},
                    data={"teiCoordinates": ["div", "head", "p"]},
                    files={"input": ("document.pdf", pdf_bytes, "application/pdf")},
                )
            except ResponseTooLargeError as exc:
                raise GrobidError(f"GROBID response exceeded the {METADATA_RESPONSE_CAP}-byte cap") from exc
            except httpx.HTTPError as exc:
                raise GrobidError(f"GROBID request failed: {exc}") from exc
            if resp.status_code == 503 and attempt < max_retries:
                attempt += 1
                delay = retry_backoff_seconds * attempt
                _log.info("GROBID pool busy (503), retrying (%d/%d) after %.1fs", attempt, max_retries, delay)
                time.sleep(delay)
                continue
            if resp.status_code != 200:
                raise GrobidError(f"GROBID returned HTTP {resp.status_code}: {resp.text[:500]}")
            return resp.content
    finally:
        if owns_client:
            http_client.close()
