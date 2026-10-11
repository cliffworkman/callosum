"""Real enrolled profile-B qualification, exact preregistration and authority ordering."""

import base64
import copy
import json
import socket
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import layerc_consumer as bridge
from experiments.ask_cli_revised import parent_synthesis_v2 as synthesis
from experiments.ask_cli_revised import producer_replay as issuer
from experiments.ask_cli_revised import profile_b as consumer
from experiments.ask_cli_revised import profile_b_replay
from experiments.ask_cli_revised import test_layerc_projection as prereg
from experiments.ask_cli_revised import test_producer_tamper as tamper
from experiments.ask_cli_revised._layerc_common import PROFILE, ProjectionIntegrityError, canonical, digest, plain


@pytest.fixture(scope="module")
def real():
    with patch.object(socket.socket, "connect", side_effect=AssertionError("offline qualification")):
        reproduction = issuer.reproduce_accepted_v8()
    raw = reproduction.input_bundle.files["preserved-run/11_verified_ledger.json"]
    before = canonical(
        [
            reproduction.smap,
            reproduction.receipt,
            reproduction.authored_contract,
            plain(reproduction.input_bundle.recovery_targets),
        ]
    )
    with patch.object(issuer, "reproduce_accepted_v8", side_effect=AssertionError("consumer must verify, not issue")):
        result = consumer.build_profile_b(
            reproduction.smap,
            raw,
            reproduction.authored_contract,
            reproduction.receipt,
            input_bundle=reproduction.input_bundle,
            profile=PROFILE,
        )
    assert before == canonical(
        [
            reproduction.smap,
            reproduction.receipt,
            reproduction.authored_contract,
            plain(reproduction.input_bundle.recovery_targets),
        ]
    )
    return reproduction, result


def build(reproduction, **changes):
    args = dict(
        smap=reproduction.smap,
        sealed_bytes=reproduction.input_bundle.files["preserved-run/11_verified_ledger.json"],
        authored_contract=reproduction.authored_contract,
        producer_receipt=reproduction.receipt,
        input_bundle=reproduction.input_bundle,
        profile=PROFILE,
    )
    args.update(changes)
    return consumer.build_profile_b(**args)


def test_exact_real_identity_counts_and_claim_material(real):
    rep, result = real
    assert (
        result["plan"]["projection_ref"]
        == "layerc-validated-projection-v1:sha256:13f2174081d418d3ec7ef1fd72fc118d0c485f6f8f9503c150147a61eb4472fa"
    )
    assert (
        result["plan"]["verified_producer_authorization_ref"]
        == "verified-producer-authorization-v1:sha256:aa9ccbfa94f100a4c8cc0cbe85f60f27eebb289528e0f280447f0fcd23bb04b2"
    )
    expected = {c["prospective_semantic_id"]: c["semantic_identity_material"] for c in prereg.FIXTURE["claims"]}
    assert {c["claim_id"]: c["semantic_identity"] for c in result["claims"]} == expected
    assert len(result["claims"]) == 17 and len(result["relation_units"]) == 41
    own = {v for c in result["claims"] for v in c["member_value_refs"]}
    assert own == {v["value_id"] for v in prereg.FIXTURE["values"]} and len(own) == 32
    assert all(
        any(x["value_ref"] == v["value_id"] for x in result["value_coverage"].values())
        for v in prereg.FIXTURE["inherited"]
    )
    assert len(prereg.FIXTURE["inherited"]) == 13
    assert digest(rep.smap) == "e1c6d1027c96098dce96b7c86ee9259d1c50e379845c1d9bb3adeb62ba00b8cf"
    assert len(rep.input_bundle.recovery_targets) == 48


