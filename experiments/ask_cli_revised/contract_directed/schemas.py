"""Structured-output schemas and validators for the three judgment stages (triage, localization, eligibility).

Every growing field carries a `maxLength`/`maxItems` and `worst_case_output_chars` recomputes the largest output a schema can
permit, so a loosened bound cannot silently truncate generation (the repo's standing rule for generation ceilings). The model
returns IDS and short labels only: sentence-unit ids, span ids, enums. It never writes a quote, a claim or a locator; code
resolves ids to exact source text. A validator drops what is invalid and RECORDS it; it never repairs, guesses or retries.
"""

from __future__ import annotations

from app.backend.pdf_processing.extraction import canonical_text_contains
from experiments.ask_cli_revised.contract_directed import closure
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract

CONTRIBUTION_TYPES = (
    "original_empirical",
    "review_or_meta_analysis",
    "theory_or_commentary",
    "methods_or_instrument",
    "undeterminable",
)
RELATIONS = ("directly_addresses", "possibly_addresses", "topical_only", "not_relevant", "cannot_tell")
PROVENANCE_CLASSES = (
    "this_study_reports", "review_own_synthesis", "recounts_other_study", "background_generic",
    "hypothesis_or_speculation", "methods", "null_result", "cannot_tell",
)  # fmt: skip
POLARITIES = ("association", "none", "mixed", "not_stated", "not_a_relation")
MAX_PROPOSITIONS = 3
MAX_IDS = 6
QUOTE_MAX = 600
REASON_MAX = 200
PHRASE_MAX = 120
NOTE_MAX = 160
NOTES_MAX = 3
CHARS_PER_TOKEN = 3.0


def triage_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "contribution_type": {"type": "string", "enum": list(CONTRIBUTION_TYPES)},
            "relation_to_child": {"type": "string", "enum": list(RELATIONS)},
            "abstract_quote": {"type": "string", "maxLength": QUOTE_MAX},
            "reason": {"type": "string", "maxLength": REASON_MAX},
        },
        "required": ["contribution_type", "relation_to_child", "abstract_quote", "reason"],
        "additionalProperties": False,
    }


def _id_array(ids: list[str], *, min_items: int = 0) -> dict:
    return {"type": "array", "items": {"type": "string", "enum": list(ids)}, "minItems": min_items, "maxItems": MAX_IDS}


def localization_schema(unit_ids: list[str]) -> dict:
    proposition = {
        "type": "object",
        "properties": {
            "establishing": _id_array(unit_ids, min_items=1),
            "qualifying": _id_array(unit_ids),
            "referents": _id_array(unit_ids),
            "provenance_class": {"type": "string", "enum": list(PROVENANCE_CLASSES)},
            "attribution_basis_phrase": {"type": "string", "maxLength": PHRASE_MAX},
            "relation_polarity": {"type": "string", "enum": list(POLARITIES)},
            "unresolved": {"type": "array", "items": {"type": "string", "maxLength": NOTE_MAX}, "maxItems": NOTES_MAX},
        },
        "required": [
            "establishing",
            "qualifying",
            "referents",
            "provenance_class",
            "attribution_basis_phrase",
            "relation_polarity",
            "unresolved",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "propositions": {"type": "array", "items": proposition, "maxItems": MAX_PROPOSITIONS},
            "none_established": {"type": "boolean"},
        },
        "required": ["propositions", "none_established"],
        "additionalProperties": False,
    }


