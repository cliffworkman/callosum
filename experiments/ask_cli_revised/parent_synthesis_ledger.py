"""Phase 26: the deterministic parent claim-ledger and unresolved-gap-report builders.

Pure: no model, no I/O, no network, no hidden global state. Consumes an already-mapped
``{child_id: SufficiencyContract}`` (``sufficiency_map_final``, Layer A's own output after
``sufficiency_diagnostic.compute_diagnostic_sufficiency_map``/``compute_direction_and_
effectiveness`` have already run) plus the sealed ledger's ``verified_propositions`` for citation
resolution, and a final ``{target_id: RecoveryTarget}`` inventory for the gap report. Zero
question/domain-specific vocabulary -- no role name, no scientific concept, no q_aib wording
appears below (mirrors ``sufficiency_engine.py``'s own charter).

This module deliberately never reads per-child Overview output (``overview.py``'s ``items``/
``proposals``): per-child Overview prose is screened only for fidelity to its cited passage, never
for fidelity to the sufficiency engine's own role-binding semantics, so it cannot serve as parent
synthesis's authority (``PHASE25_BOUNDED_PARENT_SYNTHESIS_DESIGN_AUDIT.md`` Section 2a). Parent
synthesis is a SIBLING consumer of the same ``sufficiency_map_final``/``sufficiency_recovery_
targets`` state, never a consumer of Stage B's own output.

Core invariant (Section 5 of the design audit): no novel semantic relationship may be expressed by
a realization pass that has not already been pre-approved at ledger-construction time. A
``relational`` ``ParentClaim`` is built ONLY from an instance the sufficiency engine itself already
jointly-grounded (``complete`` with 2+ own-evidence roles); a ``category_list`` ``ParentClaim`` is
built ONLY by pre-combining sibling atomic facts of the identical role/category under an audited
list-like quantifier. The realization layer (Phase 27) is never shown two independently-built
claim ids and invited to relate them.

Phase-26 correction to the Phase-25 audit (authorized by Cliff Workman, 2026-10-03): atomic
semantic identity includes the semantic SLOT, never just the surface value --
``(claim_kind, role, category_description, proposition_id, exact_text)``, not the role-omitting
key Phase 25's prose mistakenly proposed alongside its own correct statement of the same rule.
"""

from __future__ import annotations

import hashlib
import json

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt

CLAIM_KINDS = ("role_value", "relational", "category_list", "direction_or_effectiveness")

# ``exists`` is included deliberately, not merely for parity with the three obviously list-shaped
# quantifiers: ``sufficiency_recovery_targets.py``'s own module docstring (rule #3) already
# documents, as an audited, real, non-hypothetical fact, that ``sufficiency_mapping.
# _fork_instances_over_role`` can fork a ``multi_instance=False``/``exists`` requirement into more
# than one final instance whenever a ``model_nomination_only`` role yields more than one grounded
# candidate (the real c1 shape: one ``exists`` requirement, several independently-named brain
# regions). Treating those siblings as an unordered pile of identical-looking atomic claims would
# be a worse, less faithful rendering than listing them together under their shared category --
# this is the "another explicitly audited list-like policy" escape hatch the Phase-25 design named.
# ``at_least_n`` is deliberately NOT included: no equivalent real-data precedent was found, and
# auditing it is left an explicit, disclosed v1 scope boundary (see the Phase-26 results doc).
LIST_LIKE_QUANTIFIERS = frozenset({"for_each_discovered_instance", "all_requested_categories", "open_list", "exists"})

_DIRECTION_FIELDS = (
    ("direction", "direction_observations", "sign"),
    ("effectiveness", "effectiveness_observations", "conclusion"),
)


# ---------------------------------------------------------------------------------------------
# Identity / canonicalization
# ---------------------------------------------------------------------------------------------


def semantic_claim_key(*, claim_kind: str, role, category_description, proposition_id: str, exact_text: str) -> tuple:
    """The identity of ONE atomic (role-scoped) semantic fact. Role is part of the key: the same
    proposition/exact_text bound to a DIFFERENT role is a different fact and must never fold
    (Phase-26's own correction to the Phase-25 audit's dedup-key prose, Section above)."""
    return (claim_kind, role, category_description, proposition_id, exact_text)


