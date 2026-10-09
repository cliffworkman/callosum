"""Hash-verified offline v4/v5/v6 gates; no nomination, retrieval, or model calls."""

import copy
import hashlib
import json
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import ownership_context as oc
from experiments.ask_cli_revised import qwen
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_model_scope as scope
from experiments.ask_cli_revised import test_i4_2a_replay as replay

PACKET_HASH = "1949dc56e4abcbb58f7ebf512387c3c6041bdf0a2176facd64aaf44bea1e83f6"
HASHES = {
    "v4": "4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a",
    "v5": "109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77",
}


def context():
    sealed, _ = replay.inputs()
    path = replay.RUN / "08_evidence_packets.jsonl"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PACKET_HASH
    packets = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return oc.build_context_index(sealed, packets)


def replay_bytes(value):
    # Accepted baseline artifacts are sorted JSON, UTF-8, CRLF and one terminal newline.
    return (replay.canonical(value) + "\n").replace("\n", "\r\n").encode("utf-8")


@pytest.fixture(scope="module")
def results():
    index = context()
    return index, {
        v: replay.remap("sufficiency-semantics-" + v, ownership_context_index=index) for v in ("v4", "v5", "v6")
    }


def candidates(result):
    return [
        (row, c) for row in replay.evidence_rows(result["map"]) for c in row["binding"].get("candidate_supports", [])
    ]


@replay.needs_run
@pytest.mark.parametrize("version", ["v4", "v5"])
def test_historical_hashes(results, version):
    assert hashlib.sha256(replay_bytes(results[1][version])).hexdigest() == HASHES[version]


@replay.needs_run
def test_E35_v5_does_not_consume_context():
    with (
        patch.object(oc, "context_for", side_effect=AssertionError("v5 inspected context")),
        patch.object(aa, "_corrected_fields", side_effect=AssertionError("v5 entered corrected classifier")),
    ):
        actual = replay.remap(se.SUFFICIENCY_SEMANTICS_V5, ownership_context_index={"malformed": True})
    assert hashlib.sha256(replay_bytes(actual)).hexdigest() == HASHES["v5"]


@replay.needs_run
def test_E01_E02_E03_six_changes_and_no_seventh(results):
    _, runs = results
    before, after = candidates(runs["v5"]), candidates(runs["v6"])
    assert len(before) == len(after) == 10
    changed = []
    for (oldrow, old), (newrow, new) in zip(before, after, strict=True):
        assert "attribution" not in old
        se.validate_candidate_attribution(new)
        assert new["admissible"] is new["inadmissibility_reason"] is None
        # The conservative predicate is TEST ONLY. Production never evaluates it.
        assert new["assertion_kind"] == "result" and not (
            new["assertion_relation"] == "unresolved" and new["aggregation"] == "non_synthetic_or_unspecified"
        )
        if old["assertion_relation"] != new["assertion_relation"]:
            changed.append((oldrow["child"], new["span_proposition_id"], new["assertion_relation"]))
        for key in old:
            if key not in ("assertion_relation", "support_label"):
                assert old[key] == new[key], key
        assert oldrow["instance_key"] == newrow["instance_key"]
    assert changed == [
        ("c1", "p2", "current_document"),
        ("c4", "p11", "current_document"),
        ("c4", "p40", "attributed_external"),
        *[("c8", "p41", "current_document")] * 3,
    ]
    r1 = [c["attribution"]["proofs"] for row, c in after if c["span_proposition_id"] in ("p2", "p11")]
    assert r1[0] == r1[1]
    assert len(r1[0]) == 1
    assert r1[0][0]["source"]["chunk_id"] == 34974
    r2 = next(c for _, c in after if c["span_proposition_id"] == "p40")
    assert r2["attribution"]["proofs"][0]["citation_set"] == [6]
    p41 = [c for _, c in after if c["span_proposition_id"] == "p41"]
    assert [c["assertion_span"] for c in p41] == [[43, 200]] * 2 + [[208, 372]] * 3


def same_version(value):
    if isinstance(value, str):
        return value.replace("sufficiency-semantics-v6", "sufficiency-semantics-v5")
    if isinstance(value, list):
        return [same_version(v) for v in value]
    if isinstance(value, dict):
        return {k: same_version(v) for k, v in value.items() if k != "plan_sha256"}
    return value


@replay.needs_run
def test_complete_downstream_semantic_parity(results):
    _, runs = results
    old, new = copy.deepcopy(runs["v5"]), copy.deepcopy(runs["v6"])
    for (_, a), (_, b) in zip(candidates(old), candidates(new), strict=True):
        del b["attribution"]
        b["assertion_relation"] = a["assertion_relation"]
        b["support_label"] = a["support_label"]
    assert same_version(new) == same_version(old)
    rows = replay.evidence_rows(runs["v6"]["map"])
    assert len(rows) == 26
    assert sum(r["binding"]["state"] == "filled" for r in rows) == 10
    assert sum(r["binding"]["state"] == "missing" for r in rows) == 16
    assert sum(len(c["requirements"]) for c in new["map"].values()) == 13
    assert len(new["targets"]) == 48
    assert len(new["claims"]) == 17
    assert len(new["plan"]["nodes"]) == 9
    assert len(new["invariants"]) == 33
    assert all(r["passed"] for r in new["invariants"])


@replay.needs_run
def test_model_facing_equality(results):
    sealed, contracts = replay.inputs()
    old = sd.units_by_child(sealed)
    new = sd.units_by_child(sealed, ownership_context_index=results[0])
    scopes_checked = 0
    for cid, contract in contracts.items():
        for req in contract["requirements"]:
            for spec in req["role_specs"].values():
                if spec["mapping_strategy"] != "model_nomination_only":
                    continue
                a = sm._candidate_rows_for_role(spec, old.get(cid, []))
                b = sm._candidate_rows_for_role(spec, new.get(cid, []))
                assert a == b
                kwargs = {"category_description": spec["category_description"]}
                assert scope.request_fingerprint(**kwargs, candidate_rows=a) == scope.request_fingerprint(
                    **kwargs, candidate_rows=b
                )
                assert qwen.nomination_prompt(**kwargs, candidates=a) == qwen.nomination_prompt(**kwargs, candidates=b)
                scopes_checked += 1
    assert scopes_checked > 0
    assert results[1]["v5"]["targets"] == results[1]["v6"]["targets"]


@replay.needs_run
def test_v6_frozen_baseline(results):
    manifest = json.loads(
        (replay.ROOT / "experiments/ask_cli_revised/attribution_i4_2b3_replay_baseline.json").read_text()
    )
    assert hashlib.sha256(replay_bytes(results[1]["v6"])).hexdigest() == manifest["v6_sha256"]
    assert results[0]["manifest_sha256"] == manifest["context_manifest_sha256"]
