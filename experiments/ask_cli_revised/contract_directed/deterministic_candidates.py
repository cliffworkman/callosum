"""Deterministic first-pass candidates for straightforward, closed-class evidence (Cliff's #1/#3, session 2026-09-26/27).

A fast-pathed candidate is NEVER auto-verified — it is a proposition, built exactly like a model-produced one, that
still goes through the unchanged eligibility call (relata identification, polarity, `on_topic`, pairing derivation)
for a genuine judgment. The only thing a fast path ever saves is the LOCALIZATION call that decides which
sentence(s) are worth turning into a proposition at all.

Scoped narrowly, per Cliff's instruction to decline rather than invent a speculative signal: an instrument name
(`Scale/Index/Questionnaire/...`, a closed lexical class shared with `attribution.INSTRUMENT_DESCRIBES`) followed by
a measurement verb, over a COMPLETE (non-fragment) sentence, is the only pattern judged safe enough for a call-skip
in this iteration. Relationship and existence/cross-cultural findings have no equally closed-class signal — see
`CONTRACT_DIRECTED.md`'s notes on C3 (relationship: fast-pathed only when an inline statistic co-occurs, otherwise
full cost) and C4 (existence/cross-cultural: declined this iteration, full cost, named as a future direction).
"""

from __future__ import annotations

from experiments.ask_cli_revised.contract_directed import attribution as at
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract
from experiments.ask_cli_revised.contract_directed.units import SentenceUnit

INSTRUMENT_MANNER_KINDS = frozenset({"operation", "manner", "requested_item"})
MAX_CANDIDATES = 6


def applies(child: ChildContract) -> bool:
    """Whether this child owns any content unit this detector could ever be relevant to."""
    return any(u.kind in INSTRUMENT_MANNER_KINDS for u in child.content_units)


def find_instrument_pairing_candidates(unit_list: list[SentenceUnit], child: ChildContract) -> list[dict]:
    """Complete sentences matching the instrument-plus-measurement-verb pattern, as localization-shaped propositions.

    Never matches a fragment (`open_left`/`open_right`) — a truncated result is exactly the "identifiable problem"
    (Cliff's own framing) that still needs a real model call, not a deterministic guess. Each match is its own
    proposition (a neighborhood can hold several distinct instrument descriptions, e.g. a Methods paragraph
    describing three separate scales one after another); capped at `MAX_CANDIDATES` for safety, though the pattern
    itself is cheap and fully deterministic.
    """
    if not applies(child):
        return []
    out: list[dict] = []
    for unit in unit_list:
        if unit.open_left or unit.open_right:
            continue
        if not at.INSTRUMENT_DESCRIBES.search(at.dehyphenate_for_matching(unit.text)):
            continue
        out.append(
            {
                "establishing": [unit.unit_id],
                "qualifying": [],
                "referents": [],
                "provenance_class": "methods",
                "attribution_basis_phrase": "",
                "relation_polarity": "not_a_relation",
                "unresolved": [],
                "source": "deterministic_pattern:instrument_measurement_verb",
            }
        )
        if len(out) >= MAX_CANDIDATES:
            break
    return out


def only_instrument_manner_targeted(nbhd: dict, child: ChildContract) -> bool:
    """Whether the ONLY reason this neighborhood was selected at all is one or more `unit_probe` routes for
    operation/manner/requested_item units — i.e. nothing else (no abstract-page, no whole-child wording match) makes
    this neighborhood worth a model's attention for anything beyond the pattern this module already checked. This is
    the strict condition under which a clean match may skip the localization model call entirely.
    """
    routes = nbhd.get("routes", [])
    if not routes or any(not r.startswith("unit_probe:") for r in routes):
        return False
    unit_ids = {r.split(":", 1)[1] for r in routes}
    child_unit_ids = {u.unit_id for u in child.content_units}
    if not unit_ids <= child_unit_ids:
        return False
    kinds = {child.unit(uid).kind for uid in unit_ids}
    return bool(kinds) and kinds <= INSTRUMENT_MANNER_KINDS
