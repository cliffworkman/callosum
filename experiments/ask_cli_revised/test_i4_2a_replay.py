"""Offline I4-2a audit harness; preserved model bindings are held fixed, never renominated.

CLI supports an isolated HEAD-module baseline saved under .local/i4-2a/baseline. Tests use
the working implementation. Hashes are verified before any preserved data is consumed.
"""

import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import experiments.ask_cli_revised as package

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__" and "--baseline" in sys.argv:
    package.__path__.insert(0, str(ROOT / ".local/i4-2a/baseline"))

from experiments.ask_cli_revised import hierarchy_contract as hc  # noqa: E402
from experiments.ask_cli_revised import parent_synthesis_ledger as psl  # noqa: E402
from experiments.ask_cli_revised import sufficiency_diagnostic as sd  # noqa: E402
from experiments.ask_cli_revised import sufficiency_mapping as sm  # noqa: E402
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt  # noqa: E402
from experiments.ask_cli_revised.answer_plan import overlay, plan, render  # noqa: E402
from experiments.ask_cli_revised.answer_plan import text as plan_text  # noqa: E402
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION  # noqa: E402

RUN = ROOT / ".local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/run"
HASHES = {
    "11_verified_ledger.json": "a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d",
    "17_sufficiency_map.initial.json": "46a213044bc6211702fa89710268e1bfb6c4fc348259727a46cb238ef5bbc14e",
    "17_sufficiency_map.json": "28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b",
}
needs_run = pytest.mark.skipif(not (RUN / "11_verified_ledger.json").is_file(), reason="preserved Attempt2 absent")


def inputs():
    for name, expected in HASHES.items():
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == expected, f"STOP: {name} hash mismatch"
    return tuple(
        json.loads((RUN / name).read_text(encoding="utf-8"))
        for name in ("11_verified_ledger.json", "17_sufficiency_map.json")
    )


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        default=lambda x: sorted(x) if isinstance(x, (set, frozenset)) else str(x),
    )


def remap(version, *, ownership_context_index=None):
    """Run the real mapper/fork/recompute pipeline with only model-role selection replaced by frozen bindings.

    The keyed replay reads source request_context, never current instance keys or role-name heuristics.
    Parent propagation, deterministic roles, observations, and content-derived keys run normally.
    """
    sealed, preserved = inputs()
    held = {}
    for cid, contract in preserved.items():
        for req in contract["requirements"]:
            for inst in req["instances"]:
                for role, spec in req["role_specs"].items():
                    if spec["mapping_strategy"] != "model_nomination_only":
                        continue
                    key = (cid, req["id"], role, inst.get("request_context"))
                    choices = held.setdefault(key, [])
                    binding = inst["role_bindings"].get(role, {})
                    if (
                        binding.get("state") == "filled"
                        and binding.get("provenance", {}).get("candidate_source") != "parent_context"
                    ):
                        if binding not in choices:
                            choices.append(copy.deepcopy(binding))
    original = sm._bind_role_candidates
    diagnostics = []

    def replay(spec, units, **kwargs):
        if spec["mapping_strategy"] == "model_nomination_only":
            key = (kwargs.get("child_id"), kwargs.get("requirement_id"), spec["role"], kwargs.get("request_context"))
            assert key in held, f"unrecorded nomination scope: {key}"
            return copy.deepcopy(held[key])
        result = original(spec, units, **kwargs)
        if (
            version in ("sufficiency-semantics-v5", "sufficiency-semantics-v6")
            and spec["mapping_strategy"] == "achieved_outcome_predicate"
        ):
            diag = {}
            binder = (
                sm._bind_achieved_outcome_v6 if version == "sufficiency-semantics-v6" else sm._bind_achieved_outcome_v5
            )
            checked = binder(
                spec,
                units,
                sibling_bindings=kwargs.get("sibling_bindings"),
                role_completion=kwargs.get("role_completion"),
                diagnostics=diag,
            )
            assert result == checked  # diagnostics cannot affect state
            diagnostics.append(
                {
                    "child": kwargs.get("child_id"),
                    "role": spec["role"],
                    "request_context": kwargs.get("request_context"),
                    **diag,
                }
            )
        return result

    parent_of = hc.parent_of(hc.load_contract(BENCHMARK_QUESTION, pins=None))
    with patch.object(sm, "_bind_role_candidates", replay):
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed,
            copy.deepcopy(preserved),
            parent_of,
            semantics_version=version,
            ownership_context_index=ownership_context_index,
        )
    sd.compute_direction_and_effectiveness(sealed, mapped, semantics_version=version)
    targets = srt.compute_recovery_targets(mapped, parent_of, semantics_version=version)
    claims = psl.build_claim_ledger(mapped, sealed, parent_of)
    answer = plan.build_plan(
        sealed, mapped, overlay.load_overlay(), containment_semantics=version, direction_semantics=version
    )
    props = {r["proposition_id"]: r for r in sealed["verified_propositions"]}
    words = plan_text.corpus_word_set([s["text"] for s in sealed["evidence_spans"]])
    rendered = render.render_layer1(answer, props, words)
    return {
        "map": mapped,
        "targets": targets,
        "claims": claims,
        "plan": answer,
        "layer1": rendered,
        "invariants": render.invariant_report(answer, rendered, props),
        "diagnostics": diagnostics,
    }