def eligibility_schema(child: ChildContract, span_ids: list[str]) -> dict:
    pair = bool(child.pair_requirement_ids)
    unit_props = {}
    for unit in child.content_units:
        slot_props = {}
        for slot in closure.all_slot_names(unit.kind, pair_required=pair):
            entry = {"span_ids": _id_array(span_ids)}
            required = ["span_ids"]
            if slot == "polarity":
                entry_props = {
                    "span_ids": entry["span_ids"],
                    "value": {"type": "string", "enum": list(closure.POLARITY_VALUES)},
                }
                slot_props[slot] = {
                    "type": "object",
                    "properties": entry_props,
                    "required": ["span_ids", "value"],
                    "additionalProperties": False,
                }
            else:
                slot_props[slot] = {
                    "type": "object",
                    "properties": {"span_ids": entry["span_ids"]},
                    "required": required,
                    "additionalProperties": False,
                }
        unit_props[unit.unit_id] = {
            "type": "object",
            "properties": {
                "slots": {
                    "type": "object",
                    "properties": slot_props,
                    "required": list(slot_props),
                    "additionalProperties": False,
                },
                "reason": {"type": "string", "maxLength": REASON_MAX},
            },
            "required": ["slots", "reason"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "units": {
                "type": "object",
                "properties": unit_props,
                "required": list(unit_props),
                "additionalProperties": False,
            }
        },
        "required": ["units"],
        "additionalProperties": False,
    }


def worst_case_output_chars(schema: dict, *, id_chars: int = 6) -> int:
    """Upper bound on the characters a schema-valid answer can contain (keys, punctuation and enum strings counted)."""
    kind = schema.get("type")
    if kind == "string":
        if "enum" in schema:
            return max(len(v) for v in schema["enum"]) + 2
        return schema.get("maxLength", 10**6) + 2
    if kind == "boolean":
        return 5
    if kind == "array":
        item = worst_case_output_chars(schema["items"], id_chars=id_chars)
        return schema.get("maxItems", 10**4) * (item + 1) + 2
    if kind == "object":
        total = 2
        for key, sub in schema["properties"].items():
            total += len(key) + 4 + worst_case_output_chars(sub, id_chars=id_chars)
        return total
    return 16


# ---- validators: drop what is invalid and record it; never repair, guess or retry ------------------------------------------


def validate_triage(answer: dict, abstract_clean: str) -> dict:
    quote = (answer.get("abstract_quote") or "").strip()
    verbatim = bool(quote) and canonical_text_contains(needle=quote, haystack=abstract_clean)
    return {
        "contribution_type": answer["contribution_type"],
        "relation_to_child": answer["relation_to_child"],
        "abstract_quote": quote,
        "quote_verbatim": verbatim if quote else None,
        "reason": (answer.get("reason") or "").strip(),
    }


def validate_localization(answer: dict, unit_ids: list[str]) -> dict:
    valid_ids = set(unit_ids)
    kept, invalid = [], []
    for raw in answer.get("propositions", []):
        est = [u for u in dict.fromkeys(raw.get("establishing", [])) if u in valid_ids]
        bad = [
            u
            for ids in (raw.get("establishing", []), raw.get("qualifying", []), raw.get("referents", []))
            for u in ids
            if u not in valid_ids
        ]
        if bad:
            invalid.append({"unit_ids": sorted(set(bad)), "reason": "unit_id_not_in_neighborhood"})
        if not est:
            invalid.append({"proposition": "dropped", "reason": "no_valid_establishing_unit"})
            continue
        kept.append(
            {
                "establishing": est,
                "qualifying": [u for u in dict.fromkeys(raw.get("qualifying", [])) if u in valid_ids and u not in est],
                "referents": [u for u in dict.fromkeys(raw.get("referents", [])) if u in valid_ids and u not in est],
                "provenance_class": raw.get("provenance_class"),
                "attribution_basis_phrase": (raw.get("attribution_basis_phrase") or "").strip() or None,
                "relation_polarity": raw.get("relation_polarity"),
                "unresolved": [n.strip() for n in raw.get("unresolved", []) if n.strip()][:NOTES_MAX],
            }
        )
    state = "usable" if kept else ("none_established" if answer.get("none_established") else "unresolved_preserved")
    return {
        "state": state,
        "propositions": kept,
        "invalid": invalid,
        "none_established_claimed": bool(answer.get("none_established")),
    }
