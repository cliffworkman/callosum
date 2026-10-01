"""Layer A -- the generic, question/domain-agnostic semantic answer-sufficiency engine.

Pure: no model, no network, no database, no library access. This module contains zero
question- or domain-specific vocabulary -- no role name, no scientific concept, no q_aib
wording appears anywhere below. It knows only: requirement structures (atomic/relational/
cardinality, all descriptive labels -- see ``recompute_requirement``), role bindings,
evidence provenance, states, reason codes, quantifiers, role completion, direction/
effectiveness assessments, relationship verifiers, and run-level search-process bookkeeping.

A *contract* (built by Layer B, ``sufficiency_authoring.py``, for any question) declares, per
child, a list of ``SufficiencyRequirement`` dicts. This module's job is to compute, from a
contract plus a set of role-binding candidates the caller has already grounded, whether each
requirement is ``filled`` / ``partially_filled`` / ``missing`` / ``ambiguous`` -- never a score,
never a verdict on the literature as a whole.

No external scholarly method is implemented or operationalized here (see CREDIT-THE-LINEAGE.md);
this is original engineering scaffolding for evidence-bound completeness bookkeeping, not a
published method, so no lineage manifest applies.

Two axes that earlier drafts conflated, now separate (see the design doc):

* ``RoleCompletionSpec`` -- within ONE candidate instance, which roles must jointly be
  established for that instance to count as *complete*. ``exists`` means "at least one complete
  instance", never "one of several required roles happened to be found".
* ``instance_quantifier`` -- across complete instances, how many are enough.

The frozen contract (role specs, role completion, quantifier policy) never contains mutable,
per-run search-process facts (recovery budget, attempts made) -- those live in a caller-owned
``SearchStatus`` dict, joined at read time, never hashed into the contract. See
``frozen_view``/``contract_hash`` and ``compute_recovery_needed``.
"""

from __future__ import annotations

import copy
import hashlib
import json

# ---------------------------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------------------------

REQUIREMENT_KINDS = ("atomic", "relational", "cardinality")  # descriptive labels only; state
# computation dispatches on `role_completion` + `instance_quantifier`, never on `kind`.

REQUIREMENT_STATES = ("filled", "partially_filled", "missing", "ambiguous")  # never a score

REASON_CODES = (
    "not_found",  # no candidate for a required/alternative role in the searched scope yet
    "incomplete_instance",  # some required/alternative roles are filled, at least one is not
    "not_reported_in_current_evidence",  # a fact is established, but the specific requested
    # sub-fact (a sign, a category) isn't in the currently-verified evidence -- never "the
    # source doesn't have it"
    "speculative_only",  # only hedged/attempt-only language found
    "insufficient_specificity",  # evidence is generic, not a named/specific instance
    "category_missing",  # a required category has zero evidence
    "evidence_conflicting",  # verified evidence disagrees
)

INSTANCE_QUANTIFIER_POLICIES = (
    "exists",  # >=1 complete instance suffices
    "all_requested_categories",  # every named category needs its own complete instance
    "for_each_discovered_instance",  # every discovered instance-key needs its own complete pairing
    "at_least_n",  # a specific numeric floor (`quantifier_n`)
    "open_list",  # report what's supported in the inspected scope; never certifies exhaustive
    # completeness -- caps at `partially_filled`
)

MAPPING_STRATEGIES = (
    # A small, FIXED, engine-owned vocabulary. The engine dispatches its deterministic-first pass
    # on a role's DECLARED strategy name (see ``sufficiency_mapping.py``), never by inspecting or
    # pattern-matching the role's own label string -- that would be exactly the domain-ontology
    # leak this module promises not to have.
    "named_instrument_lexicon",
    "achieved_outcome_predicate",
    "explicit_category_terms",
    "direction_or_sign_pattern",
    "model_nomination_only",
)

CANDIDATE_SOURCES = ("deterministic_mapping", "model_mapping", "parent_context")

RELATIONSHIP_VERIFIERS = ("same_proposition", "contract_directed_links")


# ---------------------------------------------------------------------------------------------
# Builders -- plain dicts, mirroring hierarchy_contract.py's own house style
# ---------------------------------------------------------------------------------------------


