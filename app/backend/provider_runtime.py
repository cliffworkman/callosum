"""Application-owned lifecycle for reusable synchronous LLM provider clients."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from threading import Condition, Lock, RLock
from typing import TypeVar

T = TypeVar("T")

_HTTP_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)
_GEMINI_ENV_KEYS = ("GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION")


@dataclass(frozen=True)
class HttpClientIdentity:
    """Connection-affecting settings for one reusable HTTP pool."""

    endpoint_fingerprint: str
    timeout: float
    verify: bool = True
    trust_env: bool = True
    environment_fingerprint: str = ""


@dataclass(frozen=True)
class GeminiClientIdentity:
    """Non-reversible identity for one compatible Google GenAI client."""

    credential_fingerprint: str
    environment_fingerprint: str
    api_mode: str = "developer-api"


class _ClientEntry:
    """One lazily constructed synchronous provider client."""

    def __init__(self, factory: Callable[[], object]) -> None:
        self._factory = factory
        self._client: object | None = None
        self._load_lock = Lock()
        self._use_condition = Condition()
        self._active_uses = 0
        self._closed = False
        self.construction_count = 0

    def get(self) -> object:
        self._ensure_open()
        client = self._client
        if client is not None:
            return client
        with self._load_lock:
            self._ensure_open()
            if self._client is None:
                client = self._factory()
                self._client = client
                self.construction_count += 1
            return self._client

    def run(self, operation: Callable[[object], T]) -> T:
        """Run against the client while keeping shutdown from closing it in flight."""
        client = self.get()
        with self._use_condition:
            self._ensure_open_locked()
            self._active_uses += 1
        try:
            return operation(client)
        finally:
            with self._use_condition:
                self._active_uses -= 1
                if self._active_uses == 0:
                    self._use_condition.notify_all()

    @property
    def loaded_client(self) -> object | None:
        return self._client

    def close(self) -> None:
        with self._load_lock:
            with self._use_condition:
                self._closed = True
                while self._active_uses:
                    self._use_condition.wait()
            client, self._client = self._client, None
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def _ensure_open(self) -> None:
        with self._use_condition:
            self._ensure_open_locked()

    def _ensure_open_locked(self) -> None:
        if self._closed:
            raise RuntimeError("Provider client is closed")


class ProviderClientRuntime:
    """Per-application manager for raw HTTP pools and Gemini SDK clients.

    Clients are not wrapped in call locks: HTTPX documents ``Client`` as
    shareable between threads, and the installed Google GenAI SDK directly
    tests concurrent synchronous ``generate_content`` calls plus credential
    initialization/refresh. Construction and shutdown remain guarded.
    """

    def __init__(
        self,
        *,
        http_client_factory: Callable[[HttpClientIdentity], object] | None = None,
        gemini_client_factory: Callable[[str | None], object] | None = None,
    ) -> None:
        self._http_client_factory = http_client_factory or _load_http_client
        self._gemini_client_factory = gemini_client_factory or _load_gemini_client
        self._http_entries: dict[HttpClientIdentity, _ClientEntry] = {}
        self._gemini_entries: dict[GeminiClientIdentity, _ClientEntry] = {}
        self._registry_lock = RLock()
        self._closed = False

    def get_http_client(self, *, base_url: str, timeout: float, trust_env: bool = True) -> object:
        return self._http_entry_for(base_url=base_url, timeout=timeout, trust_env=trust_env).get()

    def get_gemini_client(self, *, api_key: str | None) -> object:
        return self._gemini_entry(api_key).get()

    def run_http(
        self,
        *,
        base_url: str,
        timeout: float,
        trust_env: bool = True,
        operation: Callable[[object], T],
    ) -> T:
        return self._http_entry_for(base_url=base_url, timeout=timeout, trust_env=trust_env).run(operation)

    def run_gemini(self, *, api_key: str | None, operation: Callable[[object], T]) -> T:
        return self._gemini_entry(api_key).run(operation)

    def client_entries(self) -> tuple[tuple[object, object | None, int], ...]:
        """Safe diagnostic snapshot without constructing unloaded clients."""
        with self._registry_lock:
            combined = [*self._http_entries.items(), *self._gemini_entries.items()]
            return tuple((identity, entry.loaded_client, entry.construction_count) for identity, entry in combined)

    def close(self) -> None:
        with self._registry_lock:
            if self._closed:
                return
            self._closed = True
            entries = tuple([*self._http_entries.values(), *self._gemini_entries.values()])
            self._http_entries.clear()
            self._gemini_entries.clear()
        first_error: Exception | None = None
        for entry in entries:
            try:
                entry.close()
            except Exception as exc:  # cleanup every client before surfacing the first failure
                first_error = first_error or exc
        if first_error is not None:
            raise first_error

    def _http_entry(self, identity: HttpClientIdentity) -> _ClientEntry:
        with self._registry_lock:
            self._ensure_open()
            entry = self._http_entries.get(identity)
            if entry is None:
                entry = _ClientEntry(lambda: self._http_client_factory(identity))
                self._http_entries[identity] = entry
            return entry

    def _http_entry_for(self, *, base_url: str, timeout: float, trust_env: bool = True) -> _ClientEntry:
        identity = HttpClientIdentity(
            endpoint_fingerprint=_fingerprint(base_url.rstrip("/")),
            timeout=timeout,
            trust_env=trust_env,
            environment_fingerprint=_environment_fingerprint(_HTTP_ENV_KEYS),
        )
        return self._http_entry(identity)

    def _gemini_entry(self, api_key: str | None) -> _ClientEntry:
        identity = GeminiClientIdentity(
            credential_fingerprint=_fingerprint(api_key or ""),
            environment_fingerprint=_environment_fingerprint(_GEMINI_ENV_KEYS),
        )
        with self._registry_lock:
            self._ensure_open()
            entry = self._gemini_entries.get(identity)
            if entry is None:
                entry = _ClientEntry(lambda: self._gemini_client_factory(api_key))
                self._gemini_entries[identity] = entry
            return entry

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Provider client runtime is closed")


def _load_http_client(identity: HttpClientIdentity) -> object:
    import httpx

    return httpx.Client(
        timeout=identity.timeout,
        verify=identity.verify,
        trust_env=identity.trust_env,
    )


def _load_gemini_client(api_key: str | None) -> object:
    from google import genai

    return genai.Client(api_key=api_key)


def _environment_fingerprint(keys: tuple[str, ...]) -> str:
    return _fingerprint(*(f"{key}={os.getenv(key, '')}" for key in keys))


def _fingerprint(*values: str) -> str:
    digest = hashlib.sha256()
    for value in values:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()
