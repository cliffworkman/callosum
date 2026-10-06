"""Structured RecoveryTarget generation (Phase 12). Pure: no model, no network, no retrieval, no
database. Consumes an already-mapped `{child_id: SufficiencyContract}` and produces one
`RecoveryTarget` dict per distinct semantic search obligation -- replacing the child-level boolean
`compute_recovery_needed(...)` collapse Phase 11's own audit found (`compute_recovery_candidates`'s
`{child_id: [requirement_id, ...]}` shape is replaced outright by `compute_recovery_targets`,
below).

Design is the result of a three-round review (`.claude/backups/plans/` / the accepted design
response) -- this module follows the house style of every sibling in this package: plain-dict
builders (`new_recovery_target`), never a class/dataclass, and zero question/domain-specific
vocabulary (no role name, no q_aib wording appears below).

Four standing rules this module exists to hold:

1. **Reason is a closed 6-value set, never a reason+boolean-modifier pair.** `relationship_
   unverified` is a first-class reason, not `reason="partial" + relationship_only=True` --
   `recompute_instance`'s own `"partially_filled"/"incomplete_instance"` pair is produced
   identically whether a role is genuinely missing or every completion-critical role is
   individually filled but their co-occurrence is unverified; this module disambiguates that by
   re-deriving the exact condition, never by string-matching `reason`.
2. **Target identity hashes the complete semantic search obligation** (`new_target_id`): search
   owner, requirement, reason, `goal_mode`, target roles, and instance/category/breadth scope --
   never `trigger_child_id`/`affected_descendants` (two descendants sharing one upstream obligation
   must produce the SAME id) and never a changing numeric deficit (one attempt is intentionally
   shared across a shrinking `at_least_n` gap).
3. **Scoping follows the requirement's RUNTIME instance count, never its declared `multi_instance`
   flag.** `sufficiency_mapping._fork_instances_over_role` can fork a `multi_instance=False`
   requirement into more than one final instance whenever a `model_nomination_only` role yields
   more than one grounded candidate (confirmed against the real preserved v9 replay -- a brain-
   attitude relational requirement with no declared `multi_instance` produces two independently
   model-dependent instances). Trusting the declared flag instead of `len(requirement["instances"])`
   would silently collapse two genuinely distinct corroboration needs into one target.
4. **A target role's own current guessed value is never fed into its own recovery hint** (the
   confirmation-bias guard) -- `category_descriptions` is built only from `RoleSpec.category_
   description`, never from any binding's `exact_text`; a DIFFERENT, already-resolved role may be
   used as relationship scaffolding, but only when that role's own provenance shows no model
   dependence, direct or transitive (`_role_is_clean`) -- otherwise it is downgraded to its own
   category_description too, never silently trusted because it "isn't the target."
"""

from __future__ import annotations

import hashlib
import json

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_model_scope as mscope

REASONS = (
    "missing",
    "partial",
    "relationship_unverified",
    "provisional_corroboration",
    "open_list_breadth",
    "cardinality_deficit",
)

# Drives BOTH target identity and hint-template dispatch (recovery_query_hint) -- one source of
# truth, never two independently-computed classifications of the same shape.
GOAL_MODES = ("single_role", "any_of_roles", "relationship", "breadth", "cardinality")


# -------------------------------------------------------------------------------------------
# RecoveryTarget builder + identity
# -------------------------------------------------------------------------------------------


