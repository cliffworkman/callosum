"""Parent-level reconciliation: where every original obligation went, including the ones that remain unresolved.

Statuses describe OWNERSHIP (structural: which child owns the obligation) plus lexical diagnostics, never certified
preservation. ``semantic_fidelity`` is always ``not_certified``. A fallback or unit-level child never counts as a
success, and a child that repeats a compound question or bundles distinct obligations leaves its obligations
``bundled_unresolved``. Open ambiguities are listed as their own unresolved rows and marked on every obligation they touch.
"""

from __future__ import annotations

from collections import Counter

from experiments.ask_cli_revised.decompose import checks, tree
from experiments.ask_cli_revised.decompose.children import CARRIER_KINDS
from experiments.ask_cli_revised.decompose.parent import PARENT_LEVEL_KINDS
from experiments.ask_cli_revised.decompose.requirements import KNOWN_LIMITATIONS

UNRESOLVED_STATUSES = frozenset(
    {
        "unowned_unresolved",
        "fallback_unresolved",
        "unit_level_unresolved",
        "elliptical_unresolved",
        "owned_semantic_conflict",
        "owned_semantic_review_required",
        "owned_conditional_on_unresolved_reading",
        "owned_source_gap",
        "owned_pending_researcher_confirmation",
        "owned_output_constraint_failure",
        "constraint_failure_unresolved",
        "bundled_unresolved",
        "owned_lexically_lost_candidate",
        "shared_lexically_lost_candidate",
        "unanchored_unverifiable",
        "parent_level_recorded_open",
        "ambiguity_open",
        "no_carrier_found",
        "no_child",
    }
)


def _overlap(a: list[list[int]], b: list[list[int]]) -> bool:
    return any(max(x[0], y[0]) < min(x[1], y[1]) for x in a for y in b)


def _preserved(child: dict, rid: str):
    diag = child.get("diagnostics")
    return None if not diag else diag["preservation"].get(rid, {}).get("preserved")


def _bundled(child: dict) -> bool:
    diag = child.get("diagnostics") or {}
    return bool(
        diag.get("copies_of_source_text")
        or diag.get("bundled_list")
        or diag.get("possible_bundling_of_other_obligations")
    )


