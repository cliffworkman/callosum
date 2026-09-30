"""Evidence-bound requirement mapping: deterministic-first, with an explicitly-unbound
model-nomination scaffold. Dispatches ONLY on a role's declared ``RoleSpec.mapping_strategy``
(``sufficiency_engine.MAPPING_STRATEGIES``) -- never by inspecting a role's own label string.

Discovery/admissibility discipline (the corrections from review):

* No global Overview-eligibility filter and no global hedge/absence/study-description exclusion.
  The only blanket gate is that the underlying proposition is itself verified (the caller's own
  responsibility -- this module only ever sees units built from ``verified_propositions``).
  Guard flags are evidence metadata, gated PER ROLE via ``RoleSpec.disqualifying_guards``.
* A role whose declared strategy is ``model_nomination_only`` has no deterministic detector by
  design -- it stays ``missing``/``not_found`` unless a (currently unbound) model nominates a
  candidate. This is a disclosed limitation, never papered over with a guessed heuristic.
* Every candidate -- deterministic or model-sourced -- passes the SAME acceptance gate:
  ``canonical_text_contains`` on the literal text, then the engine's own role-completion,
  admissibility, relational-verifier, and quantifier checks (``sufficiency_engine.py``).

No external scholarly method is implemented here (see CREDIT-THE-LINEAGE.md) -- this reuses
this codebase's own existing deterministic lexical detectors (``overview_evidence.py``,
``contract_directed/attribution.py``), unmodified, dispatched by a new declared-strategy layer.
"""

from __future__ import annotations

import re

from app.backend.pdf_processing.extraction import canonical_text_contains
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised.contract_directed import attribution as attr

_WORD_TOKEN = re.compile(r"[A-Za-z][A-Za-z']*")


# ---------------------------------------------------------------------------------------------
# Per-role admissibility (§ requirement-specific evidence eligibility)
# ---------------------------------------------------------------------------------------------


def is_admissible(role_spec: dict, guard: dict) -> bool:
    """Guard flags are evidence metadata, gated per role -- never a universal filter. A role
    with an empty `disqualifying_guards` list (the default for a named-entity role: a scale,
    region, culture, or intervention's own name) is admissible from a Methods/study-description/
    hedged passage, because a Methods sentence is exactly where such a thing is named."""
    return not any(guard.get(flag) for flag in role_spec["disqualifying_guards"])


# Shape-keyed defaults a contract MAY use when authoring RoleSpecs (Layer B's own call, not
# something this module enforces) -- named-entity identification roles are typically
# unrestricted; achieved-outcome/direction roles typically exclude hedged (speculative) language
# but NOT an explicit, unhedged null-result statement, which is itself valid evidence.
NAMED_ENTITY_DEFAULT_GUARDS: tuple[str, ...] = ()
ACHIEVED_OUTCOME_DEFAULT_GUARDS: tuple[str, ...] = ("hedged",)


# ---------------------------------------------------------------------------------------------
# Deterministic-first detectors, one per MAPPING_STRATEGIES value -- reusable across any future
# question's role of the same shape, dispatched only by strategy name.
# ---------------------------------------------------------------------------------------------


def _match_instrument(text: str) -> str | None:
    """Reuses `attribution.INSTRUMENT_DESCRIBES`/`dehyphenate_for_matching` unmodified. Tries the
    original text first (so the returned span is always a literal substring of it); the
    dehyphenated variant is tried only as a fallback, and only accepted if its match text is
    ALSO literally present in the original (never a paraphrase across a line-wrap hyphen)."""
    match = attr.INSTRUMENT_DESCRIBES.search(text)
    if match:
        return match.group(0)
    cleaned = attr.dehyphenate_for_matching(text)
    if cleaned != text:
        match = attr.INSTRUMENT_DESCRIBES.search(cleaned)
        if match and canonical_text_contains(needle=match.group(0), haystack=text):
            return match.group(0)
    return None


def _match_achieved_outcome(text: str) -> str | None:
    """Reuses `attribution.has_result_predicate` unmodified. Returns the whole passage as the
    supporting text -- a stated result is a property of the passage as a whole, not one token."""
    return text if attr.has_result_predicate(text) else None


