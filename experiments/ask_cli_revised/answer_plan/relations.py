"""Relation units and the answer layer's relation-witness status (Phase-30 D3, aligned in Phase 32 / I1a).

The witness semantics are the authoritative Phase-31 section-7 semantics, implemented once in
``relation_witness.witness_instance``. This module adapts sealed inputs to that shared function. It does not carry a
second copy of the rule.

Two properties are kept separate:

- ``witness_ids`` / the derived witness: a structural evidentiary property of the relation (section 7).
- ``status == "witnessed"``: renderability. It also requires every operand to be filled and the engine's ``complete``
  flag to hold. A witnessed but incomplete relation is never renderable.

Upstream witness metadata written by the mapping stage (``relation_witnessed``, ``witness_ids``,
``witness_provenance``) is validated against this derivation, never trusted blindly. A tampered, stale or malformed
record fails closed: the unit is marked ``metadata_check`` and is not renderable. Historical maps without the fields
follow the same derivation.

The engine's ``complete`` flag is recorded, never replaced.
"""

from __future__ import annotations

from experiments.ask_cli_revised import relation_witness as rw

# Operand source labels in the unit JSON. Kept as the historical strings so the emitted answer plan is unchanged.
_SOURCE_LABEL = {"own": "own", "inherited": "parent_context"}
_METADATA_ANOMALIES = ("disagrees", "malformed")


def _operand_source_label(binding: dict) -> str:
    return _SOURCE_LABEL[rw.operand_source(binding)]


def _stored_metadata_check(instance: dict, derived: dict) -> str | None:
    """None when no upstream metadata is present or it agrees. Otherwise ``malformed`` or ``disagrees``."""
    has_flag = "relation_witnessed" in instance
    has_ids = "witness_ids" in instance
    if not has_flag and not has_ids:
        return None
    flag = instance.get("relation_witnessed")
    ids = instance.get("witness_ids")
    well_formed = (
        has_flag
        and has_ids
        and isinstance(flag, bool)
        and isinstance(ids, list)
        and all(isinstance(pid, str) for pid in ids)
    )
    if not well_formed:
        return "malformed"
    provenance = instance.get("witness_provenance")
    stored_reason = provenance.get("failure_reason") if isinstance(provenance, dict) else None
    if (
        flag == derived["relation_witnessed"]
        and sorted(ids) == derived["witness_ids"]
        and stored_reason == derived["witness_provenance"]["failure_reason"]
    ):
        return None
    return "disagrees"


def relation_units(smap: dict, sealed: dict, *, semantics_version: str) -> list[dict]:
    """One unit per (requirement, instance) of every requirement that requires two or more roles.

    ``semantics_version`` selects the inherited-referent containment rule (Phase 32 / I1d). It is required: the caller
    decides which rule applies (see replay: the map's own version, or the contemporary rule applied explicitly)."""
    proposition_by_id = {row["proposition_id"]: row for row in sealed.get("verified_propositions", [])}
    units: list[dict] = []
    for child in sorted(smap):
        for requirement in smap[child]["requirements"]:
            required = list(requirement["role_completion"]["required_roles"])
            if len(required) < 2:
                continue
            for instance in requirement["instances"]:
                bindings = instance["role_bindings"]
                operands = []
                for role in required:
                    binding = bindings.get(role) or {}
                    if binding.get("state") != "filled":
                        continue
                    operands.append(
                        {
                            "role": role,
                            "source": _operand_source_label(binding),
                            "proposition_id": binding.get("proposition_id"),
                            "exact_text": binding.get("exact_text"),
                            "support": sorted(rw.support_ids(binding)),
                        }
                    )
                engine_complete = bool(instance.get("complete"))
                all_filled = len(operands) == len(required)
                derived = rw.witness_instance(
                    requirement, instance, proposition_by_id, semantics_version=semantics_version
                )
                witnessed = derived["relation_witnessed"]
                if not all_filled:
                    status = "incomplete"
                elif witnessed and engine_complete:
                    status = "witnessed"
                elif witnessed:
                    status = "incomplete"
                elif engine_complete:
                    status = "unwitnessed_complete"
                else:
                    status = "incomplete"
                unit = {
                    "child_id": child,
                    "requirement_id": requirement["id"],
                    "instance_key": instance["instance_key"],
                    "engine_complete": engine_complete,
                    "required_roles": required,
                    "operands": operands,
                    "parent_context_operand_roles": [op["role"] for op in operands if op["source"] == "parent_context"],
                    "witness_ids": derived["witness_ids"],
                    "status": status,
                }
                check = _stored_metadata_check(instance, derived)
                if check in _METADATA_ANOMALIES:
                    # Fail closed: contradictory or malformed upstream metadata makes the unit non-renderable.
                    unit["metadata_check"] = check
                    unit["status"] = "incomplete"
                units.append(unit)
    return units


def requirement_relation_status(units: list[dict], requirement_id: str) -> str | None:
    """Best status over a requirement's instances: witnessed beats unwitnessed_complete beats incomplete."""
    mine = [unit for unit in units if unit["requirement_id"] == requirement_id]
    if not mine:
        return None
    statuses = {unit["status"] for unit in mine}
    for status in ("witnessed", "unwitnessed_complete", "incomplete"):
        if status in statuses:
            return status
    return None


def claim_witnessed(units: list[dict], claim: dict) -> bool:
    """A relational ParentClaim is witnessed only if some instance it was built from is renderable as witnessed:
    every required operand filled, the section-7 witness present, and the engine's complete flag set."""
    keys = set(claim.get("instance_keys") or [])
    return any(
        unit["status"] == "witnessed"
        and unit["instance_key"] in keys
        and unit["requirement_id"] in claim["requirement_ids"]
        for unit in units
    )


def unit_for(units: list[dict], claim: dict) -> dict | None:
    keys = set(claim.get("instance_keys") or [])
    for unit in units:
        if unit["instance_key"] in keys and unit["requirement_id"] in claim["requirement_ids"]:
            return unit
    return None
