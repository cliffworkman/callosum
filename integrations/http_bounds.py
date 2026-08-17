"""A shared bounded-read helper for every external HTTP fetch in ``integrations/``.

Backlog #56 (surfaced by the GROBID security audit, confirmed codebase-wide): no client here
bounded the size of an inbound response before fully buffering it into memory -- each trusted
the external service to behave. ``bounded_get`` streams the response and fails closed with
``ResponseTooLargeError`` the moment the cap is crossed, before the rest of the body is read.
"""

from __future__ import annotations

import httpx

METADATA_RESPONSE_CAP = 10 * 1024 * 1024  # per-record metadata lookups (OpenAlex, Crossref, GROBID TEI, ...)
MIRROR_DOWNLOAD_CAP = 100 * 1024 * 1024  # full-database mirror downloads (Retraction Watch, TOP Factor, AJOL)


class ResponseTooLargeError(httpx.HTTPError):
    """Raised when a response body exceeds its caller-supplied byte cap."""

    def __init__(self, url: str, max_bytes: int) -> None:
        super().__init__(f"response from {url} exceeded the {max_bytes}-byte cap")
        self.url = url
        self.max_bytes = max_bytes


def bounded_get(url: str, *, max_bytes: int, client: httpx.Client | None = None, **kwargs: object) -> httpx.Response:
    """GET ``url``, streaming the body and rejecting it before fully buffering past ``max_bytes``.

    Returns a normal, fully-materialized ``httpx.Response`` (``.json()``/``.text``/``.content`` all
    work) when the body is under the cap, so existing call sites need no changes beyond swapping
    ``httpx.get(url, ...)`` for ``bounded_get(url, max_bytes=..., ...)``.
    """
    return _bounded_request("GET", url, max_bytes=max_bytes, client=client, **kwargs)


def bounded_post(url: str, *, max_bytes: int, client: httpx.Client | None = None, **kwargs: object) -> httpx.Response:
    """POST to ``url`` (``data``/``files``/``json`` kwargs pass through), same bounded-read contract as
    :func:`bounded_get`."""
    return _bounded_request("POST", url, max_bytes=max_bytes, client=client, **kwargs)


def _bounded_request(
    method: str, url: str, *, max_bytes: int, client: httpx.Client | None, **kwargs: object
) -> httpx.Response:
    owns_client = client is None
    active_client = client or httpx.Client()
    try:
        with active_client.stream(method, url, **kwargs) as response:
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ResponseTooLargeError(url, max_bytes)
                chunks.append(chunk)
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                content=b"".join(chunks),
                request=response.request,
            )
    finally:
        if owns_client:
            active_client.close()
