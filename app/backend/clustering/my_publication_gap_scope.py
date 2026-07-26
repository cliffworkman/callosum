"""Stable, server-validated scopes for My Publications citation-gap discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable

from sqlalchemy import Connection

from app.backend.persistence.profile_repo import get_profile

MAX_SELECTED_DOMAINS = 8
MAX_DOMAIN_LABEL_LEN = 200
_DOMAIN_KEY_RE = re.compile(r"domain:[0-9a-f]{20}")


@dataclass(frozen=True)
class CitationGapScope:
    key: str
    kind: str
    domain_keys: tuple[str, ...]
    domain_labels: tuple[str, ...]
    paper_ids: frozenset[int] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "domain_keys": list(self.domain_keys),
            "domain_labels": list(self.domain_labels),
            "paper_ids": sorted(self.paper_ids) if self.paper_ids is not None else [],
        }


def citation_gap_domain_key(paper_ids: Iterable[Any]) -> str:
    normalized = sorted({_positive_int(value) for value in paper_ids} - {None})
    digest = sha256(",".join(str(value) for value in normalized).encode("ascii")).hexdigest()[:20]
    return f"domain:{digest}"


def resolve_citation_gap_scope(conn: Connection, domain_keys: Iterable[str] | None) -> CitationGapScope:
    requested = _unique_bounded_keys(domain_keys)
    if not requested:
        return CitationGapScope(
            key="all",
            kind="all",
            domain_keys=(),
            domain_labels=(),
            paper_ids=None,
        )

    profile = get_profile(conn) or {}
    available: dict[str, tuple[str, frozenset[int]]] = {}
    for domain in profile.get("research_domains") or []:
        if not isinstance(domain, dict):
            continue
        paper_ids = frozenset(
            value for raw in (domain.get("paper_ids") or []) if (value := _positive_int(raw)) is not None
        )
        if not paper_ids:
            continue
        key = citation_gap_domain_key(paper_ids)
        label = str(domain.get("label") or "Domain").strip()[:MAX_DOMAIN_LABEL_LEN] or "Domain"
        available.setdefault(key, (label, paper_ids))

    unknown = [key for key in requested if key not in available]
    if unknown:
        raise ValueError("One or more selected research domains are no longer available; reload the dashboard.")

    selected_keys = tuple(sorted(requested))
    paper_ids = frozenset(paper_id for key in selected_keys for paper_id in available[key][1])
    labels = tuple(available[key][0] for key in selected_keys)
    digest = sha256("|".join(selected_keys).encode("ascii")).hexdigest()[:24]
    return CitationGapScope(
        key=f"domains:{digest}",
        kind="domains",
        domain_keys=selected_keys,
        domain_labels=labels,
        paper_ids=paper_ids,
    )


def _unique_bounded_keys(values: Iterable[str] | None) -> list[str]:
    keys: list[str] = []
    for value in values or []:
        key = str(value).strip()
        if key and _DOMAIN_KEY_RE.fullmatch(key) is None:
            raise ValueError("Invalid research-domain scope.")
        if key and key not in keys:
            keys.append(key)
    if len(keys) > MAX_SELECTED_DOMAINS:
        raise ValueError(f"Select at most {MAX_SELECTED_DOMAINS} research domains.")
    return keys


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
