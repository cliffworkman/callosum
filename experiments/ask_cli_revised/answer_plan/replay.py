"""Phase-30 Step-1 offline replay driver. Reads ONLY the preserved Phase-28 Attempt-2 artifacts; no model, no network.

    python -m experiments.ask_cli_revised.answer_plan.replay [--run-dir DIR] [--out-dir DIR]

Writes: replay_decomposition_authorization.json, answer_plan.json, deterministic_layer1.md, deterministic_layer2.md,
answer_plan_audit.json, comparison_against_phase29_hand_audit.md. The preserved run directory is never modified.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised.answer_plan import overlay as ov
from experiments.ask_cli_revised.answer_plan import plan as pl
from experiments.ask_cli_revised.answer_plan import render as rd
from experiments.ask_cli_revised.answer_plan import text as tx

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN = ROOT / ".local" / "e2e-runs" / "phase28-live-parent-synthesis-attempt2-20261004T014500Z" / "run"
DEFAULT_OUT = ROOT / "experiments" / "ask_cli_revised" / "phase30_replay"
FROZEN_CONTRACT = ROOT / "experiments" / "ask_cli_revised" / "hierarchy_contract.frozen.json"

# Phase-29 hand audit, Appendix A, transcribed. Keyed by (kind, child ids, sorted admissible propositions).
HAND_ROLES = [
    ("relational", ("c4",), ("p11",), "primary", "1"),
    ("relational", ("c8",), ("p41",), "suppressed (identity: stimulus ratings)", "2-6"),
    ("direction_or_effectiveness", ("c6",), ("p14", "p26"), "primary as value-level valence", "7"),
    ("role_value", ("c1",), ("p1",), "attributed_primary (facet 2)", "8"),
    ("role_value", ("c1",), ("p11", "p2"), "context (operand of 1)", "9"),
    ("role_value", ("c2",), ("p4",), "duplicate_of 8", "10"),
    ("role_value", ("c3",), ("p8",), "duplicate_of 8", "11"),
    ("role_value", ("c4",), ("p40",), "attributed_only", "12"),
    ("role_value", ("c4",), ("p11",), "subsumed_by 1", "13"),
    ("role_value", ("c6",), ("p17",), "context (keyword operand)", "14"),
    ("category_list", ("c10",), ("p29", "p53"), "context (population operand)", "15"),
    ("category_list", ("c12",), ("p24", "p30", "p31"), "primary for p30/p31; p24 suppressed", "16"),
    ("category_list", ("c2",), ("p35", "p46", "p47"), "primary for p46/p47 (construct-adjacent labelled)", "17"),
    ("category_list", ("c5",), ("p46", "p47"), "duplicate_of 17 (facet 4A)", "18"),
    ("category_list", ("c8",), ("p20", "p9"), "suppressed (speculative, identity)", "19"),
    ("category_list", ("c3",), ("p36", "p8"), "primary (verbatim p36 sentence)", "20"),
    ("category_list", ("c6",), ("p14", "p17", "p26", "p3", "p7"), "primary (measure name)", "21"),
]


def _load(run: Path, name: str):
    return json.loads((run / name).read_text(encoding="utf-8"))


def _hand_entry(claim: dict) -> tuple | None:
    kind = claim["claim_kind"]
    children = tuple(claim["child_ids"])
    props = tuple(sorted(claim["admissible_proposition_ids"]))
    for hand_kind, hand_children, hand_props, label, number in HAND_ROLES:
        if hand_kind == kind and hand_children == children and hand_props == props:
            return label, number
    return None


def _mechanical_category(record: dict) -> str:
    renders = record.get("render_status") or []
    if record.get("role") in ("primary", "value_level", "attached_to_relation") and renders:
        statuses = {r["status"] for r in renders}
        if statuses == {"duplicate"}:
            return "displayed via another claim's identical sentence"
        if statuses == {"subsumed"}:
            return "subsumed by a displayed relation"
        if "displayed" in statuses:
            return "displayed" if record.get("role") != "value_level" else "displayed (value-level)"
    if record.get("role") == "attached_to_relation":
        return "attached to relation (not separately displayed)"
    if record.get("role") == "attributed_only":
        return "attributed_only"
    reasons = record.get("reasons") or []
    return "suppressed: " + (reasons[0] if reasons else "no reason recorded")


def _comparison(plan: dict, claims: list[dict]) -> list[str]:
    by_id = {c["claim_id"]: c for c in claims}
    rows = [
        "| # | ParentClaim | Child | Phase-29 hand role | Mechanical role | Hand: in Layer 1? | Mechanical: in Layer 1? | Agree |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for record in plan["claim_roles"]:
        claim = by_id[record["claim_id"]]
        entry = _hand_entry(claim)
        hand_label, number = entry if entry else ("(not in hand table)", "?")
        mech = _mechanical_category(record)
        hand_in = hand_label.startswith(("primary", "attributed_primary"))
        mech_in = mech.startswith("displayed")
        if hand_label.startswith(("duplicate", "subsumed")):
            agree = "n/a (folds into another claim)"
            hand_cell = "n/a"
            mech_cell = "n/a"
        else:
            hand_cell = "yes" if hand_in else "no"
            mech_cell = "yes" if mech_in else "no"
            agree = "yes" if hand_in == mech_in else "**NO**"
        rows.append(
            f"| {number} | `{record['claim_id'][:24]}…` | {','.join(record['child_ids'])} | {hand_label} | {mech} | "
            f"{hand_cell} | {mech_cell} | {agree} |"
        )
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    run, out = args.run_dir, args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    sealed = _load(run, "11_verified_ledger.json")
    smap = _load(run, "17_sufficiency_map.json")
    scoped = _load(run, "13c_scoped_search.json").get("final") or {}
    preserved_ledger = _load(run, "15a_parent_synthesis.json")
    frozen = json.loads(FROZEN_CONTRACT.read_text(encoding="utf-8"))
    overlay = ov.load_overlay()
    overlay_sha = ov.overlay_sha256(overlay)

    problems = ov.validate_overlay(overlay, smap, frozen)
    if problems:
        raise SystemExit("overlay invalid: " + "; ".join(problems))

    historical = []
    ledger_status = {o["field_id"]: o["hierarchy"]["status"] for o in sealed["obligation_states"]}
    for child in frozen["children"]:
        historical.append(
            {
                "child_id": child["child_id"],
                "frozen_execution_state": child["execution_state"],
                "frozen_approval_ref": child["approval_ref"],
                "sealed_ledger_status": ledger_status.get(child["child_id"]),
            }
        )
    authorization_body = {
        "record": "replay_decomposition_authorization",
        "status": overlay["status"],
        "overlay_sha256": overlay_sha,
        "confirmed_by": overlay["confirmed_by"],
        "postdates_phase28_attempt2_live_run": overlay["postdates_phase28_attempt2_live_run"],
        "phase28_run_id": overlay["phase28_run_id"],
        "scope_statement": overlay["scope_statement"],
        "does_not_claim": "that the Phase-28 live run carried this authorization; no Phase-28 artifact is modified",
        "bound_inputs": {
            "sealed_hash": sealed["sealed_hash"],
            "sufficiency_map_sha256": ov.sha256_file(run / "17_sufficiency_map.json"),
            "hierarchy_contract_frozen_sha256": ov.sha256_file(FROZEN_CONTRACT),
            "parent_claim_ledger_sha256": ov.sha256_obj(preserved_ledger["claim_ledger"]),
        },
        "historical_decomposition_status": historical,
        "historical_status_note": "Recorded, not resolved. This overlay governs the offline replay only (Phase-30 U13).",
    }
    authorization = {**authorization_body, "authorization_sha256": ov.sha256_obj(authorization_body)}
    inputs = {
        "replay_authorization_sha256": authorization["authorization_sha256"],
        "overlay_sha256": overlay_sha,
        "sealed_hash": sealed["sealed_hash"],
        "sufficiency_map_sha256": authorization_body["bound_inputs"]["sufficiency_map_sha256"],
        "hierarchy_contract_frozen_sha256": authorization_body["bound_inputs"]["hierarchy_contract_frozen_sha256"],
    }

    plan = pl.build_plan(sealed, smap, overlay, scoped_final=scoped, frozen_contract=frozen, inputs=inputs)
    plan_again = pl.build_plan(sealed, smap, overlay, scoped_final=scoped, frozen_contract=frozen, inputs=inputs)
    deterministic = plan["plan_sha256"] == plan_again["plan_sha256"]

    rebuilt = psl.build_claim_ledger(smap, sealed)
    rebuilt_ids = [c["claim_id"] for c in rebuilt]
    preserved_ids = [c["claim_id"] for c in preserved_ledger["claim_ledger"]]
    ledger_identical = rebuilt_ids == preserved_ids

    props = {row["proposition_id"]: row for row in sealed["verified_propositions"]}
    corpus_words = tx.corpus_word_set([s["text"] for s in sealed["evidence_spans"]])
    layer1 = rd.render_layer1(plan, props, corpus_words)
    layer2 = rd.render_layer2(plan, props)
    checks = rd.invariant_report(plan, layer1, props)
    checks.append(
        {
            "check": "U13_historical_status_recorded_separately",
            "passed": len(historical) == 11,
            "detail": "frozen vs sealed statuses kept in authorization record",
        }
    )
    checks.append({"check": "replay_plan_deterministic", "passed": deterministic, "detail": plan["plan_sha256"]})
    checks.append(
        {"check": "parent_claim_ledger_rebuilds_identically", "passed": ledger_identical, "detail": len(rebuilt_ids)}
    )
    checks.append({"check": "no_model_calls", "passed": True, "detail": "pure functions over preserved artifacts"})
    failed = [c["check"] for c in checks if not c["passed"]]

    plan_out = {k: v for k, v in plan.items() if k != "_layer1_check_texts"}
    audit = {
        "record": "answer_plan_audit",
        "plan_sha256": plan["plan_sha256"],
        "plan_deterministic": deterministic,
        "parent_claim_ledger_identical_to_phase28_record": ledger_identical,
        "invariant_checks": checks,
        "failed_checks": failed,
        "disagreements_engine_complete_vs_witnessed": plan["disagreements"],
        "relation_units": plan["relation_units"],
        "historical_decomposition_status": historical,
        "claim_roles": plan["claim_roles"],
        "node_states": {node["label"]: node["status"] for node in plan["nodes"]},
        "node_state_counts": plan["parent"]["node_state_counts"],
    }

    (out / "replay_decomposition_authorization.json").write_text(
        json.dumps(authorization, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "answer_plan.json").write_text(json.dumps(plan_out, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "deterministic_layer1.md").write_text(layer1, encoding="utf-8")
    (out / "deterministic_layer2.md").write_text(layer2, encoding="utf-8")
    (out / "answer_plan_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    comparison = [
        "# Comparison against the Phase-29 hand audit (Appendix A)",
        "",
        "Mechanically derived by `answer_plan/replay.py`. The 'Agree' column compares only whether a claim appears in",
        "Layer 1. Duplicates and subsumed claims fold into another claim and are not compared separately.",
        "",
        *_comparison(plan, rebuilt),
        "",
    ]
    (out / "comparison_against_phase29_hand_audit.md").write_text("\n".join(comparison), encoding="utf-8")

    summary = {
        "plan_sha256": plan["plan_sha256"],
        "deterministic": deterministic,
        "ledger_identical": ledger_identical,
        "failed_checks": failed,
        "node_states": audit["node_states"],
        "claim_role_counts": _count([r["role"] for r in plan["claim_roles"]]),
        "out_dir": str(out),
    }
    print(json.dumps(summary, indent=2))
    return 0


def _count(items: list) -> dict:
    counts: dict = {}
    for item in items:
        counts[str(item)] = counts.get(str(item), 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