def new_role_spec(
    role: str,
    category_description: str,
    mapping_strategy: str,
    *,
    disqualifying_guards=(),
    model_nomination_permitted: bool = True,
    requested_category_terms=(),
    source_wording_span: str = "",
) -> dict:
    if mapping_strategy not in MAPPING_STRATEGIES:
        raise ValueError(f"unknown mapping_strategy: {mapping_strategy!r}")
    return {
        "role": role,
        "category_description": category_description,
        "mapping_strategy": mapping_strategy,
        "disqualifying_guards": list(disqualifying_guards),
        "model_nomination_permitted": bool(model_nomination_permitted),
        "requested_category_terms": list(requested_category_terms),
        "source_wording_span": source_wording_span,
    }


def new_role_completion(*, required_roles=(), alternative_role_groups=(), optional_roles=()) -> dict:
    return {
        "required_roles": list(required_roles),
        "alternative_role_groups": [list(g) for g in alternative_role_groups],
        "optional_roles": list(optional_roles),
    }


def completion_roles(role_completion: dict) -> list[str]:
    """Every role that participates in the completeness judgment (required + alternatives),
    in a stable order. `optional_roles` never gate completion and are excluded."""
    out = list(role_completion["required_roles"])
    for group in role_completion["alternative_role_groups"]:
        for role in group:
            if role not in out:
                out.append(role)
    return out


def new_role_binding(
    role: str,
    *,
    state: str = "missing",
    reason: str | None = None,
    proposition_id: str | None = None,
    exact_text: str | None = None,
    provenance: dict | None = None,
    guard: dict | None = None,
) -> dict:
    if state not in REQUIREMENT_STATES[:1] + ("missing", "ambiguous"):
        # a role binding is never itself "partially_filled" -- that's an instance/requirement-level state
        if state not in ("filled", "missing", "ambiguous"):
            raise ValueError(f"invalid role-binding state: {state!r}")
    return {
        "role": role,
        "state": state,
        "reason": reason,
        "proposition_id": proposition_id,
        "exact_text": exact_text,
        "provenance": provenance or {"candidate_source": None, "detail": "", "model": None},
        "guard": guard or {},
    }


def new_direction_assessment(
    *,
    reported: bool = False,
    sign: str | None = None,
    required_sign: str | None = None,
    causal_language_present: bool = False,
    proposition_id: str | None = None,
    exact_text: str | None = None,
) -> dict:
    return {
        "reported": bool(reported),
        "sign": sign,
        "required_sign": required_sign,
        "causal_language_present": bool(causal_language_present),
        "proposition_id": proposition_id,
        "exact_text": exact_text,
    }


def new_effectiveness_assessment(
    *,
    outcome_reported: bool = False,
    conclusion: str | None = None,
    proposition_id: str | None = None,
    exact_text: str | None = None,
) -> dict:
    if conclusion is not None and conclusion not in ("supported", "not_supported", "mixed"):
        raise ValueError(f"invalid effectiveness conclusion: {conclusion!r}")
    return {
        "outcome_reported": bool(outcome_reported),
        "conclusion": conclusion,
        "proposition_id": proposition_id,
        "exact_text": exact_text,
    }


def new_instance(instance_key: str | None = None) -> dict:
    return {
        "instance_key": instance_key,
        "role_bindings": {},
        "complete": False,
        "state": "missing",
        "reason": None,
    }


def new_requirement(
    req_id: str,
    kind: str,
    role_specs: dict,
    role_completion: dict,
    instance_quantifier: str,
    *,
    quantifier_n: int | None = None,
    relationship_verifiers=("same_proposition",),
    multi_instance: bool = False,
    parent_context_roles=(),
    direction: dict | None = None,
    effectiveness: dict | None = None,
    empty_result_semantically_allowed: bool = False,
    source_wording_span: str = "",
) -> dict:
    if kind not in REQUIREMENT_KINDS:
        raise ValueError(f"unknown kind: {kind!r}")
    if instance_quantifier not in INSTANCE_QUANTIFIER_POLICIES:
        raise ValueError(f"unknown instance_quantifier: {instance_quantifier!r}")
    if instance_quantifier == "at_least_n" and not quantifier_n:
        raise ValueError("at_least_n requires quantifier_n")
    declared_roles = set(role_specs)
    used_roles = set(completion_roles(role_completion)) | set(role_completion["optional_roles"])
    missing_specs = used_roles - declared_roles
    if missing_specs:
        raise ValueError(f"role(s) {sorted(missing_specs)} used in role_completion but have no RoleSpec")
    for verifier in relationship_verifiers:
        if verifier not in RELATIONSHIP_VERIFIERS:
            raise ValueError(f"unknown relationship verifier: {verifier!r}")
    return {
        "id": req_id,
        "kind": kind,
        "role_specs": copy.deepcopy(role_specs),
        "role_completion": copy.deepcopy(role_completion),
        "instance_quantifier": instance_quantifier,
        "quantifier_n": quantifier_n,
        "relationship_verifiers": list(relationship_verifiers),
        "multi_instance": bool(multi_instance),
        "instances": [],
        "parent_context_roles": list(parent_context_roles),
        "direction": direction,
        "effectiveness": effectiveness,
        "empty_result_semantically_allowed": bool(empty_result_semantically_allowed),
        "source_wording_span": source_wording_span,
        "state": "missing",
        "reason": "not_found",
    }


