"""I4-4C offline fixture and exact design identity qualification."""

import copy
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import layerc_projection as lp
from experiments.ask_cli_revised import test_i4_2a_replay as replay
from experiments.ask_cli_revised import test_i4_2b3_replay as v6
from experiments.ask_cli_revised._layerc_common import PROFILE, V8, digest, plain, semantic_claim_id, text_hash

FIXTURE = json.loads(Path(__file__).with_name("layerc_i4_4c_preregistered.json").read_text(encoding="utf-8"))


def authored(smap):
    return {
        "requirements": {
            c: [
                {k: copy.deepcopy(v) for k, v in r.items() if k not in lp.RUNTIME_REQUIREMENT_FIELDS}
                for r in contract["requirements"]
            ]
            for c, contract in smap.items()
        },
        "overlay": {"schema": "fixture-overlay-v1"},
    }


def profile(smap, raw, contract, contexts=()):
    props = {p["proposition_id"]: p for p in json.loads(raw)["verified_propositions"]}
    producer = {"identity": "offline-qualified-v8-producer", "output_map_sha256": digest(smap)}
    producer["receipt_sha256"] = digest(producer)
    result = {
        "name": PROFILE,
        "sufficiency_identity": {"status": "supported_noncurrent", "version": V8},
        "map_sha256": digest(smap),
        "sealed_artifact_sha256": text_hash(raw.decode()),
        "sealed_proposition_index_sha256": digest(props),
        "authored_contract_sha256": digest(contract["requirements"]),
        "overlay_sha256": digest(contract["overlay"]),
        "context_manifest_sha256": digest(contexts),
        "containment_semantics": V8,
        "direction_semantics": V8,
        "producer": producer,
    }
    result["authorization_sha256"] = digest(result)
    return result


@pytest.fixture(scope="module")
def real():
    result = replay.remap(V8, ownership_context_index=v6.context())
    smap = result["map"]
    raw = (replay.RUN / "11_verified_ledger.json").read_bytes()
    contract = authored(smap)
    contract["overlay"] = replay.overlay.load_overlay()
    return smap, raw, contract


def project(args, contexts=()):
    smap, raw, contract = args
    return lp.validate_layerc_inputs(
        smap, raw, contract, profile=profile(*args, contexts), optional_context_receipts=contexts
    )


def test_real_exact_values_and_immutable_inputs(real):
    before = copy.deepcopy(real)
    result = project(real)
    records = result.records
    expected = {v["value_id"] for v in FIXTURE["values"]}
    own = {
        r["value_id"]
        for r in records["value_coverage"].values()
        if r["establishment_refs"][0]["immediate_operand_source"] == "own"
    }
    assert own == expected
    assert len(expected) == 32
    assert len(records["support_views"]) == 51
    assert sum(m["diagnostic_only"] for m in records["candidate_metadata"].values()) == 5
    assert len(records["category_observations"]) == 7
    assert real == before
    with pytest.raises(TypeError):
        records["semantic_values"]["bad"] = {}
    value = next(iter(records["semantic_values"].values()))
    with pytest.raises(TypeError):
        value["kind"] = "bad"
    for row in FIXTURE["values"]:
        assert plain(records["semantic_values"][row["value_id"]]) == row["material"]
        actual_paths = [records["value_coverage"][ref] for ref in records["value_paths"][row["value_id"]]]
        assert {p["establishment_refs"][0]["ref"] for p in actual_paths} == {e["view_id"] for e in row["establishment"]}
        assert {p["scientific_goal_state"] for p in actual_paths} == {row["scientific"]}
        assert {
            source["proposition_id"] for p in actual_paths for source in p["authorized_display_source_refs"]
        } == set(row["authorized_display_source_inputs"])
        for obs in row["observations"]:
            assert plain(records["category_observations"][obs["id"]]) == obs["body"]
    for row in FIXTURE["inherited"]:
        assert row["value_id"] in records["semantic_values"]


def test_real_category_authority_and_future_fixture(real):
    p = project(real).records
    rows = [
        r
        for r in p["value_coverage"].values()
        if r["placement"]["requirement_id"] == "c3#suff:implicit-explicit-coverage"
    ]
    explicit = next(r for r in rows if r["placement"]["instance_key"] == "explicit")
    implicit = next(r for r in rows if r["placement"]["instance_key"] == "implicit")
    view = p["support_views"][explicit["establishment_refs"][0]["ref"]]
    assert view["supporting_proposition_ids"] == ("p8",)
    assert {
        p["category_observations"][e["ref"]]["observation"]["proposition_id"]
        for e in explicit["scientific_coverage_refs"]
    } == {"p8", "p36", "p52"}
    assert {e["proposition_id"] for e in explicit["authorized_display_source_refs"]} == {"p8", "p36", "p52"}
    # All three are authorized inputs; I4-4D presentation filters only p36 as preregistered.
    assert next(v for v in FIXTURE["values"] if v["n"] == 25)["display_ids"] == ["p36"]
    assert explicit["presentation"]["finalization_required"] is True
    assert implicit["scientific_goal_state"] == "unestablished"
    assert implicit["reported_finding"] == "null_finding"
    assert not implicit["scientific_coverage_refs"]
    assert {e["proposition_id"] for e in implicit["authorized_display_source_refs"]} == {"p36"}
    assert FIXTURE["future_node_contract"]["states"] == [
        "partial",
        "partial",
        "answered",
        "partial",
        "not_established",
        "partial",
        "partial",
        "not_established",
        "not_established",
    ]


def test_real_grouping_and_every_claim_member(real):
    p = project(real).records
    for claim in FIXTURE["claims"]:
        material = claim["semantic_identity_material"]
        assert (
            semantic_claim_id(material["family"], material["scope"], material["content"])
            == claim["prospective_semantic_id"]
        )
        assert claim["members"]
        for n in claim["members"]:
            row = next(v for v in FIXTURE["values"] if v["n"] == n)
            receipts = [p["value_coverage"][r] for r in p["value_paths"][row["value_id"]]]
            assert receipts and all(r["establishment_refs"] for r in receipts)
            assert all("citation_source_refs" in r and "authorized_display_source_refs" in r for r in receipts)
    for n, count in ((21, 2), (32, 4)):
        value = next(v["value_id"] for v in FIXTURE["values"] if v["n"] == n)
        assert len(p["value_paths"][value]) == count
        assert any(value in g["members"] and len(g["members"][value]) == count for g in p["grouping"].values())
