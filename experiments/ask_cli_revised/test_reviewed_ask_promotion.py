"""Real current reviewed execution, strict historical pins, and scientific parity."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import e2e, fresh_invocation, reviewed_ask
from experiments.ask_cli_revised import producer_replay as issuer
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised._layerc_common import digest
from experiments.ask_cli_revised.answer_plan import plan, plan_v5
from experiments.ask_cli_revised.test_fresh_recorded_identity import verify
from experiments.ask_cli_revised.test_reviewed_fresh import run_public

BASE = Path(__file__).parent
ROOT = BASE.parents[1]
# Already observed in E1B's actual public recovery controls; not new semantic baselines.
E1B_MAP_HASHES = (
    "b3930349c64ca8308157c4685b557fd12f4a888b46c4bb196c0319071e783be4",
    "d3276cd074eb12e0bfb8d5d9894e628ef81452cfe364983d4894fe588822b365",
)


@pytest.mark.parametrize("relational", [False, True])
def test_current_public_u1_u2_threads_v8_and_preserves_science(monkeypatch, relational):
    calls = []

    def watch(module, name):
        original = getattr(module, name)

        def wrapped(*args, **kwargs):
            calls.append((name, kwargs["semantics_version"]))
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, wrapped)

    for name in ("compute_diagnostic_sufficiency_map", "compute_direction_and_effectiveness"):
        watch(e2e.sufficiency_diagnostic, name)
    for name in ("compute_recovery_targets", "search_obligations", "terminal_search_status"):
        watch(e2e.sufficiency_recovery_targets, name)
    result = run_public(monkeypatch, relational=relational, recovery=True)
    out = result["layerc_v2"]
    assert reviewed_ask.CURRENT_SEMANTICS_VERSION == "sufficiency-semantics-v8"
    assert reviewed_ask.CURRENT_PLAN_VERSION == plan_v5.PLAN_VERSION == "answer-plan-step2-v5"
    assert out["plan"]["plan_version"] == reviewed_ask.CURRENT_PLAN_VERSION
    assert out["plan"]["sufficiency_identity"] == {"status": "current", "version": "sufficiency-semantics-v8"}
    assert out["plan"]["upstream_authority"]["kind"] == "trusted_fresh_invocation"
    assert out["plan"]["schemas"]["parent_synthesis"] == "parent-synthesis-v2"
    assert out["plan"]["schemas"]["parent_claim"] == "parent-claim-v2"
    assert all(version == reviewed_ask.CURRENT_SEMANTICS_VERSION for _, version in calls)
    assert [n for n, _ in calls].count("compute_diagnostic_sufficiency_map") == 2
    assert [n for n, _ in calls].count("compute_direction_and_effectiveness") == 2
    assert {"compute_recovery_targets", "search_obligations", "terminal_search_status"} <= {n for n, _ in calls}
    assert digest(result["sufficiency_map_final"]) == E1B_MAP_HASHES[relational]
    assert out["invocation_provenance"]["recovery_sha256"] == digest({})
    assert out["invocation_provenance"]["search_sha256"] == digest({})
    assert out["render"]["layer1"] == result["selected_answer"]
    assert (
        "positively associated" in result["selected_answer"]
        if relational
        else "alpha increased" in result["selected_answer"]
    )
    # No process-global version patch or promotion of the historical serializer.
    assert se.SUFFICIENCY_SEMANTICS_VERSION == "sufficiency-semantics-v7"
    assert plan.PLAN_VERSION == "answer-plan-step2-v4"


def test_current_ask_and_exact_installed_historical_producer_coexist(monkeypatch):
    manifest = json.loads(
        next((BASE / "producer_authorization_material").glob("producer-code-input-manifest-*.json")).read_bytes()
    )
    assert len(manifest["files"]) == 26
    for path, expected in manifest["files"].items():
        raw = (ROOT / path).read_bytes().decode().replace("\r\n", "\n").replace("\r", "\n").encode()
        assert hashlib.sha256(raw).hexdigest() == expected, path
    historical = issuer.reproduce_accepted_v8()
    authorization = verify(historical)
    fresh = run_public(monkeypatch)
    assert fresh["layerc_v2"]["plan"]["sufficiency_identity"]["status"] == "current"
    assert verify(historical) == authorization
    assert dict(authorization.identities["sufficiency_identity"]) == {
        "status": "supported_noncurrent",
        "version": "sufficiency-semantics-v8",
    }
    # The pinned legacy reader does not retroactively adopt the new invocation default.
    with pytest.raises(si.SemanticsIdentityError, match="supported_noncurrent"):
        si.read_map_identity(historical.smap)
    assert si.read_map_identity(historical.smap, accept_supported_noncurrent=True) == dict(
        authorization.identities["sufficiency_identity"]
    )
    forged = copy.deepcopy(historical.receipt)
    forged["sufficiency_identity"]["status"] = "current"
    from dataclasses import replace

    with pytest.raises(ValueError):
        verify(replace(historical, receipt=forged))


@pytest.mark.parametrize("bad", ["empty", "missing", "v7", "mixed", "nonmapping", "unknown", "nonstring"])
def test_fresh_handoff_cannot_relabel_wrong_or_unstamped_map(monkeypatch, bad):
    finish = fresh_invocation._Execution.finish

    def corrupt(self, **kwargs):
        smap = copy.deepcopy(kwargs["smap"])
        child = next(iter(smap))
        key = se.SEMANTICS_VERSION_KEY
        if bad == "empty":
            smap = {}
        elif bad == "missing":
            del smap[child][key]
        elif bad == "nonmapping":
            smap[child] = []
        elif bad == "mixed":
            smap["another"] = {key: se.SUFFICIENCY_SEMANTICS_V7}
        else:
            smap[child][key] = {"v7": se.SUFFICIENCY_SEMANTICS_V7, "unknown": "unknown", "nonstring": 8}[bad]
        return finish(self, **{**kwargs, "smap": smap})

    monkeypatch.setattr(fresh_invocation._Execution, "finish", corrupt)
    with pytest.raises(ValueError, match="invocation's current semantic version"):
        run_public(monkeypatch)