def new_target_id(payload: dict) -> str:
    """Canonical-JSON SHA-256 digest, mirroring `sufficiency_engine.derive_instance_key`'s own
    established collision-safety pattern -- never a hand-concatenated string. The readable
    `search_child_id::` prefix is for logs/tests only; the digest carries identity."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{payload['search_child_id']}::{digest}"


def new_recovery_target(
    *,
    search_child_id: str,
    trigger_child_id: str,
    requirement_id: str,
    target_roles: list,
    reason: str,
    goal_mode: str,
    scope: dict,
    category_descriptions: list,
    relationship_context: list | None = None,
    dependency_origins: list | None = None,
    affected_descendants: tuple = (),
    deficit_hint: int | None = None,
) -> dict:
    if reason not in REASONS:
        raise ValueError(f"unknown recovery-target reason: {reason!r}")
    if goal_mode not in GOAL_MODES:
        raise ValueError(f"unknown recovery-target goal_mode: {goal_mode!r}")
    payload = {
        "search_child_id": search_child_id,
        "requirement_id": requirement_id,
        "reason": reason,
        "goal_mode": goal_mode,
        "target_roles": sorted(target_roles),
        "scope": scope,
    }
    return {
        "target_id": new_target_id(payload),
        "search_child_id": search_child_id,
        "trigger_child_id": trigger_child_id,
        "requirement_id": requirement_id,
        "target_roles": list(target_roles),
        "reason": reason,
        "goal_mode": goal_mode,
        "scope": scope,
        "category_descriptions": list(category_descriptions),
        "relationship_context": relationship_context,
        "dependency_origins": list(dependency_origins) if dependency_origins else [],
        "affected_descendants": tuple(affected_descendants) if affected_descendants else (trigger_child_id,),
        "deficit_hint": deficit_hint,
    }


def _build_target(
    search_child_id,
    trigger_child_id,
    requirement,
    target_roles,
    reason,
    goal_mode,
    scope,
    *,
    relationship_context=None,
    dependency_origins=None,
    deficit_hint=None,
):
    category_descriptions = [
        requirement["role_specs"][r]["category_description"] for r in target_roles if r in requirement["role_specs"]
    ]
    return new_recovery_target(
        search_child_id=search_child_id,
        trigger_child_id=trigger_child_id,
        requirement_id=requirement["id"],
        target_roles=target_roles,
        reason=reason,
        goal_mode=goal_mode,
        scope=scope,
        category_descriptions=category_descriptions,
        relationship_context=relationship_context,
        dependency_origins=dependency_origins,
        deficit_hint=deficit_hint,
    )


# -------------------------------------------------------------------------------------------
# Confidence-aware relationship scaffolding (round 2 §6 / round 3's own honoring of it)
# -------------------------------------------------------------------------------------------


def _role_is_clean(binding: dict) -> bool:
    """A role's concrete value may be used as search scaffolding only when its own provenance
    shows no model dependence, direct or transitive -- the identical per-binding cleanliness test
    `sufficiency_engine._instance_completion_is_model_dependent` already applies per completion-
    critical role, evaluated here for one named (possibly non-target) role."""
    prov = binding.get("provenance") or {}
    if prov.get("candidate_source") == "model_mapping":
        return False
    if prov.get("upstream_model_dependent"):
        return False
    return True


# A "short, benchmark-neutral phrase" (the design's own standing description of a recovery hint)
# cannot include a role whose OWN exact_text is an entire passage -- `achieved_outcome_predicate`'s
# own detector (`_match_achieved_outcome`) deliberately returns the whole passage as supporting
# text ("a stated result is a property of the passage as a whole, not one token"), confirmed to
# actually occur live by the Phase 12 offline inventory (c12's own `observed_effect_or_outcome`
# role). Length, not strategy name, is the bound: this keeps the check generic over any current or
# future mapping_strategy that could return long text, rather than hard-coding one strategy's name
# into a module that is otherwise completely strategy-agnostic.
_MAX_CONTEXT_EXACT_TEXT_LENGTH = 80


def _relationship_context_for(requirement: dict, instance: dict, target_roles: list) -> list | None:
    """Every OTHER already-filled role on this instance, offered as scaffolding -- concrete
    `exact_text` when clean AND short enough to serve as a search anchor, downgraded to
    `category_description` alone otherwise (not clean, OR too long to be a short phrase). Never
    includes a target role's own value (the confirmation-bias guard, enforced structurally by
    exclusion here, not by a runtime check at the call site)."""
    if requirement["kind"] != "relational":
        return None
    context = []
    for role, binding in instance["role_bindings"].items():
        if role in target_roles or binding.get("state") != "filled":
            continue
        exact_text = binding.get("exact_text")
        usable = (
            _role_is_clean(binding) and exact_text is not None and len(exact_text) <= _MAX_CONTEXT_EXACT_TEXT_LENGTH
        )
        context.append(
            {
                "role": role,
                "category_description": requirement["role_specs"].get(role, {}).get("category_description", ""),
                "exact_text": exact_text if usable else None,
            }
        )
    return context or None


# -------------------------------------------------------------------------------------------
# Missing / partial / relationship_unverified -- one requirement, one or more instances
# -------------------------------------------------------------------------------------------


def _relationship_unverified_roles(role_completion: dict, instance: dict) -> list | None:
    """The exact `own_evidence_roles` set `sufficiency_engine.recompute_instance` itself computes
    before calling `_joint_grounded` -- never the flattened `completion_roles()` view, which would
    wrongly include an unfilled, UNUSED alternative-group member. If `required_ok and alt_ok` hold
    (every completion-critical role/group is individually satisfied) yet the instance is still not
    `complete`, the ONLY remaining cause (by `recompute_instance`'s own construction) is a failed
    joint-grounding check among the instance's own-evidence roles -- re-deriving that exact role
    set is sufficient; re-running `_joint_grounded` itself is not needed."""

    def filled(role):
        return instance["role_bindings"].get(role, {}).get("state") == "filled"

    required_ok = all(filled(r) for r in role_completion["required_roles"])
    alt_ok = all(any(filled(r) for r in group) for group in role_completion["alternative_role_groups"])
    if not (required_ok and alt_ok) or instance["complete"]:
        return None
    roles_in_play = se.completion_roles(role_completion)
    filled_roles = [r for r in roles_in_play if filled(r)]
    own_evidence_roles = [
        r
        for r in filled_roles
        if instance["role_bindings"][r].get("provenance", {}).get("candidate_source") != "parent_context"
    ]
    return sorted(own_evidence_roles) if len(own_evidence_roles) >= 2 else None


def _instance_scope(requirement: dict, instance: dict) -> dict:
    """Scoped by the requirement's RUNTIME instance count (see module docstring, rule 3) -- never
    by the declared `multi_instance` flag, which model-nomination forking can outrun."""
    if len(requirement["instances"]) <= 1:
        return {"kind": "none"}
    return {"kind": "instance", "instance_key": instance["instance_key"]}


def _incomplete_instance_targets(child_id: str, requirement: dict, instance: dict, *, semantics_version: str) -> list:
    scope = _instance_scope(requirement, instance)
    relationship_roles = _relationship_unverified_roles(requirement["role_completion"], instance)
    if relationship_roles is not None:
        return [
            _build_target(
                child_id,
                child_id,
                requirement,
                relationship_roles,
                "relationship_unverified",
                "relationship",
                scope,
            )
        ]
    rc = requirement["role_completion"]
    reason = "missing" if instance["state"] == "missing" else "partial"
    targets = []
    for role in rc["required_roles"]:
        if instance["role_bindings"].get(role, {}).get("state") != "filled":
            targets.append(
                _build_target(
                    child_id,
                    child_id,
                    requirement,
                    [role],
                    reason,
                    "single_role",
                    scope,
                    relationship_context=_relationship_context_for(requirement, instance, [role]),
                )
            )
    for group in rc["alternative_role_groups"]:
        if not any(instance["role_bindings"].get(r, {}).get("state") == "filled" for r in group):
            targets.append(_build_target(child_id, child_id, requirement, group, reason, "any_of_roles", scope))
    return targets


def _first_instance_targets(child_id: str, requirement: dict, parent_requirement: dict | None) -> list:
    """Zero-instance / first-instance discovery (round 3 item 2). Roles are sourced from the
    requirement's OWN declared `role_completion`, never an instance -- there isn't one yet.
    `scope={"kind":"none"}` is correct: there is nothing yet to discriminate.

    A parent-backed `for_each_discovered_instance` child whose parent has discovered nothing
    ELIGIBLE (Phase 16: `se.eligible_parent_instances` -- role filled AND the supplying instance
    itself `complete`, the SAME check `sufficiency_mapping.map_paired_requirement` uses, so the
    RecoveryTarget layer can never disagree with the mapper about whether a usable parent exists)
    emits NOTHING -- the real gap is upstream, and the parent's own zero/incomplete-instance
    target (generated the same way, one level up) is the sole actionable one."""
    if requirement["instance_quantifier"] == "for_each_discovered_instance" and requirement["parent_context_roles"]:
        parent_role = requirement["parent_context_roles"][0]
        parent_has_source = parent_requirement is not None and bool(
            se.eligible_parent_instances(parent_requirement, parent_role)
        )
        if not parent_has_source:
            return []
    rc = requirement["role_completion"]
    scope = {"kind": "none"}
    targets = [
        _build_target(child_id, child_id, requirement, [role], "missing", "single_role", scope)
        for role in rc["required_roles"]
    ]
    targets += [
        _build_target(child_id, child_id, requirement, group, "missing", "any_of_roles", scope)
        for group in rc["alternative_role_groups"]
    ]
    return targets


# -------------------------------------------------------------------------------------------
# open_list breadth / at_least_n deficit
# -------------------------------------------------------------------------------------------


def _open_list_breadth_targets(child_id: str, requirement: dict) -> list:
    if se.complete_instance_count(requirement) == 0:
        return []  # the zero-instance case is routed to `_first_instance_targets` by the caller
    rc = requirement["role_completion"]
    roles = se.completion_roles(rc)
    return [_build_target(child_id, child_id, requirement, roles, "open_list_breadth", "breadth", {"kind": "none"})]


def _cardinality_deficit_targets(child_id: str, requirement: dict) -> list:
    rc = requirement["role_completion"]
    roles = se.completion_roles(rc)
    deficit = max((requirement.get("quantifier_n") or 0) - se.complete_instance_count(requirement), 0)
    return [
        _build_target(
            child_id,
            child_id,
            requirement,
            roles,
            "cardinality_deficit",
            "cardinality",
            {"kind": "cardinality_deficit"},
            deficit_hint=deficit,
        )
    ]


# -------------------------------------------------------------------------------------------
# Provisional corroboration -- direct and upstream-redirected alike
# -------------------------------------------------------------------------------------------


def _provisional_corroboration_targets_for_instance(
    child_id: str, requirement: dict, instance: dict, requirement_owner_index: dict, mapped_contract_by_child: dict
) -> list:
    """Scoped to ONE already-complete instance -- checked regardless of the OVERALL requirement's
    own aggregate `state` (a `for_each_discovered_instance`/`at_least_n`/multi-instance `exists`
    requirement can be `partially_filled` overall while one of its OWN instances is already
    complete-but-model-dependent; `compute_stop_search_certified`'s documented scope -- "only ever
    consulted within compute_recovery_needed's already-filled branch" -- describes that simpler,
    requirement-wide boolean's own behavior, not a ceiling on this finer-grained generator, and
    deferring this check until the whole requirement completes could defer it forever for a
    requirement that never fully completes). Groups by (origin requirement_id, origin instance_key)
    -- never by requirement_id alone: two independently model-dependent instances (the real c6
    shape, module docstring rule 3) or two different parent-discovered instances (c8/c9-shaped
    redirection) must each get their OWN target; grouping by requirement_id alone would wrongly
    collapse them."""
    roles = se.completion_roles(requirement["role_completion"])
    by_origin: dict[tuple, dict] = {}
    for role in roles:
        binding = instance["role_bindings"].get(role, {})
        if binding.get("state") != "filled":
            continue
        prov = binding.get("provenance") or {}
        if prov.get("candidate_source") == "model_mapping":
            # Phase 22: this fallback mints an origin inline for a DIRECT model_mapping binding
            # that was never routed through `sufficiency_diagnostic._stamp_model_dependency_
            # origins` first (e.g. a caller that builds a mapped tree by hand, as several of this
            # module's own test fixtures do) -- `request_context` must match that stamping site's
            # own shape exactly, read from the SAME place it reads it from: the owning instance's
            # own field, never the binding (which never carries it).
            origins = [
                {
                    "child_id": child_id,
                    "requirement_id": requirement["id"],
                    "role": role,
                    "instance_key": instance["instance_key"],
                    "request_context": instance.get("request_context"),
                }
            ]
        elif prov.get("model_dependency_origins"):
            origins = prov["model_dependency_origins"]
        else:
            continue
        for origin in origins:
            key = (origin["requirement_id"], origin.get("instance_key"))
            bucket = by_origin.setdefault(key, {"roles": set(), "origins": []})
            bucket["roles"].add(role)
            bucket["origins"].append(origin)
    targets = []
    for (origin_requirement_id, origin_instance_key), info in by_origin.items():
        owner_child_id = requirement_owner_index.get(origin_requirement_id, child_id)
        owner_requirement = next(
            (
                r
                for r in mapped_contract_by_child.get(owner_child_id, {}).get("requirements", [])
                if r["id"] == origin_requirement_id
            ),
            requirement,  # the direct (non-redirected) case: the origin IS this requirement
        )
        category_descriptions = sorted(
            {
                owner_requirement["role_specs"][r]["category_description"]
                for r in info["roles"]
                if r in owner_requirement["role_specs"]
            }
        )
        dependency_origins = _dedupe_origins(info["origins"])
        scope = (
            {"kind": "none"}
            if origin_instance_key is None
            else {"kind": "instance", "instance_key": origin_instance_key}
        )
        targets.append(
            new_recovery_target(
                search_child_id=owner_child_id,
                trigger_child_id=child_id,
                requirement_id=origin_requirement_id,
                target_roles=sorted(info["roles"]),
                reason="provisional_corroboration",
                goal_mode="single_role",
                scope=scope,
                category_descriptions=category_descriptions,
                dependency_origins=dependency_origins,
            )
        )
    return targets


def _dedupe_origins(origins: list) -> list:
    seen_keys = set()
    deduped = []
    for origin in origins:
        key = (origin["child_id"], origin["requirement_id"], origin["role"], origin.get("instance_key"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(origin)
    return deduped


def _targets_for_instance(
    child_id: str,
    requirement: dict,
    instance: dict,
    requirement_owner_index: dict,
    mapped_contract_by_child: dict,
    *,
    semantics_version: str,
) -> list:
    """The single per-instance dispatch point: complete-and-model-dependent -> corroboration
    (origin-aware, possibly redirected); complete-and-clean -> nothing; incomplete -> missing/
    partial/relationship_unverified. `open_list`'s OWN complete instances deliberately do NOT reach
    this function (the orchestrator routes `open_list` to its own dedicated breadth branch) --
    round 2/3's own explicit, authorized retraction of a coexisting breadth+corroboration target
    for that quantifier is preserved as-is here, not silently re-opened during implementation, even
    though this same per-instance mechanism could in principle also close that disclosed gap."""
    if instance["complete"]:
        if se._instance_completion_is_model_dependent(requirement["role_completion"], instance):
            return _provisional_corroboration_targets_for_instance(
                child_id, requirement, instance, requirement_owner_index, mapped_contract_by_child
            )
        return []
    return _incomplete_instance_targets(child_id, requirement, instance, semantics_version=semantics_version)


def _resolve_parent_requirement(requirement, parent_of, child_id, mapped_contract_by_child):
    if not requirement["parent_context_roles"]:
        return None
    role = requirement["parent_context_roles"][0]
    parent_child_id = parent_of.get(child_id)
    parent_contract = mapped_contract_by_child.get(parent_child_id) if parent_child_id else None
    if parent_contract is None:
        return None
    return next((r for r in parent_contract["requirements"] if role in r["role_specs"]), None)


# -------------------------------------------------------------------------------------------
# Orchestration entry point -- replaces `sufficiency_diagnostic.compute_recovery_candidates`
# -------------------------------------------------------------------------------------------


_MERGE_BENIGN_FIELDS = frozenset({"affected_descendants", "dependency_origins", "trigger_child_id"})


def _merge_recovery_target(existing: dict, new: dict) -> dict:
    """Merges two `RecoveryTarget` dicts that share the same `target_id` -- which, by
    `new_target_id`'s own construction, already guarantees identical `{search_child_id,
    requirement_id, reason, goal_mode, target_roles, scope}`. `affected_descendants` and
    `dependency_origins` are unioned/deduplicated (Phase 16, fixing a real gap: only
    `affected_descendants` was ever merged before -- `dependency_origins` silently kept whichever
    call happened to be seen first).

    `trigger_child_id` is a REAL, confirmed disagreement found while implementing this exact fix
    (not a hypothetical): the shared-upstream-dependency case (`ProvisionalCorroborationTests.
    test_multiple_descendants_sharing_one_upstream_dependency_deduplicate`) has p's own direct
    pass set `trigger_child_id="p"` while c1's/c2's redirected calls set it to themselves -- a
    genuinely different value per call for the identical target_id, every time more than one
    child triggers the same upstream obligation. It carries no information `affected_descendants`
    (the full, unioned set) doesn't already carry more completely, so it is treated as benign,
    pre-existing "first generation call wins" bookkeeping here, same as before this fix -- an
    explicit, documented choice, not a silent one.

    Every field OTHER than the three above is asserted identical; a real disagreement there would
    mean two calls produced the same `target_id` from different underlying facts, which must be
    surfaced loudly, never silently resolved by picking one."""
    merged_descendants = tuple(sorted(set(existing["affected_descendants"]) | set(new["affected_descendants"])))
    merged_origins = _dedupe_origins([*existing["dependency_origins"], *new["dependency_origins"]])
    for key, value in existing.items():
        if key in _MERGE_BENIGN_FIELDS:
            continue
        if value != new.get(key):
            raise ValueError(
                f"RecoveryTarget merge conflict for target_id={existing['target_id']!r}: field {key!r} "
                f"disagrees ({value!r} != {new.get(key)!r}) -- two generation calls produced the same "
                "target_id from different underlying facts; this must be investigated, never silently "
                "resolved by picking one."
            )
    return {**existing, "affected_descendants": merged_descendants, "dependency_origins": merged_origins}


def compute_recovery_targets(
    mapped_contract_by_child: dict,
    parent_of: dict,
    search_status_by_requirement: dict | None = None,
    *,
    semantics_version: str,
) -> dict:
    """`{target_id: RecoveryTarget}` -- the single generation primitive, called both to drive a
    recovery round's `gaps` and, afterward, to report what would still trigger recovery (one
    shared function, two call sites -- never two independently-computed recovery-need checks).

    `search_status_by_requirement`: optional `{requirement_id: SearchStatus}`; a requirement with
    no entry gets a fresh, budget-not-yet-exhausted status (`se.new_search_status`), matching the
    existing codebase's own current behavior exactly (nothing today persists these flags across
    calls). Carries no opt-in gate of its own -- callers (e2e.py) own that decision; this function
    only ever computes what WOULD be searched for."""
    se.require_supported_semantics_version(semantics_version)
    search_status_by_requirement = search_status_by_requirement or {}
    requirement_owner_index = {
        requirement["id"]: child_id
        for child_id, contract in mapped_contract_by_child.items()
        for requirement in contract["requirements"]
    }
    targets: dict[str, dict] = {}

    def _status_for(requirement_id):
        return search_status_by_requirement.get(requirement_id) or se.new_search_status(requirement_id)

    for child_id, contract in mapped_contract_by_child.items():
        for requirement in contract["requirements"]:
            status = _gate_status(requirement, _status_for(requirement["id"]), semantics_version=semantics_version)
            if not se.compute_recovery_needed(requirement, status):
                continue
            quantifier = requirement["instance_quantifier"]
            generated: list = []
            if quantifier == "open_list":
                if se.complete_instance_count(requirement) == 0:
                    parent_requirement = _resolve_parent_requirement(
                        requirement, parent_of, child_id, mapped_contract_by_child
                    )
                    generated.extend(_first_instance_targets(child_id, requirement, parent_requirement))
                else:
                    generated.extend(_open_list_breadth_targets(child_id, requirement))
            elif quantifier == "at_least_n" and requirement["state"] != "filled":
                generated.extend(_cardinality_deficit_targets(child_id, requirement))
            elif not requirement["instances"]:
                parent_requirement = _resolve_parent_requirement(
                    requirement, parent_of, child_id, mapped_contract_by_child
                )
                generated.extend(_first_instance_targets(child_id, requirement, parent_requirement))
            else:
                # Checked per instance, never gated on the requirement's own aggregate `state` --
                # see `_targets_for_instance`'s docstring for why (a `for_each_discovered_instance`/
                # `at_least_n`/multi-instance `exists` requirement can be `partially_filled`
                # overall while one of its own instances is already complete-but-model-dependent).
                #
                # Phase 16 exception, scoped to `exists` ONLY: once `exists` is ALREADY satisfied
                # by some OTHER, complete instance, an incomplete SIBLING of the same requirement
                # is not itself a recovery obligation -- `exists` needs only one complete instance,
                # so the sibling's own gap never blocks completion (a real, previously-unexamined
                # gap Phase 15's c4 result exposed: a model nominating >1 instance for an `exists`
                # role must not spend bounded recovery budget chasing every extra candidate). The
                # sibling's data remains fully visible in the map (never hidden, invariant #4);
                # only ITS OWN `missing`/`partial`/`relationship_unverified` target is suppressed.
                # The satisfying instance's own corroboration obligation (if model-dependent) is
                # untouched -- it is `instance["complete"]`, so this branch never applies to it.
                for instance in requirement["instances"]:
                    if quantifier == "exists" and requirement["state"] == "filled" and not instance["complete"]:
                        continue
                    generated.extend(
                        _targets_for_instance(
                            child_id,
                            requirement,
                            instance,
                            requirement_owner_index,
                            mapped_contract_by_child,
                            semantics_version=semantics_version,
                        )
                    )

            for target in generated:
                existing = targets.get(target["target_id"])
                targets[target["target_id"]] = target if existing is None else _merge_recovery_target(existing, target)
    return targets


# -------------------------------------------------------------------------------------------
# Hint construction -- replaces `sufficiency_mapping.recovery_hint` outright (structurally
# incapable of the provisional case: it can only ever name an UNFILLED role).
# -------------------------------------------------------------------------------------------


def _context_phrase(context_role: dict) -> str:
    return context_role["exact_text"] if context_role.get("exact_text") else context_role["category_description"]


def recovery_query_hint(target: dict, mapped_contract_by_child: dict) -> str:
    """A short, benchmark-neutral phrase built from `target`'s own `category_descriptions`/
    `relationship_context` -- never from any role's current guessed `exact_text` for the TARGET
    role itself (`category_descriptions` structurally never carries one). `mapped_contract_by_child`
    is accepted for interface symmetry with the rest of this module and future extension; the
    current templates need nothing beyond what `target` itself already carries."""
    del mapped_contract_by_child
    goal_mode = target["goal_mode"]
    descriptions = target["category_descriptions"]
    subject = "; ".join(descriptions)
    if goal_mode == "single_role":
        context = target.get("relationship_context") or []
        if context:
            phrases = "; ".join(_context_phrase(c) for c in context)
            return f"{subject} associated with {phrases}" if subject else f"associated with {phrases}"
        return subject or "additional supporting evidence"
    if goal_mode == "any_of_roles":
        return " or ".join(descriptions) or "additional supporting evidence"
    if goal_mode == "breadth":
        return f"additional or different instances of {subject}" if subject else "additional supporting evidence"
    if goal_mode == "cardinality":
        return f"additional instances of {subject}" if subject else "additional supporting evidence"
    if goal_mode == "relationship":
        context = target.get("relationship_context") or []
        if context:
            phrases = "; ".join(_context_phrase(c) for c in context)
            return f"evidence connecting {subject} with {phrases}" if subject else f"evidence connecting with {phrases}"
        return (
            f"evidence establishing a relationship involving {subject}" if subject else "additional supporting evidence"
        )
    return "additional supporting evidence"


# -------------------------------------------------------------------------------------------
# Phase 22: RecoveryTarget -> fresh request-key projection. Pure; no model call, no mutation, no
# hidden state -- every input below is already-computed plain data (the real U1 map, two
# frozensets of composite keys, and the target inventory itself).
# -------------------------------------------------------------------------------------------


def _requirement_in(mapped_contract_by_child: dict, child_id: str, requirement_id: str) -> dict | None:
    contract = mapped_contract_by_child.get(child_id)
    if contract is None:
        return None
    return next((r for r in contract["requirements"] if r["id"] == requirement_id), None)


def project_fresh_request_keys(
    targets: dict,
    contract_by_child: dict,
    mapped_contract_by_child_initial: dict,
    initial_keys,
    post_recovery_keys,
) -> frozenset:
    """The single pure projection from a `{target_id: RecoveryTarget}` inventory to the exact,
    finite set of fresh `(ModelNominationScope, request_context)` keys U2 may authorize --
    `sufficiency_model_scope.exact_request_set_policy`'s own input shape.

    `mapped_contract_by_child_initial` (the REAL U1 map, `sufficiency_diagnostic.
    compute_diagnostic_sufficiency_map`'s own output from the initial pass) is the SOLE authority
    for "does an existing instance already have this role filled" and "what is that instance's own
    `request_context`" -- never the post-recovery dry map, whose final (possibly role-forked)
    instance tree is NOT model-output invariant (confirmed by direct trace of `map_requirement`'s
    own role-forking and `map_cardinality_requirement`'s own per-term instance construction during
    the Phase-22 audit -- only the SET of reachable request keys and their candidate rows are
    invariant for the mechanisms currently in use, never the final instance count/identity).
    `initial_keys`/`post_recovery_keys` (both iterables of the Phase-19b composite key shape,
    `(ModelNominationScope, request_context)` -- typically `dict.keys()` of a nomination context's
    own `in_pass_receipts`) are consulted ONLY to find genuinely NEW requests the post-recovery
    evidence created (`post_recovery_keys - initial_keys`) -- never to answer a question the
    initial map already answers directly.

    Two routes, matching the two ways a RecoveryTarget can legitimately bear on a model-assisted
    role (Phase-22 audit §1-2):

    1. **Reconsideration** (`target["dependency_origins"]` non-empty -- a `provisional_
       corroboration` target): each origin already names the exact historical `(scope,
       request_context)` pair (Phase 22's own provenance stamping, `sufficiency_diagnostic.
       _stamp_model_dependency_origins`). Multiple targets sharing one origin collapse to the
       identical key by ordinary set membership -- the real c6 case: two distinct instances, one
       shared upstream nomination, one fresh request key, never two.

    2. **Discovery** (every other reason -- `missing`/`partial`/`open_list_breadth`/
       `cardinality_deficit`): derive the target's own semantic scope(s) via `sufficiency_
       model_scope.model_scopes_for_recovery_target` (unchanged since Phase 19), then:
       - **Instance-scoped** (`target["scope"]["kind"] == "instance"`): resolve ONLY the one named
         instance, never a sibling -- the real c12 adversarial case: a target naming `U1` must
         never also authorize `U5`. Included iff that instance's own role is not yet `filled`.
       - **Scope-wide** (`"none"`/`"cardinality_deficit"` -- no single instance to name, either
         because none exists yet or the target is a blanket, instance-blind requirement-level
         statement): if the role is ALREADY `filled` on ANY existing instance for this requirement,
         every EXISTING request under this scope is excluded -- this is the real c8 finding:
         `_first_instance_targets` labels `individual_difference_trait_or_construct` "missing"
         purely because its SIBLING role never completes, even though the named role itself is
         filled on all four of c8's own real instances; reconsidering it here would violate
         locality for no semantic reason. Only a genuinely NEW post-recovery context may still
         enter (c8's own hypothetical `U7`). If the role is NOT filled anywhere existing (real c11:
         zero instances at all; real c5/c10: one instance, genuinely unfilled), every existing-and-
         unfilled instance's own key, plus every new one, is included.

    Deliberately never widens to "every request_context reachable under this scope" -- that was
    the rejected naive policy (Phase-22 audit §4): it would re-litigate an untargeted sibling
    merely because it happens to share a scope with a genuinely deficient one. No model call, no
    mutation, no hidden global state; the result is a plain `frozenset`, order-independent by
    construction."""
    fresh: set[tuple] = set()
    new_keys = frozenset(post_recovery_keys) - frozenset(initial_keys)

    for target in targets.values():
        origins = target.get("dependency_origins") or []
        if origins:
            for origin in origins:
                scope = (origin["child_id"], origin["requirement_id"], origin["role"])
                fresh.add((scope, origin.get("request_context")))
            continue

        scopes = mscope.model_scopes_for_recovery_target(target, contract_by_child)
        if not scopes:
            continue

        target_scope = target.get("scope") or {"kind": "none"}
        named_instance_key = target_scope.get("instance_key") if target_scope.get("kind") == "instance" else None

        for scope in scopes:
            child_id, requirement_id, role = scope
            requirement = _requirement_in(mapped_contract_by_child_initial, child_id, requirement_id)
            if requirement is None:
                for key in new_keys:
                    if key[0] == scope:
                        fresh.add(key)
                continue

            if named_instance_key is not None:
                # Instance-scoped: resolve ONLY the named instance -- never a sibling under the
                # same scope, and never a brand-new context either (an instance-scoped target was
                # generated from an EXISTING instance's own incompleteness; new-context discovery
                # is exclusively the scope-wide route below, matching `_incomplete_instance_
                # targets` vs. `_first_instance_targets`'s own disjoint generation paths).
                instance = next((i for i in requirement["instances"] if i["instance_key"] == named_instance_key), None)
                if instance is not None and instance["role_bindings"].get(role, {}).get("state") != "filled":
                    fresh.add((scope, instance.get("request_context")))
                continue

            role_filled_anywhere = any(
                inst["role_bindings"].get(role, {}).get("state") == "filled" for inst in requirement["instances"]
            )
            if not role_filled_anywhere:
                for inst in requirement["instances"]:
                    if inst["role_bindings"].get(role, {}).get("state") != "filled":
                        fresh.add((scope, inst.get("request_context")))
            for key in new_keys:
                if key[0] == scope:
                    fresh.add(key)

    return frozenset(fresh)


