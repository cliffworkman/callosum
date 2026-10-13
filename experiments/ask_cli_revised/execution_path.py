"""What actually executed in one Ask run, read from the run's own results.

Every entry is derived from an object a component produced (a stage-log row, a map, a call record, a rendered
node), never from the flag that asked for it. A component that did not run carries the reason it was skipped.
This is a report, not a gate: it changes no decision and is written after the run's outputs exist.
"""

from __future__ import annotations

import collections

from experiments.ask_cli_revised import hierarchy_contract
from experiments.ask_cli_revised import sufficiency_engine as se


def _states(smap) -> dict:
    return dict(collections.Counter(req["state"] for child in (smap or {}).values() for req in child["requirements"]))


def _versions(smap) -> list:
    return sorted({str(child.get(se.SEMANTICS_VERSION_KEY)) for child in (smap or {}).values()})


def build(
    *,
    contract: dict,
    reviewed: bool,
    stage_log: list[dict],
    map_initial,
    map_final,
    nomination_initial,
    nomination_final,
    recovery_log: list[dict],
    child_overview_manifest,
    parent_synthesis_result,
    hierarchical_answer_result,
    fresh_result,
    requested: dict,
) -> dict:
    hierarchical = contract.get("version") == hierarchy_contract.HIER_VERSION
    stages = [s["stage"] for s in stage_log]

    def component(executed: bool, evidence=None, skipped=None) -> dict:
        return {"executed": executed, **({"evidence": evidence} if executed else {"skipped_reason": skipped})}

    def receipts(context):
        rows = list((context or {}).get("in_pass_receipts", {}).values())
        return {"requests": len(rows), "by_status": dict(collections.Counter(r["status"] for r in rows))}

    parent_record = (parent_synthesis_result or {}).get("record") or {}
    components = {
        "sufficiency_mapping_initial": component(
            map_initial is not None,
            {"semantics_versions": _versions(map_initial), "requirement_states": _states(map_initial)},
            "no scientific contract for this request",
        ),
        "model_nomination": component(
            nomination_initial is not None,
            {"initial": receipts(nomination_initial), "final": receipts(nomination_final)},
            "requested but not constructed" if requested.get("sufficiency_model_assist") else "not requested",
        ),
        "recovery_round": component(
            "W2" in stages,
            {
                "targets": len(recovery_log),
                "by_reason": dict(collections.Counter(r.get("reason_code") for r in recovery_log)),
            },
            "no planned search",
        ),
        "sufficiency_mapping_final": component(
            map_final is not None,
            {"semantics_versions": _versions(map_final), "requirement_states": _states(map_final)},
            "no scientific contract for this request",
        ),
        "child_synthesis": component(
            child_overview_manifest is not None,
            {
                "children": len(child_overview_manifest or {}),
                "by_state": dict(collections.Counter(v["state"] for v in (child_overview_manifest or {}).values())),
                "child_stages_run": sum(1 for s in stages if s.startswith("S1:")),
            },
            "request is not hierarchical" if not hierarchical else "no S role bound",
        ),
        "legacy_parent_claim_realization": component(
            bool(parent_record.get("call_attempted")),
            {
                "realization_state": parent_record.get("realization_state"),
                "claims": len(parent_record.get("claim_ledger", [])),
                "grounded": parent_record.get("grounded_count"),
                "fallback": parent_record.get("fallback_count"),
            },
            "superseded on the reviewed route by Layer C's deterministic parent_synthesis_v2"
            if reviewed
            else (parent_record.get("skip_reason") or "not requested"),
        ),
        "narrative_parent_overview": component(
            hierarchical_answer_result is not None,
            ((hierarchical_answer_result or {}).get("manifest") or {}).get("parent_overview"),
            "not requested" if not requested.get("parent_narrative") else "no child syntheses to draw on",
        ),
    }
    if fresh_result is not None:
        plan, nodes = fresh_result["plan"], fresh_result["render"]["nodes"]
        components["layer_c_v2"] = component(
            True,
            {
                "profile": plan["layerc_profile"],
                "claims": len(fresh_result["claims"]),
                "claim_evidence_receipts": len(fresh_result["claim_evidence"]),
                "relation_units": len(fresh_result["relation_units"]),
                "value_coverage_records": len(fresh_result["value_coverage"]),
                "parent_synthesis_v2": fresh_result["parent_synthesis"].get("schema")
                or type(fresh_result["parent_synthesis"]).__name__,
            },
        )
        components["answer_plan_v5"] = component(
            True,
            {
                "plan_version": plan["plan_version"],
                "nodes": len(plan["nodes"]),
                "node_states": dict(collections.Counter(n["state"] for n in plan["nodes"])),
            },
        )
        # Per visible node: how many statements were rendered and which limitation kinds explain what was not.
        outcome = [
            {
                "node": n["label"],
                "state": n["state"],
                "statements": len(n["statements"]),
                "limitations": dict(collections.Counter(item["kind"] for item in n["limitations"])),
            }
            for n in nodes
        ]
        selected = {
            "artifact": "15_v2_output.json render.layer1, written as 14_final_answer.md",
            "produced_by": "answer_plan_v5 / render_v5",
            "nodes_with_statements": sum(1 for n in outcome if n["statements"]),
            "nodes_without_statements": sum(1 for n in outcome if not n["statements"]),
            "withheld_or_empty_attribution": outcome,
        }
    else:
        skipped = "request has no reviewed inputs; Layer C and plan-v5 belong to the reviewed route"
        components["layer_c_v2"] = component(False, skipped=skipped)
        components["answer_plan_v5"] = component(False, skipped=skipped)
        selected = {"artifact": "14_final_answer.md", "produced_by": "ledger renderer over the sealed evidence"}
    return {
        "route": "reviewed" if reviewed else ("hierarchical" if hierarchical else "flat"),
        "request_kind": contract.get("version"),
        "requested": requested,
        "effective_semantics_versions": _versions(map_final),
        "stage_models": [
            {"stage": s["stage"], "role": s["role"], "model": (s.get("binding") or {}).get("model")} for s in stage_log
        ],
        "components": components,
        "selected_answer": selected,
    }
