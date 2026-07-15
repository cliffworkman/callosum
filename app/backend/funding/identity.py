"""Deterministic funding-organization identity helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OrganizationCandidate:
    display_name: str
    identifiers: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    resolution_status: str = "unresolved"
    resolution_basis: str = "unresolved"


def normalize_org_name(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()
    suffixes = {"inc", "llc", "foundation", "trust", "fund", "the"}
    return " ".join(w for w in text.split() if w not in suffixes)


def resolve_organization(
    name: str,
    candidates: list[OrganizationCandidate],
    *,
    ein: str | None = None,
    ror: str | None = None,
) -> list[OrganizationCandidate]:
    """Return all plausible candidates; never force a winner on ambiguity."""
    if ein:
        wanted_ein = re.sub(r"\D+", "", ein).zfill(9)
        exact = [
            c for c in candidates if re.sub(r"\D+", "", str(c.identifiers.get("ein") or "")).zfill(9) == wanted_ein
        ]
        if exact:
            return [
                OrganizationCandidate(c.display_name, c.identifiers, c.aliases, "resolved", "exact_ein") for c in exact
            ]
    if ror:
        exact = [c for c in candidates if c.identifiers.get("ror") == ror]
        if exact:
            return [
                OrganizationCandidate(c.display_name, c.identifiers, c.aliases, "resolved", "exact_ror") for c in exact
            ]
    target = normalize_org_name(name)
    matches: list[OrganizationCandidate] = []
    for c in candidates:
        names = [c.display_name, *c.aliases]
        if any(normalize_org_name(n) == target for n in names):
            matches.append(OrganizationCandidate(c.display_name, c.identifiers, c.aliases, "probable", "name_or_alias"))
    if len(matches) == 1:
        return [
            OrganizationCandidate(
                matches[0].display_name, matches[0].identifiers, matches[0].aliases, "resolved", "exact_name"
            )
        ]
    if matches:
        return [
            OrganizationCandidate(c.display_name, c.identifiers, c.aliases, "ambiguous", c.resolution_basis)
            for c in matches
        ]
    return [OrganizationCandidate(name.strip() or "Unresolved funder", {}, [], "unresolved", "no_candidate")]
