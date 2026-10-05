"""Phase 32 / I1d: versioned inherited-referent containment (sufficiency-semantics-v1 case-sensitive, v2 case-insensitive).

The only semantic change is casing: the inherited referent and the candidate quote are both Unicode case-folded before the
unchanged canonical containment test. Generic alpha/beta fixtures; the preserved-run checks skip when the gitignored
Phase-28 artifacts are absent. No model, no network.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si

V1 = se.SUFFICIENCY_SEMANTICS_V1
V2 = se.SUFFICIENCY_SEMANTICS_V2
_DEFAULT_PROVENANCE = {"detail": "", "model": None}
ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / ".local" / "e2e-runs" / "phase28-live-parent-synthesis-attempt2-20261004T014500Z" / "run"
RUN_I1 = ROOT / ".local" / "phase32" / "run_i1"  # the preserved map with I1 fields, unstamped (historical unversioned)
_needs_preserved = pytest.mark.skipif(
    not (RUN.is_dir() and RUN_I1.is_dir()),
    reason="preserved Phase-28 Attempt-2 artifacts are not present in this checkout",
)


# ---------------------------------------------------------------------------------------------------------------------
# generic fixture builders (same shapes as test_relation_witness.py)
# ---------------------------------------------------------------------------------------------------------------------


def _prop(pid: str, quote: str, *, anchors=None, status: str = "verified") -> dict:
    row = {"proposition_id": pid, "quote": quote, "verification": {"status": status}}
    if anchors is not None:
        row["anchors"] = anchors
    return row


def _anchor(verbatim: bool) -> dict:
    return {"kind": "continuation", "chunk_id": 1, "span_id": "e", "text": "x", "verbatim": verbatim}


def _own(role: str, pid: str, text: str, supporting=()) -> tuple[str, dict]:
    provenance = {"candidate_source": "deterministic_mapping", **_DEFAULT_PROVENANCE}
    if supporting:
        provenance["supporting_proposition_ids"] = list(supporting)
    return role, {
        "role": role,
        "state": "filled",
        "reason": None,
        "proposition_id": pid,
        "exact_text": text,
        "provenance": provenance,
        "guard": {},
    }


def _inherited(role: str, pid: str, text: str) -> tuple[str, dict]:
    provenance = {"candidate_source": "parent_context", **_DEFAULT_PROVENANCE}
    return role, {
        "role": role,
        "state": "filled",
        "reason": None,
        "proposition_id": pid,
        "exact_text": text,
        "provenance": provenance,
        "guard": {},
    }


def _witness(bindings: list[tuple[str, dict]], propositions: list[dict], version: str) -> dict:
    roles = [role for role, _ in bindings]
    requirement = {"id": "syn#relation", "role_completion": {"required_roles": roles}}
    instance = {"instance_key": "i1", "complete": True, "role_bindings": dict(bindings)}
    props = {row["proposition_id"]: row for row in propositions}
    return rw.witness_instance(requirement, instance, props, semantics_version=version)


def _entity_case(inherited_text: str, quote: str, version: str) -> dict:
    """A parent supplies the entity (inherited referent); the child's own measure is supported by one proposition C1."""
    bindings = [_inherited("entity", "P1", inherited_text), _own("measure", "C1", "beta score")]
    return _witness(bindings, [_prop("C1", quote)], version)


# ---------------------------------------------------------------------------------------------------------------------
# 1-6. the synthetic v1/v2 matrix: (name, inherited surface, candidate quote, witnessed under v1, witnessed under v2)
# ---------------------------------------------------------------------------------------------------------------------

MATRIX = [
    ("same-case", "alpha region", "the alpha region predicted beta score.", True, True),
    ("sentence-initial-capitalisation", "alpha region", "Alpha region predicted beta score.", False, True),
    ("reverse-case-difference", "Alpha Region", "the alpha region predicted beta score.", False, True),
    # Not normalised by either version: a hyphen is not a space under the existing canonical containment.
    ("punctuation-difference", "alpha region", "alpha-region predicted beta score.", False, False),
    # Already true under v1: the existing canonical containment collapses whitespace runs. Nothing is added here.
    ("whitespace-run-already-canonical", "alpha region", "the alpha  region predicted beta score.", True, True),
    ("referent-absent-modulo-case", "alpha region", "the gamma region predicted beta score.", False, False),
]


