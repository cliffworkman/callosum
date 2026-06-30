"""Pluggable metadata-enrichment sources for the multi-pass, gap-filling enricher (inc 217).

Each source maps an identifier (DOI / PMID / title) → a **CSL-fragment** (a subset of CSL keys it can supply:
``title, author, issued, container-title, type, abstract, DOI, PMID, subject``); the orchestrator
(``enrichment.enrich_paper_metadata_multi``) runs the registered sources **in order** and fills only a paper's
**empty** fields, never overwriting a value already present. Adding a source = ``register()`` one provider — no
endpoint/UI edit (mirrors the discovery ``SourceRegistry`` + the acquisition ``ResolverRegistry``).

Egress here is **public bibliographic metadata** (Crossref / OpenAlex / …), the inc-87/183/210 posture — **NOT**
the Gemini library-text gate. Every source is fail-closed (any error → ``None``; never raises to the cascade).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import Connection

from app.backend.acquisition.registry import PaperRef
from integrations.crossref import CrossrefClient
from integrations.openalex import OpenAlexClient


@dataclass(frozen=True)
class EnrichRef:
    """The identifiers the enricher hands a source, built from a stored paper."""

    doi: str | None = None
    pmid: str | None = None
    title: str | None = None
    year: int | None = None

    def to_paper_ref(self) -> PaperRef | None:
        """A PaperRef for the DOI/PMID/title-keyed clients, or None if there's nothing to look up."""
        if not (self.doi or self.pmid or self.title):
            return None
        return PaperRef(doi=self.doi, pmid=self.pmid, title=self.title)


@runtime_checkable
class EnrichmentSource(Protocol):
    name: str

    def fetch(self, conn: Connection, ref: EnrichRef) -> dict[str, Any] | None:
        """Return a CSL-fragment for this paper, or None. Must not raise (fail-closed)."""
        ...


class EnrichmentRegistry:
    def __init__(self) -> None:
        self._sources: list[EnrichmentSource] = []

    def register(self, source: EnrichmentSource) -> "EnrichmentRegistry":
        self._sources.append(source)
        return self

    @property
    def sources(self) -> list[EnrichmentSource]:
        return list(self._sources)

    def fetch_all(self, conn: Connection, ref: EnrichRef) -> list[dict[str, Any]]:
        """Run every source in order; a source that raises or returns nothing is skipped (one bad source must
        never sink the cascade — mirrors ``SourceRegistry.search_all``). Returns the non-empty CSL fragments."""
        out: list[dict[str, Any]] = []
        for source in self._sources:
            try:
                fragment = source.fetch(conn, ref)
            except Exception:  # noqa: BLE001 — fail-closed; never let one source break enrichment
                continue
            if fragment:
                out.append(fragment)
        return out


class CrossrefEnrichSource:
    """Crossref by DOI → its full CSL record (the existing engine's source). DOI-only; None without one."""

    name = "crossref"

    def __init__(self, client: CrossrefClient | None = None) -> None:
        self._client = client

    def fetch(self, conn: Connection, ref: EnrichRef) -> dict[str, Any] | None:
        if not ref.doi:
            return None
        client = self._client or CrossrefClient()
        resolution = client.resolve_doi(conn, ref.doi)
        if resolution.resolved and resolution.csl_json:
            return dict(resolution.csl_json)
        return None


class OpenAlexEnrichSource:
    """OpenAlex by DOI/PMID/title → a CSL-fragment (notably venue / abstract / type that Crossref may lack)."""

    name = "openalex"

    def __init__(self, client: OpenAlexClient | None = None) -> None:
        self._client = client

    def fetch(self, conn: Connection, ref: EnrichRef) -> dict[str, Any] | None:
        paper_ref = ref.to_paper_ref()
        if paper_ref is None:
            return None
        client = self._client or OpenAlexClient()
        return client.fetch_work_csl(conn, paper_ref)


def build_default_enrich_registry(
    *,
    crossref_client: CrossrefClient | None = None,
    openalex_client: OpenAlexClient | None = None,
) -> EnrichmentRegistry:
    """The shipped enrichment cascade (gap-fill, in order). SP1: Crossref-by-DOI → OpenAlex-by-DOI/PMID/title.
    SP2 adds Europe PMC + PubMed — each one ``register()`` (the registry test proves a new source needs no other
    edit). Sources reuse the injectable clients (hermetic tests) and default to the real ones."""
    return (
        EnrichmentRegistry()
        .register(CrossrefEnrichSource(crossref_client))
        .register(OpenAlexEnrichSource(openalex_client))
    )
