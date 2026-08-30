"""Bounded Mendeley OAuth and read-only personal-library API client.

This module is deliberately transport-only. It does not publish an OAuth route, persist tokens, or import
records. The official API still requires a confidential client secret for authorization-code exchange and
documents no PKCE support, so desktop distribution/redirect ownership must be resolved before activation.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

API_ORIGIN = "https://api.mendeley.com"
AUTHORIZE_URL = f"{API_ORIGIN}/oauth/authorize"
TOKEN_URL = f"{API_ORIGIN}/oauth/token"
DOCUMENT_MEDIA = "application/vnd.mendeley-document.1+json"
FOLDER_MEDIA = "application/vnd.mendeley-folder.1+json"
FILE_MEDIA = "application/vnd.mendeley-file.1+json"

PAGE_LIMIT = 500
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_DOCUMENTS = 50_000
MAX_FOLDERS = 2_000
MAX_FILES = 100_000
MAX_PAGES = 200
MAX_URL_LENGTH = 4_096
MAX_TOKEN_LENGTH = 8_192
MAX_CODE_LENGTH = 4_096
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_SIGNED_DOWNLOAD_HOSTS = frozenset({"downloads.mendeley.com"})


class MendeleyError(RuntimeError):
    """A sanitized configuration, transport, or response-contract failure."""


@dataclass(frozen=True)
class MendeleyOAuthConfig:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str

    def __post_init__(self) -> None:
        if not self.client_id.strip() or len(self.client_id) > 256:
            raise ValueError("Mendeley client ID is missing or too long")
        if not self.client_secret.strip() or len(self.client_secret) > 512:
            raise ValueError("Mendeley client secret is missing or too long")
        _validate_loopback_redirect(self.redirect_uri)


@dataclass(frozen=True)
class MendeleyTokens:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int


class MendeleyOAuthClient:
    """Official authorization-code exchange shape, dormant until app registration is validated live."""

    def __init__(self, config: MendeleyOAuthConfig, *, http: httpx.Client | None = None, timeout: float = 20.0) -> None:
        self.config = config
        self._http = http
        self._timeout = timeout

    @staticmethod
    def generate_state() -> str:
        return secrets.token_urlsafe(32)

    def build_authorize_url(self, *, state: str) -> str:
        if not state or len(state) > 512:
            raise ValueError("Mendeley OAuth state is missing or too long")
        return f"{AUTHORIZE_URL}?{urlencode({'client_id': self.config.client_id, 'redirect_uri': self.config.redirect_uri, 'response_type': 'code', 'scope': 'all', 'state': state})}"

    def exchange_code(self, code: str) -> MendeleyTokens:
        if not code or len(code) > MAX_CODE_LENGTH:
            raise ValueError("Mendeley authorization code is missing or too long")
        return self._post_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.config.redirect_uri,
            }
        )

    def refresh(self, refresh_token: str) -> MendeleyTokens:
        if not refresh_token or len(refresh_token) > MAX_TOKEN_LENGTH:
            raise ValueError("Mendeley refresh token is missing or too long")
        return self._post_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "redirect_uri": self.config.redirect_uri,
            }
        )

    def _post_token(self, data: dict[str, str]) -> MendeleyTokens:
        try:
            if self._http is not None:
                response = self._http.post(
                    TOKEN_URL,
                    data=data,
                    auth=(self.config.client_id, self.config.client_secret),
                    follow_redirects=False,
                )
            else:
                with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                    response = client.post(
                        TOKEN_URL,
                        data=data,
                        auth=(self.config.client_id, self.config.client_secret),
                    )
            if response.status_code != 200 or len(response.content) > MAX_PAGE_BYTES:
                raise MendeleyError("Mendeley OAuth request was rejected")
            payload = response.json()
            return _tokens_from_payload(payload)
        except MendeleyError:
            raise
        except Exception:
            raise MendeleyError("Mendeley OAuth request failed") from None


class MendeleyLibraryClient:
    """Read-only, version-pinned access to the personal-library resources needed by a future importer."""

    def __init__(self, access_token: str, *, http: httpx.Client | None = None, timeout: float = 30.0) -> None:
        if not access_token or len(access_token) > MAX_TOKEN_LENGTH:
            raise ValueError("Mendeley access token is missing or too long")
        self._access_token = access_token
        self._http = http
        self._timeout = timeout

    def list_documents(self) -> tuple[dict[str, Any], ...]:
        return self._paged(
            "/documents", accept=DOCUMENT_MEDIA, params={"view": "all", "limit": PAGE_LIMIT}, cap=MAX_DOCUMENTS
        )

    def list_folders(self) -> tuple[dict[str, Any], ...]:
        return self._paged("/folders", accept=FOLDER_MEDIA, params={"limit": PAGE_LIMIT}, cap=MAX_FOLDERS)

    def list_files(self) -> tuple[dict[str, Any], ...]:
        return self._paged("/files", accept=FILE_MEDIA, params={"limit": PAGE_LIMIT}, cap=MAX_FILES)

    def list_folder_document_ids(self, folder_id: str) -> tuple[str, ...]:
        safe_id = _resource_id(folder_id)
        rows = self._paged(
            f"/folders/{safe_id}/documents",
            accept=DOCUMENT_MEDIA,
            params={"limit": PAGE_LIMIT},
            cap=MAX_DOCUMENTS,
        )
        ids: list[str] = []
        for row in rows:
            value = row.get("id")
            if not isinstance(value, str):
                raise MendeleyError("Mendeley folder response omitted a document ID")
            ids.append(_resource_id(value))
        return tuple(ids)

    def file_download_url(self, file_id: str) -> str:
        response = self._get(f"{API_ORIGIN}/files/{_resource_id(file_id)}", accept=FILE_MEDIA)
        if response.status_code != 303:
            raise MendeleyError(f"Mendeley file redirect returned HTTP {response.status_code}")
        location = response.headers.get("location", "")
        parsed = urlparse(location)
        if (
            len(location) > MAX_URL_LENGTH
            or parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.hostname not in _SIGNED_DOWNLOAD_HOSTS
            or parsed.port not in {None, 443}
            or parsed.fragment
        ):
            raise MendeleyError("Mendeley file redirect was not an approved signed-download URL")
        return location

    def _paged(self, path: str, *, accept: str, params: dict[str, object], cap: int) -> tuple[dict[str, Any], ...]:
        expected_path = path
        url = f"{API_ORIGIN}{path}"
        next_params: dict[str, object] | None = params
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for _ in range(MAX_PAGES):
            canonical = str(httpx.URL(url, params=next_params)) if next_params is not None else url
            if canonical in seen:
                raise MendeleyError("Mendeley pagination cycle detected")
            seen.add(canonical)
            response = self._get(url, accept=accept, params=next_params)
            if response.status_code != 200 or len(response.content) > MAX_PAGE_BYTES:
                raise MendeleyError(f"Mendeley collection request returned HTTP {response.status_code}")
            try:
                page = response.json()
            except ValueError:
                raise MendeleyError("Mendeley collection response was not JSON") from None
            if not isinstance(page, list) or any(not isinstance(item, dict) for item in page):
                raise MendeleyError("Mendeley collection response had an unexpected shape")
            rows.extend(page)
            if len(rows) > cap:
                raise MendeleyError(f"Mendeley collection exceeded the {cap} item safety limit")
            next_url = response.links.get("next", {}).get("url")
            if not next_url:
                return tuple(rows)
            url = _validated_page_url(str(next_url), expected_path=expected_path)
            next_params = None
        raise MendeleyError(f"Mendeley pagination exceeded the {MAX_PAGES} page safety limit")

    def _get(self, url: str, *, accept: str, params: dict[str, object] | None = None) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._access_token}", "Accept": accept}
        try:
            if self._http is not None:
                return self._http.get(url, headers=headers, params=params, follow_redirects=False)
            with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                return client.get(url, headers=headers, params=params)
        except Exception:
            raise MendeleyError("Mendeley API request failed") from None


def _tokens_from_payload(payload: object) -> MendeleyTokens:
    if not isinstance(payload, dict) or str(payload.get("token_type", "")).lower() != "bearer":
        raise MendeleyError("Mendeley OAuth response had an unexpected shape")
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    expires = payload.get("expires_in")
    if (
        not isinstance(access, str)
        or not 0 < len(access) <= MAX_TOKEN_LENGTH
        or not isinstance(refresh, str)
        or not 0 < len(refresh) <= MAX_TOKEN_LENGTH
        or not isinstance(expires, int)
        or not 0 < expires <= 7 * 24 * 60 * 60
    ):
        raise MendeleyError("Mendeley OAuth response omitted bounded token metadata")
    return MendeleyTokens(access, refresh, expires)


def _validate_loopback_redirect(uri: str) -> None:
    if len(uri) > MAX_URL_LENGTH:
        raise ValueError("Mendeley redirect URI is too long")
    parsed = urlparse(uri)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Mendeley redirect URI must be an exact plain-HTTP loopback URL")


def _resource_id(value: str) -> str:
    if not value or len(value) > 64 or any(ch not in "0123456789abcdefABCDEF-" for ch in value):
        raise ValueError("Mendeley resource ID is malformed")
    return value


def _validated_page_url(url: str, *, expected_path: str) -> str:
    if len(url) > MAX_URL_LENGTH:
        raise MendeleyError("Mendeley pagination URL is too long")
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.mendeley.com"
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != expected_path
        or parsed.fragment
    ):
        raise MendeleyError("Mendeley pagination left the approved API resource")
    return url