def _match_explicit_category_term(text: str, requested_terms: list[str]) -> str | None:
    """The contract's OWN literal, wording-derived category terms -- never a hidden list. Case-
    insensitive containment; returns the literal substring as it appears in `text`."""
    lowered = text.lower()
    for term in requested_terms:
        idx = lowered.find(term.lower())
        if idx != -1:
            return text[idx : idx + len(term)]
    return None


_POS_WORD = re.compile(r"\bpositive\b", re.IGNORECASE)
_NEG_WORD = re.compile(r"\bnegative\b", re.IGNORECASE)


def _match_direction_word(text: str) -> str | None:
    """Reuses `overview_evidence.stem`/`DIRECTION_STEMS` (a comparative/valence word list already
    used elsewhere in this codebase) -- independent of causal language entirely. Returns the
    first literal token (original casing) whose stem is direction-bearing."""
    for match in _WORD_TOKEN.finditer(text):
        token = match.group(0)
        if oe.stem(token) in oe.DIRECTION_STEMS:
            return token
    return None


def _direction_sign(word: str) -> str | None:
    """Only the literal, unambiguous valence words get a `sign` -- a bare magnitude word
    ("increased", "reduced") is genuinely ambiguous about which direction is "positive" without
    knowing what the measure represents, so it is reported (`reported=True`) without a
    fabricated sign rather than guessed."""
    if _POS_WORD.fullmatch(word):
        return "positive"
    if _NEG_WORD.fullmatch(word):
        return "negative"
    return None


_STRATEGY_DETECTORS = {
    "named_instrument_lexicon": _match_instrument,
    "achieved_outcome_predicate": _match_achieved_outcome,
    # "explicit_category_terms" and "direction_or_sign_pattern" need extra args -- handled inline
    # in `_deterministic_text_for_role` below, not through this simple one-arg registry.
}


def _deterministic_text_for_role(role_spec: dict, passage: str) -> str | None:
    strategy = role_spec["mapping_strategy"]
    if strategy == "explicit_category_terms":
        return _match_explicit_category_term(passage, role_spec["requested_category_terms"])
    if strategy == "direction_or_sign_pattern":
        return _match_direction_word(passage)
    detector = _STRATEGY_DETECTORS.get(strategy)
    return detector(passage) if detector else None  # model_nomination_only: no detector, by design


# ---------------------------------------------------------------------------------------------
# Model-nomination scaffold -- explicitly unbound. Present for provenance/type completeness and
# future wiring only; calling it is a programming error, never a silent no-op.
# ---------------------------------------------------------------------------------------------

MODEL_NOMINATION_PROMPT_TEMPLATE = (
    "Does this passage name a specific instance of {category_description}, as opposed to a "
    "generic/unspecified reference to {category_description}? If yes, return the exact "
    "supporting substring and the passage id. If no, say so plainly."
)


def nominate_with_model(role_spec: dict, candidate_units: list[dict], model_client) -> list[dict]:
    """UNBOUND. Would return a list of `{proposition_id, exact_text, proposed_role}`
    nominations -- never a verdict; the engine (`sufficiency_engine.recompute_requirement`)
    independently grounds every nomination before it can reach `filled`. Turning this on is a
    separate, later, explicitly-authorized experiment (no model call happens in this codebase
    path today)."""
    raise NotImplementedError(
        "Model-assisted nomination is scaffolded but intentionally left unbound. "
        "No live model call is authorized for this path."
    )


# ---------------------------------------------------------------------------------------------
# Discovery + per-requirement mapping orchestration
# ---------------------------------------------------------------------------------------------


def _best_unit(units: list[dict]) -> dict | None:
    return units[0] if units else None