@pytest.mark.parametrize("name, surface, quote, v1_expected, v2_expected", MATRIX, ids=[row[0] for row in MATRIX])
def test_synthetic_matrix_witnessed_under_each_version(name, surface, quote, v1_expected, v2_expected):
    assert _entity_case(surface, quote, V1)["relation_witnessed"] is v1_expected
    assert _entity_case(surface, quote, V2)["relation_witnessed"] is v2_expected


def test_all_inherited_case_insensitive_co_mention_does_not_bypass_no_own_guard():
    bindings = [_inherited("entity", "P1", "Alpha Region"), _inherited("measure", "P1", "beta score")]
    result = _witness(bindings, [_prop("P1", "The alpha region predicted beta score.")], V2)
    assert result["relation_witnessed"] is False
    assert result["witness_provenance"]["failure_reason"] == "no_own_operand"
    assert result["witness_ids"] == []


def test_distributed_evidence_is_not_witnessed_under_v2():
    # The child's own measure is supported only by C2. The referent appears only in C3, a different proposition.
    bindings = [_inherited("entity", "P1", "Alpha Region"), _own("measure", "C2", "beta score")]
    result = _witness(
        bindings,
        [_prop("C2", "Beta score rose across sessions."), _prop("C3", "the alpha region responded.")],
        V2,
    )
    assert result["relation_witnessed"] is False
    assert result["witness_ids"] == []
    assert result["witness_provenance"]["failure_reason"] == "inherited_referent_absent"


def test_parent_proposition_is_never_evidence_under_v2():
    # The parent proposition contains both operands. It is not in the child's own support, so it cannot witness.
    bindings = [_inherited("entity", "P1", "Alpha Region"), _own("measure", "C2", "beta score")]
    result = _witness(
        bindings,
        [_prop("P1", "The Alpha Region predicted beta score."), _prop("C2", "Beta score rose across sessions.")],
        V2,
    )
    assert result["relation_witnessed"] is False
    assert "P1" not in result["witness_ids"]


@pytest.mark.parametrize("verbatim", [True, False])
def test_verified_join_witnesses_under_v2_only_with_verbatim_anchors(verbatim):
    # A joined proposition whose referent differs from the quote only by case. Same admissibility rule as before.
    bindings = [_inherited("entity", "P1", "alpha region"), _own("measure", "J", "beta score")]
    join = _prop("J", "Alpha region predicted beta score.", anchors=[_anchor(verbatim)])
    v1 = _witness(bindings, [join], V1)
    v2 = _witness(bindings, [join], V2)
    assert v1["relation_witnessed"] is False
    assert v2["relation_witnessed"] is verbatim
    if verbatim:
        assert v2["witness_ids"] == ["J"]


# ---------------------------------------------------------------------------------------------------------------------
# 7. version dispatch
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name, surface, quote, v1_expected, v2_expected", MATRIX, ids=[row[0] for row in MATRIX])
def test_v1_and_v2_differ_only_on_casing_fixtures(name, surface, quote, v1_expected, v2_expected):
    full_v1 = _entity_case(surface, quote, V1)
    full_v2 = _entity_case(surface, quote, V2)
    casing_only = name in ("sentence-initial-capitalisation", "reverse-case-difference")
    assert (full_v1 == full_v2) is (not casing_only)


def test_same_case_fixture_gives_identical_full_result_under_both_versions():
    assert _entity_case("alpha region", "the alpha region predicted beta score.", V1) == _entity_case(
        "alpha region", "the alpha region predicted beta score.", V2
    )


def test_referent_predicate_is_version_dispatched():
    quote = "Alpha Region predicted beta score."
    assert rw.referent_present("alpha region", quote, semantics_version=V1) is False
    assert rw.referent_present("alpha region", quote, semantics_version=V2) is True
    assert rw.referent_present(None, quote, semantics_version=V2) is False


