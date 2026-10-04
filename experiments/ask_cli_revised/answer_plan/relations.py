"""Relation units and the answer layer's own joint-witness test (Phase-30 D3). Pure: reads the sufficiency map only.

The engine's `complete` flag is recorded, never replaced. The answer layer independently requires that one admissible
proposition support EVERY required operand, including operands inherited from the parent context. Where the two
disagree, the unit is `unwitnessed_complete` and that disagreement is Layer-3 provenance.
"""

from __future__ import annotations


def support_ids(binding: dict) -> set[str]:
    """The proposition support a binding represents: its primary proposition plus any collapsed supporting ids. Mirrors
    the sufficiency engine's support-set formula; reimplemented here so the answer layer does not reach into a private."""
    provenance = binding.get("provenance") or {}
    ids = set(provenance.get("supporting_proposition_ids") or [])
    if binding.get("proposition_id") is not None:
        ids.add(binding["proposition_id"])
    return ids


def operand_source(binding: dict) -> str:
    provenance = binding.get("provenance") or {}
    return "parent_context" if provenance.get("candidate_source") == "parent_context" else "own"


def relation_units(smap: dict) -> list[dict]:
    """One unit per (requirement, instance) of every requirement that requires two or more roles."""
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
                            "source": operand_source(binding),
                            "proposition_id": binding.get("proposition_id"),
                            "exact_text": binding.get("exact_text"),
                            "support": sorted(support_ids(binding)),
                        }
                    )
                engine_complete = bool(instance.get("complete"))
                all_filled = len(operands) == len(required)
                witness: set[str] = set()
                if all_filled and operands and all(op["support"] for op in operands):
                    witness = set.intersection(*(set(op["support"]) for op in operands))
                if not all_filled:
                    status = "incomplete"
                elif witness and engine_complete:
                    status = "witnessed"
                elif engine_complete:
                    status = "unwitnessed_complete"
                else:
                    status = "incomplete"
                units.append(
                    {
                        "child_id": child,
                        "requirement_id": requirement["id"],
                        "instance_key": instance["instance_key"],
                        "engine_complete": engine_complete,
                        "required_roles": required,
                        "operands": operands,
                        "parent_context_operand_roles": [
                            op["role"] for op in operands if op["source"] == "parent_context"
                        ],
                        "witness_ids": sorted(witness),
                        "status": status,
                    }
                )
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
    """A relational ParentClaim is witnessed only if some instance it was built from has a joint witness over every
    required operand (own and inherited)."""
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