def _sort_key(value):
    """``None`` sorts after every real string -- the same documented policy
    ``sufficiency_engine._observation_sort_key`` already established for instance keys, reproduced
    here rather than reaching into that module's own private helper."""
    return (value is None, value)


def new_claim_id(payload: dict) -> str:
    """Canonical-JSON SHA-256 digest, mirroring ``sufficiency_recovery_targets.new_target_id``'s
    own established pattern -- a readable ``claim_kind::`` prefix for logs/tests only; the digest
    carries identity. Every list-valued field in ``payload`` must already be canonically sorted by
    the caller (never re-sorted here) so the caller's own order-invariance guarantee is the single
    source of truth."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{payload['claim_kind']}::{digest}"


def _finalize_claim(raw: dict) -> dict:
    """Turns a working (set-valued) claim accumulator into a canonical, hashed ``ParentClaim``."""
    if raw["claim_kind"] not in CLAIM_KINDS:
        raise ValueError(
            f"unknown claim_kind: {raw['claim_kind']!r}"
        )  # an internal construction bug, never reachable from input data
    claim = {
        "claim_kind": raw["claim_kind"],
        "role": raw["role"],
        "category_description": raw["category_description"],
        "child_ids": sorted(raw["child_ids"]),
        "requirement_ids": sorted(raw["requirement_ids"]),
        "instance_keys": sorted(raw["instance_keys"], key=_sort_key),
        "values": sorted(raw["values"], key=lambda v: (_sort_key(v["role"]), v["proposition_id"], v["exact_text"])),
        "admissible_proposition_ids": sorted(raw["admissible_proposition_ids"]),
        "direction_or_effectiveness": raw["direction_or_effectiveness"],
        "model_dependency": dict(raw["model_dependency"]),
        "conflict_or_heterogeneity": raw["conflict_or_heterogeneity"],
    }
    claim["claim_id"] = new_claim_id(claim)
    return claim


def _resolve_proposition(proposition_index: dict, proposition_id, *, child_id, requirement_id, role) -> dict:
    row = proposition_index.get(proposition_id)
    if row is None:
        raise ValueError(
            f"ParentClaim construction: child {child_id!r} requirement {requirement_id!r} role {role!r} "
            f"names proposition_id {proposition_id!r}, which does not resolve in the supplied sealed "
            "ledger's verified_propositions -- refusing to build a claim with unresolvable provenance "
            "rather than fabricating a citation."
        )
    return row


def _support_set(binding: dict) -> set:
    """Mirrors ``sufficiency_engine._support_set`` exactly (a private helper of that module, not
    reached into here -- `sufficiency_engine.py` is an expected-zero-change file for this phase).
    The formula itself is tiny and already covered by that module's own test suite; duplicating it
    at this one call site avoids either touching ``sufficiency_engine.py`` to export it or reaching
    across a module boundary into another module's private name."""
    proposition_id = binding.get("proposition_id")
    supporting = binding.get("provenance", {}).get("supporting_proposition_ids")
    support = set(supporting) if supporting else set()
    if proposition_id is not None:
        support.add(proposition_id)
    return support


def _binding_model_dependent(binding: dict) -> bool:
    provenance = binding.get("provenance") or {}
    return provenance.get("candidate_source") == "model_mapping" or bool(provenance.get("upstream_model_dependent"))


def _stop_search_certified_for(requirement: dict) -> bool | None:
    """Requirement-scoped, per ``sufficiency_engine.compute_stop_search_certified``'s own documented
    meaning: only meaningful once the requirement has actually reached ``state == "filled"`` --
    reporting it otherwise would read as a certification of content that was never certified."""
    if requirement["state"] != "filled":
        return None
    return se.compute_stop_search_certified(requirement)


# ---------------------------------------------------------------------------------------------
# build_claim_ledger
# ---------------------------------------------------------------------------------------------