def _bind_role_from_units(role_spec: dict, units: list[dict]) -> dict:
    role = role_spec["role"]
    for unit in units:
        if not is_admissible(role_spec, unit.get("flags", {})):
            continue
        exact_text = _deterministic_text_for_role(role_spec, unit["passage"])
        if exact_text is None:
            continue
        if not canonical_text_contains(needle=exact_text, haystack=unit["passage"]):
            continue  # belt-and-suspenders: the literal-text gate is absolute, regardless of source
        proposition_id = unit["proposition_ids"][0] if unit.get("proposition_ids") else None
        return se.new_role_binding(
            role,
            state="filled",
            proposition_id=proposition_id,
            exact_text=exact_text,
            provenance={
                "candidate_source": "deterministic_mapping",
                "detail": role_spec["mapping_strategy"],
                "model": None,
            },
            guard=unit.get("flags", {}),
        )
    return se.new_role_binding(role, state="missing", reason="not_found")


def build_multi_instances(candidate_units: list[dict]) -> list[dict]:
    """One candidate instance per distinct candidate UNIT (a deduplicated source passage).

    This is the honest deterministic-only discovery granularity: when an identifying role's own
    `mapping_strategy` is `model_nomination_only` (no closed lexical class for a named culture,
    trait, intervention, ...), no named instance-key can be extracted without a model. Each unit
    becomes its own provisional instance, keyed by its own unit id -- legible in a report
    ("instance U5"), never presented as a real named entity. A future model-assisted pass can
    replace `instance_key` with the entity name it nominates, once bound.
    """
    return [se.new_instance(unit["unit_id"]) for unit in candidate_units]


def map_requirement(
    requirement: dict,
    candidate_units: list[dict],
    *,
    parent_context_bindings: dict | None = None,
) -> dict:
    """Deterministic-only mapping for one requirement. `candidate_units` are already filtered by
    the caller to units attached to this requirement's own child (never another child's, never
    a hidden benchmark list). `parent_context_bindings`: optional `{role: RoleBinding}` for roles
    declared in `parent_context_roles`, pre-seeded from a parent's own completed instance -- this
    can supply candidate CONTEXT but role-completion still requires the requirement's OTHER
    role(s) to come from this child's own evidence (parent inheritance is context, not proof).

    Returns a NEW requirement dict with `instances` populated and `state`/`reason` recomputed.
    """
    role_specs = requirement["role_specs"]
    parent_context_bindings = parent_context_bindings or {}

    if requirement["multi_instance"]:
        instances = build_multi_instances(candidate_units)
        units_by_instance = {inst["instance_key"]: [u] for inst, u in zip(instances, candidate_units)}
    else:
        instances = [se.new_instance()]
        units_by_instance = {None: candidate_units}

    for instance in instances:
        units_here = units_by_instance.get(instance["instance_key"], candidate_units)
        for role, spec in role_specs.items():
            # Own evidence first, parent context only as a FALLBACK when this child's own
            # evidence doesn't independently fill the role -- "parent inheritance is context,
            # not proof" means the child may still establish its own instance from its own
            # retrieval even when a parent has already identified something (e.g. c5 finding its
            # own region mention independently of c4's), not that the parent's identity always
            # wins once offered.
            own_binding = _bind_role_from_units(spec, units_here)
            if own_binding["state"] == "filled" or role not in parent_context_bindings:
                instance["role_bindings"][role] = own_binding
            else:
                instance["role_bindings"][role] = parent_context_bindings[role]

    new_requirement = {**requirement, "instances": instances}
    return se.recompute_requirement(new_requirement)


def map_cardinality_requirement(requirement: dict, candidate_units: list[dict]) -> dict:
    """Specialization for `all_requested_categories`: one instance per named category (from the
    role's own `requested_category_terms` -- the contract's own wording-derived terms, never a
    hidden list), each checked against that SPECIFIC literal term -- never "any category
    satisfies any instance". Exactly one category-evidence role is expected."""
    role_names = list(requirement["role_specs"])
    if len(role_names) != 1:
        raise ValueError("a cardinality requirement expects exactly one category-evidence role")
    role = role_names[0]
    spec = requirement["role_specs"][role]
    instances = []
    for term in spec["requested_category_terms"]:
        instance = se.new_instance(term)
        term_spec = {**spec, "requested_category_terms": [term]}
        instance["role_bindings"][role] = _bind_role_from_units(term_spec, candidate_units)
        instances.append(instance)
    new_requirement = {**requirement, "instances": instances}
    return se.recompute_requirement(new_requirement)


