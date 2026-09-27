"""Closure rules: when may ONE source-grounded finding close a frozen obligation unit?

The eligibility model reports which exact spans fill which slot; this module DERIVES the status. A unit closes
(`directly_establishes`) only if every required slot has a valid, ACCEPTED span inside one finding bundle (a core
proposition plus its verified links/context), no needed span is an unresolved-seam fragment, and the relata of a
relationship are tied to its relation stated in the same unit or a declared adjacent referent. Otherwise it is
`partially_establishes` (missing slots listed) or `not_addressed`. Two findings are NEVER summed; a linked span
(Methods definition of a measure) may supply only descriptive slots, never the finding itself.

**Clause-scoped acceptance (Cliff's correction, session 2026-09-27):** a listed span id is accepted for a slot only
via one of its OWN clauses (`attribution.derive_attribution`'s per-clause records — never the span's aggregate
`state`, which can blur a factual clause and a speculative one together). A descriptive slot (naming something)
accepts any clause that is `own_established`, or `methods_own` where `(kind, slot)` is in `METHODS_ELIGIBLE`. A
RELATION-BEARING slot (`relation_stated`/`polarity` for `relationship`, `outcome_reported`/`finding_of_type` for
`existence`) additionally requires that SAME clause to state a result/relation itself — a clean clause that never
asserts a result cannot validate a relationship stated only in a different, speculative clause of the same span.
Every acceptance decision records exactly which clause (offsets + text) did the work; every exclusion records why.

**`on_topic` (Cliff's correction, session 2026-09-26/27):** a universal, required slot, gated separately from
attribution — its job is topical relevance, not epistemic status, so any valid span (a core proposition part or an
attached `study_context` part; never a `linked_definition`) satisfies it once the model affirmatively lists it.
Missing `on_topic` caps a unit at `not_addressed` regardless of what else is filled.

**Cross-unit `pairing_expressed` (Cliff's correction, session 2026-09-27):** for a `#pair` child's two paired
units, `pairing_expressed` may be derived — in addition to whatever the model itself reports — only when ONE
proposition genuinely connects both paired things: the SAME clause is the accepted evidence for both units' primary
slots, or an existing VERIFIED link (`links.py`) connects the two accepted spans. A shared span id alone, filled via
two different clauses, is never sufficient.

**Affirmative-link requirement (Cliff's second correction, same session):** same-clause identity is necessary but
not sufficient — a clause can co-occur two candidate relata while explicitly stating that only ONE of them (or
neither) underwent the measurement. `derive_pairing_bonus` withholds the same-clause derivation, and records why,
whenever the shared clause contains a negation or exclusion marker (`_PAIRING_AMBIGUITY_MARKERS`: "only",
"except", "but not", "unlike", "rather than", "instead of", "not", "never", "neither/nor", "fail(ed/s) to", "no
longer", "without") — a deliberately narrow, closed marker list, not a semantic parser. A clause naming more than
one candidate with NO such marker (a genuine joint-subject design, e.g. "Both X and Y completed the same task")
is not blocked by this rule alone — the guard targets the specific failure Cliff named (negation / exclusion / a
different acting population / ambiguous agency), not every multi-population sentence. `derive_pairing_bonus`
always returns an auditable `{"outcome": "derived" | "withheld", "reason": ...}` record, never a bare `None` —
nothing about a withheld pairing is silent. A withheld pairing leaves `pairing_expressed` in the unit's `missing`
list exactly as an unreported one would, so it remains reachable by the EXISTING targeted recovery trigger
(`recovery.py`'s `widen_neighborhood` step, keyed on `partial_slot:pairing_expressed`) — no new recovery mechanism
was needed for this.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.contract_directed import attribution as at

# Deliberately narrow, closed marker list (Cliff's correction, session 2026-09-27): negation and exclusion cues
# that make same-clause co-occurrence unsafe to treat as an affirmative pairing. Not a semantic parser — a clause
# with none of these is not thereby proven to pair correctly, but one WITH one of these is conservatively withheld.
_PAIRING_AMBIGUITY_MARKERS = re.compile(
    r"\b(?:only|except(?:\s+for)?|but\s+not|unlike|rather\s+than|instead\s+of|"
    r"not|never|neither|nor|fail(?:ed|s)?\s+to|no\s+longer|without)\b",
    re.IGNORECASE,
)

DIRECTLY = "directly_establishes"
PARTIAL = "partially_establishes"
NOT_ADDRESSED = "not_addressed"
POLARITY_VALUES = ("association", "none", "mixed", "not_stated")
MAX_RELATUM_DISTANCE = 2  # units between a relatum and the relation unit when they are not the same unit

TOPIC_SLOT = "on_topic"
PAIRING_SLOT = "pairing_expressed"

# Required slots per frozen unit kind (direction is added when polarity is association/mixed; on_topic and pairing
# are appended universally/conditionally by `slots_for`, never listed here to keep exactly one place that does it).
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

# Slots a verified LINK (a definition elsewhere in the same study) may supply. Everything else must come from the
# core proposition. `on_topic` is deliberately never linkable — see TOPIC_SLOT handling in `_slot_state`.
LINKABLE_SLOTS = frozenset({"instrument_named", "manner_described", "population_named"})

# A Methods description ("The IRI assessed empathic concern") is legitimate first-hand evidence of what a study
# measured, but it must never become a finding or an outcome. Exactly these (kind, slot) pairs accept `methods_own`.
METHODS_ELIGIBLE: frozenset[tuple[str, str]] = frozenset(
    {
        ("operation", "instrument_named"),
        ("operation", "paired_with_construct"),
        ("manner", "manner_described"),
        ("manner", "tied_to_subject"),
        ("requested_item", "item_named"),
        ("requested_item", "tied_to_subject"),
    }
)

# A relationship or outcome may only be validated by the clause that actually states it — never a clean clause
# that says nothing about a result, co-listed alongside a speculative one that does.
RELATION_BEARING_SLOTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("relationship", "relation_stated"),
        ("relationship", "polarity"),
        ("existence", "outcome_reported"),
        ("existence", "finding_of_type"),
    }
)

# The slot that carries "the thing itself" for a kind — used only to locate the evidence a #pair derivation may
# connect; never used to relax what that slot itself requires.
PRIMARY_SLOT: dict[str, str] = {
    "population": "population_named",
    "manner": "manner_described",
    "operation": "instrument_named",
    "requested_item": "item_named",
}

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
    TOPIC_SLOT: (
        "the span(s) that show this finding is actually about what THIS item asks for and the question's own "
        "stated subject or context — not a same-shaped or same-topic finding about something else the question "
        "does not ask about. A span from the paper's own abstract, shown separately as study context, may also be "
        "used here if it establishes the connection; a paper's title or general topic alone does not."
    ),
}


def slots_for(kind: str, *, pair_required: bool) -> tuple[str, ...]:
    slots = REQUIRED_SLOTS.get(kind, ()) + (TOPIC_SLOT,)
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


def _accepted_clause(part: dict, *, kind: str, slot: str, attribution_full: dict) -> dict | None:
    """The FIRST clause of `part`'s own attribution that legitimately supports `(kind, slot)`, or None.

    Never the span's aggregate state — a clean, unrelated clause cannot rescue a slot whose actual content sits in
    a different clause of the same span.
    """
    clauses = attribution_full.get(part["span_id"], {}).get("clauses", [])
    relation_bearing = (kind, slot) in RELATION_BEARING_SLOTS
    for clause in clauses:
        acceptable = clause["state"] == at.OWN_ESTABLISHED or (
            clause["state"] == at.METHODS_OWN and (kind, slot) in METHODS_ELIGIBLE
        )
        if not acceptable:
            continue
        if relation_bearing and not clause["has_result_predicate"]:
            continue
        return clause
    return None


def _slot_state(
    slot: str, ids: list[str], parts: dict, attribution_full: dict, *, kind: str
) -> tuple[bool, str | None, dict | None, list[str], list[str]]:
    """(usable, reason, accepted{span_id,start,end,text,state}, excluded_span_ids, exclusion_reasons)."""
    if slot == TOPIC_SLOT:
        eligible = [i for i in ids if parts[i]["role"] in ("establishing", "qualifying", "referent", "study_context")]
        if not eligible:
            return False, f"{slot}:no_on_topic_span_offered", None, [], []
        usable = [i for i in eligible if not (parts[i].get("open_left") or parts[i].get("open_right"))]
        if not usable:
            return False, f"{slot}:seam_unresolved", None, eligible, [f"{i}:seam_unresolved" for i in eligible]
        chosen = usable[0]
        return True, None, {"span_id": chosen, "start": None, "end": None, "text": None, "state": None}, [], []

    core = [i for i in ids if parts[i]["role"] != "linked_definition"]
    if slot not in LINKABLE_SLOTS and not core:
        return False, f"{slot}:only_linked_spans_supplied", None, [], []
    used = ids if slot in LINKABLE_SLOTS else core
    excluded: list[str] = []
    reasons: list[str] = []
    for i in used:
        if parts[i].get("open_left") or parts[i].get("open_right"):
            excluded.append(i)
            reasons.append(f"{slot}:seam_unresolved")
            continue
        if parts[i]["role"] == "linked_definition":
            # A verified link (packet.py attaches only VERIFIED ones) is trustworthy by construction; it needs no
            # attribution of its own — only core spans carry that requirement (unchanged from the original design).
            return (
                True,
                None,
                {"span_id": i, "start": None, "end": None, "text": parts[i]["text"], "state": None},
                excluded,
                reasons,
            )
        clause = _accepted_clause(parts[i], kind=kind, slot=slot, attribution_full=attribution_full)
        if clause is None:
            excluded.append(i)
            worst = attribution_full.get(i, {}).get("state", "unresolved")
            tag = (
                "no_relation_bearing_accepted_clause"
                if (kind, slot) in RELATION_BEARING_SLOTS
                else f"attribution_{worst}"
            )
            reasons.append(f"{slot}:{tag}")
            continue
        accepted = {
            "span_id": i,
            "start": clause["start"],
            "end": clause["end"],
            "text": clause["text"],
            "state": clause["state"],
        }
        return True, None, accepted, excluded, reasons
    return False, (reasons[-1] if reasons else f"{slot}:no_usable_span"), None, excluded, reasons


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


def _finalize(missing: list[str], any_present: bool) -> str:
    if TOPIC_SLOT in missing:
        return NOT_ADDRESSED
    if not missing:
        return DIRECTLY
    if any_present:
        return PARTIAL
    return NOT_ADDRESSED


def derive_status(kind: str, slots: dict, packet: dict, *, pair_required: bool = False) -> dict:
    """Derive one unit's status from the reported slots and the packet's own facts (attribution, seams, roles).

    `packet["parts"]` carry `span_id`, `role`, `unit_index`, `open_left`, `open_right`; `packet["attribution"]` maps
    a span_id to its full `derive_attribution` record (read for `.clauses`, never for the aggregate `state`).
    Returns {status, missing, reasons, slot_spans, invalid_span_ids, polarity, excluded_span_ids, exclusion_reasons,
    accepted_evidence, primary_slot_evidence}.
    """
    parts = {p["span_id"]: p for p in packet["parts"]}
    attribution_full = packet.get("attribution", {})
    polarity = (slots.get("polarity") or {}).get("value")
    required = list(slots_for(kind, pair_required=pair_required))
    if kind == "relationship" and polarity in ("association", "mixed"):
        required.append("direction")

    missing: list[str] = []
    reasons: list[str] = []
    invalid: list[str] = []
    slot_spans: dict[str, list[str]] = {}
    accepted_evidence: dict[str, dict] = {}
    excluded_by_slot: dict[str, list[str]] = {}
    exclusion_reasons_by_slot: dict[str, list[str]] = {}
    any_present = False
    for slot in required:
        ids, bad = _valid_ids(slots.get(slot), parts)
        invalid += bad
        slot_spans[slot] = ids
        if not ids:
            missing.append(slot)
            continue
        any_present = True
        usable, reason, accepted, excluded, ex_reasons = _slot_state(slot, ids, parts, attribution_full, kind=kind)
        excluded_by_slot[slot] = excluded
        exclusion_reasons_by_slot[slot] = ex_reasons
        if not usable:
            missing.append(slot)
            if reason:
                reasons.append(reason)
        else:
            accepted_evidence[slot] = accepted

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

    primary_slot = PRIMARY_SLOT.get(kind)
    primary_slot_evidence = accepted_evidence.get(primary_slot) if primary_slot else None

    return {
        "status": _finalize(missing, any_present),
        "missing": missing,
        "reasons": reasons,
        "slot_spans": slot_spans,
        "invalid_span_ids": sorted(set(invalid)),
        "polarity": polarity,
        "excluded_span_ids": excluded_by_slot,
        "exclusion_reasons": exclusion_reasons_by_slot,
        "accepted_evidence": accepted_evidence,
        "primary_slot_evidence": primary_slot_evidence,
    }


# ---- cross-unit `pairing_expressed` derivation for #pair children (Cliff's correction, 2026-09-27) ------------------


def pair_partners(child) -> dict[str, str]:
    """{unit_id: partner_unit_id} for a #pair child whose exactly two content units are each other's pair partner.

    Empty for a non-#pair child, or one whose content-unit count isn't exactly two — no pairing is assumed rather
    than guessed.
    """
    if not child.pair_requirement_ids:
        return {}
    units = child.content_units
    if len(units) != 2:
        return {}
    a, b = units
    return {a.unit_id: b.unit_id, b.unit_id: a.unit_id}


def _linked_connection(packet: dict, id_a: str, id_b: str) -> bool:
    """Whether id_a/id_b are connected via an EXISTING verified link (links.py) between a core proposition and a
    linked definition elsewhere in the same study. Bare co-occurrence in the same packet is never sufficient."""
    parts = {p["span_id"]: p for p in packet["parts"]}
    part_a, part_b = parts.get(id_a), parts.get(id_b)
    if part_a is None or part_b is None:
        return False
    if part_a["role"] == "linked_definition" and part_b["role"] != "linked_definition":
        linked = part_a
    elif part_b["role"] == "linked_definition" and part_a["role"] != "linked_definition":
        linked = part_b
    else:
        return False
    link_id = linked.get("linked_from")
    return any(lk.get("link_id") == link_id and lk.get("verified") for lk in packet.get("links", []))


def derive_pairing_bonus(kind_a: str, result_a: dict, kind_b: str, result_b: dict, packet: dict) -> dict:
    """A connecting proposition for `pairing_expressed` — ALWAYS an auditable record, never a bare success/failure:
    `{"outcome": "derived", "source": ..., "span_id"/"span_id_a"+"span_id_b": ..., "start"/"end"/"text": ...}` or
    `{"outcome": "withheld", "reason": ..., ...}`. Nothing about a withheld pairing is silent.

    Requires either (a) the SAME clause is the accepted evidence for both units' primary slots AND that clause
    contains no negation/exclusion marker (`_PAIRING_AMBIGUITY_MARKERS` — Cliff's affirmative-link correction: a
    clause can co-occur two candidate relata while stating that only one of them, or neither, underwent the
    measurement; matching offsets alone never overrides that), or (b) an existing verified link connects the two
    accepted spans. A shared span id filled via two DIFFERENT clauses of the same sentence — e.g. an unrelated
    population mention and an unrelated measurement description that happen to share a sentence — is not enough
    either way.
    """
    ev_a, ev_b = result_a.get("primary_slot_evidence"), result_b.get("primary_slot_evidence")
    if not ev_a or not ev_b:
        return {"outcome": "withheld", "reason": "no_primary_evidence_for_one_or_both_paired_units"}
    same_clause = (
        ev_a["span_id"] == ev_b["span_id"]
        and ev_a["start"] is not None
        and ev_a["start"] == ev_b["start"]
        and ev_a["end"] == ev_b["end"]
    )
    if same_clause:
        marker = _PAIRING_AMBIGUITY_MARKERS.search(ev_a["text"])
        if marker:
            return {
                "outcome": "withheld",
                "reason": "same_clause_contains_a_negation_or_exclusion_marker",
                "blocking_marker": marker.group(0),
                "span_id": ev_a["span_id"],
                "start": ev_a["start"],
                "end": ev_a["end"],
                "text": ev_a["text"],
            }
        return {
            "outcome": "derived",
            "source": "same_clause",
            "span_id": ev_a["span_id"],
            "start": ev_a["start"],
            "end": ev_a["end"],
            "text": ev_a["text"],
        }
    if _linked_connection(packet, ev_a["span_id"], ev_b["span_id"]):
        return {
            "outcome": "derived",
            "source": "verified_link",
            "span_id_a": ev_a["span_id"],
            "span_id_b": ev_b["span_id"],
        }
    return {"outcome": "withheld", "reason": "no_connecting_proposition_found"}


def apply_pairing_bonus(result: dict, bonus: dict) -> dict:
    """Fold a DERIVED `derive_pairing_bonus` record into a unit's `derive_status` output, recomputing `status`.
    Never call this with a `"withheld"` record — check `bonus["outcome"] == "derived"` first; the caller is
    expected to record a withheld attempt itself (see `model_stages.judge_packet`), since there is nothing here
    to fold in."""
    if PAIRING_SLOT not in result["missing"]:
        return result
    missing = [s for s in result["missing"] if s != PAIRING_SLOT]
    slot_spans = dict(result["slot_spans"])
    ids = [bonus["span_id"]] if "span_id" in bonus else [bonus["span_id_a"], bonus["span_id_b"]]
    slot_spans[PAIRING_SLOT] = sorted(set(slot_spans.get(PAIRING_SLOT, [])) | set(ids))
    accepted_evidence = dict(result["accepted_evidence"])
    accepted_evidence[PAIRING_SLOT] = {**bonus, "derived": True}
    return {
        **result,
        "status": _finalize(missing, any_present=True),
        "missing": missing,
        "slot_spans": slot_spans,
        "accepted_evidence": accepted_evidence,
        "reasons": result["reasons"] + [f"{PAIRING_SLOT}:derived_from_pair_partner:{bonus['source']}"],
    }