def build_claim_ledger(sufficiency_map_final: dict, sealed: dict, parent_of: dict | None = None) -> list[dict]:
    """``list[ParentClaim]`` from a final, already-mapped ``{child_id: SufficiencyContract}``.

    ``parent_of`` is accepted for interface symmetry with ``sufficiency_diagnostic.compute_
    diagnostic_sufficiency_map`` (the hierarchy's own ``{child_id: parent_child_id}``) but is not
    read by this function: every parent-context exclusion this module needs is already recorded on
    each binding's own ``provenance.candidate_source`` by the mapper that produced
    ``sufficiency_map_final`` -- this function never re-derives hierarchy topology.

    proposition_id scope: treated as unique WITHIN this one sealed run (never across independent
    runs) -- a ``ParentClaim``'s own provenance is only ever meaningful alongside the sealed-ledger
    hash and sufficiency-map hash it was built from (see ``parent_synthesis_render.
    construction_record``), so cross-run proposition_id reuse is harmless by construction.
    """
    proposition_index = {row["proposition_id"]: row for row in sealed["verified_propositions"]}

    candidates_by_requirement: dict[tuple, list[dict]] = {}
    relational_by_key: dict[tuple, dict] = {}
    direction_claims: list[dict] = []

    for child_id, contract in sufficiency_map_final.items():
        for requirement in contract["requirements"]:
            role_completion = requirement["role_completion"]
            role_specs = requirement["role_specs"]
            verifiers = requirement["relationship_verifiers"]
            cert = _stop_search_certified_for(requirement)
            for instance in requirement["instances"]:
                bindings = instance["role_bindings"]
                own_roles = se.own_evidence_roles(role_completion, bindings)
                if instance["complete"] and len(own_roles) >= 2:
                    _accumulate_relational(
                        relational_by_key,
                        requirement,
                        instance,
                        own_roles,
                        verifiers,
                        proposition_index,
                        child_id,
                        cert,
                    )
                else:
                    for role in own_roles:
                        candidates_by_requirement.setdefault((child_id, requirement["id"]), []).append(
                            _atomic_candidate(
                                requirement, instance, role, role_specs, proposition_index, child_id, cert
                            )
                        )
            direction_claims.extend(
                _direction_or_effectiveness_claims(
                    requirement, instance_list=requirement["instances"], child_id=child_id, cert=cert
                )
            )

    claims = [_finalize_claim(c) for c in relational_by_key.values()]
    claims.extend(_finalize_claim(c) for c in direction_claims)
    claims.extend(_finalize_claim(c) for c in _build_atomic_claims(candidates_by_requirement))
    return claims


def _relational_identity(own_roles: list[str], bindings: dict) -> tuple:
    return (
        "relational",
        tuple(sorted((r, bindings[r]["proposition_id"], bindings[r]["exact_text"]) for r in own_roles)),
    )


def _accumulate_relational(
    relational_by_key, requirement, instance, own_roles, verifiers, proposition_index, child_id, cert
):
    bindings = instance["role_bindings"]
    witness_ids = se.relationship_witness_support_ids(requirement["role_completion"], bindings, verifiers)
    if not witness_ids:
        raise ValueError(
            f"ParentClaim construction: {child_id!r}/{requirement['id']!r} instance "
            f"{instance['instance_key']!r} is complete with {len(own_roles)} own-evidence roles but "
            "its joint-witness support set is empty -- this should be structurally unreachable given "
            "the currently sole reachable relationship verifier (same_proposition); refusing to build "
            "a relational claim with no admissible evidence rather than guessing."
        )
    values = []
    for role in own_roles:
        binding = bindings[role]
        _resolve_proposition(
            proposition_index, binding["proposition_id"], child_id=child_id, requirement_id=requirement["id"], role=role
        )
        values.append({"proposition_id": binding["proposition_id"], "exact_text": binding["exact_text"], "role": role})
    key = _relational_identity(own_roles, bindings)
    model_dependent = any(_binding_model_dependent(bindings[r]) for r in own_roles)
    existing = relational_by_key.get(key)
    if existing is None:
        relational_by_key[key] = {
            "claim_kind": "relational",
            "role": None,
            "category_description": None,
            "values": values,
            "admissible_proposition_ids": set(witness_ids),
            "child_ids": {child_id},
            "requirement_ids": {requirement["id"]},
            "instance_keys": {instance["instance_key"]},
            "model_dependency": {"any": model_dependent, "stop_search_certified": cert},
            "direction_or_effectiveness": None,
            "conflict_or_heterogeneity": None,
        }
    else:
        existing["child_ids"].add(child_id)
        existing["requirement_ids"].add(requirement["id"])
        existing["instance_keys"].add(instance["instance_key"])
        existing["admissible_proposition_ids"] |= set(witness_ids)
        existing["model_dependency"]["any"] = existing["model_dependency"]["any"] or model_dependent
        # cert is requirement-scoped; a dedup fold across requirements keeps the most permissive
        # reading rather than discarding one requirement's own certified status.
        if existing["model_dependency"]["stop_search_certified"] is None:
            existing["model_dependency"]["stop_search_certified"] = cert


