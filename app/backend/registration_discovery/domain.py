from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Literal, Protocol

LinkageClass = Literal["explicit-linkage", "strong-contextual-match", "similarity-candidate"]
_CLASS_RANK = {"explicit-linkage": 0, "strong-contextual-match": 1, "similarity-candidate": 2}
_WORDS = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class DiscoveryReference:
    provider: str
    external_id: str
    canonical_url: str | None
    extraction_method: str
    explicitly_printed: bool
    evidence_snippet: str | None


@dataclass(frozen=True)
class DiscoveryRequest:
    paper_id: int
    doi: str | None
    title: str
    authors: tuple[str, ...]
    year: int | None
    references: tuple[DiscoveryReference, ...]
    fresh: bool = False


@dataclass(frozen=True)
class RegistrationCandidate:
    provider: str
    external_id: str
    registration_doi: str | None
    canonical_url: str | None
    title: str | None
    contributors: tuple[str, ...]
    registered_at: str | None
    registration_status: str | None
    schema_name: str | None
    linkage_class: LinkageClass
    match_method: str
    match_evidence: tuple[dict[str, Any], ...]
    source_metadata: dict[str, Any]
    attachment_id: int | None = None


@dataclass(frozen=True)
class ProviderReport:
    provider: str
    status: Literal["ok", "unavailable", "error"]
    candidates: tuple[RegistrationCandidate, ...] = ()
    detail: str | None = None


class RegistrationDiscoveryProvider(Protocol):
    id: str

    def discover(self, request: DiscoveryRequest) -> ProviderReport: ...


class RegistrationDiscoveryRegistry:
    def __init__(self) -> None:
        self._providers: list[RegistrationDiscoveryProvider] = []

    def register(self, provider: RegistrationDiscoveryProvider) -> "RegistrationDiscoveryRegistry":
        self._providers.append(provider)
        return self

    def discover(self, request: DiscoveryRequest) -> tuple[list[RegistrationCandidate], list[ProviderReport]]:
        reports: list[ProviderReport] = []
        merged: dict[tuple[str, str], RegistrationCandidate] = {}
        for provider in self._providers:
            try:
                report = provider.discover(request)
            except Exception as exc:  # one provider never destroys another's result or existing state
                report = ProviderReport(provider=provider.id, status="error", detail=f"{type(exc).__name__}: {exc}")
            reports.append(report)
            for candidate in report.candidates:
                key = (candidate.provider, candidate.external_id.casefold())
                merged[key] = _merge_candidates(merged[key], candidate) if key in merged else candidate
        candidates = sorted(merged.values(), key=_candidate_sort_key)
        return candidates, reports


def contextual_evidence(request: DiscoveryRequest, candidate: RegistrationCandidate) -> tuple[dict[str, Any], ...]:
    evidence: list[dict[str, Any]] = []
    left, right = set(_WORDS.findall(request.title.casefold())), set(_WORDS.findall((candidate.title or "").casefold()))
    informative = {word for word in left & right if len(word) > 3}
    if informative:
        evidence.append({"kind": "title-terms", "terms": sorted(informative)[:12]})
    paper_families = {_family(name) for name in request.authors if _family(name)}
    candidate_families = {_family(name) for name in candidate.contributors if _family(name)}
    overlap = sorted(paper_families & candidate_families)
    if overlap:
        evidence.append({"kind": "contributor-overlap", "names": overlap})
    if request.year and candidate.registered_at:
        try:
            registration_year = int(candidate.registered_at[:4])
            evidence.append(
                {
                    "kind": "date-order",
                    "registration_year": registration_year,
                    "publication_year": request.year,
                    "registration_not_after_publication_year": registration_year <= request.year,
                }
            )
        except ValueError:
            pass
    return tuple(evidence)


def contextual_class(evidence: tuple[dict[str, Any], ...], *, one_registration_on_node: bool = False) -> LinkageClass:
    kinds = {item.get("kind") for item in evidence}
    if one_registration_on_node and ("title-terms" in kinds or "contributor-overlap" in kinds):
        return "strong-contextual-match"
    if {"title-terms", "contributor-overlap"} <= kinds:
        return "strong-contextual-match"
    return "similarity-candidate"


def _merge_candidates(left: RegistrationCandidate, right: RegistrationCandidate) -> RegistrationCandidate:
    strongest = left if _CLASS_RANK[left.linkage_class] <= _CLASS_RANK[right.linkage_class] else right
    evidence = tuple(dict.fromkeys(_json_key(item) for item in left.match_evidence + right.match_evidence))
    # Rehydrate the tiny JSON keys only after deduplication.
    import json

    return replace(
        strongest,
        registration_doi=left.registration_doi or right.registration_doi,
        canonical_url=left.canonical_url or right.canonical_url,
        title=left.title or right.title,
        contributors=left.contributors or right.contributors,
        registered_at=left.registered_at or right.registered_at,
        registration_status=left.registration_status or right.registration_status,
        schema_name=left.schema_name or right.schema_name,
        match_evidence=tuple(json.loads(item) for item in evidence),
        source_metadata=left.source_metadata | right.source_metadata,
    )


def _json_key(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _candidate_sort_key(candidate: RegistrationCandidate) -> tuple:
    return (_CLASS_RANK[candidate.linkage_class], (candidate.title or "").casefold(), candidate.external_id)


def _family(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.split(",", 1)[0].split()[-1].casefold()) if name.strip() else ""