def evidence_rows(mapped):
    rows = []
    for cid, contract in mapped.items():
        for req in contract["requirements"]:
            for role, spec in req["role_specs"].items():
                if spec["mapping_strategy"] != "achieved_outcome_predicate":
                    continue
                for inst in req["instances"]:
                    rows.append(
                        {
                            "child": cid,
                            "role": role,
                            "instance_key": inst["instance_key"],
                            "binding": inst["role_bindings"][role],
                            "complete": inst["complete"],
                            "state": inst["state"],
                            "requirement_state": req["state"],
                        }
                    )
    return rows


@pytest.fixture(scope="module")
def replays():
    return remap("sufficiency-semantics-v4"), remap("sufficiency-semantics-v5")


@needs_run
def test_real_v4_historical_evidence_unchanged(replays):
    _, preserved = inputs()
    before, after = evidence_rows(preserved), evidence_rows(replays[0]["map"])
    assert before == after
    filled = [r for r in after if r["binding"]["state"] == "filled"]
    assert len(filled) == 15
    assert len({r["binding"]["proposition_id"] for r in filled}) == 8


@needs_run
def test_real_v5_c1_c3_c12_and_headline_cases(replays):
    rows = evidence_rows(replays[1]["map"])

    def filled(cid):
        return [r for r in rows if r["child"] == cid and r["binding"]["state"] == "filled"]

    assert [r["binding"]["proposition_id"] for r in filled("c1")] == ["p2"]
    assert filled("c1")[0]["binding"]["candidate_supports"][0]["supporting_proposition_ids"] == ["p2", "p11"]
    assert len(filled("c3")) == 1
    assert not filled("c12")
    assert replays[1]["map"]["c12"]["requirements"][0]["state"] == "missing"
    assert [r["binding"]["proposition_id"] for r in filled("c2")] == ["p47"]
    assert [r["binding"]["proposition_id"] for r in filled("c4")] == ["p11", "p40"]
    assert len(filled("c8")) == 5
    assert [r["binding"]["candidate_supports"][0]["assertion_span"] for r in filled("c8")] == [[43, 200]] * 2 + [
        [208, 372]
    ] * 3
    assert not filled("c10")


@needs_run
def test_every_real_candidate_has_honest_plural_coordinates(replays):
    sealed, _ = inputs()
    quotes = {r["proposition_id"]: r["quote"] for r in sealed["verified_propositions"]}
    for row in evidence_rows(replays[1]["map"]):
        for candidate in row["binding"].get("candidate_supports", []):
            anchor = quotes[candidate["span_proposition_id"]]
            assert all(quotes[pid].encode() == anchor.encode() for pid in candidate["supporting_proposition_ids"])
            assert anchor[slice(*candidate["assertion_span"])] == candidate["exact_text"]
            assert candidate["admissible"] is None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--version", choices=["v4", "v5"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = remap("sufficiency-semantics-" + args.version)
    args.out.write_text(canonical(result) + "\n", encoding="utf-8")
    for row in evidence_rows(result["map"]):
        b = row["binding"]
        print(
            row["child"],
            row["instance_key"],
            b["state"],
            b["proposition_id"],
            len(b.get("candidate_supports", [])),
            row["state"],
            row["complete"],
        )
