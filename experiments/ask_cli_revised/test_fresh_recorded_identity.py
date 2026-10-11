"""Recorded qualification and fresh routing coexist; exact replay bytes stay historical."""

import copy

import pytest

from experiments.ask_cli_revised import producer_authorization as pa
from experiments.ask_cli_revised import producer_authorization_store as store
from experiments.ask_cli_revised import producer_replay as issuer
from experiments.ask_cli_revised import profile_b
from experiments.ask_cli_revised import reporting_contract as rc
from experiments.ask_cli_revised import reporting_qualification as rq
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised._layerc_common import PROFILE, canonical
from experiments.ask_cli_revised.recorded_sufficiency_identity import check_recorded_binding
from experiments.ask_cli_revised.test_reviewed_fresh import run_public


@pytest.fixture(scope="module")
def reproduction():
    return issuer.reproduce_accepted_v8()


def verify(rep):
    return pa.verify_producer_authorization(
        rep.smap,
        rep.input_bundle.files["preserved-run/11_verified_ledger.json"],
        rep.authored_contract,
        rep.receipt,
        input_bundle=rep.input_bundle,
        trusted_registry=store.load_trusted_producer_registry(),
    )


def test_recorded_and_fresh_current_coexist(monkeypatch, reproduction):
    rep = reproduction
    old = verify(rep)
    with monkeypatch.context() as current:
        current.setattr(se, "SUFFICIENCY_SEMANTICS_VERSION", se.SUFFICIENCY_SEMANTICS_V8)
        assert si.read_map_identity(rep.smap) == {"status": "current", "version": se.SUFFICIENCY_SEMANTICS_V8}
        assert verify(rep) == old
        assert old.identities["sufficiency_identity"]["status"] == "supported_noncurrent"
        fresh = run_public(current)
        assert fresh["layerc_v2"]["plan"]["sufficiency_identity"]["status"] == "current"
        result = profile_b.build_profile_b(
            rep.smap,
            rep.input_bundle.files["preserved-run/11_verified_ledger.json"],
            rep.authored_contract,
            rep.receipt,
            input_bundle=rep.input_bundle,
            profile=PROFILE,
        )
        assert result["combined_sha256"] == "e697596b8fb3dd3ce426cdc1b82909ca93f4bbc3346e46b74bf2f96f980eafde"
        # The runtime checker remains strict; only authenticated recorded events use the new checker.
        with pytest.raises(ValueError):
            si.check_authorization_binding(dict(old.identities["sufficiency_identity"]), rep.smap)
        import hashlib

        from experiments.ask_cli_revised import test_i4_2a_replay as replay
        from experiments.ask_cli_revised import test_i4_2b3_replay as v6

        legacy = replay.remap(se.SUFFICIENCY_SEMANTICS_V8, ownership_context_index=v6.context())
        assert (
            hashlib.sha256(v6.replay_bytes(legacy)).hexdigest()
            == "1b8c89473bf1cf7d562483c29f6d14c1ef503de2788f3d81563842a1cc7659f0"
        )
    assert se.SUFFICIENCY_SEMANTICS_VERSION == se.SUFFICIENCY_SEMANTICS_V7
    assert verify(rep) == old


def test_qualification_view_not_new_historical_serialization(reproduction):
    rep = reproduction
    before = canonical([rep.smap, rep.receipt, rep.authored_contract])
    view = rq.reporting_view(
        rep.smap,
        rep.input_bundle.files["preserved-run/11_verified_ledger.json"],
        rep.authored_contract,
        rep.receipt,
        input_bundle=rep.input_bundle,
    )
    expected = rep.authored_contract["overlay"]
    assert rc.consumer_view(view["reporting"]) == {
        "nodes": [
            {k: n.get(k) for k in ("label", "literal_text", "parent", "owning_child_ids")} for n in expected["nodes"]
        ],
        "requested_construct_terms": expected["requested_construct_terms"],
    }
    assert view["provenance"]["claims_live_run_possession"] is False
    assert before == canonical([rep.smap, rep.receipt, rep.authored_contract])
    bad = copy.deepcopy(rep.receipt)
    bad["sufficiency_identity"]["status"] = "current"
    with pytest.raises(ValueError):
        rq.reporting_view(
            rep.smap,
            rep.input_bundle.files["preserved-run/11_verified_ledger.json"],
            rep.authored_contract,
            bad,
            input_bundle=rep.input_bundle,
        )


@pytest.mark.parametrize(
    "status,version",
    [
        ("latest", "sufficiency-semantics-v8"),
        ("current", "sufficiency-semantics-v8"),
        ("supported_noncurrent", "sufficiency-semantics-v9"),
    ],
)
def test_recorded_forgery_rejected(status, version):
    authorized = {"status": "supported_noncurrent", "version": "sufficiency-semantics-v8"}
    with pytest.raises(ValueError):
        check_recorded_binding(
            {"status": status, "version": version},
            {"child": {se.SEMANTICS_VERSION_KEY: "sufficiency-semantics-v8"}},
            authorized_identity=authorized,
        )