def _atomic_candidate(requirement, instance, role, role_specs, proposition_index, child_id, cert) -> dict:
    binding = instance["role_bindings"][role]
    _resolve_proposition(
        proposition_index, binding["proposition_id"], child_id=child_id, requirement_id=requirement["id"], role=role
    )
    return {
        "role": role,
        "category_description": role_specs[role]["category_description"],
        "proposition_id": binding["proposition_id"],
        "exact_text": binding["exact_text"],
        "admissible": _support_set(binding),
        "child_ids": {child_id},
        "requirement_ids": {requirement["id"]},
        "instance_keys": {instance["instance_key"]},
        "model_dependent": _binding_model_dependent(binding),
        "list_like": requirement["instance_quantifier"] in LIST_LIKE_QUANTIFIERS,
        "cert": cert,
    }


def _copy_member(item: dict) -> dict:
    return {
        **item,
        "admissible": set(item["admissible"]),
        "child_ids": set(item["child_ids"]),
        "requirement_ids": set(item["requirement_ids"]),
        "instance_keys": set(item["instance_keys"]),
    }


def _merge_member(target: dict, other: dict) -> None:
    target["admissible"] |= other["admissible"]
    target["child_ids"] |= other["child_ids"]
    target["requirement_ids"] |= other["requirement_ids"]
    target["instance_keys"] |= other["instance_keys"]
    target["model_dependent"] = target["model_dependent"] or other["model_dependent"]
    target["list_like"] = target["list_like"] or other["list_like"]
    if target["cert"] is None:
        target["cert"] = other["cert"]


def _fold(items: list[dict], key_fn) -> list[dict]:
    out: dict[tuple, dict] = {}
    for item in items:
        key = key_fn(item)
        if key in out:
            _merge_member(out[key], item)
        else:
            out[key] = _copy_member(item)
    return list(out.values())


def _build_atomic_claims(candidates_by_requirement: dict[tuple, list[dict]]) -> list[dict]:
    """Two scopes, never conflated:

    1. WITHIN one requirement (the ``(child_id, requirement_id)`` key this dict is already keyed
       by), per role: an exact literal duplicate (the identical ``(proposition_id, exact_text)``,
       e.g. the same manifestation evidence repeated across several forked instances of one
       requirement) always collapses to one distinct value, merging instance keys. If 2+ DISTINCT
       values remain for that one role AND the requirement's own quantifier is audited list-like,
       they pre-combine into exactly ONE ``category_list`` claim -- Section 11's own explicit "same
       requirement" condition, never relaxed to "same role anywhere".

    2. ACROSS requirements/children (rule D, Section 9): only among the resulting STANDALONE
       atomic values (never among already-pre-combined ``category_list`` claims, which stay
       requirement-scoped) -- the identical ``semantic_claim_key`` folds sibling requirements'
       independently-surfaced identical facts into one claim with joint provenance.
    """
    standalone: list[dict] = []
    category_lists: list[dict] = []
    for candidates in candidates_by_requirement.values():
        by_role: dict[str, list[dict]] = {}
        for c in candidates:
            by_role.setdefault(c["role"], []).append(c)
        for role_candidates in by_role.values():
            distinct_values = _fold(role_candidates, lambda c: (c["proposition_id"], c["exact_text"]))
            if len(distinct_values) >= 2 and distinct_values[0]["list_like"]:
                category_lists.append(_category_list_claim(distinct_values))
            else:
                standalone.extend(distinct_values)

    folded = _fold(
        standalone,
        lambda c: semantic_claim_key(
            claim_kind="role_value",
            role=c["role"],
            category_description=c["category_description"],
            proposition_id=c["proposition_id"],
            exact_text=c["exact_text"],
        ),
    )
    return [_role_value_claim(m) for m in folded] + category_lists