def new_contract(child_id: str, requirements: list[dict]) -> dict:
    return {"child_id": child_id, "requirements": copy.deepcopy(requirements)}


# ---------------------------------------------------------------------------------------------
# Frozen contract vs. per-run search state (never mixed; never hashed together)
# ---------------------------------------------------------------------------------------------

_RUNTIME_ONLY_KEYS = frozenset({"instances", "state", "reason"})


def frozen_view(contract: dict) -> dict:
    """The contract's own definitional content -- role specs, role completion, quantifier
    policy, direction/effectiveness declarations -- with every run-populated field stripped.
    This is what gets hashed; it is identical whether or not mapping has ever been run, and
    identical across runs with different recovery budgets (those never appear here at all)."""
    out = {"child_id": contract["child_id"], "requirements": []}
    for req in contract["requirements"]:
        stripped = {k: v for k, v in req.items() if k not in _RUNTIME_ONLY_KEYS}
        out["requirements"].append(stripped)
    return out


def contract_hash(contract: dict) -> str:
    canonical = json.dumps(frozen_view(contract), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_instance_key(role_bindings: dict, *, root_key: str | None = None) -> str:
    """Deterministic, content-derived instance identity. Two instances with different bound
    content always get different keys; identical content always gets the same key across a
    deterministic replay (same canonical-hash discipline as `contract_hash` above).

    Exists specifically because a positional/index-based fork-suffix scheme (e.g.
    ``f"{parent_key}#{index}"``) can collide: when two roles in one requirement independently
    fork from a shared ancestor instance, two DIFFERENT final instances can end up computing the
    same local index at the same nesting depth even though their actual bound content differs
    (found live in the Phase 2 diagnostic's own replay -- see `MODEL_NOMINATION_DIAGNOSTIC_
    RESULTS.md` Finding 1). Deriving the key from the instance's own final content instead of its
    fork lineage/position makes two differently-bound instances structurally unable to collide.

    `root_key`: the instance's pre-fork identity (a multi-instance base's `unit_id`, or `None` for
    a single-instance requirement) -- kept as a human-legible prefix only; it is NEVER itself the
    uniqueness guarantee (two instances forked from the SAME root_key with different content must
    still diverge, which the content hash below provides).

    Deliberately NOT the same notion as a physical evidence anchor (paper/chunk/span) -- that is
    proposition/evidence identity, a separate axis from semantic-instance identity. Collapsing
    instances that share an anchor is `nominate_with_model`'s own dedup step, upstream of this
    function; this function only ever makes ALREADY-DECIDED distinct instances non-collidingly
    identifiable, never decides which instances should exist.
    """
    canonical = {
        role: {
            "state": binding.get("state"),
            "proposition_id": binding.get("proposition_id"),
            "exact_text": binding.get("exact_text"),
        }
        for role, binding in sorted(role_bindings.items())
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    prefix = root_key if root_key is not None else "i"
    return f"{prefix}::{digest}"


def new_search_status(
    requirement_id: str,
    *,
    configured_recovery_budget: int = 1,
    attempts_made: int = 0,
    recovery_budget_exhausted: bool = False,
    scoped_search_completed_no_additional_support: bool = False,
    breadth_pass_used: bool = False,
) -> dict:
    """RUN-LEVEL only. Never part of a SufficiencyContract; never hashed with it (see
    `contract_hash`). `breadth_pass_used` matters only for `open_list` requirements -- see
    `compute_recovery_needed`."""
    return {
        "requirement_id": requirement_id,
        "configured_recovery_budget": configured_recovery_budget,
        "attempts_made": attempts_made,
        "recovery_budget_exhausted": bool(recovery_budget_exhausted),
        "scoped_search_completed_no_additional_support": bool(scoped_search_completed_no_additional_support),
        "breadth_pass_used": bool(breadth_pass_used),
    }


# ---------------------------------------------------------------------------------------------
# Relationship verifiers -- joint-grounding for any 2+ jointly-required roles (§ role completion)
# ---------------------------------------------------------------------------------------------


def _support_set(binding: dict) -> set:
    """The full proposition-support set a binding represents for `same_proposition` joint-
    grounding -- `supporting_proposition_ids` (the Phase 3 anchor-dedup's own provenance field,
    present only on a model-sourced binding that collapsed 2+ same-anchor propositions) UNION the
    binding's own primary `proposition_id`, never the primary ALONE. The primary stays the
    deterministic citation/provenance representative; it must not by itself narrow the semantic
    support the binding actually carries (Phase 3's own `MODEL_NOMINATION_DIAGNOSTIC_RESULTS.md`/
    `PHASE3_BOUNDED_FIXES_RESULTS.md` finding: two jointly-required bindings collapsed to
    DIFFERENT primaries from the SAME anchor-duplicate pair could spuriously fail this check even
    though they share real, recorded proposition support). A binding with no `supporting_
    proposition_ids` (every deterministic binding, and every model binding that never needed to
    collapse anything) degrades to exactly `{proposition_id}` -- byte-identical to the pre-fix
    check for every such binding."""
    proposition_id = binding.get("proposition_id")
    supporting = binding.get("provenance", {}).get("supporting_proposition_ids")
    support = set(supporting) if supporting else set()
    if proposition_id is not None:
        support.add(proposition_id)
    return support


def _verify_same_proposition(role_bindings: dict, roles: list[str]) -> bool:
    """TRUE iff every role's own proposition-support set (see `_support_set`) shares at least one
    common proposition_id -- the natural N-way generalization of "all roles cite the identical
    proposition": when every binding's support set is a singleton (the universal case before
    Phase 3's dedup existed), this is byte-identical to the original literal-equality check.
    Deliberately still proposition-identity, never evidence-ANCHOR identity -- a physical anchor
    co-occurrence alone never satisfies this (see the module's own adversarial tests)."""
    support_sets = [_support_set(role_bindings[r]) for r in roles]
    if any(not s for s in support_sets):
        return False
    return bool(set.intersection(*support_sets))


def _verify_contract_directed_links(role_bindings: dict, roles: list[str], *, context: dict | None = None) -> bool:
    """One AVAILABLE verifier, never the universal mechanism (see the design doc). Reuses
    `contract_directed/links.py`'s closed designator kinds (definition/acronym, shared
    designator, explicit reference) when the caller supplies enough context to check them.

    `contract_directed/links.py`'s full `find_links`/`verify_link` operate over document-chunk
    `attachment_pieces` (section/page-scoped text) that a sealed-ledger-only sufficiency pass
    does not carry by default. Without that context this returns False -- an honest "not
    applicable here", never a silent pass -- rather than reimplementing a narrower, unverified
    substitute. When `context["attachment_pieces"]` is supplied, this checks the lightweight,
    real sub-case: the same extracted designator (instrument name, acronym, or explicit label)
    appears in more than one role's own `exact_text`, which is exactly `links.py`'s
    `shared_designator` basis applied to role-bound spans instead of finding-vs-attachment spans.
    """
    if not context or not context.get("attachment_pieces"):
        return False
    from experiments.ask_cli_revised.contract_directed import links as _links

    texts = [role_bindings[r].get("exact_text") for r in roles]
    if any(not t for t in texts):
        return False
    designator_sets = [{d.surface.lower() for d in _links.extract_designators(t)} for t in texts]
    shared = set.intersection(*designator_sets) if designator_sets else set()
    return bool(shared)


_VERIFIER_FUNCS = {
    "same_proposition": _verify_same_proposition,
    "contract_directed_links": _verify_contract_directed_links,
}


def _joint_grounded(
    role_bindings: dict, roles: list[str], verifiers: list[str], *, context: dict | None = None
) -> bool:
    if len(roles) < 2:
        return True  # nothing to jointly ground
    for name in verifiers:
        fn = _VERIFIER_FUNCS[name]
        try:
            ok = fn(role_bindings, roles, context=context) if name != "same_proposition" else fn(role_bindings, roles)
        except TypeError:
            ok = fn(role_bindings, roles)
        if ok:
            return True
    return False


# ---------------------------------------------------------------------------------------------
# State computation -- pure, dispatched by role_completion + instance_quantifier only
# ---------------------------------------------------------------------------------------------


def recompute_instance(
    role_completion: dict, instance: dict, relationship_verifiers: list[str], *, context: dict | None = None
) -> dict:
    """Pure: returns a NEW instance dict with `complete`/`state`/`reason` derived from
    `role_bindings`. `exists` (at the requirement level) means "at least one instance for which
    this returns complete=True" -- never "one role happened to be found"."""
    bindings = instance["role_bindings"]
    required = role_completion["required_roles"]
    alt_groups = role_completion["alternative_role_groups"]

    def filled(role):
        return bindings.get(role, {}).get("state") == "filled"

    required_ok = all(filled(r) for r in required)
    alt_ok = all(any(filled(r) for r in group) for group in alt_groups)
    complete = required_ok and alt_ok

    roles_in_play = completion_roles(role_completion)
    if complete:
        filled_roles = [r for r in roles_in_play if filled(r)]
        # Parent-context roles are trusted as background context, not evidence this child itself
        # retrieved -- they can never by themselves complete an instance (a required/alternative
        # role check already enforces that), and they structurally cannot share a proposition
        # with anything this child retrieves. Joint grounding (§ relational-binding semantics)
        # therefore applies only among roles this child's OWN evidence actually filled; a single
        # own-evidence role paired with trusted parent context needs nothing further to link, but
        # two or more OWN roles must still be shown to co-occur in evidence that ties them
        # together -- never independently true from unrelated propositions.
        own_evidence_roles = [
            r for r in filled_roles if bindings[r].get("provenance", {}).get("candidate_source") != "parent_context"
        ]
        if len(own_evidence_roles) >= 2 and not _joint_grounded(
            bindings, own_evidence_roles, relationship_verifiers, context=context
        ):
            complete = False

    any_ambiguous = any(bindings.get(r, {}).get("state") == "ambiguous" for r in roles_in_play)
    any_filled = any(filled(r) for r in roles_in_play)

    if complete:
        state, reason = "filled", None
    elif any_ambiguous:
        state, reason = "ambiguous", "evidence_conflicting"
    elif any_filled:
        state, reason = "partially_filled", "incomplete_instance"
    else:
        seen_reasons = {bindings[r]["reason"] for r in roles_in_play if r in bindings and bindings[r].get("reason")}
        reason = next(iter(seen_reasons), "not_found")
        state = "missing"

    return {**instance, "complete": bool(complete), "state": state, "reason": reason}


def _aggregate_exists(instances: list[dict]) -> tuple[str, str | None]:
    if any(i["complete"] for i in instances):
        return "filled", None
    if any(i["state"] == "ambiguous" for i in instances):
        return "ambiguous", "evidence_conflicting"
    if any(i["state"] == "partially_filled" for i in instances):
        return "partially_filled", "incomplete_instance"
    return "missing", "not_found"


def _aggregate_all_requested_categories(instances: list[dict]) -> tuple[str, str | None]:
    if not instances:
        return "missing", "category_missing"
    complete = sum(1 for i in instances if i["complete"])
    if complete == len(instances):
        return "filled", None
    if complete == 0:
        return "missing", "category_missing"
    return "partially_filled", "category_missing"


def _aggregate_for_each_discovered_instance(instances: list[dict]) -> tuple[str, str | None]:
    if not instances:
        return "missing", "not_found"
    complete = sum(1 for i in instances if i["complete"])
    if complete == len(instances):
        return "filled", None
    if any(i["state"] != "missing" for i in instances):
        return "partially_filled", "incomplete_instance"
    return "missing", "not_found"


def _aggregate_at_least_n(instances: list[dict], n: int) -> tuple[str, str | None]:
    complete = sum(1 for i in instances if i["complete"])
    if complete >= n:
        return "filled", None
    if complete == 0:
        return "missing", "not_found"
    return "partially_filled", "incomplete_instance"


def _aggregate_open_list(instances: list[dict]) -> tuple[str, str | None]:
    # NEVER "filled" -- an open-ended list can never be certified exhaustively answered.
    if any(i["complete"] for i in instances):
        return "partially_filled", None
    if any(i["state"] == "partially_filled" for i in instances):
        return "partially_filled", "incomplete_instance"
    return "missing", "not_found"


_AGGREGATORS = {
    "exists": lambda instances, n: _aggregate_exists(instances),
    "all_requested_categories": lambda instances, n: _aggregate_all_requested_categories(instances),
    "for_each_discovered_instance": lambda instances, n: _aggregate_for_each_discovered_instance(instances),
    "at_least_n": lambda instances, n: _aggregate_at_least_n(instances, n),
    "open_list": lambda instances, n: _aggregate_open_list(instances),
}


def recompute_requirement(requirement: dict, *, context: dict | None = None) -> dict:
    """Pure: returns a NEW requirement dict. Recomputes every instance's `complete`/`state`/
    `reason` from its `role_bindings`, then aggregates across instances per
    `instance_quantifier`. Never mutates the input."""
    role_completion = requirement["role_completion"]
    verifiers = requirement["relationship_verifiers"]
    recomputed_instances = [
        recompute_instance(role_completion, inst, verifiers, context=context) for inst in requirement["instances"]
    ]
    aggregator = _AGGREGATORS[requirement["instance_quantifier"]]
    state, reason = aggregator(recomputed_instances, requirement.get("quantifier_n"))
    return {**requirement, "instances": recomputed_instances, "state": state, "reason": reason}


def complete_instance_count(requirement: dict) -> int:
    return sum(1 for inst in requirement["instances"] if inst["complete"])


# ---------------------------------------------------------------------------------------------
# Stop-search authority -- a SEPARATE axis from semantic `state` (Phase 9, Phase 8 Option F).
#
# `state == "filled"` answers "is there enough evidence to construct an answer". It does NOT, by
# itself, answer "should a recovery controller stop searching" -- those are different questions a
# single boolean cannot honestly carry. A model-assisted nomination is exactly the PRINCIPLES.md
# "signal, not verdict" case applied to search control: Phase 7's live diagnostic found a model-
# sourced binding can complete a requirement on a vague, non-identifying nomination (see
# PHASE7_LIVE_TWO_KEY_DIAGNOSTIC_RESULTS.md) -- so a `filled` state that DEPENDS on one or more
# `model_mapping` bindings must never, by itself, certify that recovery should stop. It remains
# fully `filled` and fully usable for answer construction (never hidden, never downgraded in the
# user-facing map -- the direct analogue of invariant #4, "never hide a low-confidence or flagged
# claim") while a SEPARATE query, `compute_stop_search_certified`, tells a recovery controller
# whether THIS fill is safe to treat as a stop-search certificate.
# ---------------------------------------------------------------------------------------------


def _instance_completion_is_model_dependent(role_completion: dict, instance: dict) -> bool:
    """True iff this COMPLETE instance's own-evidence completion-critical bindings include at
    least one sourced from `model_mapping`. Mirrors `recompute_instance`'s own `filled_roles`
    subset (every role participating in `role_completion`, i.e. `completion_roles`) -- a
    `parent_context` binding is trusted background from an already-computed PARENT requirement,
    never this instance's own search result, so it is inspected like any other role here (its
    `candidate_source` is never `model_mapping` by construction, so it never flags an instance)."""
    if not instance.get("complete"):
        return False
    bindings = instance["role_bindings"]
    for role in completion_roles(role_completion):
        binding = bindings.get(role, {})
        if binding.get("state") != "filled":
            continue
        if binding.get("provenance", {}).get("candidate_source") == "model_mapping":
            return True
    return False


def _stop_search_exists(flagged: list[dict], n) -> bool:
    return any(i["complete"] and not i["_model_dependent"] for i in flagged)


def _stop_search_all_complete_clean(flagged: list[dict], n) -> bool:
    complete = [i for i in flagged if i["complete"]]
    return bool(complete) and all(not i["_model_dependent"] for i in complete)


def _stop_search_at_least_n(flagged: list[dict], n: int) -> bool:
    clean_complete = sum(1 for i in flagged if i["complete"] and not i["_model_dependent"])
    return clean_complete >= n


_STOP_SEARCH_AGGREGATORS = {
    # Mirrors `_AGGREGATORS`'s own per-`instance_quantifier` dispatch shape exactly, evaluated
    # against "clean completion" (no model-mapping-dependent completion-critical binding) instead
    # of "any completion" -- a deterministic re-aggregation of the SAME instance set against an
    # already-present provenance fact, never a confidence score.
    "exists": _stop_search_exists,
    "all_requested_categories": _stop_search_all_complete_clean,
    "for_each_discovered_instance": _stop_search_all_complete_clean,
    "at_least_n": _stop_search_at_least_n,
    "open_list": lambda flagged, n: False,  # open_list's own aggregator never returns "filled"
}


def compute_stop_search_certified(requirement: dict) -> bool:
    """Whether `requirement`'s OWN `state == "filled"` can be explained WITHOUT relying on any
    model-mapping-sourced completion-critical binding. Returns True (certified) whenever
    `state != "filled"` -- this predicate is only ever meaningful, and only ever consulted, within
    `compute_recovery_needed`'s already-`filled` branch; outside that branch the caller's existing
    `state`-based logic already applies and this query has nothing to add.

    Reads only `state`/`instances`/`role_completion`/`instance_quantifier` -- already-computed,
    already-hashed-separately runtime fields (see `_RUNTIME_ONLY_KEYS`) and the frozen
    `role_completion`/`instance_quantifier` declarations themselves. Never mutates its input,
    never writes back a field onto the requirement -- `state` stays the sole semantic-completeness
    axis (never overloaded); this is a parallel, separately-named query, not a second state."""
    if requirement["state"] != "filled":
        return True
    role_completion = requirement["role_completion"]
    flagged = [
        {**inst, "_model_dependent": _instance_completion_is_model_dependent(role_completion, inst)}
        for inst in requirement["instances"]
    ]
    aggregator = _STOP_SEARCH_AGGREGATORS[requirement["instance_quantifier"]]
    return bool(aggregator(flagged, requirement.get("quantifier_n")))


# ---------------------------------------------------------------------------------------------
# Recovery routing -- run-level, separate from semantic `state` (never "keep recovering forever")
# ---------------------------------------------------------------------------------------------

_RECOVERABLE_REASONS = frozenset({"not_found", "incomplete_instance", "category_missing"})


def compute_recovery_needed(requirement: dict, search_status: dict) -> bool:
    """Whether this requirement should trigger a recovery attempt right now. A run-level
    decision, computed from `state`/`reason` (semantic) and `search_status` (process) together --
    never stored on the frozen contract, never conflated with `state` itself.

    `open_list` gets the approved bounded-breadth policy: once >=1 complete instance exists,
    exactly one more recovery attempt is allowed (if budget remains and the breadth pass hasn't
    already run) to look for additional supported instances; after that bounded pass, or once
    budget is exhausted, recovery stops and the requirement may terminate honestly as
    `partially_filled` -- disclosed as non-exhaustive (see the rendering layer), never as if the
    literature had been searched to completion.

    A `filled` requirement whose fill is NOT stop-search-certified (Phase 9, Phase 8 Option F --
    see `compute_stop_search_certified`) gets the SAME bounded-breadth shape `open_list` already
    uses, rather than either blind trust (treat a model-only fill like a certified one, Phase 7's
    own demonstrated failure mode) or unlimited re-search (treat it like `missing`): exactly one
    further recovery opportunity, then honest termination. Recovery stays OFF wherever this
    function's caller does not independently enable it; this function only ever computes whether
    recovery *would* be needed.
    """
    budget_spent = search_status.get("recovery_budget_exhausted") or search_status.get(
        "scoped_search_completed_no_additional_support"
    )
    if requirement["instance_quantifier"] == "open_list":
        if complete_instance_count(requirement) == 0:
            return not budget_spent
        if search_status.get("breadth_pass_used"):
            return False
        return not budget_spent
    if requirement["state"] == "filled":
        if compute_stop_search_certified(requirement):
            return False
        if search_status.get("breadth_pass_used"):
            return False
        return not budget_spent
    if budget_spent:
        return False
    return requirement.get("reason") in _RECOVERABLE_REASONS