def test_exact_real_display_paths_and_nine_nodes(real):
    _, x = real
    for value in prereg.FIXTURE["values"]:
        paths = [p for p in x["value_coverage"].values() if p["value_ref"] == value["value_id"]]
        assert sorted({a["prop_id"] for p in paths for a in p["accepted"]}) == value["display_ids"]
        assert {p["scientific_goal_state"] for p in paths} == {value["scientific"]}
        assert {p["reported_finding"] for p in paths} == {value["finding"]}
    assert [n["state"] for n in x["plan"]["nodes"]] == prereg.FIXTURE["future_node_contract"]["states"]
    node = next(n for n in x["plan"]["nodes"] if n["label"] == "3")
    category = next(f for f in node["facets"] if f["category_axes"])
    assert category["report_state"] == "answered" and category["scientific_goal_state"] == "incomplete"
    assert category["covered_categories"] == ["explicit", "implicit"]
    assert category["category_axes"]["implicit"]["reported_finding"] == "null_finding"
    assert category["category_axes"]["implicit"]["scientific_goal_state"] == "unestablished"
    assert not category["recovery_closed_by_reporting"]


def test_p8_p36_and_value_specific_citation_transport(real):
    rep, x = real
    req = next(q for q in rep.smap["c3"]["requirements"] if q["instance_quantifier"] == "all_requested_categories")
    explicit = next(i for i in req["instances"] if i["instance_key"] == "explicit")
    assert explicit["role_bindings"]["category_evidence"]["proposition_id"] == "p8"
    assert all(v["supporting_proposition_ids"] == ["p8"] for v in explicit["witness_bundle"]["support_views"].values())
    receipts = x["claim_evidence"]
    for node in x["render"]["nodes"]:
        for statement in node["statements"]:
            for member in statement["members"]:
                receipt = receipts[member["receipt_ref"]]
                assert receipt["value_ref"] == member["value_ref"]
                assert member["source_ref"] in receipt["citation"]
    assert not any(
        "does not establish" in limitation["text"]
        for node in x["render"]["nodes"]
        for limitation in node["limitations"]
        if limitation["kind"] == "presentation_limitation"
    )


@pytest.mark.parametrize("value", [None, {}, "callosum.qaib.preserved-v8-reproduction"])
def test_raw_verified_lookalikes_fail_before_projection(real, value):
    rep, _ = real
    with patch.object(bridge.lp, "validate_layerc_inputs", side_effect=AssertionError("projection entered")):
        with pytest.raises(ProjectionIntegrityError):
            bridge.project_authorized(
                rep.smap,
                rep.input_bundle.files["preserved-run/11_verified_ledger.json"],
                rep.authored_contract,
                rep.receipt,
                input_bundle=rep.input_bundle,
                verified_authorization=value,
            )


@pytest.mark.parametrize("attack", ["missing", "raw_id", "map", "disposition", "revoked", "downstream", "nomination"])
def test_upstream_rejections_before_projection(real, attack, monkeypatch):
    rep, output = real
    changes = {}
    if attack in ("missing", "raw_id", "downstream"):
        changes["producer_receipt"] = {"missing": None, "raw_id": "known", "downstream": output["output_manifest"]}[
            attack
        ]
    elif attack == "map":
        smap = copy.deepcopy(rep.smap)
        smap["c1"]["requirements"][0]["state"] = "missing"
        changes["smap"] = smap
    elif attack == "disposition":
        receipt = copy.deepcopy(rep.receipt)
        receipt["sufficiency_identity"]["status"] = "current"
        changes["producer_receipt"] = receipt
    elif attack == "nomination":
        changes["input_bundle"] = replace(rep.input_bundle, nominations=())
    else:
        registry = tamper.trusted_test_registry(lifecycle="revoked")
        monkeypatch.setattr(bridge, "load_trusted_producer_registry", lambda: registry)
    with patch.object(bridge.lp, "validate_layerc_inputs", side_effect=AssertionError("projection entered")):
        with pytest.raises(ValueError):
            build(rep, **changes)


def test_ordering_and_no_consumer_issuance(real, monkeypatch):
    rep, expected = real
    calls = []
    verify, project = bridge.pa.verify_producer_authorization, bridge.lp.validate_layerc_inputs

    def verified(*a, **kw):
        result = verify(*a, **kw)
        calls.append("verified")
        return result

    def projected(*a, **kw):
        assert calls and calls[-1] == "verified"
        calls.append("projection")
        return project(*a, **kw)

    monkeypatch.setattr(bridge.pa, "verify_producer_authorization", verified)
    monkeypatch.setattr(bridge.lp, "validate_layerc_inputs", projected)
    with patch.object(issuer, "reproduce_accepted_v8", side_effect=AssertionError("re-issuance")):
        assert build(rep) == expected
    assert calls == ["verified", "verified", "projection"]


