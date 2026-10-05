"""Phase 32 / I1a: the answer layer's relation units implement the authoritative section-7 witness semantics.

All fixtures are generic (alpha/beta) and reuse the builders in ``test_relation_witness`` rather than duplicating them.
Expected values are written by hand from the section-7 rules. They are not read back from either implementation.
The preserved-artifact checks are the only place preserved identifiers appear, and they skip when the gitignored
artifacts are absent.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised.answer_plan import relations as rel
from experiments.ask_cli_revised.test_relation_witness import (
    _as_smap,
    _case1,
    _case2,
    _case3,
    _case4,
    _case5,
    _case6,
    _inherited,
    _own,
    _prop,
    _relational,
)


def _unit(bindings, props, *, engine_complete: bool = True) -> dict:
    requirement, instance = _relational(bindings)
    instance["complete"] = engine_complete
    sealed = {"verified_propositions": props}
    return rel.relation_units(_as_smap(requirement, instance), sealed)[0]


def _claim(unit: dict) -> dict:
    return {"instance_keys": [unit["instance_key"]], "requirement_ids": [unit["requirement_id"]]}


# ---------------------------------------------------------------------------------------------------------------------
# semantics, hand-written expectations
# ---------------------------------------------------------------------------------------------------------------------


def test_own_plus_inherited_relation_is_witnessed_and_renderable():
    bindings, props = _case1()
    unit = _unit(bindings, props)
    assert unit["witness_ids"] == ["C1"]
    assert unit["status"] == "witnessed"


def test_inherited_referent_absent_from_the_child_proposition_is_not_witnessed():
    bindings, props = _case2()
    unit = _unit(bindings, props)
    assert unit["witness_ids"] == []
    assert unit["status"] == "unwitnessed_complete"


def test_parent_proposition_with_both_operands_is_not_evidentiary_support():
    bindings, props = _case3()
    unit = _unit(bindings, props)
    assert "P3" not in unit["witness_ids"]
    assert unit["witness_ids"] == []
    assert unit["status"] == "unwitnessed_complete"


def test_distributed_propositions_do_not_witness_the_relation():
    bindings, props = _case4()
    unit = _unit(bindings, props)
    assert unit["witness_ids"] == []
    assert unit["status"] == "unwitnessed_complete"


def test_two_own_operands_in_separate_propositions_do_not_witness():
    bindings = [_own("measure_y", "C2", "beta score"), _own("measure_z", "C3", "gamma score")]
    props = [_prop("C2", "beta score rose."), _prop("C3", "gamma score rose.")]
    unit = _unit(bindings, props)
    assert unit["witness_ids"] == []
    assert unit["status"] == "unwitnessed_complete"


def test_verified_joined_proposition_witnesses():
    bindings, props = _case5(True)
    unit = _unit(bindings, props)
    assert unit["witness_ids"] == ["J"]
    assert unit["status"] == "witnessed"


def test_unverified_join_does_not_witness():
    bindings, props = _case5(False)
    unit = _unit(bindings, props)
    assert unit["witness_ids"] == []
    assert unit["status"] == "unwitnessed_complete"


def test_all_inherited_shared_parent_relation_does_not_witness():
    bindings = [_inherited("entity_x", "P1", "alpha signal"), _inherited("measure_y", "P1", "beta score")]
    props = [_prop("P1", "The alpha signal predicted the beta score.")]
    unit = _unit(bindings, props)
    assert unit["witness_ids"] == []
    assert unit["status"] == "unwitnessed_complete"


def test_all_inherited_co_mention_in_a_child_passage_does_not_witness():
    bindings, props = _case6()
    unit = _unit(bindings, props)
    assert unit["witness_ids"] == []
    assert unit["status"] == "unwitnessed_complete"


def test_witnessed_but_engine_incomplete_is_not_renderable():
    # relation_witnessed is a structural property; renderability also needs the engine's complete flag.
    bindings, props = _case1()
    unit = _unit(bindings, props, engine_complete=False)
    assert unit["witness_ids"] == ["C1"]
    assert unit["status"] == "incomplete"
    assert rel.claim_witnessed([unit], _claim(unit)) is False


def test_claim_is_witnessed_only_through_a_renderable_unit():
    bindings, props = _case1()
    unit = _unit(bindings, props)
    assert rel.claim_witnessed([unit], _claim(unit)) is True


# ---------------------------------------------------------------------------------------------------------------------
# historical maps and metadata consistency
# ---------------------------------------------------------------------------------------------------------------------


def test_historical_map_without_i1_metadata_follows_the_same_semantics():
    bindings, props = _case1()
    requirement, instance = _relational(bindings)
    sealed = {"verified_propositions": props}
    historical = rel.relation_units(_as_smap(requirement, instance), sealed)
    stamped_smap = _as_smap(requirement, instance)
    rw.attach_relation_witnesses(stamped_smap, sealed)
    stamped = rel.relation_units(stamped_smap, sealed)
    assert historical == stamped
    assert all("metadata_check" not in unit for unit in historical)


def test_consistent_upstream_metadata_produces_no_metadata_check():
    bindings, props = _case1()
    requirement, instance = _relational(bindings)
    sealed = {"verified_propositions": props}
    smap = _as_smap(requirement, instance)
    rw.attach_relation_witnesses(smap, sealed)
    (unit,) = rel.relation_units(smap, sealed)
    assert "metadata_check" not in unit
    assert unit["status"] == "witnessed"


def _stamped(bindings, props):
    requirement, instance = _relational(bindings)
    sealed = {"verified_propositions": props}
    smap = _as_smap(requirement, instance)
    rw.attach_relation_witnesses(smap, sealed)
    return smap, sealed


def test_tampered_witness_flag_fails_closed():
    bindings, props = _case1()
    smap, sealed = _stamped(bindings, props)
    instance = next(iter(smap["syn"]["requirements"][0]["instances"]))
    instance["relation_witnessed"] = False  # contradicts the derivation from the bindings
    (unit,) = rel.relation_units(smap, sealed)
    assert unit["metadata_check"] == "disagrees"
    assert unit["status"] == "incomplete"
    assert rel.claim_witnessed([unit], _claim(unit)) is False


def test_stale_witness_ids_fail_closed():
    bindings, props = _case1()
    smap, sealed = _stamped(bindings, props)
    instance = next(iter(smap["syn"]["requirements"][0]["instances"]))
    instance["witness_ids"] = ["STALE"]
    (unit,) = rel.relation_units(smap, sealed)
    assert unit["metadata_check"] == "disagrees"
    assert unit["status"] == "incomplete"


def test_stale_provenance_failure_reason_is_reported():
    bindings, props = _case2()
    smap, sealed = _stamped(bindings, props)
    instance = next(iter(smap["syn"]["requirements"][0]["instances"]))
    instance["witness_provenance"]["failure_reason"] = None  # claims witnessed; the derivation says otherwise
    (unit,) = rel.relation_units(smap, sealed)
    assert unit["metadata_check"] == "disagrees"
    assert unit["status"] == "incomplete"


def test_malformed_witness_metadata_fails_closed():
    bindings, props = _case1()
    smap, sealed = _stamped(bindings, props)
    instance = next(iter(smap["syn"]["requirements"][0]["instances"]))
    instance["witness_ids"] = "C1"  # a string, not a list
    (unit,) = rel.relation_units(smap, sealed)
    assert unit["metadata_check"] == "malformed"
    assert unit["status"] == "incomplete"


def test_partial_metadata_is_malformed():
    bindings, props = _case1()
    smap, sealed = _stamped(bindings, props)
    instance = next(iter(smap["syn"]["requirements"][0]["instances"]))
    del instance["witness_ids"]  # flag present, ids missing
    (unit,) = rel.relation_units(smap, sealed)
    assert unit["metadata_check"] == "malformed"


def test_answer_layer_result_does_not_depend_on_trusting_stored_metadata():
    # Whatever the stored flag says, the unit's witness ids come from the derivation. A stale stored id is reported,
    # and the derived id is what the unit carries.
    bindings, props = _case1()
    smap, sealed = _stamped(bindings, props)
    instance = next(iter(smap["syn"]["requirements"][0]["instances"]))
    instance["witness_ids"] = ["STALE"]
    (unit,) = rel.relation_units(smap, sealed)
    assert unit["witness_ids"] == ["C1"]


# ---------------------------------------------------------------------------------------------------------------------
# preserved-artifact checks (skip when the gitignored artifacts are absent)
# ---------------------------------------------------------------------------------------------------------------------

_RUN = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "phase28-live-parent-synthesis-attempt2-20261004T014500Z"
    / "run"
)
_PRESERVED_MAP = _RUN / "17_sufficiency_map.json"
_PRESERVED_LEDGER = _RUN / "11_verified_ledger.json"
_needs_preserved = pytest.mark.skipif(
    not (_PRESERVED_MAP.is_file() and _PRESERVED_LEDGER.is_file()),
    reason="preserved Phase-28 Attempt-2 artifacts are not present in this checkout",
)


@_needs_preserved
def test_preserved_units_are_identical_with_and_without_stored_metadata():
    smap = json.loads(_PRESERVED_MAP.read_text(encoding="utf-8"))
    sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
    historical = rel.relation_units(copy.deepcopy(smap), sealed)
    stamped_smap = copy.deepcopy(smap)
    rw.attach_relation_witnesses(stamped_smap, sealed)
    assert historical == rel.relation_units(stamped_smap, sealed)


@_needs_preserved
def test_preserved_witnessed_and_unwitnessed_sets_are_unchanged_by_the_alignment():
    smap = json.loads(_PRESERVED_MAP.read_text(encoding="utf-8"))
    sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
    rw.attach_relation_witnesses(smap, sealed)
    units = rel.relation_units(smap, sealed)
    assert len(units) == 36
    witnessed = {(u["child_id"], u["instance_key"]) for u in units if u["status"] == "witnessed"}
    assert {cid for cid, _ in witnessed} == {"c4", "c8"}
    assert len(witnessed) == 6
    unwitnessed_complete = {u["child_id"] for u in units if u["status"] == "unwitnessed_complete"}
    assert unwitnessed_complete == {"c5", "c6"}
    assert len([u for u in units if u["status"] == "unwitnessed_complete"]) == 4
    assert not [u for u in units if "metadata_check" in u]