@pytest.mark.parametrize("bad", ["sufficiency-semantics-v99", "", "sufficiency-semantics-v0"])
def test_unknown_version_fails_closed_everywhere(bad):
    with pytest.raises(si.SemanticsIdentityError):
        rw.referent_present("alpha region", "alpha region", semantics_version=bad)
    with pytest.raises(si.SemanticsIdentityError):
        _entity_case("alpha region", "alpha region", bad)
    requirement = {"id": "syn#relation", "role_completion": {"required_roles": ["entity", "measure"]}, "instances": []}
    requirement["instances"] = [{"instance_key": "i", "complete": False, "role_bindings": {}}]
    smap = {"c1": se.new_contract("c1", [requirement])}
    with pytest.raises(si.SemanticsIdentityError):
        rw.attach_relation_witnesses(smap, {"verified_propositions": []}, semantics_version=bad)


def test_witness_entry_points_require_an_explicit_version():
    requirement = {"id": "syn#relation", "role_completion": {"required_roles": ["entity", "measure"]}}
    instance = {"instance_key": "i1", "complete": True, "role_bindings": {}}
    with pytest.raises(TypeError):
        rw.witness_instance(requirement, instance, {})  # no semantics_version: never defaulted
    with pytest.raises(TypeError):
        rw.attach_relation_witnesses({}, {})


def test_identity_states_are_distinct_and_membership_is_not_currency():
    # Supported (readable) does not mean current.
    assert V1 in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS
    assert V1 != se.SUFFICIENCY_SEMANTICS_VERSION
    v1_map = si.stamp_map({"c1": se.new_contract("c1", [])})
    for contract in v1_map.values():
        contract[se.SEMANTICS_VERSION_KEY] = V1
    with pytest.raises(si.SemanticsIdentityError, match="not current"):
        si.read_map_identity(v1_map)
    assert si.read_map_identity(v1_map, accept_historical_versioned=True) == {
        "status": si.STATUS_HISTORICAL_VERSIONED,
        "version": V1,
    }


def test_applied_containment_for_each_state():
    assert si.applied_containment_version({"status": "current", "version": V2}) == V2
    assert si.applied_containment_version({"status": "historical_versioned", "version": V1}) == V1
    # An unversioned artifact is not attributed a version: the contemporary rule is applied explicitly.
    assert si.applied_containment_version({"status": "historical_unversioned", "version": None}) == V2


# ---------------------------------------------------------------------------------------------------------------------
# 8. replay identity on the preserved run (skipped without the gitignored artifacts)
# ---------------------------------------------------------------------------------------------------------------------


def _write_run(tmp: Path, map_identity: str) -> Path:
    """A run directory with the preserved ledger/answer inputs and a 17 map stamped as requested.

    map_identity: "v2" (current), "v1" (historical versioned: witnesses recomputed under v1, stamped v1), or
    "unversioned" (the preserved I1-field map, no stamp).
    """
    run = tmp / "run"
    run.mkdir(parents=True)
    for name in ("11_verified_ledger.json", "13c_scoped_search.json", "15a_parent_synthesis.json"):
        shutil.copy(RUN / name, run / name)
    sealed = json.loads((RUN / "11_verified_ledger.json").read_text(encoding="utf-8"))
    if map_identity == "unversioned":
        smap = json.loads((RUN_I1 / "17_sufficiency_map.json").read_text(encoding="utf-8"))
    else:
        version = V2 if map_identity == "v2" else V1
        smap = json.loads((RUN / "17_sufficiency_map.json").read_text(encoding="utf-8"))
        rw.attach_relation_witnesses(smap, sealed, semantics_version=version)
        for contract in smap.values():
            contract[se.SEMANTICS_VERSION_KEY] = version
    (run / "17_sufficiency_map.json").write_text(json.dumps(smap, indent=2, ensure_ascii=False), encoding="utf-8")
    return run


def _replay(run: Path, out: Path, *flags: str) -> dict:
    from experiments.ask_cli_revised.answer_plan import replay

    assert replay.main(["--run-dir", str(run), "--out-dir", str(out), *flags]) == 0
    return json.loads((out / "replay_decomposition_authorization.json").read_text(encoding="utf-8"))