# -------------------------------------------------------------------------------------------
# Scoped-search terminality for allowed-empty requirements (Phase 27b, Option A)
#
# `empty_result_semantically_allowed` means: a SEARCHED requirement may legitimately end with zero supported findings.
# It never means "skip the search". Its effect is gated by two independent facts, both required:
#   1. the requirement is genuinely empty in the FINAL semantic map (no binding is filled, partial, or ambiguous), and
#   2. every structured RecoveryTarget the INITIAL inventory emitted for that requirement ran to completion in the
#      recovery round (the scoped search actually happened and ended).
# Only when both hold is the requirement's zero-evidence deficit closed. A generic (non-sufficiency) gap, a planned
# no-search, a mechanical NO ANSWER query, or a skipped target is never completion.
# -------------------------------------------------------------------------------------------

# Only these recovery-log reason codes mean a structured search ran to its end. `__main__._recover` emits them after
# the search and its verification pass have finished. Every other outcome is not completion.
_COMPLETED_SEARCH_REASON_CODES = frozenset({"recovery_added_evidence", "recovery_no_new_evidence"})


def is_genuinely_empty(requirement: dict) -> bool:
    """No established support: the requirement is `missing`, and every role binding in every instance is `missing`.
    A filled, partially-filled, or ambiguous binding is evidence, so this is never true for such a requirement."""
    return requirement["state"] == "missing" and all(
        binding.get("state") == "missing"
        for instance in requirement["instances"]
        for binding in instance["role_bindings"].values()
    )


