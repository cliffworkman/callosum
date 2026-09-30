"""Diagnostic sufficiency-mapping orchestration: ties Layer A (`sufficiency_engine`) and the
deterministic mapper (`sufficiency_mapping`) to a real sealed hierarchical ledger. Deterministic
only -- no model. Pure with respect to its inputs; never mutates the sealed ledger, never writes
a trace file itself (the caller, `e2e.py`, owns that).

This is the (A) "diagnostic sufficiency assessment" of the design doc: it always runs, once a
frozen sufficiency contract is supplied, independent of whether any model-assisted nomination
role is ever bound -- see `compute_diagnostic_sufficiency_map`. Sufficiency-driven RECOVERY
GATING, the (B) concern, stays a strictly separate, explicitly opt-in decision the caller makes
(see `e2e.py`'s own `sufficiency_recovery_gate_enabled` parameter) -- this module never decides
that on its own.
"""

from __future__ import annotations

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm


def units_by_child(sealed: dict) -> dict[str, list[dict]]:
    """``{child_id: [unit, ...]}`` -- units whose ``attached_children`` include that child, in
    ``overview_evidence.build_units``'s own first-restating-claim order. `attached_children` is
    the coverage authority's own topical judgment (already computed elsewhere in the pipeline);
    this module never re-derives or second-guesses it -- it only reads which candidate units a
    child is even eligible to consider.

    `build_units` dedupes by (paper_id, passage text): an identical passage independently
    retrieved and tagged responsive under several different children collapses into ONE unit
    whose `proposition_ids` mixes propositions from all of them. Citing `proposition_ids[0]`
    blind would cite an arbitrary sibling proposition -- one that was never itself judged
    responsive to THIS child -- merely because it happened to be inserted into the shared unit
    first. Each child's own view of a shared unit therefore reorders `proposition_ids` so a
    proposition actually tagged responsive to THAT child is cited first (the underlying text is
    identical either way, so this only affects which proposition_id is on record, not what
    evidence is used).

    Each returned unit additionally carries `proposition_anchor`: `{proposition_id: (paper_id,
    chunk_id, span_id)}` for every proposition folded into that unit, read directly from `sealed`'s
    own `verified_propositions` rows -- the same physical-locator fields `overview_evidence.
    build_units` itself reads to compute a unit's own `locators`. This is the established
    coordinate identity (never an invented parallel one); it exists so a model-nomination-path
    consumer (`sufficiency_mapping.nominate_with_model`) can tell whether two DIFFERENT
    proposition_ids sharing one unit's (deduped-by-TEXT) passage are also the SAME physical anchor
    -- they are not always: a unit can pool propositions from more than one chunk/span whose text
    happens to be identical (confirmed live in the Phase 2 diagnostic's own Finding 2). A
    proposition missing from `sealed` is simply absent from this map, never guessed.
    """
    units, _claims = oe.build_units(sealed)
    tagged_for_child: dict[str, set[str]] = {}
    anchor_by_proposition: dict[str, tuple] = {}
    for row in sealed["verified_propositions"]:
        for child_id in row.get("responsive_obligation_ids", []):
            tagged_for_child.setdefault(child_id, set()).add(row["proposition_id"])
        anchor_by_proposition[row["proposition_id"]] = (
            row["paper_id"],
            row["evidence_anchor_chunk_id"],
            row["evidence_span_id"],
        )

    by_child: dict[str, list[dict]] = {}
    for unit in units:
        proposition_anchor = {
            pid: anchor_by_proposition[pid] for pid in unit["proposition_ids"] if pid in anchor_by_proposition
        }
        for child_id in unit["attached_children"]:
            own_ids = tagged_for_child.get(child_id, set())
            ordered = [pid for pid in unit["proposition_ids"] if pid in own_ids] + [
                pid for pid in unit["proposition_ids"] if pid not in own_ids
            ]
            by_child.setdefault(child_id, []).append(
                {**unit, "proposition_ids": ordered, "proposition_anchor": proposition_anchor}
            )
    return by_child