@_needs_preserved
def test_current_v2_map_replays_strictly_and_records_v2(tmp_path):
    from experiments.ask_cli_revised.answer_plan import plan as pl

    run = _write_run(tmp_path, "v2")
    out = tmp_path / "out"
    authorization = _replay(run, out)  # strict: no historical flag
    bound = authorization["bound_inputs"]
    assert bound["sufficiency_semantics"] == {"status": "current", "version": V2}
    assert bound["answer_containment_semantics"] == V2
    assert pl.PLAN_VERSION == "answer-plan-step2-v3"
    plan = json.loads((out / "answer_plan.json").read_text(encoding="utf-8"))
    assert plan["plan_version"] == "answer-plan-step2-v3"
    assert plan["containment_semantics"] == V2


@_needs_preserved
def test_v1_map_is_refused_in_strict_mode(tmp_path):
    from experiments.ask_cli_revised.answer_plan import replay

    run = _write_run(tmp_path, "v1")
    with pytest.raises(si.SemanticsIdentityError, match="not current"):
        replay.main(["--run-dir", str(run), "--out-dir", str(tmp_path / "out")])


@_needs_preserved
def test_v1_map_is_readable_through_the_explicit_historical_path_and_v1_is_applied(tmp_path):
    run = _write_run(tmp_path, "v1")
    authorization = _replay(run, tmp_path / "out", "--allow-historical-versioned")
    bound = authorization["bound_inputs"]
    assert bound["sufficiency_semantics"] == {"status": "historical_versioned", "version": V1}
    assert bound["answer_containment_semantics"] == V1
    plan = json.loads((tmp_path / "out" / "answer_plan.json").read_text(encoding="utf-8"))
    assert plan["containment_semantics"] == V1


@_needs_preserved
def test_unversioned_map_applies_contemporary_rule_and_does_not_attribute_it(tmp_path):
    run = _write_run(tmp_path, "unversioned")
    authorization = _replay(run, tmp_path / "out", "--allow-historical-unversioned-map")
    bound = authorization["bound_inputs"]
    assert bound["sufficiency_semantics"] == {"status": "historical_unversioned", "version": None}
    assert bound["answer_containment_semantics"] == V2  # applied and recorded; the map itself is not labelled v2
    plan = json.loads((tmp_path / "out" / "answer_plan.json").read_text(encoding="utf-8"))
    assert plan["containment_semantics"] == V2


@_needs_preserved
def test_v1_and_v2_replays_give_identical_layers_1_and_2_on_the_preserved_run(tmp_path):
    # Zero witness change on the preserved run means the answer text cannot differ by version.
    _replay(_write_run(tmp_path / "a", "v2"), tmp_path / "a_out")
    _replay(_write_run(tmp_path / "b", "v1"), tmp_path / "b_out", "--allow-historical-versioned")
    for layer in ("deterministic_layer1.md", "deterministic_layer2.md"):
        assert (tmp_path / "a_out" / layer).read_bytes() == (tmp_path / "b_out" / layer).read_bytes(), layer


@_needs_preserved
@pytest.mark.parametrize("from_version, to_version", [(V1, V2), (V2, V1)])
def test_tampered_authorization_version_fails_closed(tmp_path, from_version, to_version):
    from experiments.ask_cli_revised.answer_plan import overlay as ov
    from experiments.ask_cli_revised.answer_plan import replay

    source = "v1" if from_version == V1 else "v2"
    run = _write_run(tmp_path, source)
    authorization = _replay(run, tmp_path / "out", *(["--allow-historical-versioned"] if source == "v1" else []))
    smap = json.loads((run / "17_sufficiency_map.json").read_text(encoding="utf-8"))
    status = "current" if to_version == V2 else "historical_versioned"

    # (a) edit the bound version without recomputing the digest: digest check catches it.
    stale = copy.deepcopy(authorization)
    stale["bound_inputs"]["sufficiency_semantics"] = {"status": status, "version": to_version}
    with pytest.raises(si.SemanticsIdentityError, match="digest"):
        replay.verify_replay_authorization(stale, smap)

    # (b) recompute the digest: the binding check against the map catches the version swap.
    forged = copy.deepcopy(stale)
    body = {key: value for key, value in forged.items() if key != "authorization_sha256"}
    forged["authorization_sha256"] = ov.sha256_obj(body)
    with pytest.raises(si.SemanticsIdentityError, match="binds"):
        replay.verify_replay_authorization(forged, smap)

    # (c) swap identity AND containment consistently, then recompute: the binding check against the map still rejects it,
    #     because the map itself records the source version.
    consistent = copy.deepcopy(authorization)
    consistent["bound_inputs"]["sufficiency_semantics"] = {"status": status, "version": to_version}
    consistent["bound_inputs"]["answer_containment_semantics"] = to_version
    body = {key: value for key, value in consistent.items() if key != "authorization_sha256"}
    consistent["authorization_sha256"] = ov.sha256_obj(body)
    with pytest.raises(si.SemanticsIdentityError, match="binds"):
        replay.verify_replay_authorization(consistent, smap)


