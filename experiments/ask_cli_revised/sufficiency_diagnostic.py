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
from experiments.ask_cli_revised import ownership_context as oc
from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised import sufficiency_mapping as sm


def units_by_child(sealed: dict, *, ownership_context_index=None) -> dict[str, list[dict]]:
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
    context_by_pid = (
        {r["proposition_id"]: oc.context_for(ownership_context_index, r) for r in sealed["verified_propositions"]}
        if ownership_context_index is not None
        else {}
    )
    units, _claims = oe.build_units(sealed)
    tagged_for_child: dict[str, set[str]] = {}
    anchor_by_proposition: dict[str, tuple] = {}
    passage_by_proposition = {row["proposition_id"]: row["quote"] for row in sealed["verified_propositions"]}
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
                {
                    **unit,
                    "proposition_ids": ordered,
                    "proposition_anchor": proposition_anchor,
                    # Exact quotes allow v5 to verify shared offset coordinates. No historical consumer reads this.
                    "proposition_passages": {pid: passage_by_proposition[pid] for pid in ordered},
                    **({"ownership_contexts": {pid: context_by_pid[pid] for pid in ordered}} if context_by_pid else {}),
                }
            )
    return by_child


def compute_diagnostic_sufficiency_map(
    sealed: dict,
    contract_by_child: dict,
    parent_of: dict,
    *,
    model_client=None,
    nomination_context: dict | None = None,
    semantics_version: str,
    ownership_context_index=None,
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

    `nomination_context` (Phase 19, default `None`, matching every existing caller including
    `e2e.py`): `child_id` is already this loop's own variable -- the one piece of identity a
    `requirement` dict never carries on its own (confirmed directly against `sufficiency_engine.
    new_requirement`'s return shape; only its owning `SufficiencyContract` does, via `new_contract`).
    Passing it straight into `map_any_requirement` is what lets the model-nomination checkpoint
    several calls deeper construct a real `(child_id, requirement_id, role)` scope, never one
    parsed back out of `requirement['id']`'s own `"childid#..."` naming convention (which is an
    authoring convention, not a structural guarantee). Omitted entirely, this function's
    behavior is unchanged."""
    se.require_supported_semantics_version(semantics_version)
    by_child = units_by_child(
        sealed,
        ownership_context_index=ownership_context_index
        if semantics_version in (se.SUFFICIENCY_SEMANTICS_V6, se.SUFFICIENCY_SEMANTICS_V7)
        else None,
    )
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
            mapped_req = sm.map_any_requirement(
                req,
                candidate_units,
                parent_requirement=parent_requirement,
                model_client=model_client,
                child_id=child_id,
                nomination_context=nomination_context,
                semantics_version=semantics_version,
            )
            new_requirements.append(_stamp_model_dependency_origins(mapped_req, child_id))
        mapped[child_id] = se.new_contract(child_id, new_requirements)
    # Phase 32 / I1: additive runtime witness metadata on relational instances. Adds keys only; `complete` and
    # every other field are untouched, and nothing downstream reads these keys yet. Phase 32 / I1d: written under the
    # current semantics version, which is also the version stamped below.
    rw.attach_relation_witnesses(mapped, sealed, semantics_version=semantics_version)
    # Phase 32 / I1c: the single stamping path for produced diagnostic maps (authored contracts are never stamped).
    si.stamp_map(mapped, semantics_version=semantics_version)
    return mapped


def _stamp_model_dependency_origins(requirement: dict, child_id: str) -> dict:
    """Pure; returns a NEW requirement. Stamps origin ONLY on a FRESH, un-propagated
    `model_mapping` binding -- one with no existing `model_dependency_origins` -- naming its own
    location (`{child_id, requirement_id, role, instance_key, request_context}`). A propagated
    `parent_context` binding already carries its origin forward via `sufficiency_mapping.
    _propagated_provenance` and is left untouched here.

    Called from THIS per-child loop (never from `sufficiency_mapping.py`, which is deliberately
    child-agnostic -- see that module's own "zero question/domain-specific vocabulary" charter)
    right after `map_any_requirement` returns, so each instance's FINAL `instance_key` is already
    known (`_rederive_keys_if_forked` only assigns it after every role has been bound). Because
    parent-less children are mapped (and thus stamped) first, a paired child's own
    `_propagated_provenance` call reads an ALREADY-stamped parent binding -- no extra ordering
    logic needed beyond the existing topological pass above.

    `requirement_id` global uniqueness is NOT an engine invariant (`sufficiency_engine.
    new_requirement`/`new_contract` validate nothing about it) -- `child_id` is therefore stamped
    explicitly rather than reconstructed later from a naming convention.

    Phase 22: `request_context` is read from the OWNING INSTANCE's own `request_context` field
    (`sufficiency_mapping.map_requirement`'s own pre-fork stamp, Phase 22) -- never from the
    binding itself (which never carries it) and never the final `instance_key` (which, per Phase
    19b's own established distinction, is NOT the same value once a role has forked). An instance
    produced by `map_paired_requirement`/`map_cardinality_requirement` simply has no
    `request_context` field at all, degrading correctly to `None` via `.get(...)` -- matching
    their own already-established `request_context=None` invariant exactly."""
    new_instances = []
    for instance in requirement["instances"]:
        bindings = dict(instance["role_bindings"])
        changed = False
        for role, binding in list(bindings.items()):
            provenance = binding.get("provenance") or {}
            if provenance.get("candidate_source") == "model_mapping" and not provenance.get("model_dependency_origins"):
                bindings[role] = {
                    **binding,
                    "provenance": {
                        **provenance,
                        "model_dependency_origins": [
                            {
                                "child_id": child_id,
                                "requirement_id": requirement["id"],
                                "role": role,
                                "instance_key": instance["instance_key"],
                                "request_context": instance.get("request_context"),
                            }
                        ],
                    },
                }
                changed = True
        new_instances.append({**instance, "role_bindings": bindings} if changed else instance)
    return {**requirement, "instances": new_instances}


def _instance_scoped_units(units_for_child: list[dict], unit_by_proposition: dict, witness_ids: set) -> list[dict]:
    """One shallow copy per UNIQUE physical unit touched by `witness_ids`, with `proposition_ids`
    narrowed to exactly the witness ids that unit actually contains (Phase 18) -- the unit's own
    `passage`/physical evidence fields pass through unchanged. A unit with no admissible overlap is
    dropped entirely, never included with an empty id list (never "include the whole unit because
    SOME id in it was admissible" -- a deduplicated unit can carry proposition ids that are NOT
    admissible for this instance, and those must not be allowed to supply this instance's own
    `proposition_id` provenance). Deterministically ordered by `unit_id` so the returned list --
    and every downstream observation set -- is order-invariant regardless of `witness_ids`' own
    iteration order or the per-child pool's own build order."""
    admissible_by_unit_id: dict[str, set] = {}
    unit_by_unit_id: dict[str, dict] = {}
    for pid in witness_ids:
        unit = unit_by_proposition.get(pid)
        if unit is None:
            continue
        admissible_by_unit_id.setdefault(unit["unit_id"], set()).add(pid)
        unit_by_unit_id[unit["unit_id"]] = unit
    scoped = [{**unit_by_unit_id[uid], "proposition_ids": sorted(ids)} for uid, ids in admissible_by_unit_id.items()]
    scoped.sort(key=lambda u: u["unit_id"])
    return scoped


def _require_matching_version(mapped_contract_by_child: dict, semantics_version: str) -> None:
    """A map already stamped with a version must be computed under that same version. Unstamped maps are unconstrained."""
    for child_id, contract in mapped_contract_by_child.items():
        recorded = contract.get(se.SEMANTICS_VERSION_KEY)
        if recorded is not None and recorded != semantics_version:
            raise si.SemanticsIdentityError(
                f"child {child_id!r} is stamped {recorded!r}; direction semantics {semantics_version!r} do not match it"
            )


def _bound_surfaces(req: dict, instance: dict) -> dict[str, str]:
    """Each required role's bound verbatim surface, for the shared direction-target classifier."""
    bindings = instance["role_bindings"]
    surfaces = {}
    for role in req["role_completion"]["required_roles"]:
        binding = bindings.get(role) or {}
        if binding.get("state") == "filled" and binding.get("exact_text"):
            surfaces[role] = binding["exact_text"]
    return surfaces


def _relation_witness_ids(instance: dict) -> frozenset | None:
    """The instance's relation witness set when its relation is witnessed under the applied version, else None."""
    if instance.get("relation_witnessed") is True:
        return frozenset(instance.get("witness_ids") or [])
    return None


def compute_direction_and_effectiveness(
    sealed: dict, mapped_contract_by_child: dict, *, semantics_version: str
) -> None:
    """Populates INSTANCE-level `direction_observations`/`effectiveness_observations` (Phase 18)
    on every instance of an already-mapped requirement that declares a `direction`/`effectiveness`
    template -- replaced from scratch every call, never append-accumulated (idempotent) -- using
    ONLY evidence that actually witnesses THAT instance's own jointly-grounded relationship
    (`sufficiency_engine.relationship_witness_support_ids`), never the whole child's undifferentiated
    pool (the Phase 17/18 defect: a requirement-level first-match scan could be hijacked by
    unrelated same-child evidence, or silently reflect whichever of a multi-instance requirement's
    instances happened to sit earliest in ledger order). Computed for EVERY instance regardless of
    completeness -- diagnostic metadata on a partial instance is still useful and visible -- but the
    derived `direction_summary`/`effectiveness_summary` requirement-level VIEW
    (`sufficiency_engine.summarize_observations`) is computed from COMPLETE instances only. The
    authored `direction`/`effectiveness` declaration/template on the requirement itself is NEVER
    touched here -- it stays exactly whatever `sufficiency_authoring`/`sufficiency_engine.
    new_requirement` set it to; the summary is a strictly separate, runtime-only key. Mutates the
    requirement/instance dicts IN PLACE (they are freshly built by `compute_diagnostic_sufficiency_
    map`, never the frozen contract Layer B authored) -- kept as a separate pass so the base
    role-completion mapping above stays simple and testable on its own.

    `semantics_version` selects the direction behaviour (I3): v1/v2 record the historical first-match behaviour, and v3 is
    target-aware, with a relation summary that counts only relation-eligible observations. It is required, and it must
    agree with a map that already carries a version. Effectiveness is identical under every version."""
    _require_matching_version(mapped_contract_by_child, semantics_version)
    by_child = units_by_child(sealed)
    for child_id, contract in mapped_contract_by_child.items():
        units_for_child = by_child.get(child_id, [])
        unit_by_proposition = {pid: unit for unit in units_for_child for pid in unit["proposition_ids"]}
        for req in contract["requirements"]:
            has_direction = req.get("direction") is not None
            has_effectiveness = req.get("effectiveness") is not None
            if not has_direction and not has_effectiveness:
                continue
            for instance in req["instances"]:
                witness_ids = se.relationship_witness_support_ids(
                    req["role_completion"], instance["role_bindings"], req["relationship_verifiers"]
                )
                instance_units = _instance_scoped_units(units_for_child, unit_by_proposition, witness_ids)
                if has_direction:
                    instance["direction_observations"] = sm.find_direction_observations(
                        req,
                        instance_units,
                        semantics_version=semantics_version,
                        operands=_bound_surfaces(req, instance),
                        relation_witness_ids=_relation_witness_ids(instance),
                    )
                if has_effectiveness:
                    instance["effectiveness_observations"] = sm.find_effectiveness_observations(req, instance_units)
            if has_direction:
                req["direction_summary"] = se.summarize_observations(
                    req["instances"],
                    "direction_observations",
                    "sign",
                    observation_filter=se.counts_toward_relation_direction,
                )
            if has_effectiveness:
                req["effectiveness_summary"] = se.summarize_observations(
                    req["instances"], "effectiveness_observations", "conclusion"
                )


# `compute_recovery_candidates` (the child-level `{child_id: [requirement_id, ...]}` boolean
# collapse Phase 11's own audit found sufficiency-blind) is retired -- replaced outright by
# `sufficiency_recovery_targets.compute_recovery_targets`, which this module's own
# `_stamp_model_dependency_origins` above directly feeds.