def compute_diagnostic_sufficiency_map(
    sealed: dict, contract_by_child: dict, parent_of: dict, *, model_client=None
) -> dict:
    """`contract_by_child`: `{child_id: SufficiencyContract}` (Layer B's frozen instance, e.g.
    `sufficiency_authoring.build_qaib_contract(...)`). `parent_of`: `{child_id: parent_child_id}`,
    read from the SAME approved hierarchy contract's own `child["parent"]` field -- never
    invented here. Returns `{child_id: SufficiencyContract}` with every requirement's `instances`/
    `state` recomputed against `sealed`'s own verified propositions/evidence.

    `model_client` (default `None`, matching every existing caller including `e2e.py`) is threaded
    through to `sufficiency_mapping.map_any_requirement` for every child. Because children with no
    `parent_context_roles` are mapped FIRST (see below), a parent's own model-assisted instances
    -- not just its deterministic ones -- are already fully resolved by the time a paired child
    (e.g. c9 pairing against c8) reads them; no separate propagation step exists or is needed, the
    SAME topological ordering that already served the deterministic-only case does this for free.

    Children with no `parent_context_roles` on any requirement are mapped first, so a parent's
    own discovered instances are available by the time a paired child needs them (q_aib's own
    hierarchy is exactly two levels deep, so one ordering pass suffices; a deeper future
    hierarchy would need a topological sort here, not built since q_aib doesn't require it).
    """
    by_child = units_by_child(sealed)
    mapped: dict[str, dict] = {}
    child_ids = list(contract_by_child)
    no_parent_context = [
        cid for cid in child_ids if not any(r["parent_context_roles"] for r in contract_by_child[cid]["requirements"])
    ]
    with_parent_context = [cid for cid in child_ids if cid not in no_parent_context]

    for child_id in no_parent_context + with_parent_context:
        contract = contract_by_child[child_id]
        candidate_units = by_child.get(child_id, [])
        new_requirements = []
        for req in contract["requirements"]:
            parent_requirement = None
            if req["parent_context_roles"]:
                role = req["parent_context_roles"][0]
                parent_child_id = parent_of.get(child_id)
                parent_contract = mapped.get(parent_child_id) if parent_child_id else None
                if parent_contract is not None:
                    parent_requirement = next(
                        (r for r in parent_contract["requirements"] if role in r["role_specs"]), None
                    )
                if parent_requirement is None:
                    # Fail loudly, never silently fall through to the generic (non-paired) mapper:
                    # that fallback is exactly what let a role-name mismatch between a child and
                    # its declared parent go undetected until the real preserved-run replay caught
                    # it (see sufficiency_authoring.py's own comment on c9's role naming).
                    raise ValueError(
                        f"{req['id']!r} declares parent_context_roles={req['parent_context_roles']!r} but no "
                        f"requirement named {role!r} was found on parent child {parent_child_id!r} "
                        f"(parent_of={parent_of!r}, mapped so far={sorted(mapped)!r}) -- check role-name "
                        "agreement between the child and its parent, and that the parent was mapped first."
                    )
            new_requirements.append(
                sm.map_any_requirement(
                    req, candidate_units, parent_requirement=parent_requirement, model_client=model_client
                )
            )
        mapped[child_id] = se.new_contract(child_id, new_requirements)
    return mapped


def compute_direction_and_effectiveness(sealed: dict, mapped_contract_by_child: dict) -> None:
    """Populates `direction`/`effectiveness` on every already-mapped requirement that declares
    one, scanning the same per-child candidate units. Mutates the requirement dicts IN PLACE
    (they are freshly built by `compute_diagnostic_sufficiency_map`, never the frozen contract
    Layer B authored) -- kept as a separate pass so the base role-completion mapping above stays
    simple and testable on its own."""
    by_child = units_by_child(sealed)
    for child_id, contract in mapped_contract_by_child.items():
        candidate_units = by_child.get(child_id, [])
        for req in contract["requirements"]:
            if req.get("direction") is not None:
                req["direction"] = sm.map_direction(req, candidate_units)
            if req.get("effectiveness") is not None:
                req["effectiveness"] = sm.map_effectiveness(req, candidate_units)


def compute_recovery_candidates(mapped_contract_by_child: dict) -> dict[str, list[str]]:
    """`{child_id: [requirement_id, ...]}` for every requirement that WOULD trigger recovery
    right now, under a fresh (budget-not-yet-exhausted) `SearchStatus` -- i.e. "what would
    trigger recovery if the sufficiency-driven recovery gate were enabled", independent of
    whether it actually is. Never mutates anything; a pure read over already-mapped
    requirements."""
    candidates: dict[str, list[str]] = {}
    for child_id, contract in mapped_contract_by_child.items():
        for req in contract["requirements"]:
            status = se.new_search_status(req["id"])
            if se.compute_recovery_needed(req, status):
                candidates.setdefault(child_id, []).append(req["id"])
    return candidates