@_needs_preserved
def test_containment_record_is_checked_against_the_bound_identity(tmp_path):
    from experiments.ask_cli_revised.answer_plan import overlay as ov
    from experiments.ask_cli_revised.answer_plan import replay

    run = _write_run(tmp_path, "unversioned")
    authorization = _replay(run, tmp_path / "out", "--allow-historical-unversioned-map")
    smap = json.loads((run / "17_sufficiency_map.json").read_text(encoding="utf-8"))
    # Attribute the unversioned map a version it does not record: the containment record no longer follows the identity.
    tampered = copy.deepcopy(authorization)
    tampered["bound_inputs"]["answer_containment_semantics"] = V1
    body = {key: value for key, value in tampered.items() if key != "authorization_sha256"}
    tampered["authorization_sha256"] = ov.sha256_obj(body)
    with pytest.raises(si.SemanticsIdentityError, match="implies"):
        replay.verify_replay_authorization(tampered, smap)


@_needs_preserved
def test_unknown_version_map_fails_in_every_mode(tmp_path):
    from experiments.ask_cli_revised.answer_plan import replay

    run = _write_run(tmp_path, "v2")
    smap = json.loads((run / "17_sufficiency_map.json").read_text(encoding="utf-8"))
    for contract in smap.values():
        contract[se.SEMANTICS_VERSION_KEY] = "sufficiency-semantics-v99"
    (run / "17_sufficiency_map.json").write_text(json.dumps(smap, ensure_ascii=False), encoding="utf-8")
    for flags in ([], ["--allow-historical-versioned"], ["--allow-historical-unversioned-map"]):
        with pytest.raises(si.SemanticsIdentityError, match="unsupported"):
            replay.main(["--run-dir", str(run), "--out-dir", str(tmp_path / "out"), *flags])


@_needs_preserved
def test_preserved_witness_set_is_unchanged_under_v2_and_is_not_forced():
    sealed = json.loads((RUN / "11_verified_ledger.json").read_text(encoding="utf-8"))
    smap = json.loads((RUN_I1 / "17_sufficiency_map.json").read_text(encoding="utf-8"))
    rw.attach_relation_witnesses(smap, sealed, semantics_version=V2)
    witnessed, complete_unwitnessed = set(), set()
    for child, contract in smap.items():
        for requirement in contract["requirements"]:
            for instance in requirement.get("instances", []):
                if "relation_witnessed" not in instance:
                    continue
                key = (child, instance["instance_key"][-12:])
                if instance["relation_witnessed"]:
                    witnessed.add(key)
                elif instance["complete"]:
                    complete_unwitnessed.add(key)
    assert witnessed == {("c4", "e60509ac4c8b")} | {
        ("c8", suffix) for suffix in ("d6d8a8225859", "360f15addd4a", "ad0452a402ec", "c660cdb1a0de", "b077fe124a0e")
    }
    assert complete_unwitnessed == {
        ("c5", "8a1c59aaa360"),
        ("c5", "6948ec530e13"),
        ("c6", "08aa35e6e926"),
        ("c6", "2674ba934ce3"),
    }