def map_paired_requirement(requirement: dict, parent_requirement: dict, candidate_units: list[dict]) -> dict:
    """For a `for_each_discovered_instance` requirement whose identifying role is declared in
    `parent_context_roles` (paired against a PARENT requirement's own discovered instances --
    e.g. a scale-per-trait pairing scoped to exactly the traits a parent has *currently*
    discovered, never "all conceivable traits"): one instance per parent instance whose own
    parent-context role is filled. Parent inheritance is CONTEXT, not proof -- the paired
    role(s) must still come from this requirement's own candidate units."""
    parent_role = requirement["parent_context_roles"][0]
    other_roles = [r for r in requirement["role_specs"] if r != parent_role]
    instances = []
    for parent_instance in parent_requirement["instances"]:
        parent_binding = parent_instance["role_bindings"].get(parent_role)
        if not parent_binding or parent_binding.get("state") != "filled":
            continue  # nothing to pair against yet -- not yet discovered by the parent
        instance = se.new_instance(parent_instance["instance_key"])
        # Re-stamped, never passed through verbatim: from THIS requirement's own perspective the
        # role is parent-context, regardless of how the parent itself originally established it
        # (deterministically, or via a future model nomination) -- this is what exempts it from
        # the joint-grounding check below (a parent-context role can never share a proposition
        # with anything this child retrieves, by construction) while still recording, for full
        # transparency, exactly how the parent arrived at it.
        instance["role_bindings"][parent_role] = {
            **parent_binding,
            "provenance": {
                "candidate_source": "parent_context",
                "detail": f"from parent {parent_requirement['id']!r}: {parent_binding.get('provenance', {}).get('candidate_source')}",
                "model": parent_binding.get("provenance", {}).get("model"),
            },
        }
        for role in other_roles:
            instance["role_bindings"][role] = _bind_role_from_units(requirement["role_specs"][role], candidate_units)
        instances.append(instance)
    new_requirement = {**requirement, "instances": instances}
    return se.recompute_requirement(new_requirement)


def _parent_context_binding_for_single_instance(requirement: dict, parent_requirement: dict) -> dict:
    """For a requirement that is NOT `for_each_discovered_instance` (a single instance overall,
    e.g. c5/c6's own relational pairing with a region inherited from c4): the parent's own
    (also single, non-multi-instance) role binding, re-stamped `parent_context`, offered as a
    FALLBACK candidate only -- `map_requirement` tries this child's own evidence first."""
    if parent_requirement is None or parent_requirement.get("multi_instance") or not parent_requirement["instances"]:
        return {}
    parent_instance = parent_requirement["instances"][0]
    role = requirement["parent_context_roles"][0]
    binding = parent_instance["role_bindings"].get(role)
    if not binding or binding.get("state") != "filled":
        return {}
    return {
        role: {
            **binding,
            "provenance": {
                "candidate_source": "parent_context",
                "detail": f"from parent {parent_requirement['id']!r}: {binding.get('provenance', {}).get('candidate_source')}",
                "model": binding.get("provenance", {}).get("model"),
            },
        }
    }


