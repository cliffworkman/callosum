from __future__ import annotations

import json
from typing import Protocol
from urllib.parse import urlsplit

import httpx

MAX_REGISTRY_JSON_BYTES = 5 * 1024 * 1024
_REGISTRY_PATHS = {
    "api.osf.io": "/v2/",
    "api.datacite.org": "/",
}


class RegistryHttpError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


class JsonFetcher(Protocol):
    def __call__(self, url: str) -> dict: ...


def get_registry_json(url: str) -> dict:
    """Bounded GET for provider-constructed OSF/DataCite URLs; never accepts a user URL at the API seam."""
    _validate_registry_url(url)
    try:
        with httpx.Client(timeout=20.0, follow_redirects=False, headers={"User-Agent": "Callosum/0.1"}) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise RegistryHttpError(response.status_code, f"registry returned HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "").partition(";")[0].strip().casefold()
                if content_type not in {"application/json", "application/vnd.api+json"}:
                    raise RegistryHttpError(502, "registry returned a non-JSON content type")
                raw = bytearray()
                for block in response.iter_bytes():
                    raw.extend(block)
                    if len(raw) > MAX_REGISTRY_JSON_BYTES:
                        raise RegistryHttpError(413, "registry metadata exceeded the 5 MiB limit")
    except httpx.HTTPError as exc:
        raise RegistryHttpError(503, f"registry request failed: {type(exc).__name__}") from exc
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RegistryHttpError(502, "registry returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RegistryHttpError(502, "registry returned an unexpected JSON shape")
    return value


def _validate_registry_url(url: str) -> None:
    parsed = urlsplit(url)
    expected_path = _REGISTRY_PATHS.get(parsed.hostname or "")
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or expected_path is None
        or not parsed.path.startswith(expected_path)
    ):
        raise RegistryHttpError(400, "registry provider constructed an invalid URL")
