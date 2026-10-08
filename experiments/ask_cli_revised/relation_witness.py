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
unaffected. The answer layer (``answer_plan.relations``) derives witnesses through this module's
``witness_instance`` and validates any stored metadata against that derivation (Phase 32 / I1a).

Operand source (Phase-31 section 7):
- OWN operand: binding source is not ``parent_context``. Its admissible support set is witness support.
- INHERITED operand: binding source is ``parent_context``. It supplies referent identity only. Its parent
  proposition ids are never witness support.

Witness rule for a relational instance:
- ``relation_witnessed`` iff at least one OWN operand exists AND one admissible verified proposition ``p`` satisfies
  every OWN operand by support membership AND contains every INHERITED referent surface (canonical containment of the
  parent binding's verbatim ``exact_text``). The containment predicate is version-dispatched (I1d): v1 is
  case-sensitive, v2 (current) folds case on both sides. Nothing else is normalised by either version.
- The all-inherited guard: with no OWN operand the relation is never witnessed, however the inherited surfaces co-occur.
- No distributed witness: a single ``p`` must satisfy all operands. Two propositions cannot jointly witness.
- Admissibility: a candidate must be a sealed verified proposition. A continuation join is admissible only when every
  one of its recorded anchors is verbatim (existing Stage-A verification). An unverified join is never a witness.
- Model nomination is never a witness; this module reads only sealed propositions and bindings.
"""

from __future__ import annotations

import copy

from app.backend.pdf_processing.extraction import canonical_text_contains
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si

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


def support_ids(binding: dict) -> frozenset[str]:
    """Primary proposition id plus any collapsed supporting ids. The single support definition used by both the
    mapping-stage metadata and the answer layer (Phase 32 / I1a removed the answer layer's separate copy)."""
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


def _contains_case_sensitive(surface: str, quote: str) -> bool:
    """sufficiency-semantics-v1 (I1c): canonical containment exactly as I1 applied it."""
    return canonical_text_contains(needle=surface, haystack=quote)


def _contains_case_insensitive(surface: str, quote: str) -> bool:
    """sufficiency-semantics-v2 (I1d): the same canonical containment, applied to Unicode case-folded forms of BOTH
    sides. Changes casing only: no whitespace, punctuation, hyphenation, morphology, alias or paraphrase normalisation
    is added here."""
    return canonical_text_contains(needle=surface.casefold(), haystack=quote.casefold())


# The one place the inherited-referent predicate varies by semantics version. The witness algorithm is the same for
# every version. An unknown version has no rule and fails closed (see referent_present).
_REFERENT_CONTAINMENT = {
    se.SUFFICIENCY_SEMANTICS_V1: _contains_case_sensitive,
    se.SUFFICIENCY_SEMANTICS_V2: _contains_case_insensitive,
    # v3 (I3) changes direction semantics only; its referent containment is the v2 rule.
    se.SUFFICIENCY_SEMANTICS_V3: _contains_case_insensitive,
    # v4 changes category semantics only; referent containment is the v2/v3 rule.
    se.SUFFICIENCY_SEMANTICS_V4: _contains_case_insensitive,
    # v5 (I4-2a) changes achieved-outcome mapping only; referent containment is the v2/v3/v4 rule, unchanged.
    se.SUFFICIENCY_SEMANTICS_V5: _contains_case_insensitive,
}


def referent_present(surface: str | None, quote: str, *, semantics_version: str) -> bool:
    """Whether the inherited referent ``surface`` is contained in ``quote`` under the named semantics version."""
    try:
        contains = _REFERENT_CONTAINMENT[semantics_version]
    except KeyError:
        raise si.SemanticsIdentityError(
            f"no inherited-referent containment rule for sufficiency-semantics version {semantics_version!r}"
        ) from None
    if not surface:
        return False
    return contains(surface, quote)


def witness_instance(
    requirement: dict, instance: dict, proposition_by_id: dict[str, dict], *, semantics_version: str
) -> dict:
    """The I1 fields for one relational instance. Pure: reads the requirement, instance and sealed propositions.

    ``semantics_version`` selects the inherited-referent containment rule (I1d). It is required, never defaulted, so a
    caller cannot silently apply one version's behaviour under another's identity."""
    if semantics_version not in _REFERENT_CONTAINMENT:
        raise si.SemanticsIdentityError(
            f"no inherited-referent containment rule for sufficiency-semantics version {semantics_version!r}"
        )
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
        provenance["own_support"][role] = sorted(support_ids(bindings[role]))
    shared = frozenset.intersection(*(support_ids(bindings[role]) for role in own_roles))
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
                check["inherited_referent_present"][role] = referent_present(
                    bindings[role].get("exact_text"), quote, semantics_version=semantics_version
                )
            if all(check["inherited_referent_present"].values()):
                admissible_witnesses.append(pid)
        provenance["candidate_checks"].append(check)
    if not any_admissible:
        return _finish("no_admissible_candidate")
    if not admissible_witnesses:
        return _finish("inherited_referent_absent")
    return _finish(None, admissible_witnesses)


def attach_relation_witnesses(mapped: dict, sealed: dict, *, semantics_version: str) -> None:
    """Write the I1 fields onto every relational instance of every mapped contract, in place. Adds keys only.

    ``semantics_version`` is required: production passes the current version, and a historical reproduction passes the
    version it reproduces (I1d)."""
    proposition_by_id = {row["proposition_id"]: row for row in sealed.get("verified_propositions", [])}
    for contract in mapped.values():
        for requirement in contract["requirements"]:
            if not is_relational(requirement):
                continue
            for instance in requirement["instances"]:
                instance.update(
                    witness_instance(requirement, instance, proposition_by_id, semantics_version=semantics_version)
                )


def project_out_i1(smap: dict) -> dict:
    """A deep copy with ONLY the I1 fields removed from instances. Used for projection parity."""
    projected = copy.deepcopy(smap)
    for contract in projected.values():
        for requirement in contract["requirements"]:
            for instance in requirement["instances"]:
                for key in I1_FIELDS:
                    instance.pop(key, None)
    return projected
