"""The literature-acquisition resolver seam — the structural guarantee for the legally-clear OA lane.

A resolver returns an ``OaLocation`` (or ``None``), **never a bare URL**. ``OaLocation`` carries a
**required** open-access color (gold/green/bronze — there is deliberately no "closed"/"none" member) and a
version, so a resolver cannot mint one unless a maintained OA database (OpenAlex/DOAJ/CORE) asserts the
copy is open access. The downloader (``app/backend/acquisition/fetch.py``) takes an ``OaLocation``, never a
URL string — so there is no surface on which an arbitrary or non-OA URL can be fetched. OA-ness is decided
by the databases, never by callosum.

This is the seam-enforced form of the acquisition bright lines (cf. the inc-58 egress gate, where the
guarantee lives in the DI seam, not in per-call convention). Structural tests pin both properties:
``OaLocation`` rejects a non-OA color, and no public function in this package fetches a bare URL.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable
from urllib.parse import urlparse

from sqlalchemy import Connection

OaColor = Literal["gold", "green", "bronze"]
OaVersion = Literal["vor", "am", "preprint"]

_OA_COLORS = frozenset({"gold", "green", "bronze"})
_OA_VERSIONS = frozenset({"vor", "am", "preprint"})


@dataclass(frozen=True)
class PaperRef:
    """The identifiers a resolver may use, built at the API boundary from a stored paper."""

    doi: str | None = None
    pmid: str | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        if not (self.doi or self.pmid or self.title):
            raise ValueError("PaperRef needs at least one of doi / pmid / title")


@dataclass(frozen=True)
class OaLocation:
    """An authorized open-access PDF location, as asserted by an OA database.

    The ONLY currency between "what a database said is free" and "what we download." There is deliberately
    no "closed" OA color — an instance cannot exist for a non-OA copy.
    """

    pdf_url: str
    oa_color: OaColor
    version: OaVersion
    source: str  # the resolver id that produced this (e.g. "openalex")
    landing_page_url: str | None = None
    license: str | None = None

    def __post_init__(self) -> None:
        if self.oa_color not in _OA_COLORS:
            raise ValueError(f"oa_color must be one of {sorted(_OA_COLORS)}; got {self.oa_color!r}")
        if self.version not in _OA_VERSIONS:
            raise ValueError(f"version must be one of {sorted(_OA_VERSIONS)}; got {self.version!r}")
        _require_safe_https(self.pdf_url)

    @property
    def bronze_unstable(self) -> bool:
        """Bronze = free-to-read on the publisher site without an open license; it can revert to paywalled,
        so it is never presented as durable."""
        return self.oa_color == "bronze"


def _require_safe_https(url: str) -> None:
    """An OA pdf_url must be https with a real domain host (defense-in-depth SSRF; the URL already comes
    from an OA database, not user input)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"OA pdf_url must be https; got scheme {parsed.scheme!r}")
    host = parsed.hostname or ""
    if not host:
        raise ValueError("OA pdf_url must have a host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return  # not an IP literal — good (a domain name)
    raise ValueError(f"OA pdf_url host must be a domain, not an IP literal: {host!r}")


@runtime_checkable
class Resolver(Protocol):
    """Resolve a paper to an authorized-OA location, or None. Never returns or accepts a bare URL to fetch."""

    id: str

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None: ...


class ResolverRegistry:
    """An ordered cascade of resolvers. ``resolve()`` returns the FIRST authorized OA copy (registration
    order is the only knob). A new resolver joins via ``register()`` **without editing** ``resolve()`` — the
    cascade loop is closed to edits (proven by a test)."""

    def __init__(self) -> None:
        self._resolvers: list[Resolver] = []

    def register(self, resolver: Resolver) -> None:
        self._resolvers.append(resolver)

    def resolvers(self) -> tuple[Resolver, ...]:
        return tuple(self._resolvers)

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        for resolver in self._resolvers:
            location = resolver.resolve(conn, ref)
            if location is not None:
                return location
        return None


def build_default_registry(*, openalex_client=None) -> ResolverRegistry:
    """The single wiring point for the cascade. Increment B appends ``register(...)`` calls here in
    gold→green→preprint order; the ``resolve()`` loop never changes."""
    # Imported here (not at module top) to avoid a load-time cycle: the resolver imports OaLocation/PaperRef
    # from this module.
    from app.backend.acquisition.resolvers.openalex_resolver import OpenAlexResolver

    registry = ResolverRegistry()
    registry.register(OpenAlexResolver(client=openalex_client))
    return registry
