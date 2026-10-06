"""Phase 32 / I1c: sufficiency-semantics identity plumbing. ZERO semantic change.

Generic fixtures where possible. The preserved-artifact checks skip when the gitignored artifacts are absent. No model, no
network. Expected values are written by hand from the specification.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised.answer_plan import relations as rel

CURRENT = "sufficiency-semantics-v3"
HISTORICAL_V1 = "sufficiency-semantics-v1"
HISTORICAL_V2 = "sufficiency-semantics-v2"
RUN = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "phase28-live-parent-synthesis-attempt2-20261004T014500Z"
    / "run"
)
PRESERVED_MAP = RUN / "17_sufficiency_map.json"
PRESERVED_LEDGER = RUN / "11_verified_ledger.json"
PRESERVED_CLAIMS = RUN / "15a_parent_synthesis.json"
_needs_preserved = pytest.mark.skipif(
    not (PRESERVED_MAP.is_file() and PRESERVED_LEDGER.is_file()),
    reason="preserved Phase-28 Attempt-2 artifacts are not present in this checkout",
)


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _synthetic_map() -> dict:
    requirement = {"id": "syn#relation", "role_completion": {"required_roles": ["ra", "rb"]}, "instances": []}
    return {"c1": se.new_contract("c1", [requirement]), "c2": se.new_contract("c2", [])}


# ---------------------------------------------------------------------------------------------------------------------
# A. a new map carries the version
# ---------------------------------------------------------------------------------------------------------------------


def test_a_stamped_map_carries_the_semantics_version_on_every_child():
    stamped = si.stamp_map(_synthetic_map(), semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
    assert all(contract[se.SEMANTICS_VERSION_KEY] == CURRENT for contract in stamped.values())
    assert si.read_map_identity(stamped) == {"status": "current", "version": CURRENT}


def test_the_constant_and_its_key_are_the_documented_values():
    assert se.SUFFICIENCY_SEMANTICS_VERSION == CURRENT == "sufficiency-semantics-v3"
    assert se.SEMANTICS_VERSION_KEY == "sufficiency_semantics_version"
    assert se.HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS == frozenset({HISTORICAL_V1, HISTORICAL_V2})
    # Readable is not current: the supported set contains the historical version too.
    assert se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS == frozenset({CURRENT, HISTORICAL_V1, HISTORICAL_V2})


# ---------------------------------------------------------------------------------------------------------------------
# B. same inputs and same version produce identical output
# ---------------------------------------------------------------------------------------------------------------------


def test_b_same_inputs_and_version_produce_deterministic_output():
    first = _canon(si.stamp_map(_synthetic_map(), semantics_version=se.SUFFICIENCY_SEMANTICS_V3))
    second = _canon(si.stamp_map(_synthetic_map(), semantics_version=se.SUFFICIENCY_SEMANTICS_V3))
    assert first == second


# ---------------------------------------------------------------------------------------------------------------------
# C. a historical map without the field is recognised as historical, never as current
# ---------------------------------------------------------------------------------------------------------------------


def test_c_a_map_without_the_field_is_historical_unversioned_not_current():
    identity = si.read_map_identity(_synthetic_map(), accept_historical_unversioned=True)
    assert identity == {"status": "historical_unversioned", "version": None}
    assert identity["status"] != "current"


def test_c_absence_is_not_inferred_as_current_even_for_a_non_empty_map():
    historical = _synthetic_map()
    assert (
        si.read_map_identity(historical, accept_historical_unversioned=True)["status"]
        == si.STATUS_HISTORICAL_UNVERSIONED
    )
    # Without the explicit path, absence is refused rather than read as current.
    with pytest.raises(si.SemanticsIdentityError, match="not accepted"):
        si.read_map_identity(historical)


# ---------------------------------------------------------------------------------------------------------------------
# D. the production path refuses a missing version
# ---------------------------------------------------------------------------------------------------------------------


def test_d_production_refuses_a_missing_version():
    with pytest.raises(si.SemanticsIdentityError, match="not accepted"):
        si.read_map_identity(_synthetic_map())


def test_d_partial_identity_is_an_error_in_every_mode():
    partial = si.stamp_map(_synthetic_map(), semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
    del partial["c2"][se.SEMANTICS_VERSION_KEY]
    with pytest.raises(si.SemanticsIdentityError, match="partial"):
        si.read_map_identity(partial)


def test_d_an_empty_map_has_no_identity():
    with pytest.raises(si.SemanticsIdentityError):
        si.read_map_identity({})


# ---------------------------------------------------------------------------------------------------------------------
# E. an unknown future version fails closed, as do mixed versions and non-string values
# ---------------------------------------------------------------------------------------------------------------------


def test_e_unknown_future_version_fails_closed():
    future = si.stamp_map(_synthetic_map(), semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
    for contract in future.values():
        contract[se.SEMANTICS_VERSION_KEY] = "sufficiency-semantics-v99"
    with pytest.raises(si.SemanticsIdentityError, match="unsupported"):
        si.read_map_identity(future)


def test_e_mixed_versions_across_children_fail_closed():
    mixed = si.stamp_map(_synthetic_map(), semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
    mixed["c2"][se.SEMANTICS_VERSION_KEY] = "sufficiency-semantics-v0"
    with pytest.raises(si.SemanticsIdentityError):
        si.read_map_identity(mixed)


def test_e_a_non_string_version_fails_closed():
    bad = si.stamp_map(_synthetic_map(), semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
    for contract in bad.values():
        contract[se.SEMANTICS_VERSION_KEY] = ["sufficiency-semantics-v1"]
    with pytest.raises(si.SemanticsIdentityError, match="string"):
        si.read_map_identity(bad)


# ---------------------------------------------------------------------------------------------------------------------
# F / G. replay authorization binds the version; tampering fails closed
# ---------------------------------------------------------------------------------------------------------------------


def _current_run_dir(tmp_path: Path) -> Path:
    """A run directory whose map carries the version: the preserved map with I1 fields, stamped as a new production map.

    The stamp is the only change, so the answer outputs are unaffected. This simulates a newly produced versioned map.
    """
    from experiments.ask_cli_revised import relation_witness as rw_mod

    run = tmp_path / "run"
    run.mkdir()
    for name in ("11_verified_ledger.json", "13c_scoped_search.json", "15a_parent_synthesis.json"):
        (run / name).write_bytes((RUN / name).read_bytes())
    smap = json.loads(PRESERVED_MAP.read_text(encoding="utf-8"))
    sealed = json.loads(PRESERVED_LEDGER.read_text(encoding="utf-8"))
    rw_mod.attach_relation_witnesses(smap, sealed, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION)
    si.stamp_map(smap, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
    (run / "17_sufficiency_map.json").write_text(json.dumps(smap, indent=2, ensure_ascii=False), encoding="utf-8")
    return run


@_needs_preserved
def test_f_replay_authorization_binds_the_version_for_a_current_map(tmp_path):
    from experiments.ask_cli_revised.answer_plan import replay

    run = _current_run_dir(tmp_path)
    out = tmp_path / "out"
    assert replay.main(["--run-dir", str(run), "--out-dir", str(out)]) == 0  # strict: a current map is accepted
    authorization = json.loads((out / "replay_decomposition_authorization.json").read_text(encoding="utf-8"))
    assert authorization["bound_inputs"]["sufficiency_semantics"] == {"status": "current", "version": CURRENT}
    smap = json.loads((run / "17_sufficiency_map.json").read_text(encoding="utf-8"))
    replay.verify_replay_authorization(authorization, smap)  # does not raise


@_needs_preserved
def test_g_tampered_authorization_version_fails_closed(tmp_path):
    from experiments.ask_cli_revised.answer_plan import replay

    run = _current_run_dir(tmp_path)
    out = tmp_path / "out"
    replay.main(["--run-dir", str(run), "--out-dir", str(out)])
    authorization = json.loads((out / "replay_decomposition_authorization.json").read_text(encoding="utf-8"))
    smap = json.loads((run / "17_sufficiency_map.json").read_text(encoding="utf-8"))

    tampered = copy.deepcopy(authorization)
    tampered["bound_inputs"]["sufficiency_semantics"]["version"] = "sufficiency-semantics-v99"
    with pytest.raises(si.SemanticsIdentityError, match="digest"):
        replay.verify_replay_authorization(tampered, smap)  # stale digest is caught first

    # An attacker who also recomputes the digest is caught by the binding check against the map.
    forged = copy.deepcopy(tampered)
    body = {key: value for key, value in forged.items() if key != "authorization_sha256"}
    from experiments.ask_cli_revised.answer_plan import overlay as ov

    forged["authorization_sha256"] = ov.sha256_obj(body)
    with pytest.raises(si.SemanticsIdentityError, match="binds"):
        replay.verify_replay_authorization(forged, smap)


@_needs_preserved
def test_g_the_strict_replay_refuses_the_unversioned_preserved_map(tmp_path):
    from experiments.ask_cli_revised.answer_plan import replay

    with pytest.raises(si.SemanticsIdentityError, match="not accepted"):
        replay.main(["--run-dir", str(RUN), "--out-dir", str(tmp_path / "out")])


# ---------------------------------------------------------------------------------------------------------------------
# H. projection removing only the version plumbing is the exact pre-I1c structure
# ---------------------------------------------------------------------------------------------------------------------


def test_h_stripping_only_the_version_recovers_the_pre_i1c_structure_exactly():
    before = _synthetic_map()
    before["c1"]["requirements"][0]["instances"] = [
        {
            "instance_key": "i",
            "complete": True,
            "relation_witnessed": True,
            "witness_ids": ["p"],
            "witness_provenance": {"failure_reason": None},
        }
    ]
    after = si.stamp_map(copy.deepcopy(before), semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
    assert _canon(si.strip_identity(after)) == _canon(before)
    assert _canon(after) != _canon(before)  # the version is really serialised


# ---------------------------------------------------------------------------------------------------------------------
# I. the version causes no change to witness, recovery, stop-search, or ParentClaims
# ---------------------------------------------------------------------------------------------------------------------


@_needs_preserved
def test_i_the_version_changes_no_witness_recovery_stop_search_or_parent_claim_output():
    from experiments.ask_cli_revised import parent_synthesis_ledger as psl
    from experiments.ask_cli_revised import sufficiency_engine as se_mod

    sealed = json.loads(PRESERVED_LEDGER.read_text(encoding="utf-8"))
    plain = json.loads(PRESERVED_MAP.read_text(encoding="utf-8"))
    rw.attach_relation_witnesses(plain, sealed, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION)
    stamped = si.stamp_map(copy.deepcopy(plain), semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

    assert _canon(rel.relation_units(stamped, sealed, semantics_version=CURRENT)) == _canon(
        rel.relation_units(plain, sealed, semantics_version=CURRENT)
    )
    assert _canon(psl.build_claim_ledger(stamped, sealed)) == _canon(psl.build_claim_ledger(plain, sealed))
    assert _canon(srt.compute_recovery_targets(stamped, {}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)) == _canon(
        srt.compute_recovery_targets(plain, {}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
    )

    def stop_search(smap: dict) -> dict:
        return {
            f"{child}|{req['id']}": se_mod.compute_stop_search_certified(req)
            for child, contract in sorted(smap.items())
            for req in contract["requirements"]
        }

    assert stop_search(stamped) == stop_search(plain)


# ---------------------------------------------------------------------------------------------------------------------
# Authored contracts are never stamped, and the frozen artifact is unchanged
# ---------------------------------------------------------------------------------------------------------------------


def test_authored_frozen_contracts_carry_no_semantics_version():
    frozen = json.loads(
        (Path(__file__).resolve().parent / "sufficiency_contract.aib_hier_v9.frozen.json").read_text(encoding="utf-8")
    )
    assert se.SEMANTICS_VERSION_KEY not in _canon(frozen)


def test_the_future_change_invariant_is_recorded_in_the_engine():
    source = (Path(__file__).resolve().parent / "sufficiency_engine.py").read_text(encoding="utf-8")
    # The comment wraps across lines; join the comment text so the phrase check is about wording, not line breaks.
    comment = " ".join(line.lstrip("# ").strip() for line in source.splitlines() if line.lstrip().startswith("#"))
    assert "MUST bump SUFFICIENCY_SEMANTICS_VERSION" in comment
    assert "Authored contract changes need a new frozen contract version" in comment