def _role_value_claim(member: dict) -> dict:
    return {
        "claim_kind": "role_value",
        "role": member["role"],
        "category_description": member["category_description"],
        "values": [
            {"proposition_id": member["proposition_id"], "exact_text": member["exact_text"], "role": member["role"]}
        ],
        "admissible_proposition_ids": set(member["admissible"]),
        "child_ids": set(member["child_ids"]),
        "requirement_ids": set(member["requirement_ids"]),
        "instance_keys": set(member["instance_keys"]),
        "model_dependency": {"any": member["model_dependent"], "stop_search_certified": member["cert"]},
        "direction_or_effectiveness": None,
        "conflict_or_heterogeneity": None,
    }


def _category_list_claim(members: list[dict]) -> dict:
    role, category_description = members[0]["role"], members[0]["category_description"]
    values, admissible, child_ids, requirement_ids, instance_keys = [], set(), set(), set(), set()
    model_dependent, cert = False, None
    for m in members:
        values.append({"proposition_id": m["proposition_id"], "exact_text": m["exact_text"], "role": role})
        admissible |= m["admissible"]
        child_ids |= m["child_ids"]
        requirement_ids |= m["requirement_ids"]
        instance_keys |= m["instance_keys"]
        model_dependent = model_dependent or m["model_dependent"]
        if cert is None:
            cert = m["cert"]
    return {
        "claim_kind": "category_list",
        "role": role,
        "category_description": category_description,
        "values": values,
        "admissible_proposition_ids": admissible,
        "child_ids": child_ids,
        "requirement_ids": requirement_ids,
        "instance_keys": instance_keys,
        "model_dependency": {"any": model_dependent, "stop_search_certified": cert},
        "direction_or_effectiveness": None,
        "conflict_or_heterogeneity": None,
    }


def _direction_or_effectiveness_claims(requirement, instance_list, child_id, cert) -> list[dict]:
    out = []
    for field, obs_key, _value_key in _DIRECTION_FIELDS:
        if requirement.get(field) is None:
            continue
        summary = requirement.get(f"{field}_summary")
        if summary is None:
            continue  # declared but the caller never ran compute_direction_and_effectiveness
        if not summary["instance_keys_with_observations"] and not summary["conflicted_instance_keys"]:
            continue  # nothing observed anywhere -- this becomes a gap, never a claim
        admissible: set = set()
        model_dependent = False
        contributing_instances = set(summary["instance_keys_with_observations"]) | set(
            summary["conflicted_instance_keys"]
        )
        for instance in instance_list:
            if instance["instance_key"] not in contributing_instances:
                continue
            for obs in instance.get(obs_key, []):
                # A direction claim is a RELATION claim (I3): its admissible propositions are the observations that count
                # toward the relation summary, never operand-level valence. Effectiveness is unfiltered.
                counts = se.counts_toward_relation_direction(obs) if field == "direction" else True
                if obs.get("proposition_id") and counts:
                    admissible.add(obs["proposition_id"])
            own_roles = se.own_evidence_roles(requirement["role_completion"], instance["role_bindings"])
            model_dependent = model_dependent or any(
                _binding_model_dependent(instance["role_bindings"][r]) for r in own_roles
            )
        out.append(
            {
                "claim_kind": "direction_or_effectiveness",
                "role": None,
                "category_description": None,
                "values": [],
                "admissible_proposition_ids": admissible,
                "child_ids": {child_id},
                "requirement_ids": {requirement["id"]},
                "instance_keys": set(contributing_instances),
                "model_dependency": {"any": model_dependent, "stop_search_certified": cert},
                "direction_or_effectiveness": {"field": field, **summary},
                "conflict_or_heterogeneity": {
                    "has_within_instance_conflict": summary["has_within_instance_conflict"],
                    "has_across_instance_heterogeneity": summary["has_across_instance_heterogeneity"],
                },
            }
        )
    return out


# ---------------------------------------------------------------------------------------------
# build_gap_report
# ---------------------------------------------------------------------------------------------

_GAP_FIELDS = (
    "target_id",
    "search_child_id",
    "requirement_id",
    "target_roles",
    "reason",
    "goal_mode",
    "category_descriptions",
)