@pytest.mark.parametrize(
    "field",
    [
        "claims",
        "claim_evidence",
        "relation_units",
        "value_coverage",
        "parent_synthesis",
        "plan",
        "render",
        "output_manifest",
    ],
)
def test_output_tamper_is_rejected(real, field):
    _, original = real
    result = copy.deepcopy(original)
    if isinstance(result[field], dict):
        result[field]["unknown"] = True
    else:
        result[field].append({"unknown": True})
    with pytest.raises(ValueError):
        consumer.validate_output(result)


def test_frozen_B_baseline_and_inherited_transport(real):
    _, result = real
    frozen = json.loads(Path(__file__).with_name("layerc_i4_4d2_profile_b_baseline.json").read_text(encoding="utf-8"))
    for key in ("output_manifest", "output_manifest_ref", "combined_sha256"):
        assert result[key] == frozen[key]
    inherited = [
        p
        for p in result["value_coverage"].values()
        if p["coverage"]["establishment_refs"][0]["immediate_operand_source"] == "inherited"
    ]
    assert len(inherited) == 13
    assert all(p["semantic_value"]["schema"] == "semantic-value-v1" for p in inherited)


def test_snapshot_replay_verifies_without_issuance(real, tmp_path, monkeypatch):
    rep, expected = real
    bundle = rep.input_bundle
    snapshot = {
        "schema": "profile-b-input-snapshot-v1",
        "map": rep.smap,
        "sealed_bytes": base64.b64encode(bundle.files["preserved-run/11_verified_ledger.json"]).decode(),
        "authored_contract": rep.authored_contract,
        "producer_receipt": rep.receipt,
        "input_bundle": {
            **{
                k: plain(getattr(bundle, k))
                for k in ("nominations", "replay_requests", "ownership_context", "recovery_targets")
            },
            "files": {k: base64.b64encode(v).decode() for k, v in bundle.files.items()},
        },
    }
    path = tmp_path / "snapshot.json"
    path.write_text(canonical(snapshot), encoding="utf-8")

    def denied(*args, **kwargs):
        raise AssertionError("consumer invoked issuer")

    monkeypatch.setattr(issuer, "reproduce_accepted_v8", denied)
    actual = profile_b_replay.replay(path, tmp_path / "output")
    assert actual == expected
    assert json.loads((tmp_path / "output/profile_b_output.json").read_text(encoding="utf-8")) == expected
    with pytest.raises(ValueError, match="must be new"):
        profile_b_replay.replay(path, tmp_path / "output")


@pytest.mark.parametrize("change", ["value_ref", "receipt_ref", "source_ref", "text", "reported_finding"])
def test_typed_realization_does_not_borrow_between_members(real, change):
    _, output = real
    segment = next(s for s in output["parent_synthesis"]["segments"] if s["items"])
    claim = next(c for c in output["claims"] if c["claim_id"] == segment["claim_ref"])
    item = copy.deepcopy(segment["items"][0])
    args = (output["claim_evidence"], output["value_coverage"], output["relation_units"])
    assert synthesis.claim_value_reasons(claim, item, *args) == []
    item[change] = "foreign"
    assert synthesis.source_passage_reasons(claim, item, *args) == ["unauthorized_value_path"]


def test_v2_synthesis_audit_rebuild_rejects_changed_segments(real):
    rep, output = real
    bound = bridge.verify_and_project(
        rep.smap,
        rep.input_bundle.files["preserved-run/11_verified_ledger.json"],
        rep.authored_contract,
        rep.receipt,
        input_bundle=rep.input_bundle,
    )
    args = (
        output["claims"],
        bound.projection,
        output["claim_evidence"],
        output["value_coverage"],
        output["relation_units"],
    )
    assert synthesis.audit(output["parent_synthesis"], *args)["valid"]
    changed = copy.deepcopy(output["parent_synthesis"])
    next(s for s in changed["segments"] if s["items"])["items"][0]["reported_finding"] = "invented"
    with pytest.raises(ValueError, match="rebuild"):
        synthesis.audit(changed, *args)