def is_zero_evidence_terminal(requirement: dict) -> bool:
    """The authored permission applied to a genuinely empty requirement. Permission alone never suffices; the scoped
    search must also have completed (see `terminal_search_status`)."""
    return bool(requirement.get("empty_result_semantically_allowed")) and is_genuinely_empty(requirement)


def structured_search_outcomes(recovery_targets_initial: dict, recovery_log: list) -> dict:
    """`{requirement_id: {"completed": bool, "target_states": {target_id: {"state", "reason_code"}}}}` for every
    requirement that owned at least one INITIAL structured RecoveryTarget.

    Structured rows only: a log row counts for a target only if its gap carries that target's `_recovery_target_id`.
    A generic child gap for the same child can never prove that a requirement's structured search completed.

    Per target: `not_attempted` when no row names it (its subquestion was unresolved, it had no planned action, or the
    round never ran); `completed` when exactly one row names it with a completing reason code; `not_completed` otherwise
    (a planned no-search, a NO ANSWER query, or more than one row naming it).

    Per requirement: `completed` only when EVERY one of its initial targets is `completed` (conservative aggregation: one
    query finding nothing is not the requirement having been searched sufficiently)."""
    rows_by_target: dict[str, list[dict]] = {}
    for row in recovery_log:
        target_id = (row.get("gap") or {}).get("_recovery_target_id")
        if target_id is not None:
            rows_by_target.setdefault(target_id, []).append(row)
    by_requirement: dict[str, dict] = {}
    for target_id in sorted(recovery_targets_initial):
        target = recovery_targets_initial[target_id]
        rows = rows_by_target.get(target_id, [])
        if not rows:
            state, reason_code = "not_attempted", None
        elif len(rows) > 1:
            state, reason_code = "not_completed", "ambiguous_log_rows"
        else:
            reason_code = rows[0].get("reason_code")
            state = "completed" if reason_code in _COMPLETED_SEARCH_REASON_CODES else "not_completed"
        entry = by_requirement.setdefault(target["requirement_id"], {"target_states": {}})
        entry["target_states"][target_id] = {"state": state, "reason_code": reason_code}
    for entry in by_requirement.values():
        entry["completed"] = all(state["state"] == "completed" for state in entry["target_states"].values())
    return by_requirement


