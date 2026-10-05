"""Phase 32 / I1 tests for the additive relation-witness metadata (relation_witness.py).

Synthetic fixtures are generic (entities ``alpha``/``beta``) and question-agnostic. The preserved-artifact checks at
the bottom are the only place preserved-run identifiers appear, and they skip when the gitignored artifacts are absent.
No model, no network: the pipeline regression uses a deterministic fake nomination client.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised.answer_plan import relations as rel

# ---------------------------------------------------------------------------------------------------------------------
# generic fixture builders
# ---------------------------------------------------------------------------------------------------------------------

_DEFAULT_PROVENANCE = {"detail": "", "model": None}


def _prop(pid: str, quote: str, *, anchors=None, status: str = "verified") -> dict:
    row = {"proposition_id": pid, "quote": quote, "verification": {"status": status}}
    if anchors is not None:
        row["anchors"] = anchors
    return row


def _anchor(verbatim: bool) -> dict:
    return {"kind": "continuation", "chunk_id": 1, "span_id": "e", "text": "x", "verbatim": verbatim}


def _own(role: str, pid: str | None, text: str | None, supporting=()) -> tuple[str, dict]:
    provenance = {"candidate_source": "deterministic_mapping", **_DEFAULT_PROVENANCE}
    if supporting:
        provenance["supporting_proposition_ids"] = list(supporting)
    return role, {"role": role, "state": "filled", "reason": None, "proposition_id": pid,
                  "exact_text": text, "provenance": provenance, "guard": {}}  # fmt: skip


def _inherited(role: str, pid: str, text: str) -> tuple[str, dict]:
    provenance = {"candidate_source": "parent_context", **_DEFAULT_PROVENANCE}
    return role, {"role": role, "state": "filled", "reason": None, "proposition_id": pid,
                  "exact_text": text, "provenance": provenance, "guard": {}}  # fmt: skip


def _unfilled(role: str) -> tuple[str, dict]:
    return role, {"role": role, "state": "missing", "reason": "not_found", "proposition_id": None,
                  "exact_text": None, "provenance": {"candidate_source": None, **_DEFAULT_PROVENANCE}, "guard": {}}  # fmt: skip


def _relational(bindings: list[tuple[str, dict]], required: list[str] | None = None) -> tuple[dict, dict]:
    roles = [role for role, _ in bindings]
    requirement = {"id": "syn#relation", "role_completion": {"required_roles": required or roles}}
    instance = {"instance_key": "i1", "complete": True, "role_bindings": dict(bindings)}
    return requirement, instance


def _witness(bindings, propositions, required=None) -> dict:
    requirement, instance = _relational(bindings, required)
    return rw.witness_instance(requirement, instance, {row["proposition_id"]: row for row in propositions})


def _as_smap(requirement: dict, instance: dict) -> dict:
    requirement = copy.deepcopy(requirement)
    requirement["instances"] = [copy.deepcopy(instance)]
    return {"syn": {"child_id": "syn", "requirements": [requirement]}}


# The six Phase-31 section-7 cases (alpha = parent-supplied identity, beta = child's measure).
P1 = _prop("P1", "The alpha signal was recorded during the task.")


def _case1():
    return [_inherited("entity_x", "P1", "alpha signal"), _own("measure_y", "C1", "beta score")], [
        P1,
        _prop("C1", "The alpha signal predicted the beta score."),
    ]


def _case2():
    return [_inherited("entity_x", "P1", "alpha signal"), _own("measure_y", "C2", "beta score")], [
        P1,
        _prop("C2", "The beta score rose across sessions."),
    ]


def _case3():
    # The parent proposition itself co-mentions alpha and beta; the child's own evidence does not.
    return [_inherited("entity_x", "P3", "alpha signal"), _own("measure_y", "C2", "beta score")], [
        _prop("P3", "The alpha signal predicted the beta score."),
        _prop("C2", "The beta score rose across sessions."),
    ]


def _case4():
    # Alpha and beta sit in separate child propositions; beta's own support is the beta-only proposition.
    return [_inherited("entity_x", "P1", "alpha signal"), _own("measure_y", "C2", "beta score")], [
        P1,
        _prop("C2", "The beta score rose across sessions."),
        _prop("C3", "The alpha signal was recorded."),
    ]


def _case5(anchors_ok: bool = True):
    joined = _prop("J", "The alpha signal and the beta score were recorded together.",
                   anchors=[_anchor(True), _anchor(anchors_ok)])  # fmt: skip
    return [_inherited("entity_x", "P1", "alpha signal"), _own("measure_y", "J", "beta score")], [P1, joined]


def _case6():
    # ALL operands inherited; the child passage co-mentions both referents; no OWN operand, no verifier.
    return [_inherited("entity_x", "P1", "alpha signal"), _inherited("measure_y", "P2", "beta score")], [
        P1, _prop("P2", "The beta score was reported by the parent."),
        _prop("C4", "The alpha signal and the beta score were mentioned together.")]  # fmt: skip


# ---------------------------------------------------------------------------------------------------------------------
# the six synthetic cases
# ---------------------------------------------------------------------------------------------------------------------


def test_case1_parent_supplies_alpha_child_relates_alpha_to_beta_is_witnessed():
    bindings, props = _case1()
    result = _witness(bindings, props)
    assert result["relation_witnessed"] is True
    assert result["witness_ids"] == ["C1"]
    assert result["witness_provenance"]["failure_reason"] is None


def test_case2_child_mentions_beta_only_is_not_witnessed():
    bindings, props = _case2()
    result = _witness(bindings, props)
    assert result["relation_witnessed"] is False
    assert result["witness_ids"] == []
    assert result["witness_provenance"]["failure_reason"] == "inherited_referent_absent"


def test_case3_parent_proposition_with_both_operands_does_not_witness_child_relation():
    bindings, props = _case3()
    result = _witness(bindings, props)
    assert result["relation_witnessed"] is False
    assert "P3" not in result["witness_ids"]
    assert result["witness_provenance"]["candidate_ids"] == ["C2"]  # the parent's P3 is not in the child's support


def test_case4_alpha_and_beta_in_separate_child_propositions_is_not_witnessed():
    bindings, props = _case4()
    result = _witness(bindings, props)
    assert result["relation_witnessed"] is False
    assert result["witness_provenance"]["failure_reason"] == "inherited_referent_absent"


def test_case5_verified_joined_proposition_witnesses_only_with_valid_continuation():
    bindings, props = _case5(anchors_ok=True)
    assert _witness(bindings, props)["witness_ids"] == ["J"]


def test_case5_identical_unverified_join_does_not_witness():
    bindings, props = _case5(anchors_ok=False)
    result = _witness(bindings, props)
    assert result["relation_witnessed"] is False
    assert result["witness_provenance"]["failure_reason"] == "no_admissible_candidate"
    assert result["witness_provenance"]["candidate_checks"][0]["admissible"] is False


def test_case6_all_inherited_co_mention_is_not_witnessed():
    bindings, props = _case6()
    result = _witness(bindings, props)
    assert result["relation_witnessed"] is False
    assert result["witness_provenance"]["failure_reason"] == "no_own_operand"
    assert result["witness_provenance"]["own_roles"] == []


# ---------------------------------------------------------------------------------------------------------------------
# additional invariant tests
# ---------------------------------------------------------------------------------------------------------------------


def test_unfilled_required_operand_is_not_witnessed():
    result = _witness([_own("measure_y", "C1", "beta score"), _unfilled("entity_x")], [_prop("C1", "beta score")])
    assert result["relation_witnessed"] is False
    assert result["witness_provenance"]["failure_reason"] == "incomplete_operands"


def test_parent_proposition_admitted_by_the_childs_own_mapping_can_witness():
    # W3 is precise: the exclusion is about parent_context reachability, not about the proposition's text. When the
    # child's own mapping admits P1 as support for its own operand, P1 is a legitimate child witness.
    bindings = [_inherited("entity_x", "P1", "alpha signal"), _own("measure_y", "P1", "beta score", supporting=())]
    result = _witness(bindings, [_prop("P1", "The alpha signal predicted the beta score.")])
    assert result["witness_ids"] == ["P1"]


def test_two_own_operands_in_separate_propositions_do_not_jointly_witness():
    bindings = [_own("measure_y", "C2", "beta score"), _own("measure_z", "C3", "gamma score")]
    result = _witness(bindings, [_prop("C2", "beta score"), _prop("C3", "gamma score")])
    assert result["relation_witnessed"] is False
    assert result["witness_provenance"]["failure_reason"] == "no_single_proposition"


def test_two_own_operands_in_one_proposition_witness():
    bindings = [_own("measure_y", "C1", "beta score"), _own("measure_z", "C1", "gamma score")]
    result = _witness(bindings, [_prop("C1", "The beta score tracked the gamma score.")])
    assert result["witness_ids"] == ["C1"]


def test_support_id_order_does_not_change_the_result():
    forward = _witness(
        [_own("m", "C1", "beta score", supporting=["C1", "C5"]), _inherited("e", "P1", "alpha signal")],
        [P1, _prop("C1", "The alpha signal predicted the beta score."), _prop("C5", "beta score")],
    )
    reverse = _witness(
        [_own("m", "C1", "beta score", supporting=["C5", "C1"]), _inherited("e", "P1", "alpha signal")],
        [P1, _prop("C1", "The alpha signal predicted the beta score."), _prop("C5", "beta score")],
    )
    assert forward == reverse


def test_duplicate_support_ids_do_not_change_the_result():
    single = _witness(
        [_own("m", "C1", "beta score", supporting=["C1"]), _inherited("e", "P1", "alpha signal")],
        [P1, _prop("C1", "The alpha signal predicted the beta score.")],
    )
    duplicated = _witness(
        [_own("m", "C1", "beta score", supporting=["C1", "C1"]), _inherited("e", "P1", "alpha signal")],
        [P1, _prop("C1", "The alpha signal predicted the beta score.")],
    )
    assert single == duplicated


def test_provenance_is_deterministic_and_serialisable():
    bindings, props = _case1()
    first = json.dumps(_witness(bindings, props), sort_keys=True)
    second = json.dumps(_witness(bindings, props), sort_keys=True)
    assert first == second


def test_result_carries_no_confidence_or_score_field():
    result = _witness(*_case1())
    assert set(result) == {"relation_witnessed", "witness_ids", "witness_provenance"}
    assert not any("score" in key or "confidence" in key for key in result["witness_provenance"])


def test_non_relational_instances_receive_no_relational_keys():
    requirement = {"id": "syn#single", "role_completion": {"required_roles": ["only_role"]}}
    instance = {"instance_key": "i", "complete": True, "role_bindings": {"only_role": _own("only_role", "C1", "x")[1]}}
    contract = {"syn": {"child_id": "syn", "requirements": [{**requirement, "instances": [instance]}]}}
    rw.attach_relation_witnesses(contract, {"verified_propositions": [_prop("C1", "x")]})
    assert set(contract["syn"]["requirements"][0]["instances"][0]) == {"instance_key", "complete", "role_bindings"}


def test_attach_adds_keys_only_and_never_touches_complete_or_bindings():
    bindings, props = _case1()
    requirement, instance = _relational(bindings)
    instance["complete"] = False  # engine says incomplete; the I1 metadata must not alter that
    before = copy.deepcopy(instance)
    contract = {"syn": {"child_id": "syn", "requirements": [{**requirement, "instances": [copy.deepcopy(instance)]}]}}
    rw.attach_relation_witnesses(contract, {"verified_propositions": props})
    after = contract["syn"]["requirements"][0]["instances"][0]
    assert after["complete"] is False
    assert after["role_bindings"] == before["role_bindings"]
    assert after["relation_witnessed"] is True
    assert rw.project_out_i1(contract)["syn"]["requirements"][0]["instances"][0] == before


def test_is_admissible_rejects_unverified_status_and_unverified_join():
    assert rw.is_admissible(_prop("p", "x")) is True
    assert rw.is_admissible(_prop("p", "x", status="unverified")) is False
    assert rw.is_admissible(_prop("p", "x", anchors=[_anchor(True), _anchor(False)])) is False
    assert rw.is_admissible(None) is False


# ---------------------------------------------------------------------------------------------------------------------
# cross-check against the Phase-30 answer-layer witness (answer_plan.relations)
# ---------------------------------------------------------------------------------------------------------------------

# Phase 32 / I1a: the answer layer now derives witnesses through the same section-7 implementation (relation_witness),
# so the three I1 legacy divergences are ordinary agreement tests. The expected values below are written by hand from the
# section-7 rules. They are not read back from either implementation.

_EXPECTED = [
    pytest.param(_case1, True, ["C1"], id="case1-inherited-referent-with-own-beta-proposition-witnessed"),
    pytest.param(_case2, False, [], id="case2-child-mentions-beta-only"),
    pytest.param(lambda: _case3(), False, [], id="case3-parent-proposition-is-not-evidence"),
    pytest.param(lambda: _case4(), False, [], id="case4-distributed-propositions"),
    pytest.param(lambda: _case5(True), True, ["J"], id="case5a-verified-joined-witnessed"),
    pytest.param(lambda: _case5(False), False, [], id="case5b-unverified-join-not-witnessed"),
    pytest.param(_case6, False, [], id="case6-all-inherited-not-witnessed"),
]


def _answer_layer_witness(bindings, props):
    requirement, instance = _relational(bindings)
    unit = rel.relation_units(_as_smap(requirement, instance), {"verified_propositions": props})[0]
    return bool(unit["witness_ids"]), unit["witness_ids"]


@pytest.mark.parametrize("make_case, expected, expected_ids", _EXPECTED)
def test_upstream_and_answer_layer_both_implement_the_section7_expectation(make_case, expected, expected_ids):
    bindings, props = make_case()
    requirement, instance = _relational(bindings)
    upstream = rw.witness_instance(requirement, instance, {p["proposition_id"]: p for p in props})
    answer_witnessed, answer_ids = _answer_layer_witness(bindings, props)
    assert upstream["relation_witnessed"] is expected
    assert upstream["witness_ids"] == expected_ids
    assert answer_witnessed is expected
    assert answer_ids == expected_ids


def test_all_inherited_shared_parent_is_not_witnessed_by_either_layer():
    # Formerly the latent legacy divergence: both operands inherited from one parent proposition, no OWN operand.
    bindings = [_inherited("entity_x", "P1", "alpha signal"), _inherited("measure_y", "P1", "beta score")]
    props = [_prop("P1", "The alpha signal predicted the beta score.")]
    requirement, instance = _relational(bindings)
    upstream = rw.witness_instance(requirement, instance, {p["proposition_id"]: p for p in props})
    answer_witnessed, _ = _answer_layer_witness(bindings, props)
    assert upstream["relation_witnessed"] is False
    assert answer_witnessed is False


# ---------------------------------------------------------------------------------------------------------------------
# preserved-artifact regression (q_aib identifiers permitted here only; skips when gitignored artifacts are absent)
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


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


@_needs_preserved
def test_preserved_map_projection_round_trips_exactly():
    smap = json.loads(_PRESERVED_MAP.read_text(encoding="utf-8"))
    sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
    work = copy.deepcopy(smap)
    rw.attach_relation_witnesses(work, sealed)
    assert _canon(rw.project_out_i1(work)) == _canon(smap)


@_needs_preserved
def test_preserved_phase28_engine_complete_but_unwitnessed_instances_are_exactly_c5_and_c6():
    smap = json.loads(_PRESERVED_MAP.read_text(encoding="utf-8"))
    sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
    rw.attach_relation_witnesses(smap, sealed)
    unwitnessed = set()
    for cid, child in smap.items():
        for requirement in child["requirements"]:
            if not rw.is_relational(requirement):
                continue
            for instance in requirement["instances"]:
                if instance["complete"] and not instance["relation_witnessed"]:
                    unwitnessed.add((cid, requirement["id"], instance["instance_key"]))
    assert {cid for cid, _, _ in unwitnessed} == {"c5", "c6"}
    assert len(unwitnessed) == 4


@_needs_preserved
def test_preserved_c4_region_instance_is_witnessed_by_its_own_passage():
    smap = json.loads(_PRESERVED_MAP.read_text(encoding="utf-8"))
    sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
    rw.attach_relation_witnesses(smap, sealed)
    c4 = next(i for i in smap["c4"]["requirements"][0]["instances"] if i["instance_key"] == "i::b140e60509ac4c8b")
    assert c4["relation_witnessed"] is True
    assert c4["witness_ids"] == ["p11"]


@_needs_preserved
def test_preserved_answer_layer_derivation_agrees_with_stored_metadata_on_every_relational_instance():
    # I1a hard gate: the answer layer's derivation (shared section-7 semantics) must agree with the mapping-stage
    # metadata, both booleans and witness ids, on every preserved relational instance. No unit may carry a metadata anomaly.
    smap = json.loads(_PRESERVED_MAP.read_text(encoding="utf-8"))
    sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
    rw.attach_relation_witnesses(smap, sealed)
    units = {(u["child_id"], u["requirement_id"], u["instance_key"]): u for u in rel.relation_units(smap, sealed)}
    assert not [key for key, unit in units.items() if "metadata_check" in unit]
    disagreements = []
    for cid, child in smap.items():
        for requirement in child["requirements"]:
            if not rw.is_relational(requirement):
                continue
            for instance in requirement["instances"]:
                key = (cid, requirement["id"], instance["instance_key"])
                unit = units[key]
                if (
                    bool(unit["witness_ids"]) != instance["relation_witnessed"]
                    or unit["witness_ids"] != instance["witness_ids"]
                ):
                    disagreements.append(key)
    assert disagreements == []
    assert len(units) == 36


@_needs_preserved
def test_preserved_c8_trait_relations_are_witnessed_by_the_shared_rating_passage():
    # Recorded observation, not an endorsement. Both OWN operands are supported by the same rating proposition, so
    # the approved invariant witnesses them structurally; Phase 30 already reports them as witnessed. Whether the
    # trait bearer is right is the separate measurement-subject problem (audit section 9), which I1 does not solve.
    smap = json.loads(_PRESERVED_MAP.read_text(encoding="utf-8"))
    sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
    rw.attach_relation_witnesses(smap, sealed)
    witnessed = {i["instance_key"] for i in smap["c8"]["requirements"][0]["instances"] if i["relation_witnessed"]}
    assert len(witnessed) == 5
    assert all(
        i["witness_ids"] == ["p41"] for i in smap["c8"]["requirements"][0]["instances"] if i["relation_witnessed"]
    )


# ---------------------------------------------------------------------------------------------------------------------
# pipeline projection parity: the REAL mapping/direction/ParentClaim/recovery/stop-search path, pre-I1 baseline hashes
# ---------------------------------------------------------------------------------------------------------------------

# Captured on the pre-I1 code (HEAD e886bf73) with the deterministic fake client below. Any change here is a
# semantic change to the mapping pipeline and must be explained, not re-baselined silently.
_PRE_I1_BASELINE = {
    "map_projected_sha": "fff5e6fc2129f038a0cd0cb1de34f478feef3bbdfa8ce10f1fe9c951890f2074",
    "claims_sha": "1070dde97a216522946dbe2e642715a2644aeb239435e01eee9406c8ed0520fe",
    "recovery_sha": "e051a8df84c1eb042dacb56b790647f04ecfea675cf68fced1b710a846cbf92e",
    "stop_sha": "cdcd5c4ad68badf112bc582bb5e03c31a88c1dbd7215f219ecd896ccc5ceccf5",
}


class _FakeNominationClient:
    """Deterministic, offline stand-in. It never reaches a model; it nominates the first offered candidate's prefix."""

    # The mapper copies this name into each nomination's provenance, so it is part of the baseline identity and must
    # match the name the pre-I1 baseline was captured with (see .local/phase32/harness.py).
    model_name = "fake-phase32-harness"

    def nominate_sufficiency_role(self, *, category_description, candidates):
        if not candidates:
            return []
        first = candidates[0]
        return [{"proposition_id": first["proposition_id"], "exact_text": first["passage"][:15]}]


