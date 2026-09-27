"""Section families as provenance/direction clues, never as gates.

`chunks.section` is a heuristic label (NULL on ~10% of chunks) and GROBID section kinds are mostly NULL, so a family is a
*direction* for where to look, not a fact about a passage. Family pools are UNIONS: chunks labelled with a wanted family plus
every chunk with no usable label. A paper is never excluded, and never shrunk to nothing, because its metadata is missing.
"""

from __future__ import annotations

KNOWN_FAMILIES = frozenset(
    {
        "abstract", "introduction", "methods", "results", "discussion", "references", "supplementary_material",
        "data_availability", "funding", "conflict_of_interest", "ethics", "code_availability",
    }
)  # fmt: skip

# Frozen obligation kind -> where its answer is most likely stated. A hypothesis whose contribution is attributed
# (anchor_route), not assumed.
KIND_FAMILIES: dict[str, tuple[str, ...]] = {
    "operation": ("methods", "results", "abstract"),
    "manner": ("methods", "results", "abstract"),
    "population": ("methods", "results", "abstract"),
    "relationship": ("results", "discussion", "abstract"),
    "existence": ("results", "discussion", "abstract"),
    "requested_item": ("results", "discussion", "abstract"),
    "kinds": ("results", "discussion", "abstract"),
}

LABELED = "labeled"
GROBID = "grobid"
UNKNOWN = "unknown"


def family_of(section: str | None, grobid_kind: str | None = None) -> tuple[str | None, str]:
    """(family, state). `chunks.section` wins; a GROBID kind is used only when the heuristic label is missing."""
    if section in KNOWN_FAMILIES:
        return section, LABELED
    if grobid_kind in KNOWN_FAMILIES:
        return grobid_kind, GROBID
    return None, UNKNOWN


def families_for_units(unit_kinds: list[str]) -> tuple[str, ...]:
    """The union of the kind-directed families for a child's content units, in first-seen order."""
    seen: list[str] = []
    for kind in unit_kinds:
        for family in KIND_FAMILIES.get(kind, ()):
            if family not in seen:
                seen.append(family)
    return tuple(seen)


def family_pool(chunks: list[dict], families: tuple[str, ...]) -> list[dict]:
    """Chunks labelled with a wanted family plus every chunk with no usable label. References never enter a pool."""
    pool = []
    for chunk in chunks:
        family, _state = family_of(chunk.get("section"), chunk.get("grobid_kind"))
        if family == "references":
            continue
        if family is None or family in families:
            pool.append(chunk)
    return pool