def terminal_search_status(
    sufficiency_map_final: dict, outcomes_by_requirement: dict, *, semantics_version: str
) -> dict:
    """The canonical per-requirement scoped-search status used by the FINAL target computation and recorded in the
    parent construction record. `terminal` is true only when the search completed AND the final map is zero-evidence
    terminal for the requirement. Only requirements that owned round outcomes appear; others have no entry."""
    se.require_supported_semantics_version(semantics_version)
    final_requirements = {
        requirement["id"]: requirement
        for contract in sufficiency_map_final.values()
        for requirement in contract["requirements"]
    }
    status = {}
    for requirement_id in sorted(outcomes_by_requirement):
        outcome = outcomes_by_requirement[requirement_id]
        requirement = final_requirements.get(requirement_id)
        terminal = bool(outcome["completed"]) and requirement is not None and is_zero_evidence_terminal(requirement)
        status[requirement_id] = {
            "completed": bool(outcome["completed"]),
            "terminal": terminal,
            "target_states": outcome["target_states"],
        }
    return status


def engine_search_status(terminal_status: dict) -> dict:
    """The run-level `search_status_by_requirement` shape `compute_recovery_targets` consumes (`se.new_search_status`).
    Only `terminal` drives the scoped-completion flag; every other field keeps its default."""
    return {
        requirement_id: se.new_search_status(
            requirement_id, scoped_search_completed_no_additional_support=entry["terminal"]
        )
        for requirement_id, entry in terminal_status.items()
    }


def _gate_status(requirement: dict, status: dict, *, semantics_version: str) -> dict:
    """The scoped-completion flag counts only for a zero-evidence terminal requirement. The engine reads it as
    budget-spent for EVERY state, so a stray flag on a partial, relational, ambiguous, or corroborating requirement would
    silence a real obligation. Such a flag is ignored here, never trusted."""
    if status.get("scoped_search_completed_no_additional_support") and not is_zero_evidence_terminal(requirement):
        return {**status, "scoped_search_completed_no_additional_support": False}
    return status
