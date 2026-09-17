"""Run 0.6 bounded targeted repair — at most ONE pass on the chosen candidate.

Fires when the chosen candidate is not ready: global reconstruction below the (empirical) readiness gate, OR
a source unit is coverage-flagged, OR an item shows clear source-local drift. Repairs ONLY the flagged
item(s) by re-rephrasing with visible evidence about the decomposition (the original question, the affected
unit, its current rewrite, the other rewrites, and a plain-language problem) — never metrics, never
scientific answers. Similarity is repair guidance, NEVER a delete rule. Reuses Run 0.5 `_repair_prompt` /
`_rewrite_once` / `_call_record`. The orchestrator re-audits the returned candidate and RE-SELECTS between
{pre-repair, repaired}; the repaired candidate never auto-replaces.
"""

from __future__ import annotations

from experiments.ask_cli_revised.calibration import decomposition as dec
from experiments.ask_cli_revised.calibration.audit import AuditThresholds

# A rewrite whose cosine to its own source unit is below this shows CLEAR drift worth a repair look.
# Conservative/provisional; a short unit's faithful rewrite can legitimately be only moderately similar.
DRIFT_REPAIR_FLOOR = 0.30


def diagnose(audit: dict, *, drift_floor: float = DRIFT_REPAIR_FLOOR) -> dict:
    weak_units = [u["source_unit_id"] for u in audit["source_unit_coverage"] if u["weak"]]
    drifted_items = [
        d["item_id"] for d in audit.get("source_local_drift", []) if d["source_local_similarity"] < drift_floor
    ]
    needed = (not audit["passes_global"]) or bool(weak_units) or bool(drifted_items)
    return {
        "needed": needed,
        "global_below_gate": not audit["passes_global"],
        "weak_units": weak_units,
        "drifted_items": drifted_items,
    }


def repair_candidate(
    base_config,
    question: str,
    candidate: dict,
    *,
    mode: str,
    thresholds: AuditThresholds,  # noqa: ARG001 - kept for call-site symmetry / future gate tuning
    drift_floor: float = DRIFT_REPAIR_FLOOR,
) -> dict:
    """Return {needed, candidate (repaired copy or the input), repair_details, diagnosis}. <=1 pass."""
    diagnosis = diagnose(candidate["audit"], drift_floor=drift_floor)
    if not diagnosis["needed"]:
        return {"needed": False, "candidate": candidate, "repair_details": [], "diagnosis": diagnosis}

    items = [dict(i) for i in candidate["items"]]
    calls = list(candidate["calls"])
    decomposition_texts = [i["text"] for i in items]
    target_units = set(diagnosis["weak_units"])
    target_items = set(diagnosis["drifted_items"])
    details: list[dict] = []
    for index, item in enumerate(items):
        if item["source_unit_id"] not in target_units and item["item_id"] not in target_items:
            continue
        text, call = dec._rewrite_once(
            base_config,
            dec._repair_prompt(question, item["source_text"], item["text"], decomposition_texts),
            mode=mode,
        )
        calls.append(dec._call_record("repair", item["source_unit_id"], item["source_text"], text, call))
        before = item["text"]
        if text is not None:
            items[index] = {**item, "text": text, "from_fallback": False, "repaired": True}
        details.append(
            {"item_id": item["item_id"], "before": before, "after": items[index]["text"], "changed": text is not None}
        )

    repaired = {**candidate, "items": items, "calls": calls, "style": candidate["style"] + "+repair"}
    return {"needed": True, "candidate": repaired, "repair_details": details, "diagnosis": diagnosis}
