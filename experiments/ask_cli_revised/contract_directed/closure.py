"""Closure rules: when may ONE source-grounded finding close a frozen obligation unit?

The eligibility model reports which exact spans fill which slot; this module DERIVES the status. A unit closes
(`directly_establishes`) only if every required slot has valid span ids inside one finding bundle (a core proposition plus its
verified links), the core spans carry `own_established` attribution, no needed span is an unresolved-seam fragment, and the
relata of a relationship are tied to its relation stated in the same unit or a declared adjacent referent. Otherwise it is
`partially_establishes` (missing slots listed) or `not_addressed`. Two findings are NEVER summed; a linked span (Methods
definition of a measure) may supply only descriptive slots, never the finding-bearing ones. Pure.
"""

from __future__ import annotations

from experiments.ask_cli_revised.contract_directed import attribution as at

DIRECTLY = "directly_establishes"
PARTIAL = "partially_establishes"
NOT_ADDRESSED = "not_addressed"
POLARITY_VALUES = ("association", "none", "mixed", "not_stated")
MAX_RELATUM_DISTANCE = 2  # units between a relatum and the relation unit when they are not the same unit

# Required slots per frozen unit kind (direction is added when polarity is association/mixed; pairing when the child has #pair).
REQUIRED_SLOTS: dict[str, tuple[str, ...]] = {
    "relationship": ("relatum_a", "relatum_b", "relation_stated", "polarity"),
    "requested_item": ("item_named", "tied_to_subject"),
    "kinds": ("kind_named", "tied_to_relation"),
    "operation": ("instrument_named", "paired_with_construct"),
    "manner": ("manner_described", "tied_to_subject"),
    "population": ("population_named", "tied_to_finding"),
    "existence": ("finding_of_type", "outcome_reported"),
}
OPTIONAL_SLOTS = (
    "direction",
    "population",
    "qualifiers",
)  # preserved when the source states them; recorded, not required
PAIRING_SLOT = "pairing_expressed"
# Slots a verified LINK (a definition elsewhere in the same study) may supply. Everything else must come from the core proposition.
LINKABLE_SLOTS = frozenset({"instrument_named", "manner_described", "population_named"})

SLOT_DEFINITIONS = {
    "relatum_a": "the first thing the relation is about (for example a brain area), named in the span",
    "relatum_b": "the second thing the relation is about (for example a behavior or attitude), named in the span",
    "relation_stated": "the sentence that actually states how A and B are related (association, difference, prediction) or that they are not",
    "polarity": "whether the source reports an association (value association), no association (none), mixed results (mixed), or does not say (not_stated)",
    "direction": "the stated direction or nature of an association (more/less, positive/negative), if the source states one",
    "population": "the sample or population the finding is reported in, if stated",
    "qualifiers": "spans that limit or condition the finding (subgroup, moderator, caveat), if stated",
    "item_named": "the asked-for item named in the span (for example a specific brain area, trait, or scale)",
    "tied_to_subject": "the span ties that item to the asked subject (it is reported as implicated in / related to it), not merely mentioned",
    "kind_named": "the asked-for kind (for example a kind of behavior or attitude) named in the span",
    "tied_to_relation": "the span ties that kind to the relation being asked about",
    "instrument_named": "the named measure, scale, task or procedure",
    "paired_with_construct": "the span states which construct or target that instrument measures or applies to",
    "manner_described": "how something was measured or done, as the source describes it",
    "population_named": "the named population, culture or sample",
    "tied_to_finding": "the span ties that population to the finding or test being asked about",
    "finding_of_type": "a reported finding of the asked type (a result the source itself reports)",
    "outcome_reported": "a reported outcome or result (an intended, proposed or hypothesized one does not count)",
    PAIRING_SLOT: "the span pairs the two required members explicitly (for example a culture with the measure used there)",
}


def slots_for(kind: str, *, pair_required: bool) -> tuple[str, ...]:
    slots = REQUIRED_SLOTS.get(kind, ())
    return slots + (PAIRING_SLOT,) if pair_required else slots


