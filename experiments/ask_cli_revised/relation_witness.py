"""Phase 32 / I1 -- additive relation-witness metadata (runtime only; zero semantic behaviour change).

Implements the Phase-31 audit section 7 invariant for RELATIONAL instances, defined as instances of a requirement
with two or more required roles (the same instance set the answer layer's relation units cover).

Writes three runtime fields onto each relational instance, and nothing else:

    relation_witnessed : bool
    witness_ids        : sorted proposition ids that witness the relation (empty unless witnessed)
    witness_provenance : deterministic record of WHY the relation is or is not witnessed

Non-relational instances receive none of these keys. ``complete`` is neither read nor written here, and no
existing field is modified. Nothing downstream consumes the new fields in I1: parent eligibility, recovery,
stop-search, mapping, direction/effectiveness, ParentClaim construction, answerability, rendering and search are
unaffected. The Phase-30 answer-layer witness (``answer_plan.relations``) remains the answer authority; it is only
cross-checked against these fields in tests.

Operand source (Phase-31 section 7):
- OWN operand: binding source is not ``parent_context``. Its admissible support set is witness support.
- INHERITED operand: binding source is ``parent_context``. It supplies referent identity only. Its parent
  proposition ids are never witness support.

Witness rule for a relational instance:
- ``relation_witnessed`` iff at least one OWN operand exists AND one admissible verified proposition ``p`` satisfies
  every OWN operand by support membership AND contains every INHERITED referent surface (canonical containment of the
  parent binding's verbatim ``exact_text``; I1 deliberately does not normalise it).
- The all-inherited guard: with no OWN operand the relation is never witnessed, however the inherited surfaces co-occur.
- No distributed witness: a single ``p`` must satisfy all operands. Two propositions cannot jointly witness.
- Admissibility: a candidate must be a sealed verified proposition. A continuation join is admissible only when every
  one of its recorded anchors is verbatim (existing Stage-A verification). An unverified join is never a witness.
- Model nomination is never a witness; this module reads only sealed propositions and bindings.
"""

from __future__ import annotations

import copy

from app.backend.pdf_processing.extraction import canonical_text_contains

RULE = "operand_source_witness"  # a descriptive label for audit, not a semantic version
PARENT_CONTEXT = "parent_context"
I1_FIELDS = ("relation_witnessed", "witness_ids", "witness_provenance")

# Failure reasons, most specific first. None means witnessed.
FAILURE_REASONS = (
    "incomplete_operands",  # a required operand is not filled
    "no_own_operand",  # every operand is inherited; identity cannot be evidence
    "no_single_proposition",  # OWN operands share no proposition
    "no_admissible_candidate",  # shared proposition(s) exist but none is admissible
    "inherited_referent_absent",  # admissible candidates exist; none contains every inherited referent
)


def is_relational(requirement: dict) -> bool:
    """Structural definition shared with the answer layer's relation units: two or more required roles."""
    return len(requirement["role_completion"]["required_roles"]) >= 2


def operand_source(binding: dict) -> str:
    provenance = binding.get("provenance") or {}
    return "inherited" if provenance.get("candidate_source") == PARENT_CONTEXT else "own"


def _support_ids(binding: dict) -> frozenset[str]:
    """Primary proposition id plus any collapsed supporting ids. Deliberately an independent copy of the engine's
    support-set helper, so the cross-check against the answer layer is not circular."""
    provenance = binding.get("provenance") or {}
    ids = set(provenance.get("supporting_proposition_ids") or [])
    if binding.get("proposition_id") is not None:
        ids.add(binding["proposition_id"])
    return frozenset(ids)


def is_admissible(proposition: dict | None) -> bool:
    """A sealed verified proposition, whose continuation join (if any) carries only verbatim, verified anchors."""
    if proposition is None or not proposition.get("quote"):
        return False
    if (proposition.get("verification") or {}).get("status") != "verified":
        return False
    anchors = proposition.get("anchors")
    if anchors:
        return all(anchor.get("verbatim") is True for anchor in anchors)
    return True


def _referent_present(surface: str | None, quote: str) -> bool:
    if not surface:
        return False
    return canonical_text_contains(needle=surface, haystack=quote)


def witness_instance(requirement: dict, instance: dict, proposition_by_id: dict[str, dict]) -> dict:
    """The I1 fields for one relational instance. Pure: reads the requirement, instance and sealed propositions."""
    required = sorted(requirement["role_completion"]["required_roles"])
    bindings = instance["role_bindings"]
    sources = {role: operand_source(bindings.get(role) or {}) for role in required}
    own_roles = [role for role in required if sources[role] == "own"]
    inherited_roles = [role for role in required if sources[role] == "inherited"]
    provenance: dict = {
        "rule": RULE,
        "own_roles": own_roles,
        "inherited_roles": inherited_roles,
        "own_support": {},
        "inherited_referents": {},
        "candidate_ids": [],
        "candidate_checks": [],
        "failure_reason": None,
    }

    def _finish(reason: str | None, witness_ids: list[str] | None = None) -> dict:
        provenance["failure_reason"] = reason
        return {
            "relation_witnessed": reason is None,
            "witness_ids": witness_ids or [],
            "witness_provenance": provenance,
        }

    if any((bindings.get(role) or {}).get("state") != "filled" for role in required):
        return _finish("incomplete_operands")
    for role in inherited_roles:
        provenance["inherited_referents"][role] = bindings[role].get("exact_text")
    if not own_roles:
        return _finish("no_own_operand")
    for role in own_roles:
        provenance["own_support"][role] = sorted(_support_ids(bindings[role]))
    shared = frozenset.intersection(*(_support_ids(bindings[role]) for role in own_roles))
    provenance["candidate_ids"] = sorted(shared)
    if not shared:
        return _finish("no_single_proposition")

    admissible_witnesses: list[str] = []
    any_admissible = False
    for pid in sorted(shared):
        proposition = proposition_by_id.get(pid)
        admissible = is_admissible(proposition)
        check: dict = {"proposition_id": pid, "admissible": admissible, "inherited_referent_present": {}}
        if admissible:
            any_admissible = True
            quote = proposition["quote"]
            for role in inherited_roles:
                check["inherited_referent_present"][role] = _referent_present(bindings[role].get("exact_text"), quote)
            if all(check["inherited_referent_present"].values()):
                admissible_witnesses.append(pid)
        provenance["candidate_checks"].append(check)
    if not any_admissible:
        return _finish("no_admissible_candidate")
    if not admissible_witnesses:
        return _finish("inherited_referent_absent")
    return _finish(None, admissible_witnesses)


def attach_relation_witnesses(mapped: dict, sealed: dict) -> None:
    """Write the I1 fields onto every relational instance of every mapped contract, in place. Adds keys only."""
    proposition_by_id = {row["proposition_id"]: row for row in sealed.get("verified_propositions", [])}
    for contract in mapped.values():
        for requirement in contract["requirements"]:
            if not is_relational(requirement):
                continue
            for instance in requirement["instances"]:
                instance.update(witness_instance(requirement, instance, proposition_by_id))


def project_out_i1(smap: dict) -> dict:
    """A deep copy with ONLY the I1 fields removed from instances. Used for projection parity."""
    projected = copy.deepcopy(smap)
    for contract in projected.values():
        for requirement in contract["requirements"]:
            for instance in requirement["instances"]:
                for key in I1_FIELDS:
                    instance.pop(key, None)
    return projected
