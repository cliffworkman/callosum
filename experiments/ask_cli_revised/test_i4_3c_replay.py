"""Real explicit v8 qualification; historical bytes and identity gates remain exact."""

import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import compatible_witness as cw
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised import test_i4_2a_replay as r
from experiments.ask_cli_revised import test_i4_2b3_replay as v6
from experiments.ask_cli_revised.answer_plan import overlay
from experiments.ask_cli_revised.answer_plan import replay as cli

V = se.SUFFICIENCY_SEMANTICS_V8
HISTORICAL = {
    "v4": "4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a",
    "v5": "109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77",
    "v6": "dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be",
    "v7": "04eb38b1ef12dc694c075279f7d03228a96ac5938cdb7d1bd9782957fb960c72",
}
NEW_FIELDS = {"witness_bundle", "joint_grounding", "witness_proofs", "evidence_alignment"}


@pytest.fixture(scope="module")
def replays():
    context = v6.context()
    result = {}
    for version in HISTORICAL:
        with (
            patch.object(cw, "build_support_views", side_effect=AssertionError("historical adapter call")),
            patch.object(cw, "select_completion_proofs", side_effect=AssertionError("historical selector call")),
            patch.object(r.sm, "attach_aligned_observations", side_effect=AssertionError("historical aligned scope")),
        ):
            result[version] = r.remap("sufficiency-semantics-" + version, ownership_context_index=context)
    result["v8"] = r.remap(V, ownership_context_index=context)
    return result


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from walk(item)


@pytest.mark.parametrize("version", HISTORICAL)
def test_exact_historical_bytes_and_no_new_fields(replays, version):
    assert hashlib.sha256(v6.replay_bytes(replays[version])).hexdigest() == HISTORICAL[version], (
        "STOP: historical drift"
    )
    assert not any(NEW_FIELDS & set(row) for row in walk(replays[version]))


def projection(value):
    # Only runtime witness explanation/alignment and version-dependent hashes are excluded.
    if isinstance(value, dict):
        return {
            k: projection(v) for k, v in value.items() if k not in NEW_FIELDS | {"witness_provenance", "plan_sha256"}
        }
    if isinstance(value, (tuple, list)):
        return [projection(v) for v in value]
    if isinstance(value, str):
        return value.replace(V, se.SUFFICIENCY_SEMANTICS_V7)
    return value


def test_real_proof_counts_and_semantic_parity(replays):
    a, b = replays["v7"], replays["v8"]
    baseline = json.loads(Path(__file__).with_name("witness_i4_3c_replay_baseline.json").read_text(encoding="utf-8"))
    assert baseline["identity"] == {"status": "supported_noncurrent", "version": V}
    assert baseline["current_default"] == se.SUFFICIENCY_SEMANTICS_V7
    assert {v: hashlib.sha256(v6.replay_bytes(value)).hexdigest() for v, value in replays.items()} == baseline["hashes"]
    assert projection(a) == projection(b), "STOP: unexpected real semantic delta"
    instances = [i for c in b["map"].values() for req in c["requirements"] for i in req["instances"]]
    proofs = [p for i in instances for p in i["witness_bundle"]["proofs"].values()]
    assert len(instances) == 46
    assert sum(len(i["witness_bundle"]["support_views"]) for i in instances) == 51
    assert sum(p["purpose"] == "completion_joint" for p in proofs) == 11
    assert sum(p["purpose"] == "i1_relation_witness" for p in proofs) == 9
    assert sum(i.get("relation_witnessed", False) for i in instances) == 8
    assert sum(len(c["requirements"]) for c in b["map"].values()) == 13
    assert len(b["targets"]) == 48 and b["targets"] == a["targets"]
    assert len(b["claims"]) == 17 and b["claims"] == a["claims"]
    assert len(b["plan"]["nodes"]) == 9
    assert b["layer1"] == a["layer1"]
    assert len(b["invariants"]) == 33 and all(c["passed"] for c in b["invariants"])
    directions = [o for i in instances for o in i.get("direction_observations", [])]
    assert len(directions) == 6 and all(not o["relation_eligible"] for o in directions)
    assert not any(i.get("effectiveness_observations") for i in instances)
    # Collector, attribution, guard/policy payloads, preserved model nominations: exact equality.
    assert r.evidence_rows(a["map"]) == r.evidence_rows(b["map"])
    assert a["diagnostics"] == b["diagnostics"]


def test_real_v8_identity_and_authorization(replays):
    mapped = replays["v8"]["map"]
    identity = {"status": "supported_noncurrent", "version": V}
    assert se.SUFFICIENCY_SEMANTICS_VERSION == se.SUFFICIENCY_SEMANTICS_V7
    assert V in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS
    assert V not in se.HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS
    for flags in (
        {},
        {"accept_historical_versioned": True},
        {"accept_historical_unversioned": True},
        {"accept_historical_versioned": True, "accept_historical_unversioned": True},
    ):
        with pytest.raises(si.SemanticsIdentityError):
            si.read_map_identity(mapped, **flags)
    assert si.read_map_identity(mapped, accept_supported_noncurrent=True) == identity
    assert si.applied_semantics_version(identity) == V
    si.check_authorization_binding(identity, mapped)
    for status in ("current", "historical_versioned"):
        with pytest.raises(si.SemanticsIdentityError):
            si.check_authorization_binding({"status": status, "version": V}, mapped)


def test_real_cli_replay_without_sentinel_or_semantic_test_double(replays, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    for name in ("11_verified_ledger.json", "13c_scoped_search.json", "15a_parent_synthesis.json"):
        (run / name).write_bytes((r.RUN / name).read_bytes())
    mapped = replays["v8"]["map"]
    (run / "17_sufficiency_map.json").write_text(r.canonical(mapped), encoding="utf-8")
    args = ["--run-dir", str(run), "--out-dir", str(tmp_path / "out")]
    for flags in (
        [],
        ["--allow-historical-versioned"],
        ["--allow-historical-unversioned-map"],
        ["--allow-historical-versioned", "--allow-historical-unversioned-map"],
    ):
        with pytest.raises(si.SemanticsIdentityError, match="supported_noncurrent"):
            cli.main(args + flags)
    assert cli.main(args + ["--allow-supported-noncurrent"]) == 0
    auth = json.loads((tmp_path / "out/replay_decomposition_authorization.json").read_text(encoding="utf-8"))
    assert auth["bound_inputs"]["sufficiency_semantics"] == {"status": "supported_noncurrent", "version": V}
    assert auth["bound_inputs"]["answer_containment_semantics"] == V
    assert auth["bound_inputs"]["answer_direction_semantics"] == V
    cli.verify_replay_authorization(auth, mapped)
    for status in ("current", "historical_versioned"):
        forged = copy.deepcopy(auth)
        forged["bound_inputs"]["sufficiency_semantics"]["status"] = status
        forged["authorization_sha256"] = overlay.sha256_obj(
            {k: v for k, v in forged.items() if k != "authorization_sha256"}
        )
        with pytest.raises(si.SemanticsIdentityError, match="binds"):
            cli.verify_replay_authorization(forged, mapped)
