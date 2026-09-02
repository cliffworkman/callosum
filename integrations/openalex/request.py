"""Shared request identity for every OpenAlex client.

The API key is optional and environment-only. No client logs or persists it; every request receives the same
current application identity and polite-pool parameters.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

import httpx

from integrations.http_bounds import METADATA_RESPONSE_CAP, bounded_get

OPENALEX_CACHE_TTL_SECONDS = 24 * 60 * 60
_RETRY_STATUSES = {429, 500, 502, 503, 504}


class OpenAlexResponseUnavailable(RuntimeError):
    """A complete OpenAlex response could not be established."""


def openalex_params(mailto: str | None) -> dict[str, str]:
    params: dict[str, str] = {}
    if mailto:
        params["mailto"] = mailto
    api_key = os.getenv("CALLOSUM_OPENALEX_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key
    return params


def openalex_headers(mailto: str | None) -> dict[str, str]:
    user_agent = "Callosum/0.5.2 (local-first reference manager)"
    if mailto:
        user_agent = f"{user_agent}; mailto:{mailto}"
    return {"User-Agent": user_agent, "Accept": "application/json"}


def bounded_openalex_get(
    url: str,
    *,
    params: dict[str, str],
    headers: dict[str, str],
    timeout: float,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Bounded OpenAlex GET with conservative Retry-After/exponential handling for transient responses."""
    last_response: httpx.Response | None = None
    last_error: httpx.TransportError | None = None
    for attempt in range(max(1, attempts)):
        try:
            response = bounded_get(
                url,
                max_bytes=METADATA_RESPONSE_CAP,
                params=params,
                headers=headers,
                timeout=timeout,
            )
        except httpx.TransportError as exc:
            last_error = exc
        else:
            last_response = response
            if response.status_code not in _RETRY_STATUSES:
                return response
        if attempt + 1 < max(1, attempts):
            sleep(_retry_delay(last_response, attempt))
    if last_response is not None:
        return last_response
    assert last_error is not None
    raise last_error


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    raw = response.headers.get("Retry-After") if response is not None else None
    try:
        requested = float(raw) if raw is not None else 0.0
    except ValueError:
        requested = 0.0
    return min(5.0, max(requested, 0.25 * (2**attempt)))
