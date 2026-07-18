"""The SourceProvider registry + the normalized discovery Item (backlog #28, inc 183).

A source is a self-registering module conforming to ``SourceProvider`` (``name`` + ``search(query, limit)``); the
registry fans out to all of them. Adding a source = register one provider — **no endpoint/UI edit** (the registry
test proves this). Mirrors the acquisition-resolver registry + the pane registry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Protocol, runtime_checkable

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalized_title(title: str | None) -> str:
    return _NON_ALNUM.sub(" ", (title or "").lower()).strip()


@dataclass(frozen=True)
class Item:
    """A normalized search result, deduped across providers. PDF acquisition is out of scope (metadata only)."""

    title: str
    sources: tuple[str, ...] = ()  # provider names that returned this item (>1 when deduped across sources)
    doi: str | None = None
    pmid: str | None = None
    abstract: str | None = None
    authors: tuple[str, ...] = ()  # "Family, Given" strings
    journal: str | None = None
    year: int | None = None
    url: str | None = None
    in_library: bool = False  # set by the search service (dedup vs the library)

    @property
    def dedup_key(self) -> str:
        if self.doi:
            return "doi:" + self.doi.lower()
        if self.pmid:
            return "pmid:" + self.pmid
        return "title:" + normalized_title(self.title)

    def merged_with(self, other: "Item") -> "Item":
        """Combine a duplicate from another provider: union the source labels, fill any blank fields."""
        sources = tuple(dict.fromkeys(self.sources + other.sources))
        return replace(
            self,
            sources=sources,
            doi=self.doi or other.doi,
            pmid=self.pmid or other.pmid,
            abstract=self.abstract or other.abstract,
            authors=self.authors or other.authors,
            journal=self.journal or other.journal,
            year=self.year or other.year,
            url=self.url or other.url,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sources": list(self.sources),
            "doi": self.doi,
            "pmid": self.pmid,
            "abstract": self.abstract,
            "authors": list(self.authors),
            "journal": self.journal,
            "year": self.year,
            "url": self.url,
            "in_library": self.in_library,
            "dedup_key": self.dedup_key,
        }


@runtime_checkable
class SourceProvider(Protocol):
    name: str
    label: str

    def search(self, query: str, limit: int) -> list[Item]: ...


class SourceRegistry:
    def __init__(self) -> None:
        self._providers: list[SourceProvider] = []

    def register(self, provider: SourceProvider) -> "SourceRegistry":
        self._providers.append(provider)
        return self

    @property
    def providers(self) -> list[SourceProvider]:
        return list(self._providers)

    @property
    def kinds(self) -> list[str]:
        return [provider.name for provider in self._providers]

    @property
    def source_meta(self) -> list[dict[str, str]]:
        return [
            {"kind": provider.name, "label": getattr(provider, "label", provider.name)} for provider in self._providers
        ]

    def get(self, name: str) -> SourceProvider | None:
        normalized = (name or "").strip().lower()
        return next((provider for provider in self._providers if provider.name == normalized), None)

    def search_all(self, query: str, limit: int) -> list[Item]:
        """Fan out to every provider; a provider that raises is skipped (never breaks the whole search)."""
        out: list[Item] = []
        for provider in self._providers:
            try:
                out.extend(provider.search(query, limit))
            except Exception:  # noqa: BLE001 — one bad source must not sink the others
                continue
        return out

    def search_one(self, name: str, query: str, limit: int) -> list[Item]:
        """Search one named provider; provider errors still fail closed to an empty list."""
        provider = self.get(name)
        if provider is None:
            raise KeyError(name)
        try:
            return provider.search(query, limit)
        except Exception:  # noqa: BLE001 — one bad source must not sink the search UI
            return []


def build_default_registry() -> SourceRegistry:
    """The shipped providers. Crossref (journals + preprints) + PubMed (biomedical, SP1a). Adding a source is one
    `register()` — no endpoint/UI edit (the registry test proves it). bioRxiv lands in the Feed (SP2)."""
    from app.backend.discovery.crossref_provider import CrossrefSearchProvider
    from app.backend.discovery.pubmed_provider import PubMedSearchProvider

    return SourceRegistry().register(CrossrefSearchProvider()).register(PubMedSearchProvider())