def map_any_requirement(
    requirement: dict, candidate_units: list[dict], *, parent_requirement: dict | None = None
) -> dict:
    """Generic dispatch, by the requirement's OWN declared shape -- never by child/role identity.

    A cardinality requirement always uses the per-category mapper. A requirement declaring
    `parent_context_roles` FAILS LOUDLY if no parent requirement was supplied -- never silently
    falls through to a mapper that would independently "discover" instances from this child's own
    units and never actually pair them against the parent at all (a real role-name mismatch
    between a child and its declared parent produced exactly this silent fallback before this
    guard existed; see `sufficiency_authoring.py`'s comments on c9's and c5/c6's role naming).
    Among parent-context requirements, the SHAPE decides which mapper: `for_each_discovered_
    instance` (a genuine list-pairing need, e.g. c9's trait<->scale pairing, one instance per
    parent-discovered referent) uses the paired mapper; anything else (a single-instance ask that
    merely inherits candidate CONTEXT, e.g. c5/c6's region) uses the generic mapper with the
    parent's binding offered only as a fallback, never overriding this child's own evidence."""
    if requirement["instance_quantifier"] == "all_requested_categories":
        return map_cardinality_requirement(requirement, candidate_units)
    if requirement["parent_context_roles"]:
        if parent_requirement is None:
            raise ValueError(
                f"{requirement['id']!r} declares parent_context_roles={requirement['parent_context_roles']!r} "
                "but no parent_requirement was supplied -- this must never silently fall through to a "
                "mapper that ignores the parent relationship entirely."
            )
        if requirement["instance_quantifier"] == "for_each_discovered_instance":
            return map_paired_requirement(requirement, parent_requirement, candidate_units)
        parent_context_bindings = _parent_context_binding_for_single_instance(requirement, parent_requirement)
        return map_requirement(requirement, candidate_units, parent_context_bindings=parent_context_bindings)
    return map_requirement(requirement, candidate_units)


def recovery_hint(requirement: dict) -> str:
    """A short, benchmark-neutral phrase built ONLY from role `category_description`s -- never
    from a requirement id (carries `RC-`/`c\\d+` provenance tokens) or a hidden qualification's
    own stored text. Appended to the existing `qwen.recovery_query(obligation_note=...)` call so
    a recovery attempt is steered toward the SPECIFIC missing thing, never a benchmark term."""
    missing_roles: set[str] = set()
    for instance in requirement["instances"] or [se.new_instance()]:
        for role, binding in instance["role_bindings"].items():
            if binding["state"] != "filled":
                missing_roles.add(role)
    if not missing_roles:
        missing_roles = set(requirement["role_completion"]["required_roles"])
    descriptions = [
        requirement["role_specs"][role]["category_description"]
        for role in sorted(missing_roles)
        if role in requirement["role_specs"]
    ]
    return "; ".join(descriptions) or "additional supporting evidence"


def map_direction(requirement: dict, grounding_units: list[dict]) -> dict | None:
    """Populates `direction` (only when the contract declares one) from the SAME units that
    grounded a complete instance -- never a substitute for role completion, and never inferred
    from `causal_cues`/`correlational` (a correlational finding can report a perfectly clear
    direction with zero causal language)."""
    if requirement.get("direction") is None:
        return None
    for unit in grounding_units:
        word = _match_direction_word(unit["passage"])
        if word is None:
            continue
        proposition_id = unit["proposition_ids"][0] if unit.get("proposition_ids") else None
        return se.new_direction_assessment(
            reported=True,
            sign=_direction_sign(word),
            required_sign=requirement["direction"].get("required_sign"),
            causal_language_present=bool(unit.get("flags", {}).get("causal_cues")),
            proposition_id=proposition_id,
            exact_text=word,
        )
    return se.new_direction_assessment(required_sign=requirement["direction"].get("required_sign"))


def map_effectiveness(requirement: dict, grounding_units: list[dict]) -> dict | None:
    """Populates `effectiveness` (only when declared): `outcome_reported` is TRUE even for a
    definitive null/failed result -- only genuinely speculative/attempt-only language (guarded
    by the `observed_effect_or_outcome`-shaped role's own `disqualifying_guards`, typically
    `hedged` but never `absence_statement`) leaves it False. `conclusion` is populated only once
    an outcome is reported, and is never inferred from a numeric sign."""
    if requirement.get("effectiveness") is None:
        return None
    for unit in grounding_units:
        if not attr.has_result_predicate(unit["passage"]):
            continue
        proposition_id = unit["proposition_ids"][0] if unit.get("proposition_ids") else None
        negated = bool(unit.get("flags", {}).get("negated")) or bool(unit.get("flags", {}).get("absence_statement"))
        conclusion = "not_supported" if negated else "supported"
        return se.new_effectiveness_assessment(
            outcome_reported=True, conclusion=conclusion, proposition_id=proposition_id, exact_text=unit["passage"]
        )
    return se.new_effectiveness_assessment()