def build_gap_report(sufficiency_recovery_targets: dict, sufficiency_map_final: dict | None = None) -> list[dict]:
    """``list[UnresolvedGap]`` from the FINAL ``{target_id: RecoveryTarget}`` inventory, one entry
    per ``target_id`` (already deduplicated upstream by ``sufficiency_recovery_targets.
    new_target_id``'s own content hash), sorted by ``target_id`` for deterministic output.

    Every target is reported exactly as the final RecoveryTarget inventory holds it. This function never suppresses a
    target itself. A zero-evidence deficit that a completed scoped search made terminal (Phase 27b) is already absent
    from that inventory, because ``sufficiency_recovery_targets.compute_recovery_targets`` omitted it upstream.

    ``sufficiency_map_final``, when supplied, is used ONLY as an integrity cross-check: every
    target's own ``requirement_id`` must resolve against SOME requirement in the map (a mismatch
    signals the two inputs were computed against different runs, a caller-side integration bug
    worth failing loudly on -- never a semantic question this function silently decides)."""
    if sufficiency_map_final is not None:
        known_requirement_ids = {
            req["id"] for contract in sufficiency_map_final.values() for req in contract["requirements"]
        }
        for target in sufficiency_recovery_targets.values():
            if target["requirement_id"] not in known_requirement_ids:
                raise ValueError(
                    f"build_gap_report: target {target['target_id']!r} names requirement_id "
                    f"{target['requirement_id']!r}, which does not resolve in the supplied "
                    "sufficiency_map_final -- the gap inventory and the map appear to come from "
                    "different runs."
                )
    gaps = [{field: target[field] for field in _GAP_FIELDS} for target in sufficiency_recovery_targets.values()]
    gaps.sort(key=lambda g: g["target_id"])
    return gaps


# ---------------------------------------------------------------------------------------------
# Identity hash of the authoritative input itself (for the construction record, Section 22)
# ---------------------------------------------------------------------------------------------


def sufficiency_map_hash(sufficiency_map_final: dict) -> str:
    """A canonical hash of the final sufficiency map this ledger was built from -- the same
    ``json.dumps(..., sort_keys=True)`` + SHA-256 discipline ``overview_audit.sealed_hash_of``/
    ``sufficiency_engine.contract_hash`` already use, applied to the whole per-child map so it is
    order-invariant over dict insertion order (Python dicts preserve insertion order, but ``{child_
    id: contract}``'s own insertion order carries no semantic meaning)."""
    canonical = json.dumps(sufficiency_map_final, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------
# Phase 27b: ResolvedEmptyOutcome -- a positive statement that a completed scoped search established no support.
#
# Deliberately NOT a ParentClaim (it asserts nothing about the literature) and NOT an UnresolvedGap (it is not
# outstanding). It is an epistemic/search outcome, projected deterministically from the final semantic map and the
# persisted scoped-search status. It never reaches the S2 realization prompt, and it is never derived from model prose
# or from RecoveryTarget absence alone.
# ---------------------------------------------------------------------------------------------

RESOLVED_EMPTY_OUTCOME = "searched_no_support_established"


def _category_descriptions(requirement: dict) -> list[str]:
    """Each completion role's own authored category description, in completion-role order, de-duplicated."""
    described: list[str] = []
    for role in se.completion_roles(requirement["role_completion"]):
        description = requirement["role_specs"][role]["category_description"]
        if description not in described:
            described.append(description)
    return described


def build_resolved_empty_outcomes(sufficiency_map_final: dict, terminal_status: dict | None) -> list[dict]:
    """One ``ResolvedEmptyOutcome`` per requirement that is zero-evidence terminal in the FINAL map AND whose persisted
    scoped-search status records a completed, terminal search. The map is re-checked here, so the status alone can
    never create an outcome for a requirement that still has support. Sorted by (child_id, requirement_id)."""
    status = terminal_status or {}
    outcomes = []
    for child_id in sorted(sufficiency_map_final):
        for requirement in sufficiency_map_final[child_id]["requirements"]:
            entry = status.get(requirement["id"])
            if not entry or not (entry.get("completed") and entry.get("terminal")):
                continue
            if not srt.is_zero_evidence_terminal(requirement):
                continue
            outcomes.append(
                {
                    "child_id": child_id,
                    "requirement_id": requirement["id"],
                    "category_descriptions": _category_descriptions(requirement),
                    "outcome": RESOLVED_EMPTY_OUTCOME,
                }
            )
    outcomes.sort(key=lambda o: (o["child_id"], o["requirement_id"]))
    return outcomes
