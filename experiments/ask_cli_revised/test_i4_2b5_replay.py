"""Offline v7 replay, independent historical hashes and exact semantic/model isolation."""

import copy
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import qwen
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_model_scope as scope
from experiments.ask_cli_revised import test_i4_2a_replay as r
from experiments.ask_cli_revised import test_i4_2b3_replay as v6

HASHES = {**v6.HASHES, "v6": "dabef2f553b5e9301f9daa3a344b624ee6afb3e0f41fbce18b096587736822be"}


@pytest.fixture(scope="module")
def results():
    context = v6.context()
    return {v: r.remap("sufficiency-semantics-" + v, ownership_context_index=context) for v in ("v4", "v5", "v6", "v7")}


@pytest.mark.parametrize("version", HASHES)
@r.needs_run
def test_historical_hard_gate(results, version):
    assert hashlib.sha256(v6.replay_bytes(results[version])).hexdigest() == HASHES[version], (
        "STOP: historical replay drift"
    )


def rowkey(row):
    return row["child"], row["role"], row["instance_key"]


@r.needs_run
def test_frozen_four_version_baseline(results):
    manifest = json.loads(
        Path(__file__).with_name("support_policy_i4_2b5_replay_baseline.json").read_text(encoding="utf-8")
    )
    assert manifest["context_manifest_sha256"] == v6.context()["manifest_sha256"]
    for version, result in results.items():
        assert hashlib.sha256(v6.replay_bytes(result)).hexdigest() == manifest["hashes"][version]