def reconcile(parent: dict, doc: dict, traceability: dict) -> dict:
    children = doc["children"]
    live = [r for r in parent["requirements"] if r["origin"] != "source_unit_floor"]
    rows: list[dict] = []
    for u in parent["source_units"]:
        uid = u["source_unit_id"]
        kids = [c for c in children if uid in c["origin"]["source_unit_ids"]]
        if any(c["kind"] == "passthrough" for c in kids):
            status = "passed_through_unchanged_ask_pending"
        elif any(c["kind"] == "generated" for c in kids):
            status = "has_generated_children_candidate"
        elif kids:
            status = "fallback_or_unit_level_only_unresolved"
        elif any(r["kind"] in PARENT_LEVEL_KINDS and uid in r["unit_ids"] for r in live):
            status = "parent_level_only"
        else:
            status = "no_child"
        rows.append(
            {
                "id": f"P-{uid}",
                "kind": "source_unit",
                "text": u["text"],
                "spans": [[u["start"], u["end"]]],
                "unit_ids": [uid],
                "carriers": [{"child_id": c["child_id"], "child_kind": c["kind"]} for c in kids],
                "status": status,
            }
        )
    for r in live:
        owners = [c for c in children if r["id"] in c["owns"]]
        shared = [c for c in children if r["id"] in c["carries_shared"]]
        amb = [a["id"] for a in parent["ambiguities"] if a["spans"] and r["spans"] and _overlap(a["spans"], r["spans"])]
        real = [c for c in owners if c["kind"] in CARRIER_KINDS]
        if r.get("superseded"):
            status = r["status"]  # split_into_items | covered_by_finer_obligations
        elif r["anchoring"] == "none":
            status = "unanchored_unverifiable"
        elif r["kind"] in PARENT_LEVEL_KINDS:
            status = "parent_level_recorded_open"
        elif r["origin"] == "deterministic_cue" and r["kind"] == "operation":
            status = "operation_cue_informational"
        elif owners:
            if not real:
                kinds = {c["kind"] for c in owners}
                status = (
                    "fallback_unresolved"
                    if "fallback" in kinds
                    else (
                        "constraint_failure_unresolved"
                        if "constraint_failure" in kinds
                        else (
                            "not_selected"
                            if "not_selected" in kinds
                            else (
                                "elliptical_unresolved" if "unresolved_elliptical" in kinds else "unit_level_unresolved"
                            )
                        )
                    )
                )
            elif all(c["kind"] == "passthrough" for c in real):
                status = "owned_passed_through_unchanged"
            elif any(_bundled(c) for c in real):
                status = "bundled_unresolved"
            elif any(c["status"] == "semantic_conflict" for c in real):
                status = "owned_semantic_conflict"
            elif any(c["status"] == "output_constraint_failure" for c in real):
                status = "owned_output_constraint_failure"
            elif any(_preserved(c, r["id"]) is False for c in real):
                status = "owned_lexically_lost_candidate"
            elif any(c["status"] == "conditional_on_unresolved_reading" for c in real):
                status = "owned_conditional_on_unresolved_reading"
            elif any(c["status"] == "semantic_review_required" for c in real):
                status = "owned_semantic_review_required"
            elif any(c["status"] == "source_gap" for c in real):
                status = "owned_source_gap"
            elif any(c["status"] == "pending_researcher_confirmation" for c in real):
                status = "owned_pending_researcher_confirmation"
            elif all(_preserved(c, r["id"]) is None for c in real):
                status = "owned_not_lexically_assessable"
            else:
                status = "owned_lexically_preserved_candidate"
        elif shared:
            real_shared = [c for c in shared if c["kind"] in CARRIER_KINDS]
            if not real_shared:
                status = "no_carrier_found"
            elif any(_preserved(c, r["id"]) is False for c in real_shared):
                status = "shared_lexically_lost_candidate"
            else:
                status = "shared_carried_candidate"
        elif r["kind"] in ("requested_item", "relationship", "existence", "polarity", "manner", "kinds"):
            status = "unowned_unresolved"
        else:
            status = "no_carrier_found"
        rows.append(
            {
                "id": r["id"],
                "kind": r["kind"],
                "origin": r["origin"],
                "produced_by": r["produced_by"],
                "text": r["text"],
                "spans": r["spans"],
                "unit_ids": r["unit_ids"],
                "anchoring": r["anchoring"],
                "part_of": r.get("part_of"),
                "owners": [
                    {"child_id": c["child_id"], "child_kind": c["kind"], "lexically_preserved": _preserved(c, r["id"])}
                    for c in owners
                ],
                "carried_shared_by": [c["child_id"] for c in shared],
                "depends_on_open_ambiguity": amb,
                "status": status,
            }
        )
    for a in parent["ambiguities"]:
        touching = [c["child_id"] for c in children if any(i["ambiguity_id"] == a["id"] for i in c["interpretations"])]
        resolved = [
            c["child_id"]
            for c in children
            if any(
                i["ambiguity_id"] == a["id"] and i["kind"] == "reference_resolved_by_rewrite"
                for i in c["interpretations"]
            )
        ]
        rows.append(
            {
                "id": a["id"],
                "kind": a["kind"],
                "origin": a["origin"],
                "produced_by": a["produced_by"],
                "text": a["text"],
                "spans": a["spans"],
                "unit_ids": a["unit_ids"],
                "alternatives": a.get("alternatives") or [],
                "touching_children": touching,
                "children_whose_wording_dropped_the_reference": resolved,
                "status": "resolved_by_user_clarification" if a.get("clarification") else "ambiguity_open",
                "clarification": a.get("clarification"),
                "note": "resolved only because a user clarification names these exact words"
                if a.get("clarification")
                else "never resolved by the engine; a child that avoids the word made a model choice",
            }
        )
    for s in parent.get("referents", []):
        rows.append(
            {
                "id": s["id"],
                "kind": s["kind"],
                "origin": s["origin"],
                "produced_by": s["produced_by"],
                "text": s["text"],
                "spans": s["spans"],
                "unit_ids": s["unit_ids"],
                "carriers": [c["child_id"] for c in children if s["id"] in c.get("context_referents", [])],
                "status": "context_referent_candidate",
                "note": "background only; never owned or asked; a human confirms it",
            }
        )
    counts = Counter(r["status"] for r in rows)
    gen = [c for c in children if c["kind"] == "generated"]
    passed_through = [c["child_id"] for c in children if c["kind"] == "passthrough"]
    bundled = [c["child_id"] for c in children if _bundled(c)]
    conditional = [c["child_id"] for c in gen if c["status"] == "conditional_on_unresolved_reading"]
    conflict = [c["child_id"] for c in gen if c["status"] == "semantic_conflict"]
    review = [c["child_id"] for c in gen if c["status"] == "semantic_review_required"]
    gap = [c["child_id"] for c in gen if c["status"] == "source_gap"]
    pending = [c["child_id"] for c in gen if c["status"] == "pending_researcher_confirmation"]
    output_failed = [c["child_id"] for c in gen if c["status"] == "output_constraint_failure"]
    successful = [
        c["child_id"]
        for c in gen
        if not (c.get("diagnostics") or {}).get("hard_fail")
        and c["child_id"] not in bundled
        and c["child_id"] not in conditional
        and c["child_id"] not in conflict
        and c["child_id"] not in review
        and c["child_id"] not in gap
        and c["child_id"] not in pending
        and c["child_id"] not in output_failed
        and not (c.get("diagnostics") or {}).get("lost")
    ]
    out = {
        "semantic_fidelity": {
            "status": "not_certified",
            "note": "statuses are ownership plus lexical diagnostics, not certification",
        },
        "verified_traceability": traceability,
        "rows": rows,
        "unresolved": [r for r in rows if r["status"] in UNRESOLVED_STATUSES],
        "clarifications": parent.get("clarifications", []),
        "unaccounted_text_diagnostic": parent["unaccounted_text_diagnostic"],
        "summary": {
            "status_counts": dict(sorted(counts.items())),
            "units": len(parent["source_units"]),
            "children": len(children),
            "children_by_kind": dict(Counter(c["kind"] for c in children)),
            "successful_children": successful,
            "passed_through_children": passed_through,
            "answer_state": "not_executed",
            "bundled_children": bundled,
            "conditional_on_unresolved_reading": conditional,
            "semantic_conflict": conflict,
            "semantic_review_required": review,
            "source_gap": gap,
            "known_limitations": list(KNOWN_LIMITATIONS),
            "background_subject_scope": {
                "subject": (parent.get("referents") or [{}])[0].get("text"),
                "single": True,
                "derived_from": "the first source unit only",
                "unverified_for": [
                    c["child_id"]
                    for c in gen
                    if any(f["flag"] == "background_subject_scope_unverified" for f in c["flags"])
                ],
                "note": "one candidate subject is derived for the whole request; a request about several unrelated subjects is a known limit, not a modelled case",
            },
            "human_review_required": [c["child_id"] for c in gen if c.get("human_review_required")],
            "pending_researcher_confirmation": pending,
            "output_constraint_failures": output_failed,
            "unverified_by_lexical_checks": {
                c["child_id"]: c["edit_ledger"]["verification_limits"]
                for c in gen
                if (c.get("edit_ledger") or {}).get("verification_limits")
            },
            "constraint_failures": [c["child_id"] for c in children if c["kind"] == "constraint_failure"],
            "not_selected": [c["child_id"] for c in children if c["kind"] == "not_selected"],
            "unstated_context_links": [c["child_id"] for c in gen if c.get("unresolved_links")],
            "elliptical_or_unit_level_unresolved": [
                c["child_id"] for c in children if c["kind"] in ("unresolved_elliptical", "unit_level")
            ],
            "pending_human_review": [c["child_id"] for c in children if c.get("pending_human_review")],
            "children_with_unpreserved_obligations": [
                c["child_id"] for c in gen if (c.get("diagnostics") or {}).get("lost")
            ],
            "units_without_child": traceability["units_without_child"],
            "open_ambiguities": sum(1 for r in rows if r["status"] == "ambiguity_open"),
            "unresolved_count": sum(1 for r in rows if r["status"] in UNRESOLVED_STATUSES),
            "note": "fallback, unit-level, elliptical, conditional and bundled children are excluded from every success count; "
            "a passed-through request is decomposition-complete only, never answered (answer_state)",
        },
        "diagnostic_thresholds": {
            "lexical_support": checks.LEXICAL_SUPPORT_THRESHOLD,
            "compound_coverage": checks.COMPOUND_COVERAGE,
        },
    }
    if doc.get("question_tree"):  # roll up from subordinate nodes through their ancestors to the request
        out["question_tree"] = tree.reconcile_tree(doc["question_tree"], children, out["summary"])
    return out