@_needs_preserved
def test_pipeline_projection_matches_pre_i1_baseline():
    from experiments.ask_cli_revised import hierarchy_contract as hc
    from experiments.ask_cli_revised import parent_synthesis_ledger as psl
    from experiments.ask_cli_revised import sufficiency_diagnostic as sd
    from experiments.ask_cli_revised import sufficiency_engine as se
    from experiments.ask_cli_revised import sufficiency_freeze as sf
    from experiments.ask_cli_revised import sufficiency_identity as si
    from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
    from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

    sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
    contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
    contract_by_child = sf.load_verified()
    parent_of = hc.parent_of(contract)
    mapped = sd.compute_diagnostic_sufficiency_map(
        sealed, contract_by_child, parent_of, model_client=_FakeNominationClient()
    )
    sd.compute_direction_and_effectiveness(sealed, mapped)
    stop = {
        f"{cid}|{req['id']}": se.compute_stop_search_certified(req)
        for cid, child in sorted(mapped.items())
        for req in child["requirements"]
    }
    observed = {
        "map_projected_sha": _sha(si.strip_identity(rw.project_out_i1(mapped))),
        "claims_sha": _sha(psl.build_claim_ledger(mapped, sealed, parent_of)),
        "recovery_sha": _sha(srt.compute_recovery_targets(mapped, parent_of)),
        "stop_sha": _sha(stop),
    }
    assert observed == _PRE_I1_BASELINE


def _sha(obj) -> str:
    """Same canonical form the pre-I1 baseline was captured with (compact separators, default=str)."""
    import hashlib

    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
