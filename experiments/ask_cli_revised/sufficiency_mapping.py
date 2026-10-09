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

import copy
import re

from app.backend.pdf_processing.extraction import canonical_text_contains
from experiments.ask_cli_revised import achieved_outcome_span as aos
from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import category_polarity as cp
from experiments.ask_cli_revised import direction_target as dtg
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import ownership_context as oc
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_model_scope as mscope
from experiments.ask_cli_revised import target_relevance as tr
from experiments.ask_cli_revised.contract_directed import attribution as attr

# I4-2a: this is the ONE authorized production seam for the I4-1 local-grounding family
# (assertion_authority / achieved_outcome_span / target_relevance). No other production module
# may import any of the three -- each has its own static guard proving exactly that (see
# test_assertion_authority.py / test_achieved_outcome_span.py / test_i4_1j_local_grounding.py's
# own allow-list guards, all updated in this increment to name this one file and no other).

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
    supporting text -- a stated result is a property of the passage as a whole, not one token.
    This is the v1-v4 HISTORICAL rule, frozen exactly as-is; see `_bind_achieved_outcome_v5` for
    the v5 local-grounding replacement, which never calls this function."""
    return text if attr.has_result_predicate(text) else None


# ---------------------------------------------------------------------------------------------
# I4-2a / sufficiency-semantics-v5: local-grounding candidate collection for `achieved_outcome_
# predicate` roles only. Every other mapping_strategy, and this same strategy under any historical
# version, is completely untouched -- `_bind_achieved_outcome_v5` is reached only from the one
# `semantics_version == V5` branch in `_bind_role_candidates`.
# ---------------------------------------------------------------------------------------------


def _sibling_support_set(binding: dict) -> set:
    """Mirrors ``sufficiency_engine._support_set`` exactly (a private helper of that module, not
    reached into here -- the same documented choice `parent_synthesis_ledger.py`'s own identical
    copy already made: the formula is tiny and already covered by that module's own test suite,
    and duplicating it avoids reaching across a module boundary into another module's private
    name). Normalizes a binding's singular `proposition_id` UNION its plural `provenance.
    supporting_proposition_ids` (when present) into one proposition-identity set -- the relationship-
    derived allowed scope for I4-2a's own target-relevance matching (directive section 9)."""
    proposition_id = binding.get("proposition_id")
    supporting = binding.get("provenance", {}).get("supporting_proposition_ids")
    support = set(supporting) if supporting else set()
    if proposition_id is not None:
        support.add(proposition_id)
    return support


def resolve_target_dependency(role_completion: dict | None, evidence_role: str, sibling_bindings: dict | None) -> dict:
    """Resolve completion dependencies without interpreting role names or inventing multi-target semantics.

    Each other required role and each required alternative group is a dependency slot. A group containing
    the evidence role needs no sibling: filling the evidence itself satisfies that alternative. Optional
    roles impose no dependency. More than one slot, or multiple filled alternatives, is ambiguous.
    Missing completion context is unavailable, never an implicit target-free contract.
    """

    def result(status, reason, role=None, binding=None):
        return {
            "status": status,
            "reason": reason,
            "role": role,
            "target_text": binding["exact_text"] if binding else None,
            "allowed_proposition_ids": _sibling_support_set(binding) if binding else None,
        }

    if role_completion is None:
        return result("unavailable", "completion_context_unavailable")
    slots = [[r] for r in role_completion.get("required_roles", []) if r != evidence_role]
    slots.extend(
        list(group) for group in role_completion.get("alternative_role_groups", []) if evidence_role not in group
    )
    if not slots:
        return result("target_free", "no_dependency")
    if len(slots) > 1:
        return result("ambiguous", "multiple_dependencies")
    bindings = sibling_bindings or {}
    roles = slots[0]
    filled = [role for role in roles if bindings.get(role, {}).get("state") == "filled"]
    if len(filled) > 1:
        return result("ambiguous", "multiple_filled_alternatives")
    if not filled:
        return result("unavailable", "dependency_not_filled", roles[0] if len(roles) == 1 else None)
    role = filled[0]
    binding = bindings[role]
    if not isinstance(binding.get("exact_text"), str) or not binding["exact_text"].strip():
        return result("unavailable", "target_text_unavailable", role)
    if not _sibling_support_set(binding):
        return result("unavailable", "proposition_support_unavailable", role)
    return result("ready", "unique_dependency", role, binding)


def _bind_achieved_outcome_v5(
    role_spec: dict,
    units: list[dict],
    *,
    sibling_bindings: dict | None,
    role_completion: dict | None,
    diagnostics: dict | None = None,
) -> list[dict]:
    """Collect grounded, relevant assertions; project the first only for legacy compatibility.

    Existing guards run before localization. Raw hits join to containing assertions, deduplicated by
    (coordinate-anchor proposition, assertion span). Both target matching and exact_text use the full
    LOCAL assertion region, including its subject; content_span retains the tighter localization.
    Plural identity preserves input unit order. A multi-id unit must carry sealed proposition_passages
    with byte-identical text once raw hits exist; its first id is an offset anchor, never its sole semantic source.
    Diagnostics are optional observations and never control mapping state. No support policy is read.
    """
    role = role_spec["role"]
    dependency = resolve_target_dependency(role_completion, role, sibling_bindings)
    counts = dict.fromkeys(
        (
            "eligible_units",
            "guard_excluded_units",
            "raw_result_predicate_hits",
            "successful_assertion_joins",
            "join_failures",
            "raw_hits_deduplicated",
            "locally_grounded_assertions",
            "target_scoped_assertions",
            "target_matches",
            "target_unmatched",
            "candidate_supports_emitted",
            "missing_no_grounded_relevant_support",
        ),
        0,
    )
    resolved = []
    seen = set()
    for unit in units:
        counts["eligible_units"] += 1
        if not is_admissible(role_spec, unit.get("flags", {})):
            counts["guard_excluded_units"] += 1
            continue
        proposition_ids = list(unit.get("proposition_ids") or [])
        if not proposition_ids:
            continue
        if len(set(proposition_ids)) != len(proposition_ids):
            raise ValueError("supporting_proposition_ids must not contain duplicates")
        passage = unit["passage"]
        matches = aos.find_achieved_outcome_matches(passage).matches
        if not matches:
            continue
        # Raw spans require a shared coordinate system before assertion joining.
        if len(proposition_ids) > 1:
            quotes = unit.get("proposition_passages", {})
            if any(quotes.get(pid) != passage for pid in proposition_ids):
                raise ValueError("plural proposition spans require byte-identical sealed passages")
        anchor = proposition_ids[0]
        for match in matches:
            counts["raw_result_predicate_hits"] += 1
            joined = aa.locate_containing_assertion(
                passage,
                match.content_span[0],
                match.content_span[1],
                ruleset_version=aa.ASSERTION_AUTHORITY_RULESET_I4_1F,
            )
            if not joined["resolved"]:
                counts["join_failures"] += 1
                continue
            counts["successful_assertion_joins"] += 1
            key = (anchor, tuple(joined["assertion"]["span"]))
            if key in seen:
                counts["raw_hits_deduplicated"] += 1
                continue
            seen.add(key)
            resolved.append(
                {
                    "proposition_ids": proposition_ids,
                    "assertion": joined["assertion"],
                    "predicate_span": match.predicate_span,
                    "content_span": match.content_span,
                    "flags": unit.get("flags", {}),
                }
            )
    counts["locally_grounded_assertions"] = len(resolved)
    if dependency["status"] == "target_free":
        relevant = resolved
    elif dependency["status"] == "ready":
        scoped = [
            (i, r) for i, r in enumerate(resolved) if set(r["proposition_ids"]) & dependency["allowed_proposition_ids"]
        ]
        counts["target_scoped_assertions"] = len(scoped)
        matcher_candidates = [
            {"proposition_id": r["proposition_ids"][0], "text": r["assertion"]["assertion"]["text"], "_i": i}
            for i, r in scoped
        ]
        matched = tr.match_target_to_assertions(
            target_text=dependency["target_text"],
            candidate_assertions=matcher_candidates,
        )
        indices = {m["_i"] for m in matched["matches"]}
        relevant = [record for i, record in enumerate(resolved) if i in indices]
        counts["target_matches"] = len(relevant)
        counts["target_unmatched"] = len(scoped) - len(relevant)
    elif dependency["status"] in ("unavailable", "ambiguous"):
        relevant = []
    else:
        raise ValueError(f"unknown dependency status: {dependency['status']!r}")

    candidate_supports = []
    for record in relevant:
        assertion = record["assertion"]
        relation = aa.assertion_relation(assertion["assertion_source"])
        aggregation = assertion["aggregation"]
        kind = assertion["assertion_kind"]
        candidate_supports.append(
            se.new_candidate_support(
                supporting_proposition_ids=record["proposition_ids"],
                span_proposition_id=record["proposition_ids"][0],
                exact_text=assertion["assertion"]["text"],
                assertion_span=list(assertion["span"]),
                predicate_span=list(record["predicate_span"]) if record["predicate_span"] else None,
                content_span=list(record["content_span"]) if record["content_span"] else None,
                assertion_relation=relation,
                aggregation=aggregation,
                assertion_kind=kind,
                support_label=aa.support_label(relation, aggregation, kind),
                authority_veto=assertion.get("authority_veto"),
                is_caption=False,
                attachment_ambiguous=False,
                admissible=None,
                inadmissibility_reason=None,
            )
        )
    counts["candidate_supports_emitted"] = len(candidate_supports)
    counts["missing_no_grounded_relevant_support"] = int(not candidate_supports)
    if diagnostics is not None:
        diagnostics.update(counts)
        diagnostics["dependency"] = dependency
    if not candidate_supports:
        return []
    representative = candidate_supports[0]
    binding = se.new_role_binding(
        role,
        state="filled",
        proposition_id=representative["span_proposition_id"],
        exact_text=representative["exact_text"],
        provenance={
            "candidate_source": "deterministic_mapping",
            "detail": "achieved_outcome_predicate",
            "model": None,
            "supporting_proposition_ids": representative["supporting_proposition_ids"],
        },
        guard=relevant[0]["flags"],
    )
    return [{**binding, "candidate_supports": candidate_supports}]


def _bind_achieved_outcome_v6(role_spec, units, *, sibling_bindings, role_completion, diagnostics=None):
    """Annotate the frozen v5 collector. Ownership never selects candidates or changes policy state."""
    bindings = _bind_achieved_outcome_v5(
        role_spec,
        units,
        sibling_bindings=sibling_bindings,
        role_completion=role_completion,
        diagnostics=diagnostics,
    )
    for binding in bindings:
        for candidate in binding["candidate_supports"]:
            frozen = copy.deepcopy(candidate)
            ids = candidate["supporting_proposition_ids"]
            unit = next(u for u in units if u["proposition_ids"] == ids)
            quote = unit["passage"]
            contexts = unit.get("ownership_contexts", {})
            resolved = []
            for pid in ids:
                context = contexts.get(pid, oc.failure("context_unavailable"))
                records = []
                if context.get("status") == "available":
                    paragraph = context["paragraph_text"]
                    records = aa.classify_target_assertions(
                        paragraph,
                        target_start=0,
                        target_end=len(paragraph),
                        ruleset_version=aa.ASSERTION_AUTHORITY_RULESET_I4_1F,
                    )["assertions"]
                resolved.append(oc.resolve_local_antecedent(context, quote, candidate["assertion_span"], records))
            context = oc.combine_proofs(resolved)
            joined = aa.locate_containing_assertion(
                quote,
                *candidate["content_span"],
                ruleset_version=aa.ASSERTION_AUTHORITY_RULESET_I4_2B3,
                ownership_context=context,
            )
            if not joined["resolved"]:
                raise AssertionError("STOP: corrected attribution changed assertion attachment")
            assertion = joined["assertion"]
            if (
                assertion["assertion"]["text"] != candidate["exact_text"]
                or list(assertion["span"]) != candidate["assertion_span"]
                or any(assertion[k] != candidate[k] for k in ("assertion_kind", "aggregation", "authority_veto"))
            ):
                raise AssertionError("STOP: corrected attribution changed frozen grounding/classification")
            relation = aa.assertion_relation(assertion["assertion_source"])
            candidate["assertion_relation"] = relation
            candidate["support_label"] = aa.support_label(
                relation, candidate["aggregation"], candidate["assertion_kind"]
            )
            candidate["attribution"] = {
                **assertion["ownership"],
                "target": {
                    "quote_sha256": oc.text_hash(quote),
                    "span_proposition_id": candidate["span_proposition_id"],
                    "assertion_span": list(candidate["assertion_span"]),
                    "supporting_proposition_ids": list(ids),
                },
            }
            se.validate_candidate_attribution(candidate)
            if any(
                candidate[key] != value
                for key, value in frozen.items()
                if key not in ("assertion_relation", "support_label")
            ):
                raise AssertionError("STOP: annotation changed a frozen candidate field")
    return bindings


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
# Model-nomination: a narrow evidence-grounded nomination task, not synthesis. The model may
# propose only {proposition_id, exact_text} per excerpt (see qwen.QwenTasks.nominate_
# sufficiency_role); `proposed_role` is always host-stamped from the role_spec this call was
# scoped to, never asked of the model (one call is always scoped to exactly one role). This
# function remains responsible for literal grounding (canonical_text_contains against that exact
# proposition's own verified passage) and admissibility (is_admissible) before anything it
# returns can become a role binding -- see `_bind_role_candidates`, its only caller.
# ---------------------------------------------------------------------------------------------


def _unit_for_proposition(units: list[dict], proposition_id: str) -> dict | None:
    for unit in units:
        if proposition_id in (unit.get("proposition_ids") or []):
            return unit
    return None


def _candidate_rows_for_role(role_spec: dict, candidate_units: list[dict]) -> list[dict]:
    """Exactly the `{proposition_id, passage}` rows `nominate_with_model` would offer the model
    for this role over these units -- one row per admissible, unique proposition_id (never per
    unit_id). Extracted as its own pure helper (Phase 19) so a model-facing request can be
    fingerprinted (`sufficiency_model_scope.request_fingerprint`) WITHOUT making a call, using the
    identical logic `nominate_with_model` itself runs -- never a parallel, driftable re-derivation."""
    admissible_units = [u for u in candidate_units if is_admissible(role_spec, u.get("flags", {}))]
    seen: set[str] = set()
    rows: list[dict] = []
    for unit in admissible_units:
        for proposition_id in unit.get("proposition_ids") or []:
            if proposition_id in seen:
                continue  # a proposition_id is structurally unique to one unit
            seen.add(proposition_id)
            rows.append({"proposition_id": proposition_id, "passage": unit["passage"]})
    return rows


def nominate_with_model(role_spec: dict, candidate_units: list[dict], model_client) -> list[dict]:
    """Proposition-scoped nomination (never a unit_id, never an index-based unit->proposition
    translation -- a returned `proposition_id` IS the grounding reference). Shows the model one
    candidate row per PROPOSITION (a unit whose several proposition_ids share one passage yields
    one row per id, since only the id is a closed-enum choice; the underlying text is identical
    either way) and this role's own `category_description` -- nothing else. `model_client` is a
    QwenTasks-shaped object (or test fake) exposing `nominate_sufficiency_role(category_
    description=..., candidates=...)`.

    Returns ALL independently grounded nominations, deduplicated by `(proposition_id, normalized
    exact_text)` -- never just the first: a single passage may name several distinct instances of
    the same open-list/multi-instance role (e.g. two traits in one sentence), and the caller
    (`_bind_role_candidates`) forks an instance for each one. Every returned nomination has
    already passed `canonical_text_contains` against that specific proposition's own verified
    passage and `is_admissible` against this role's own guards -- the engine, not the model,
    decided it is literally grounded and admissible.

    Grounded nominations that share BOTH the same normalized `exact_text` AND the same physical
    evidence anchor (`unit["proposition_anchor"][proposition_id]` -- paper/chunk/span, read
    verbatim from `sufficiency_diagnostic.units_by_child`, never a parallel notion invented here)
    collapse into ONE returned nomination -- multiple proposition_ids over one physical passage
    are the SAME finding cited several ways, not several findings (Phase 2 diagnostic Finding 2).
    The collapsed nomination keeps a single deterministic `proposition_id` (the lexicographically
    lowest of the group -- arbitrary but stable across replay) plus `supporting_proposition_ids`
    (every proposition_id in the group, sorted, never discarded). A proposition whose anchor is
    unknown (no `proposition_anchor` entry -- e.g. a hand-built test fixture) is NEVER collapsed
    with anything: this function only ever merges nominations it can POSITIVELY prove share one
    physical anchor, never ones it simply lacks anchor information for. Distinct exact_text values
    from the SAME anchor are never collapsed with each other, and nominations from genuinely
    different anchors are never collapsed even when their exact_text happens to match (no fuzzy
    cross-anchor entity resolution)."""
    unit_by_proposition: dict[str, dict] = {}
    for unit in candidate_units:
        if not is_admissible(role_spec, unit.get("flags", {})):
            continue
        for proposition_id in unit.get("proposition_ids") or []:
            unit_by_proposition.setdefault(proposition_id, unit)
    candidates = _candidate_rows_for_role(role_spec, candidate_units)
    if not candidates:
        return []
    raw = model_client.nominate_sufficiency_role(
        category_description=role_spec["category_description"], candidates=candidates
    )
    grouped: dict[tuple, list[tuple[str, str]]] = {}
    order: list[tuple] = []
    for item in raw:
        proposition_id = item["proposition_id"]
        unit = unit_by_proposition.get(proposition_id)
        if unit is None:
            continue  # not in the closed eligible set this call actually offered -- dropped, never raised
        exact_text = item["exact_text"]
        if not canonical_text_contains(needle=exact_text, haystack=unit["passage"]):
            continue  # not a literal substring of that proposition's own verified passage
        anchor = (unit.get("proposition_anchor") or {}).get(proposition_id)
        normalized_text = exact_text.strip().lower()
        # An unknown anchor is scoped to its OWN proposition_id (never shared across propositions)
        # so it can never be silently merged across anchors -- only an exact (proposition_id,
        # normalized exact_text) repeat collapses, matching this function's pre-Finding-2 dedup
        # semantics exactly. A KNOWN, shared anchor is what additionally allows collapsing ACROSS
        # different proposition_ids -- see the docstring above.
        dedup_key = (
            (anchor, normalized_text) if anchor is not None else (("_no_anchor", proposition_id), normalized_text)
        )
        if dedup_key not in grouped:
            grouped[dedup_key] = []
            order.append(dedup_key)
        grouped[dedup_key].append((proposition_id, exact_text))

    accepted: list[dict] = []
    for dedup_key in order:
        members = grouped[dedup_key]
        supporting_proposition_ids = sorted({pid for pid, _ in members})
        primary_proposition_id = supporting_proposition_ids[0]
        exact_text = members[0][1]
        accepted.append(
            {
                "proposition_id": primary_proposition_id,
                "supporting_proposition_ids": supporting_proposition_ids,
                "exact_text": exact_text,
                "proposed_role": role_spec["role"],
            }
        )
    return accepted


# ---------------------------------------------------------------------------------------------
# Phase 6 added a second-pass specificity-confirmation gate here (`confirm_specific_instances`),
# a VETO-ONLY check between `nominate_with_model` and binding construction. Phase 7's live
# diagnostic found it net-harmful (it missed the one vague/circular nomination it existed to
# catch while incorrectly vetoing 8 of the other 10 genuinely specific candidates), and Phase 8's
# forensic pass found the real fix belonged in the nomination task itself, not a second judgment
# pass -- see PHASE7_LIVE_TWO_KEY_DIAGNOSTIC_RESULTS.md / PHASE8_FORENSIC_PLANNING_RESULTS.md.
# Phase 9 retires it: the active mapping path is back to ONE model operation (nomination ->
# deterministic grounding/admissibility -> RoleBinding, exactly `_bind_role_candidates` below),
# with the minimal-referent-extraction reformulation now carried entirely by
# `qwen.nomination_prompt`. The retired function's exact specification is preserved in git history
# (commits f0814716/8bf203b2) and the two markdown reports above; `sufficiency_phase5_replay.py`
# reproduces its historical effect as a self-contained scripted fixture, never by calling this
# (now-deleted) function.
# ---------------------------------------------------------------------------------------------


# ---------------------------------------------------------------------------------------------
# Discovery + per-requirement mapping orchestration
# ---------------------------------------------------------------------------------------------


def _best_unit(units: list[dict]) -> dict | None:
    return units[0] if units else None


def _prior_receipt_is_admissible(receipt: dict, role_spec: dict, units: list[dict]) -> bool:
    """Phase 19 §L: a prior-pass nomination receipt may be replayed only when every accepted item
    is STILL admissible/grounded against the CURRENT candidate pool. Phase 17's append-only
    evidence model means this ordinarily holds, but it is verified here rather than assumed -- a
    receipt with even one no-longer-admissible or no-longer-grounded accepted item is rejected
    wholesale (never pruned item-by-item): "do not silently retain stale semantic evidence"."""
    unit_by_proposition: dict[str, dict] = {}
    for unit in units:
        for pid in unit.get("proposition_ids") or []:
            unit_by_proposition.setdefault(pid, unit)
    for item in receipt["accepted"]:
        proposition_ids = [item["proposition_id"], *item.get("supporting_proposition_ids", [])]
        for pid in proposition_ids:
            unit = unit_by_proposition.get(pid)
            if unit is None:
                return False
            if not is_admissible(role_spec, unit.get("flags", {})):
                return False
            if not canonical_text_contains(needle=item["exact_text"], haystack=unit["passage"]):
                return False
    return True


def _bind_role_candidates(
    role_spec: dict,
    units: list[dict],
    *,
    model_client=None,
    child_id: str | None = None,
    requirement_id: str | None = None,
    nomination_context: dict | None = None,
    request_context: str | None = None,
    semantics_version: str,
    sibling_bindings: dict | None = None,
    role_completion: dict | None = None,
) -> list[dict]:
    """0+ FILLED role bindings for this role from these units. A deterministic-strategy role can
    only ever produce 0 or 1 candidate here (the first admissible unit whose detector matches,
    exactly as before `model_client` existed) -- ONLY `model_nomination_only` with a supplied
    `model_client` can return more than one, which is what lets a caller fork an instance
    (`map_requirement`/`map_paired_requirement`). With `model_client=None` (every existing call
    site) this function's observable behavior is identical to the old `_bind_role_from_units`.

    I4-2a: `sibling_bindings`/`role_completion` are BOTH optional, default `None`, and consulted
    ONLY by the v5 `achieved_outcome_predicate` path (`_bind_achieved_outcome_v5`) -- every other
    strategy, and every historical semantics version, ignores them completely, so every existing
    call site that omits them (every one before this phase) is byte-identical. `sibling_bindings`
    is the CURRENT fork's own `role_bindings` dict as already built by `_fork_instances_over_role`
    at the moment this role is reached -- never re-derived, never read from anywhere else -- and
    `role_completion` is the owning requirement's own, already-authored `role_completion` (never
    inferred from role names).

    Phase 19: `child_id`/`requirement_id`/`nomination_context` are ALL optional and default to
    `None`. When `nomination_context is None` (every pre-Phase-19 caller), the model branch below
    calls `nominate_with_model` directly -- byte-identical legacy behavior, no scope ever
    constructed. Only when a caller explicitly supplies `nomination_context` does this function
    construct a `(child_id, requirement_id, role)` scope and route the call through
    `sufficiency_model_scope.resolve_nomination` (authorization, in-pass memoization, held-fixed
    replay, mechanical-failure fallback -- see that module). `child_id`/`requirement_id` then
    become REQUIRED (a missing one raises, rather than silently running unauthorized) -- this is
    the one integration checkpoint the whole Phase-19 seam lives behind; no scope comparison
    exists anywhere else in this module.

    Phase 19b: `request_context` (optional, default `None`) is passed straight through to
    `resolve_nomination` unchanged -- this function makes no decision based on it, it only relays
    the caller's own pre-fork `root_key` (`map_requirement`'s loop variable) so that two legitimate
    requests sharing one authorization scope (`build_multi_instances`-partitioned units, e.g. real
    q_aib c12) get independent receipt slots instead of colliding. Every caller that omits it (the
    overwhelming majority -- any non-multi-instance requirement) observes `request_context=None`,
    byte-identical to before this phase."""
    se.require_supported_semantics_version(semantics_version)
    if (
        semantics_version in (se.SUFFICIENCY_SEMANTICS_V4, se.SUFFICIENCY_SEMANTICS_V5, se.SUFFICIENCY_SEMANTICS_V6)
        and role_spec["mapping_strategy"] == "explicit_category_terms"
    ):
        # v4/v5 category observations are collected only by the cardinality mapper (v5 reuses v4's own category
        # rule unchanged). A non-cardinality category role has no v4/v5 rule and must not silently fall back to
        # first-match.
        raise ValueError("v4/v5 category observations apply only to all_requested_categories requirements")
    if (
        semantics_version == se.SUFFICIENCY_SEMANTICS_V6
        and role_spec["mapping_strategy"] == "achieved_outcome_predicate"
    ):
        return _bind_achieved_outcome_v6(
            role_spec, units, sibling_bindings=sibling_bindings, role_completion=role_completion
        )
    if (
        semantics_version == se.SUFFICIENCY_SEMANTICS_V5
        and role_spec["mapping_strategy"] == "achieved_outcome_predicate"
    ):
        return _bind_achieved_outcome_v5(
            role_spec, units, sibling_bindings=sibling_bindings, role_completion=role_completion
        )
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
        return [
            se.new_role_binding(
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
        ]
    if (
        model_client is not None
        and role_spec["mapping_strategy"] == "model_nomination_only"
        and role_spec["model_nomination_permitted"]
    ):
        model_name = getattr(model_client, "model_name", None)
        if nomination_context is None:
            nominations = nominate_with_model(role_spec, units, model_client)
            receipt_status = None
        else:
            if child_id is None or requirement_id is None:
                raise ValueError(
                    "nomination_context was supplied but child_id/requirement_id was not -- "
                    "every caller that opts into Phase-19 scoping must thread both explicitly "
                    "(never silently broaden authorization by proceeding without a real scope)"
                )
            scope = mscope.new_model_nomination_scope(child_id, requirement_id, role)
            nominations, receipt_status = mscope.resolve_nomination(
                scope,
                request_context=request_context,
                candidate_rows=_candidate_rows_for_role(role_spec, units),
                category_description=role_spec["category_description"],
                model_name=model_name,
                make_fresh_call=lambda: nominate_with_model(role_spec, units, model_client),
                validate_prior_receipt=lambda receipt: _prior_receipt_is_admissible(receipt, role_spec, units),
                nomination_context=nomination_context,
            )
        bindings = []
        for nomination in nominations:
            src_unit = _unit_for_proposition(units, nomination["proposition_id"])
            provenance = {
                "candidate_source": "model_mapping",
                "detail": "model_nomination_only",
                "model": model_name,
                "supporting_proposition_ids": nomination["supporting_proposition_ids"],
            }
            if receipt_status is not None:
                # Phase-19 diagnostic-only addition: never propagated through parent_context
                # (see `_propagated_provenance` -- deliberately minimal, audit §O) and never
                # read by any correctness check; purely for inspectability of WHERE this
                # binding's value actually came from this pass.
                provenance["nomination_receipt_status"] = receipt_status
            bindings.append(
                se.new_role_binding(
                    role,
                    state="filled",
                    proposition_id=nomination["proposition_id"],
                    exact_text=nomination["exact_text"],
                    provenance=provenance,
                    guard=(src_unit or {}).get("flags", {}),
                )
            )
        return bindings
    return []


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


def _fork_instances_over_role(
    forks: list[dict],
    role: str,
    spec: dict,
    units_here: list[dict],
    model_client,
    *,
    child_id: str | None = None,
    requirement_id: str | None = None,
    nomination_context: dict | None = None,
    request_context: str | None = None,
    semantics_version: str,
    role_completion: dict | None = None,
) -> list[dict]:
    """Extends each of `forks` (a list of in-progress `Instance` dicts, initially length 1) with a
    binding for `role`. When `_bind_role_candidates` returns MORE THAN ONE grounded candidate for
    a fork (only possible for a `model_nomination_only` role when `model_client` is supplied -- a
    deterministic strategy always yields 0 or 1, so `model_client=None` never forks anything), that
    one fork is replaced by N copies so each carries a distinct grounded instance rather than
    silently keeping only the first. `instance_key` is intentionally left UNCHANGED here (each
    copy still carries its parent's key) -- a positional/index-based suffix scheme here is exactly
    what caused the Phase 2 diagnostic's Finding 1 collision (two roles independently forking from
    a shared ancestor can reach the same local index with different content). The caller
    (`map_requirement`/`map_paired_requirement`) re-derives a content-based key, once, only after
    ALL roles have been processed for an original instance -- see `sufficiency_engine.
    derive_instance_key`.

    I4-2a: `role_completion` (optional, default `None`) is the owning requirement's own, already-
    authored `role_completion` -- relayed, unread, straight to `_bind_role_candidates`, which is
    the only place it (and this fork's own `role_bindings`-so-far) is actually consulted, and only
    for a v5 `achieved_outcome_predicate` role. A v5 achieved-outcome role still yields 0 or 1
    candidate here, same as every other deterministic strategy -- MULTIPLE locally-grounded,
    relevant local assertions never fork multiple instances; they are retained together inside
    that one binding's own additive `candidate_supports` list instead (section 16 of the
    directive). Forking remains exclusively a `model_nomination_only` behavior.

    Phase 16: the `parent_context_bindings` fallback this function used to offer was retired --
    own-evidence-vs-parent-context dispatch for the ONE role that can legitimately inherit a
    parent value now happens once, at a higher level, in `map_paired_requirement` itself (never
    once per non-parent-context role, which never had anything to fall back to anyway). A role
    with zero candidates here is simply `missing`.

    Phase 19b: `request_context` (optional, default `None`) is relayed unchanged to every
    `_bind_role_candidates` call for every fork -- it is the CALLER's own pre-fork `root_key`, the
    same value for every fork of one original instance (forking happens strictly after
    `request_context` is fixed), which is exactly what keeps role-fork-duplicate requests
    collapsing to one physical call (they all share the same `(scope, request_context)` key)."""
    next_forks: list[dict] = []
    for forked in forks:
        candidates = _bind_role_candidates(
            spec,
            units_here,
            model_client=model_client,
            child_id=child_id,
            requirement_id=requirement_id,
            nomination_context=nomination_context,
            request_context=request_context,
            semantics_version=semantics_version,
            sibling_bindings=forked["role_bindings"],
            role_completion=role_completion,
        )
        if not candidates:
            missing = se.new_role_binding(role, state="missing", reason="not_found")
            next_forks.append({**forked, "role_bindings": {**forked["role_bindings"], role: missing}})
            continue
        for candidate in candidates:
            next_forks.append({**forked, "role_bindings": {**forked["role_bindings"], role: candidate}})
    return next_forks


def _rederive_keys_if_forked(forks: list[dict], root_key: str | None) -> list[dict]:
    """Applied once, after a full per-role fork pass for one original instance: when forking
    actually produced more than one instance, each gets a deterministic, content-derived key
    (never colliding -- see `sufficiency_engine.derive_instance_key`). When it produced exactly
    one (the overwhelmingly common case, and ALWAYS true when `model_client` is omitted, since a
    deterministic-only role can never fork), the original key is left completely untouched -- this
    is what keeps every existing deterministic-only caller and test byte-identical."""
    if len(forks) <= 1:
        return forks
    return [
        {**fork, "instance_key": se.derive_instance_key(fork["role_bindings"], root_key=root_key)} for fork in forks
    ]


def map_requirement(
    requirement: dict,
    candidate_units: list[dict],
    *,
    model_client=None,
    child_id: str | None = None,
    nomination_context: dict | None = None,
    semantics_version: str,
) -> dict:
    """Mapping for one requirement with NO parent context (see `map_paired_requirement` for that
    shape -- Phase 16 retired this function's own former `parent_context_bindings` fallback,
    which only one caller ever supplied). Deterministic-first, with model-assisted nomination
    attempted for any still-unfilled `model_nomination_only` role ONLY when `model_client` is
    explicitly supplied (every existing caller omits it, so behavior is unchanged for them -- see
    `_fork_instances_over_role`'s own docstring for the forking mechanics this introduces).
    `candidate_units` are already filtered by the caller to units attached to this requirement's
    own child (never another child's, never a hidden benchmark list).

    `child_id`/`nomination_context` (Phase 19, both optional) thread straight through to every
    role's own `_bind_role_candidates` call unchanged -- `requirement["id"]` already supplies
    this requirement's own identity, so only `child_id` is new here. Omitted entirely (the
    pre-Phase-19 default), this function's behavior is unchanged.

    Phase 19b: `root_key` (this function's own pre-existing per-instance loop variable -- `None`
    for a `multi_instance=False` requirement, one real candidate unit's own `unit_id` per iteration
    for a `build_multi_instances`-partitioned one) is passed to every role's own
    `_fork_instances_over_role` call as `request_context`. This is the exact, already-computed
    value the Phase-21-preflight audit found was missing: for a partitioned requirement, each
    outer-loop iteration legitimately offers a DIFFERENT, disjoint candidate pool to the SAME
    `(child_id, requirement_id, role)` authorization scope (real q_aib c12: two units, two
    requests) -- `request_context` is what lets `resolve_nomination` give each its own receipt slot
    instead of raising `RequestFingerprintMismatch`. For a non-partitioned requirement, every
    iteration already shares the same `root_key=None`, so this is a no-op there -- byte-identical
    to the pre-Phase-19b behavior.

    Phase 22: `instance["request_context"]` is stamped to `root_key` BEFORE any role is bound or
    forked -- a top-level field on the instance itself, never only on one role's own binding. This
    is what lets a later RecoveryTarget projection answer "which evidence partition did THIS
    instance originate from" even when every one of its roles stays `missing`/`fresh_no_candidates`
    (no binding ever exists to carry the value in that case -- the instance is the only object that
    reliably does). Survives `_fork_instances_over_role`'s shallow-spread copies and `_rederive_
    keys_if_forked`'s key replacement unchanged (neither touches unrecognized top-level keys), so
    it is identical across every fork of one original instance, exactly mirroring `request_context`
    itself. Deliberately NOT the final, possibly-rederived `instance_key` (Phase 19b's own
    established distinction, now also a documented top-level field rather than only a memoization
    parameter) -- and deliberately NOT added to `se.new_instance`'s own signature, since every other
    instance-producing path (`map_paired_requirement`, `map_cardinality_requirement`) never has a
    `root_key` concept at all and correctly leaves this field absent (`.get("request_context")`
    degrades to `None` there, matching their own already-`request_context=None` invariant).

    Returns a NEW requirement dict with `instances` populated and `state`/`reason` recomputed.
    """
    se.require_supported_semantics_version(semantics_version)
    role_specs = requirement["role_specs"]
    requirement_id = requirement["id"]

    if requirement["multi_instance"]:
        instances = build_multi_instances(candidate_units)
        units_by_instance = {inst["instance_key"]: [u] for inst, u in zip(instances, candidate_units, strict=True)}
    else:
        instances = [se.new_instance()]
        units_by_instance = {None: candidate_units}

    all_instances: list[dict] = []
    for instance in instances:
        root_key = instance["instance_key"]
        instance = {**instance, "request_context": root_key}
        units_here = units_by_instance.get(root_key, candidate_units)
        forks = [instance]
        for role, spec in role_specs.items():
            forks = _fork_instances_over_role(
                forks,
                role,
                spec,
                units_here,
                model_client,
                child_id=child_id,
                requirement_id=requirement_id,
                nomination_context=nomination_context,
                request_context=root_key,
                semantics_version=semantics_version,
                role_completion=requirement["role_completion"],
            )
        all_instances.extend(_rederive_keys_if_forked(forks, root_key))

    new_requirement = {**requirement, "instances": all_instances}
    return se.recompute_requirement(new_requirement, semantics_version=semantics_version)


def map_cardinality_requirement(
    requirement: dict,
    candidate_units: list[dict],
    *,
    model_client=None,
    child_id: str | None = None,
    nomination_context: dict | None = None,
    semantics_version: str,
) -> dict:
    """Specialization for `all_requested_categories`: one instance per named category (from the
    role's own `requested_category_terms` -- the contract's own wording-derived terms, never a
    hidden list), each checked against that SPECIFIC literal term -- never "any category
    satisfies any instance". Exactly one category-evidence role is expected. `model_client`
    threaded for architectural consistency (no q_aib category role declares
    `model_nomination_only` today, so this is inert in practice -- the category identity is
    already fixed by the requested term, so no forking applies here even if it were used).

    Phase 22 audit finding (dormant, never yet triggered by any real contract): unlike
    `map_requirement`, this function has no `root_key`/`request_context` concept at all -- every
    term's own `_bind_role_candidates` call shares the bare `(child_id, requirement_id, role)`
    scope with `request_context=None`, identical for every term. If this role were ever
    `model_nomination_only` with MORE than one `requested_category_term`, two or more structurally
    distinct requests (different `category_description`/candidate framing per term) would collide
    on the exact same composite memoization key `resolve_nomination` uses -- the same class of
    identity collision `build_multi_instances` had before Phase 19b, left unfixed here because
    nothing has ever exercised it. Rather than let that collision manifest as either a confusing
    `RequestFingerprintMismatch` or, worse, a silently wrong `memoized_in_pass` reuse of one term's
    receipt for another, this is refused deterministically below, before any model call, whenever
    the unsupported shape is detected. The proper fix -- threading a stable per-term
    `request_context` through this function, analogous in spirit to Phase 19b's own fix for
    `build_multi_instances` -- is backlogged, not built here, since no current contract needs it."""
    se.require_supported_semantics_version(semantics_version)
    role_names = list(requirement["role_specs"])
    if len(role_names) != 1:
        raise ValueError("a cardinality requirement expects exactly one category-evidence role")
    role = role_names[0]
    spec = requirement["role_specs"][role]
    if (
        nomination_context is not None
        and spec["mapping_strategy"] == "model_nomination_only"
        and spec["model_nomination_permitted"]
        and len(spec["requested_category_terms"]) > 1
    ):
        raise ValueError(
            f"{requirement['id']!r}'s role {role!r} is model_nomination_only with "
            f"{len(spec['requested_category_terms'])} requested_category_terms under Phase-19/22 "
            "scoped nomination -- map_cardinality_requirement has no per-term request_context, so "
            "every term would collide on the identical (child_id, requirement_id, role) composite "
            "key, exactly the identity collision Phase 19b fixed for build_multi_instances but never "
            "extended here (dormant until now because no contract previously exercised this shape). "
            "Refusing before any model call rather than silently colliding two terms' receipts; see "
            "sufficiency_mapping.py's map_cardinality_requirement docstring for the backlogged fix."
        )
    # I4-2a: category requirements are completely untouched by v5 (the local-grounding change applies only to
    # achieved_outcome_predicate roles) -- v5 reuses v4's own rich category-observation behavior unchanged.
    if semantics_version in (se.SUFFICIENCY_SEMANTICS_V4, se.SUFFICIENCY_SEMANTICS_V5, se.SUFFICIENCY_SEMANTICS_V6):
        return _map_category_requirement_v4(
            requirement, candidate_units, spec=spec, role=role, semantics_version=semantics_version
        )
    instances = []
    for term in spec["requested_category_terms"]:
        instance = se.new_instance(term)
        term_spec = {**spec, "requested_category_terms": [term]}
        candidates = _bind_role_candidates(
            term_spec,
            candidate_units,
            model_client=model_client,
            child_id=child_id,
            requirement_id=requirement["id"],
            nomination_context=nomination_context,
            semantics_version=semantics_version,
        )
        instance["role_bindings"][role] = (
            candidates[0] if candidates else se.new_role_binding(role, state="missing", reason="not_found")
        )
        instances.append(instance)
    new_requirement = {**requirement, "instances": instances}
    return se.recompute_requirement(new_requirement, semantics_version=semantics_version)


_CATEGORY_AUDIT_KEYS = (
    "term_occurrences",
    "matched_surface",
    "term_clause",
    "contrast_clause",
    "contrast_connective",
    "finding_cues",
    "directional_cues",
    "measurement_cues",
    "null_cues",
    "competing_terms_in_contrast",
    "hedge",
    "absence_statement",
    "occurrence_results",
    "result_complement",
)
_OBSERVATION_PRECEDENCE = (
    se.OBSERVATION_POSITIVE,
    se.OBSERVATION_NULL,
    se.OBSERVATION_MENTIONED,
    se.OBSERVATION_UNKNOWN,
)


def _category_observations(term: str, competing: tuple, spec: dict, units: list) -> list:
    """Every admissible literal observation of `term`, one per candidate unit, in unit order (never first-match).
    Literal matching is the existing case-insensitive substring rule; the polarity is the pure classifier's."""
    observations = []
    for unit in units:
        if not is_admissible(spec, unit.get("flags", {})):
            continue
        passage = unit["passage"]
        at = passage.lower().find(term.lower())
        if at == -1:
            continue
        result = cp.classify_category_observation(passage, term, competing_terms=competing)
        proposition_ids = unit.get("proposition_ids") or []
        observations.append(
            {
                "term": term,
                "proposition_id": proposition_ids[0] if proposition_ids else None,
                "unit_id": unit.get("unit_id"),
                "exact_text": passage[at : at + len(term)],
                "source_passage": passage,
                "observation_polarity": result["observation_polarity"],
                "rule": result["rule"],
                "ambiguity": result["ambiguity"],
                "classifier": result["classifier"],
                "competing_terms": list(competing),
                "classifier_audit": {key: result[key] for key in _CATEGORY_AUDIT_KEYS if key in result},
                "guard": dict(unit.get("flags", {})),
            }
        )
    return observations


def _representative_observation(observations: list) -> dict | None:
    """The compatibility representative: first positive, else first null, else first mentioned, else first unknown.
    Ties resolve by deterministic unit order. It never decides satisfaction."""
    for polarity in _OBSERVATION_PRECEDENCE:
        for observation in observations:
            if observation["observation_polarity"] == polarity:
                return observation
    return None


def _map_category_requirement_v4(
    requirement: dict, candidate_units: list, *, spec: dict, role: str, semantics_version: str
) -> dict:
    instances = []
    terms = spec["requested_category_terms"]
    for term in terms:
        instance = se.new_instance(term)
        competing = tuple(other for other in terms if other != term)
        observations = _category_observations(term, competing, spec, candidate_units)
        instance["category_observations"] = observations
        representative = _representative_observation(observations)
        if representative is None:
            instance["role_bindings"][role] = se.new_role_binding(role, state="missing", reason="not_found")
        else:
            instance["role_bindings"][role] = se.new_role_binding(
                role,
                state="filled",
                proposition_id=representative["proposition_id"],
                exact_text=representative["exact_text"],
                provenance={
                    "candidate_source": "deterministic_mapping",
                    "detail": spec["mapping_strategy"],
                    "model": None,
                    "observation_polarity": representative["observation_polarity"],
                    "classifier_rule": representative["rule"],
                },
                guard=representative["guard"],
            )
        instances.append(instance)
    new_requirement = {**requirement, "instances": instances}
    return se.recompute_requirement(new_requirement, semantics_version=semantics_version)


def _propagated_provenance(parent_requirement_id: str, source_binding: dict) -> dict:
    """Builds the re-stamped `parent_context` provenance for a binding inherited from a parent
    requirement's own completed instance -- the ONE shared construction both `map_paired_
    requirement` and `_parent_context_binding_for_single_instance` use (Phase 11 de-duplicated
    two previously-identical inline copies).

    Preserves `candidate_source="parent_context"` as the IMMEDIATE source identity, unchanged and
    never overloaded -- `same_proposition`'s own joint-grounding exemption for parent-context
    roles depends on this literal value staying exactly `"parent_context"`.

    Adds STRUCTURED, machine-readable upstream provenance that survives arbitrary propagation
    depth without ever parsing `detail`'s free text (Phase 10's confirmed gap: `detail` alone is
    not machine-readable, and `compute_stop_search_certified` must never need to parse it):

    - `upstream_model_dependent`: True iff `source_binding`'s own immediate `candidate_source` is
      `"model_mapping"`, OR `source_binding`'s own `upstream_model_dependent` was already True.
      Recursive by construction: a grandchild inheriting from a parent_context binding that itself
      carries `upstream_model_dependent=True` reads that flag straight through -- model_mapping ->
      parent_context -> parent_context -> ... all stay machine-readably model-dependent, no matter
      how many hops deep, with zero special-casing per hop.
    - `source_lineage`: the full ordered list of every `candidate_source` this value has passed
      through, oldest first (e.g. `["model_mapping", "parent_context", "parent_context"]`) --
      preserves useful ancestry rather than only a lossy boolean, at the cost of one list append
      per hop. Never required by any correctness check; purely for inspectability.

    Robust to a `source_binding` that never carried either new key (every deterministic/direct-
    model-mapping binding built before this phase, and every binding built elsewhere in this
    codebase) -- `.get(...)` defaults degrade correctly to a plain first-hop computation.

    Phase 12 (recovery targeting) adds one more carried-forward field, `model_dependency_origins`
    -- a pass-through only, never minted here: the ORIGINAL creation site
    (`sufficiency_diagnostic._stamp_model_dependency_origins`) is the only place a new origin
    record is ever appended; a propagation hop simply carries the list it was handed forward
    unchanged, exactly like `source_lineage` above."""
    source_provenance = source_binding.get("provenance") or {}
    source_candidate_source = source_provenance.get("candidate_source")
    source_lineage = source_provenance.get("source_lineage") or (
        [source_candidate_source] if source_candidate_source else []
    )
    upstream_model_dependent = source_candidate_source == "model_mapping" or bool(
        source_provenance.get("upstream_model_dependent")
    )
    return {
        "candidate_source": "parent_context",
        "detail": f"from parent {parent_requirement_id!r}: {source_candidate_source}",
        "model": source_provenance.get("model"),
        "upstream_model_dependent": upstream_model_dependent,
        "source_lineage": [*source_lineage, "parent_context"],
        "model_dependency_origins": list(source_provenance.get("model_dependency_origins") or []),
    }


def map_paired_requirement(
    requirement: dict,
    parent_requirement: dict,
    candidate_units: list[dict],
    *,
    model_client=None,
    child_id: str | None = None,
    nomination_context: dict | None = None,
    semantics_version: str,
) -> dict:
    """The SOLE parent-context instance-generation path (Phase 16) -- used for EVERY quantifier a
    `parent_context_roles` requirement declares, `exists` (e.g. c4->c5/c6's region inheritance)
    and `for_each_discovered_instance` (e.g. c8->c9's trait<->scale pairing) alike. Quantifier-
    specific aggregation is untouched and unconsulted here: `se.recompute_requirement` already
    dispatches on `requirement["instance_quantifier"]` generically, so this function only ever
    needs to produce the right SET of instances; `exists` then needs one of them complete, `for_
    each_discovered_instance` needs all of them. `multi_instance` is never consulted either --
    exactly Phase 12's own established rule: runtime multiplicity follows what's actually eligible
    to pair against, never a declared flag.

    Own-evidence-first (Phase 16): for an `exists`-shaped (or any non-`for_each_discovered_
    instance`) parent-context requirement, this child's OWN evidence is tried for the parent-
    context role itself FIRST, exactly as `_fork_instances_over_role` already does for every
    OTHER role -- own evidence always wins when it exists. If it does, the parent is never
    consulted at all for this role (no per-eligible-parent duplication merely because eligible
    parents happen to exist); if it is empty, the parent IS consulted, but only its ELIGIBLE
    instances (`se.eligible_parent_instances` -- role filled AND `instance.complete`; never
    `instances[0]`, never list order -- see the Phase-15 adversarial finding this closes).

    `for_each_discovered_instance` NEVER tries own evidence for the parent-context role (found
    necessary empirically, not assumed -- see the Phase-16 regression this surfaced against real
    c8/c9 and Phase 2/5/9 replay fixtures): that quantifier's own semantics is "mirror exactly
    what the parent discovered," which is incompatible with the child ALSO independently
    re-discovering the identical role from its own evidence -- c9's own `sufficiency_authoring.py`
    comment is explicit that it "does not ask again which traits relate to the bias", a deliberate,
    pre-Phase-16 design commitment this preserves rather than overrides. A role-name collision
    between a child's own candidate pool and its parent's is common (shared units), so this is not
    a hypothetical: naively trying own-evidence here would silently swap a parent-context
    inheritance for an independent (and untested-by-replay) re-discovery.

    Zero eligible parents and empty/skipped own evidence together mean the role stays unresolved
    -- but what that produces differs by shape, matching each quantifier's own pre-existing
    contract exactly (found necessary by a real regression against the Phase-15 harness, not
    assumed): `for_each_discovered_instance` means "one instance per discovered/eligible parent",
    so zero eligible correctly means zero instances (`test_no_parent_discovered_instances_means_
    no_child_instances` already locks this in). Every OTHER shape (e.g. `exists`) is a SINGLE
    overall instance whose roles are evaluated independently -- the historical single-instance
    fallback mapper (`map_requirement`, which this function replaces for parent-context
    requirements) always built exactly one base instance regardless of whether the parent-context
    role resolved, so this requirement's OTHER role(s) still get a genuine chance against this
    child's own evidence. Returning zero instances here instead would silently also skip testing
    those OTHER roles -- not a cosmetic difference, a real evidence-blind gap -- so exactly one
    base instance (parent role `missing`) is built instead, never omitted.

    `parent_requirement` is read as the caller (`compute_diagnostic_sufficiency_map`) last
    computed it -- when the SAME `model_client` was supplied for the parent's own mapping pass
    (the caller's topological ordering guarantees the parent is mapped first), a trait the
    deterministic pass alone could never fill but a model nomination did is a `filled`, possibly-
    `complete` parent instance here exactly like any other, so pairing against it just works: no
    separate propagation step exists or is needed. A parent instance's OWN model-dependence is a
    SEPARATE axis from its eligibility (`instance.complete` never implies `compute_stop_search_
    certified`) -- it propagates forward unchanged via `_propagated_provenance`."""
    parent_role = requirement["parent_context_roles"][0]
    other_roles = [r for r in requirement["role_specs"] if r != parent_role]
    parent_role_spec = requirement["role_specs"][parent_role]
    is_for_each = requirement["instance_quantifier"] == "for_each_discovered_instance"
    requirement_id = requirement["id"]

    def _forked_over_other_roles(base_instances: list[dict], root_key: str | None) -> list[dict]:
        forks = base_instances
        for role in other_roles:
            forks = _fork_instances_over_role(
                forks,
                role,
                requirement["role_specs"][role],
                candidate_units,
                model_client,
                child_id=child_id,
                requirement_id=requirement_id,
                nomination_context=nomination_context,
                semantics_version=semantics_version,
                role_completion=requirement["role_completion"],
            )
        return _rederive_keys_if_forked(forks, root_key)

    own_candidates = (
        []
        if is_for_each
        else _bind_role_candidates(
            parent_role_spec,
            candidate_units,
            model_client=model_client,
            child_id=child_id,
            requirement_id=requirement_id,
            nomination_context=nomination_context,
            semantics_version=semantics_version,
            role_completion=requirement["role_completion"],
        )
    )
    if own_candidates:
        base_instances = [{**se.new_instance(), "role_bindings": {parent_role: c}} for c in own_candidates]
        instances = _forked_over_other_roles(base_instances, None)
    else:
        eligible = se.eligible_parent_instances(parent_requirement, parent_role)
        if not eligible and not is_for_each:
            missing_binding = se.new_role_binding(parent_role, state="missing", reason="not_found")
            instances = _forked_over_other_roles(
                [{**se.new_instance(), "role_bindings": {parent_role: missing_binding}}], None
            )
        else:
            instances = []
            for parent_instance in eligible:
                root_key = parent_instance["instance_key"]
                parent_binding = parent_instance["role_bindings"][parent_role]
                instance = se.new_instance(root_key)
                # Re-stamped, never passed through verbatim: from THIS requirement's own
                # perspective the role is parent-context, regardless of how the parent itself
                # originally established it (deterministically, or via model nomination) -- this
                # is what exempts it from the joint-grounding check below (a parent-context role
                # can never share a proposition with anything this child retrieves, by
                # construction) while still recording, for full transparency, exactly how the
                # parent arrived at it.
                instance["role_bindings"][parent_role] = {
                    **parent_binding,
                    "provenance": _propagated_provenance(parent_requirement["id"], parent_binding),
                }
                instances.extend(_forked_over_other_roles([instance], root_key))
    new_requirement = {**requirement, "instances": instances}
    return se.recompute_requirement(new_requirement, semantics_version=semantics_version)


def map_any_requirement(
    requirement: dict,
    candidate_units: list[dict],
    *,
    parent_requirement: dict | None = None,
    model_client=None,
    child_id: str | None = None,
    nomination_context: dict | None = None,
    semantics_version: str,
) -> dict:
    """Generic dispatch, by the requirement's OWN declared shape -- never by child/role identity.

    A cardinality requirement always uses the per-category mapper. A requirement declaring
    `parent_context_roles` FAILS LOUDLY if no parent requirement was supplied -- never silently
    falls through to a mapper that would independently "discover" instances from this child's own
    units and never actually pair them against the parent at all (a real role-name mismatch
    between a child and its declared parent produced exactly this silent fallback before this
    guard existed; see `sufficiency_authoring.py`'s comments on c9's and c5/c6's role naming).

    Phase 16: EVERY parent-context requirement, regardless of its own `instance_quantifier`, now
    uses `map_paired_requirement` -- the former quantifier-based branch (a bespoke single-instance
    fallback mapper for `exists`-shaped children, `_parent_context_binding_for_single_instance`,
    retired outright) read only `parent_requirement["instances"][0]`, which a real adversarial
    case (Phase 15's c4 recovery) proved lets an incomplete, newly-nominated instance silently
    displace an already-complete one purely by raw model list order. `map_paired_requirement`'s
    own instance-generation is already fully quantifier-agnostic (it never reads `instance_
    quantifier` at all); only aggregation, already handled generically by `se.recompute_
    requirement`, depends on which quantifier the child declares.

    `model_client`, threaded through to every mapper below, defaults to `None` everywhere -- every
    existing call site (including `e2e.py`) omits it and observes identical deterministic-only
    behavior.

    `child_id`/`nomination_context` (Phase 19, both optional, default `None`): `child_id` is the
    one piece of identity this requirement dict never carries on its own (only its owning
    `SufficiencyContract` does -- see `sufficiency_engine.new_contract`); threading it here,
    structurally, from wherever the caller already has it (`sufficiency_diagnostic`'s own
    per-child loop variable) is what lets the model-nomination checkpoint construct a real
    `(child_id, requirement_id, role)` scope several calls deeper, without ever parsing it back
    out of `requirement['id']`'s own naming convention."""
    se.require_supported_semantics_version(semantics_version)
    if requirement["instance_quantifier"] == "all_requested_categories":
        return map_cardinality_requirement(
            requirement,
            candidate_units,
            model_client=model_client,
            child_id=child_id,
            nomination_context=nomination_context,
            semantics_version=semantics_version,
        )
    if requirement["parent_context_roles"]:
        if parent_requirement is None:
            raise ValueError(
                f"{requirement['id']!r} declares parent_context_roles={requirement['parent_context_roles']!r} "
                "but no parent_requirement was supplied -- this must never silently fall through to a "
                "mapper that ignores the parent relationship entirely."
            )
        return map_paired_requirement(
            requirement,
            parent_requirement,
            candidate_units,
            model_client=model_client,
            child_id=child_id,
            nomination_context=nomination_context,
            semantics_version=semantics_version,
        )
    return map_requirement(
        requirement,
        candidate_units,
        model_client=model_client,
        child_id=child_id,
        nomination_context=nomination_context,
        semantics_version=semantics_version,
    )


def _find_direction_observations_v1_v2(requirement: dict, grounding_units: list[dict]) -> list[dict]:
    """sufficiency-semantics-v1/v2 direction observations, exactly as recorded by those versions (I3 keeps them readable
    and unchanged). Reached only through `find_direction_observations` with a historical version.

    ALL grounded direction observations from `grounding_units` (Phase 18 -- replaces the former
    `map_direction`, which returned only the first whole-child-pool match; that first-match-wins
    shape was the actual bug this phase exists to fix, so it is not preserved even as a wrapper).
    One observation per matching PHYSICAL unit, never per proposition-id alias: several admissible
    proposition ids pointing at the same deduplicated passage must not manufacture fake
    corroboration -- the lexicographically-smallest remaining proposition id on the unit is used
    as each observation's deterministic representative. `grounding_units` must already be scoped
    to exactly the evidence admissible for whatever instance/relationship is being annotated (see
    `sufficiency_engine.relationship_witness_support_ids` and `sufficiency_diagnostic.
    compute_direction_and_effectiveness`'s instance-scoped unit construction) -- this function
    performs no instance scoping of its own, and never stops at the first match. Never a
    substitute for role completion, and never inferred from `causal_cues`/`correlational` (a
    correlational finding can report a perfectly clear direction with zero causal language)."""
    if requirement.get("direction") is None:
        return []
    observations = []
    for unit in grounding_units:
        word = _match_direction_word(unit["passage"])
        if word is None:
            continue
        proposition_ids = unit.get("proposition_ids") or []
        proposition_id = min(proposition_ids) if proposition_ids else None
        observations.append(
            se.new_direction_assessment(
                reported=True,
                sign=_direction_sign(word),
                required_sign=requirement["direction"].get("required_sign"),
                causal_language_present=bool(unit.get("flags", {}).get("causal_cues")),
                proposition_id=proposition_id,
                exact_text=word,
            )
        )
    return observations


def find_direction_observations(
    requirement: dict,
    grounding_units: list[dict],
    *,
    semantics_version: str,
    operands: dict[str, str] | None = None,
    relation_witness_ids: frozenset | None = None,
) -> list[dict]:
    """Direction observations, dispatched by sufficiency-semantics version (I3).

    v1/v2: the recorded historical behaviour, unchanged (first direction word per passage, no target).
    v3: one observation per direction-bearing SENTENCE of each physical unit, each carrying a deterministic target from
    the shared classifier (direction_target). ``operands`` maps each required role to its bound surface. ``relation_witness_ids``
    is the instance's witness set when the relation is witnessed, and None when it is not. A sentence is relation-eligible
    only when its target is ``relation``, it has a literal sign, and its proposition is within that witness set.
    """
    # Only the pre-I3 versions take the historical rule. v3 is historical as an identity (I2-2) but is NOT the v1/v2 rule.
    if semantics_version in (se.SUFFICIENCY_SEMANTICS_V1, se.SUFFICIENCY_SEMANTICS_V2):
        return _find_direction_observations_v1_v2(requirement, grounding_units)
    # I4-2a: v5 changes achieved-outcome mapping only; direction observations are the unchanged v3/v4 rule.
    if semantics_version not in (
        se.SUFFICIENCY_SEMANTICS_V3,
        se.SUFFICIENCY_SEMANTICS_V4,
        se.SUFFICIENCY_SEMANTICS_V5,
        se.SUFFICIENCY_SEMANTICS_V6,
    ):
        raise ValueError(f"no direction-observation rule for sufficiency-semantics version {semantics_version!r}")
    if requirement.get("direction") is None:
        return []
    if operands is None:
        raise ValueError("v3 direction observations require the instance's operand surfaces")
    required_sign = requirement["direction"].get("required_sign")
    observations = []
    for unit in grounding_units:
        proposition_ids = sorted(unit.get("proposition_ids") or [])
        witnessed = sorted(set(proposition_ids) & relation_witness_ids) if relation_witness_ids is not None else []
        representative = witnessed[0] if witnessed else (proposition_ids[0] if proposition_ids else None)
        for sentence in dtg.split_sentences(unit["passage"]):
            if not dtg.has_direction_word(sentence):
                continue
            sign = dtg.literal_direction_sign(sentence)
            result = dtg.classify_sentence(sentence, operands, None, semantics_version=semantics_version)
            observations.append(
                se.new_targeted_direction_assessment(
                    sign=sign,
                    required_sign=required_sign,
                    causal_language_present=bool(unit.get("flags", {}).get("causal_cues")),
                    proposition_id=representative,
                    exact_text=sentence,
                    target=result["target"],
                    target_role=result["role"],
                    target_reason=result["reason"],
                    relation_eligible=bool(witnessed) and result["target"] == "relation" and sign is not None,
                )
            )
    return observations


def find_effectiveness_observations(requirement: dict, grounding_units: list[dict]) -> list[dict]:
    """ALL grounded effectiveness observations (Phase 18 -- replaces the former
    `map_effectiveness`'s first-match-wins shape; see `find_direction_observations`'s docstring for
    the shared one-observation-per-physical-unit / instance-scoping contract this function follows
    identically). `outcome_reported` is TRUE even for a definitive null/failed result -- only
    genuinely speculative/attempt-only language (guarded by the `observed_effect_or_outcome`-shaped
    role's own `disqualifying_guards`, typically `hedged` but never `absence_statement`) leaves it
    False. `conclusion` is populated only once an outcome is reported, and is never inferred from a
    numeric sign."""
    if requirement.get("effectiveness") is None:
        return []
    observations = []
    for unit in grounding_units:
        if not attr.has_result_predicate(unit["passage"]):
            continue
        proposition_ids = unit.get("proposition_ids") or []
        proposition_id = min(proposition_ids) if proposition_ids else None
        negated = bool(unit.get("flags", {}).get("negated")) or bool(unit.get("flags", {}).get("absence_statement"))
        conclusion = "not_supported" if negated else "supported"
        observations.append(
            se.new_effectiveness_assessment(
                outcome_reported=True,
                conclusion=conclusion,
                proposition_id=proposition_id,
                exact_text=unit["passage"],
            )
        )
    return observations