def all_slot_names(kind: str, *, pair_required: bool) -> tuple[str, ...]:
    names = list(slots_for(kind, pair_required=pair_required))
    if kind == "relationship":
        names += ["direction"]
    names += [s for s in ("population", "qualifiers") if s not in names]
    return tuple(names)


def _valid_ids(entry: dict | None, parts: dict) -> tuple[list[str], list[str]]:
    ids = [i for i in (entry or {}).get("span_ids", []) if isinstance(i, str)]
    return [i for i in ids if i in parts], [i for i in ids if i not in parts]


def _slot_state(slot: str, ids: list[str], parts: dict, attribution: dict) -> tuple[bool, str | None]:
    """(usable, reason). A slot is usable only if its spans respect the linked-vs-core, attribution and seam rules."""
    core = [i for i in ids if parts[i]["role"] != "linked_definition"]
    if slot not in LINKABLE_SLOTS and not core:
        return False, f"{slot}:only_linked_spans_supplied"
    bad = next((i for i in core if attribution.get(i) != at.OWN_ESTABLISHED), None)
    if bad is not None:
        return False, f"{slot}:attribution_{attribution.get(bad, 'unknown')}"
    used = ids if slot in LINKABLE_SLOTS else core
    if any(parts[i].get("open_left") or parts[i].get("open_right") for i in used):
        return False, f"{slot}:seam_unresolved"
    return True, None


def _relata_tied_to_relation(slot_spans: dict, parts: dict) -> list[str]:
    """Relata (A, B) must be the relation's own unit, or an establishing/referent unit within MAX_RELATUM_DISTANCE of it."""
    relation_ids = slot_spans.get("relation_stated", [])
    relation_units = {parts[i].get("unit_index") for i in relation_ids}
    untied = []
    for slot in ("relatum_a", "relatum_b"):
        ok = any(
            i in relation_ids
            or (
                parts[i]["role"] in ("establishing", "referent")
                and parts[i].get("unit_index") is not None
                and any(
                    r is not None and abs(parts[i]["unit_index"] - r) <= MAX_RELATUM_DISTANCE for r in relation_units
                )
            )
            for i in slot_spans.get(slot, [])
        )
        if not ok:
            untied.append(slot)
    return untied


def derive_status(kind: str, slots: dict, packet: dict, *, pair_required: bool = False) -> dict:
    """Derive one unit's status from the reported slots and the packet's own facts (attribution, seams, roles).

    `packet["parts"]` carry `span_id`, `role`, `unit_index`, `open_left`, `open_right`; `packet["part_attribution"]` maps a
    span_id to an attribution state. Returns {status, missing, reasons, slot_spans, invalid_span_ids, polarity}.
    """
    parts = {p["span_id"]: p for p in packet["parts"]}
    attribution = packet.get("part_attribution", {})
    polarity = (slots.get("polarity") or {}).get("value")
    required = list(slots_for(kind, pair_required=pair_required))
    if kind == "relationship" and polarity in ("association", "mixed"):
        required.append("direction")

    missing: list[str] = []
    reasons: list[str] = []
    invalid: list[str] = []
    slot_spans: dict[str, list[str]] = {}
    any_present = False
    for slot in required:
        ids, bad = _valid_ids(slots.get(slot), parts)
        invalid += bad
        slot_spans[slot] = ids
        if not ids:
            missing.append(slot)
            continue
        any_present = True
        usable, reason = _slot_state(slot, ids, parts, attribution)
        if not usable:
            missing.append(slot)
            reasons.append(reason)

    if kind == "relationship":
        if polarity not in ("association", "none", "mixed"):
            if "polarity" not in missing:
                missing.append("polarity")
            reasons.append("polarity:value_missing_not_stated_or_invalid")
        if "relation_stated" not in missing:
            for slot in _relata_tied_to_relation(slot_spans, parts):
                if slot not in missing:
                    missing.append(slot)
                reasons.append(f"{slot}:not_tied_to_the_stated_relation")

    if not missing:
        status = DIRECTLY
    elif any_present:
        status = PARTIAL
    else:
        status = NOT_ADDRESSED
    return {
        "status": status,
        "missing": missing,
        "reasons": reasons,
        "slot_spans": slot_spans,
        "invalid_span_ids": sorted(set(invalid)),
        "polarity": polarity,
    }
