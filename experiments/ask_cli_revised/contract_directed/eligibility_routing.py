"""Fair, call-metered eligibility scheduling (Cliff's #2, corrected v2, session 2026-09-26/27). Pure helpers only —
the actual scheduling loop (which needs the model client) lives in `pipeline.schedule_and_judge`.

Every child's own-route packets are judged first, round-robin across children (never one child's whole queue before
another's — a binding global budget can otherwise starve a later child even with own-route-first). Cross-route
packets are ordered by a SOFT lexical-overlap hint only: missing vocabulary is not proof of irrelevance (a real
amygdala finding need not say "brain areas"; a real Hadza finding need not say "cross-cultural"), so nothing here
ever excludes a candidate — the hint only decides which order a bounded budget tries them in. No safe hard-exclusion
rule was found; this is recorded as an open point in `GATE1_REPAIR_HANDBACK.md`, not papered over.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.contract_directed.freeze import ChildContract

_STOP = frozenset(
    {
        "the", "a", "an", "of", "in", "on", "to", "and", "or", "is", "are", "was", "were", "that", "this", "these",
        "those", "for", "with", "as", "by", "at", "from", "be", "which", "it", "its", "their", "than", "then",
        "who", "what", "when", "where", "how", "not", "no", "any", "some", "has", "have", "had", "been", "being",
        "into", "about", "also", "such", "other", "each", "both", "between", "among", "across", "during", "after",
        "before", "while", "because", "however",
    }
)  # fmt: skip
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]{3,}")


def salient_terms(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "") if w.lower() not in _STOP}


def _packet_core_text(packet: dict) -> str:
    return " ".join(p["text"] for p in packet["parts"] if p["role"] not in ("linked_definition", "study_context"))


def _child_terms(child: ChildContract) -> set[str]:
    terms = salient_terms(child.contract_text)
    for unit in child.content_units:
        terms |= salient_terms(unit.text)
    return terms


def cross_child_priority_hint(packet: dict, child: ChildContract) -> float:
    """A SOFT ordering signal in [0, 1] — never a truth claim about relevance. A packet scoring 0 is still checked
    if the child's obligation remains open and budget allows; the hint only decides the order a bounded budget
    tries candidates in."""
    packet_terms = _packet_core_text(packet)
    packet_terms = salient_terms(packet_terms)
    if not packet_terms:
        return 0.0
    shared = packet_terms & _child_terms(child)
    return len(shared) / len(packet_terms)


def own_route_packets(child: ChildContract, packets: list[dict]) -> list[dict]:
    own = [p for p in packets if child.child_id in p["found_under"]]
    return sorted(own, key=lambda p: (-p.get("nbhd_score", 0.0), p["paper_id"], p["packet_id"]))


def cross_route_packets(child: ChildContract, packets: list[dict]) -> list[dict]:
    cross = [p for p in packets if child.child_id not in p["found_under"]]
    return sorted(
        cross,
        key=lambda p: (-cross_child_priority_hint(p, child), -p.get("nbhd_score", 0.0), p["paper_id"], p["packet_id"]),
    )


def _chunk_range(packet: dict) -> tuple[int | None, int | None]:
    ids = [pc["chunk_id"] for part in packet["parts"] for pc in part["pieces"]]
    return (min(ids), max(ids)) if ids else (None, None)


def is_distinct_from(packet: dict, closing_packets: list[dict]) -> bool:
    """A cheap, mechanical distinctness test for Tier 3: a different paper, or a non-overlapping chunk range of the
    same paper, than whatever already closed the unit. Never a claim about content similarity — this decides
    whether a candidate is worth a Tier-3 call, not whether it would actually add something."""
    p_lo, p_hi = _chunk_range(packet)
    for other in closing_packets:
        if other["paper_id"] != packet["paper_id"]:
            continue
        o_lo, o_hi = _chunk_range(other)
        if p_lo is None or o_lo is None:
            return False
        if not (p_hi < o_lo or o_hi < p_lo):
            return False
    return True
