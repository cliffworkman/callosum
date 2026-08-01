from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class RegistrationAcquisitionError(RuntimeError):
    """A confirmed registration could not be safely acquired or canonicalized."""


@dataclass(frozen=True)
class AcquiredRegistration:
    provider: str
    external_id: str
    canonical_url: str
    content_hash: str
    registered_at: str | None
    registration_status: str
    schema_name: str | None
    schema_version: str | None
    structured: dict[str, Any]
    rendered_text: str
    source_metadata: dict[str, Any]
    file_bytes: bytes
    file_suffix: str
    content_type: str


class RegistrationAcquirer(Protocol):
    id: str

    def acquire(self, link: dict[str, Any]) -> AcquiredRegistration: ...


class RegistrationAcquisitionRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, RegistrationAcquirer] = {}

    def register(self, provider: RegistrationAcquirer) -> "RegistrationAcquisitionRegistry":
        self._providers[provider.id] = provider
        return self

    def acquire(self, link: dict[str, Any]) -> AcquiredRegistration:
        provider = self._providers.get(str(link["provider"]))
        if provider is None:
            raise RegistrationAcquisitionError(
                f"No managed acquisition provider is available for {link['provider']}; attach a local PDF instead."
            )
        return provider.acquire(link)