def strip_version(value):
    if isinstance(value, str):
        return value.replace("sufficiency-semantics-v7", "sufficiency-semantics-v6")
    if isinstance(value, list):
        return [strip_version(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_version(v) for k, v in value.items() if k != "plan_sha256"}
    return value


@r.needs_run
def test_real_candidate_and_complete_downstream_hard_gate(results):
    old, new = copy.deepcopy(results["v6"]), copy.deepcopy(results["v7"])
    before, after = r.evidence_rows(old["map"]), r.evidence_rows(new["map"])
    assert len(before) == len(after) == 26
    assert Counter(x["binding"]["state"] for x in after) == {"filled": 10, "missing": 16}
    assert sum(len(c["requirements"]) for c in new["map"].values()) == 13
    extra = []
    for a, b in zip(before, after, strict=True):
        assert rowkey(a) == rowkey(b)
        ac = a["binding"].pop("candidate_supports", [])
        bc = b["binding"].pop("candidate_supports", [])
        assert all(
            c["admissible"] is None and "guard_exclusions" not in c and "support_policy_evaluation" not in c for c in ac
        )
        for i, c in enumerate(bc):
            se.validate_evaluated_candidate_support(c)
            if i < len(ac):
                assert c["guard_exclusions"] == [] and c["admissible"] is True
                assert c["support_policy_evaluation"]["passed"] is True
                stripped = {k: v for k, v in c.items() if k not in ("guard_exclusions", "support_policy_evaluation")}
                stripped["admissible"] = None
                assert stripped == ac[i], "STOP: original grounding or attribution drift"
            else:
                extra.append((b, c))
        if b["binding"]["reason"] == "candidate_supports_excluded":
            assert b["child"] == "c8" and a["binding"]["reason"] == "not_found"
            b["binding"]["reason"] = "not_found"
        assert a == b
    assert len(extra) == 5
    expected = json.loads(
        Path(__file__).with_name("support_policy_i4_2b5_expected_new_candidates.json").read_text(encoding="utf-8")
    )["candidates"]
    for (row, candidate), frozen in zip(extra, expected, strict=True):
        assert rowkey(row) == (frozen["child"], frozen["role"], frozen["instance_key"])
        assert candidate == {
            k: v for k, v in frozen.items() if k not in ("child", "requirement", "role", "instance_key")
        }
    assert Counter(row["child"] for row, c in extra) == {"c3": 1, "c8": 4}
    assert {row["instance_key"] for row, c in extra} == {
        None,
        "U6::b2958c5ad5164563",
        "U6::ce8933c59b53a00f",
        "U6::da37435ef9b489b6",
        "U6::d41542e10edf3ea7",
    }
    for row, c in extra:
        assert c["supporting_proposition_ids"] == (["p9", "p20"] if row["child"] == "c3" else ["p20", "p9"])
        assert c["assertion_span"] == [0, 302] and c["predicate_span"] == [250, 260] and c["content_span"] == [250, 303]
        assert c["assertion_relation"] == "current_document"
        assert c["aggregation"] == "non_synthetic_or_unspecified" and c["assertion_kind"] == "interpretation"
        assert c["guard_exclusions"] == ["hedged"] and c["admissible"] is False
        assert c["inadmissibility_reason"] == "guard_and_support_policy_excluded"
        assert c["support_policy_evaluation"]["failed_dimensions"] == ["kind"]
        assert c["support_policy_evaluation"]["reasons"] == ["non_result_kind"]
        assert c["support_policy_evaluation"]["policy_identity"] == "empirical-default-v1"
        assert c["attribution"]["ruleset_version"] == "i4-2b3.0" and c["attribution"]["proofs"] == []
    assert all(
        not row["binding"].get("candidate_supports")
        for row in r.evidence_rows(results["v7"]["map"])
        if row["child"] in ("c10", "c12")
    )
    old.pop("diagnostics")
    new.pop("diagnostics")
    assert strip_version(new) == strip_version(old), "STOP: downstream semantic surprise"
    assert len(new["targets"]) == 48 and len(new["claims"]) == 17 and len(new["plan"]["nodes"]) == 9
    assert len(new["invariants"]) == 33 and all(i["passed"] for i in new["invariants"])
    cs = [c for _, c in v6.candidates(results["v7"])]
    assert len(cs) == 15 and sum(c["admissible"] for c in cs) == 10
    assert all(c["aggregation"] != "literature_synthesis" for c in cs)


@r.needs_run
def test_diagnostics(results):
    rows = results["v7"]["diagnostics"]
    totals = {
        k: sum(d[k] for d in rows)
        for k in (
            "guard_triggered_units",
            "guard_prefiltered_units",
            "guard_excluded_candidates",
            "policy_excluded_candidates",
            "admissible_candidates",
        )
    }
    assert totals == dict(
        guard_triggered_units=21,
        guard_prefiltered_units=0,
        guard_excluded_candidates=5,
        policy_excluded_candidates=5,
        admissible_candidates=10,
    )
    assert sum(d["candidate_supports_emitted"] for d in rows) == 15
    assert sum(d["missing_no_grounded_relevant_support"] for d in rows) == 12
    assert all("guard_triggered_units" not in d for d in results["v6"]["diagnostics"])


@r.needs_run
def test_reached_model_rows_prompts_fingerprints():
    original = sm._fork_instances_over_role
    signature = inspect.signature(original)
    traces = []
    for version in ("v6", "v7"):
        trace = []

        def observe(*args, _trace=trace, **kwargs):
            values = signature.bind(*args, **kwargs).arguments
            spec = values["spec"]
            if spec["mapping_strategy"] == "model_nomination_only":
                rows = sm._candidate_rows_for_role(spec, values["units_here"])
                description = spec["category_description"]
                _trace.append(
                    dict(
                        scope=[values.get(k) for k in ("child_id", "requirement_id", "role", "request_context")],
                        rows=rows,
                        description=description,
                        prompt=qwen.nomination_prompt(category_description=description, candidates=rows),
                        fingerprint=scope.request_fingerprint(category_description=description, candidate_rows=rows),
                    )
                )
            return original(*args, **kwargs)

        with patch.object(sm, "_fork_instances_over_role", observe):
            r.remap("sufficiency-semantics-" + version, ownership_context_index=v6.context())
        traces.append(trace)
    assert len(traces[0]) == 31 and len({tuple(t["scope"]) for t in traces[0]}) == 29
    assert traces[0] == traces[1], "STOP: model-facing change"


@r.needs_run
def test_real_derivation_guard_invariant():
    original = sm._collect_achieved_outcome
    observed = []

    def inspect_records(*args, **kwargs):
        out = original(*args, **kwargs)
        if kwargs["guard_mode"] == "retain_for_v7":
            for record in out[1]:
                observed.append(copy.deepcopy(record["derivations"]))
        return out

    with patch.object(sm, "_collect_achieved_outcome", inspect_records):
        r.remap("sufficiency-semantics-v7", ownership_context_index=v6.context())
    # The replay also invokes the diagnostic binder, hence each of the fifteen candidates is visited twice.
    assert len(observed) == 30
    assert sum(len(ds) > 1 for ds in observed) == 6
    assert all(len({d["unit_index"] for d in ds}) == 1 for ds in observed)
    assert all(all(d["flags"] == ds[0]["flags"] for d in ds) for ds in observed)
