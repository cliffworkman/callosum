"""Phase 3: descriptively correlate the FROZEN deterministic metrics against the human fidelity labels.

Joins each rich-question candidate item to its metrics (source-local similarity, per-unit coverage
best-match, leave-one-out delta) and its human label, then summarizes how well each metric tracks fidelity.
No calibrated-classifier claims — descriptive ranges + named specimens only. Uses the human labels (this is
correlation analysis, not the metric-only policy).
"""

from __future__ import annotations

import statistics

from experiments.ask_cli_revised.calibration.run06a import fidelity, inputs

RICH = inputs.RICH_CASES
QWEN_STYLES = ("minimal", "relation", "multi")


def joined_rows(frozen) -> list[dict]:
    rows = []
    for case in RICH:
        cands = frozen["data"]["02_candidates.json"][case]["candidates"]
        for style in QWEN_STYLES:
            entry = cands[style]
            sls = {d["item_id"]: d["source_local_similarity"] for d in entry["audit"]["source_local_drift"]}
            loo = {d["item_id"]: d["delta"] for d in entry["audit"]["leave_one_out"]}
            cov = {c["source_unit_id"]: c["best_match"] for c in entry["audit"]["source_unit_coverage"]}
            for it in entry["items"]:
                lab = fidelity.item_label(case, style, it["item_id"])
                if lab is None:
                    continue
                rows.append(
                    {
                        "case": case, "style": style, "unit": it["source_unit_id"], "item_id": it["item_id"],
                        "sls": sls.get(it["item_id"]), "coverage_best_match": cov.get(it["source_unit_id"]),
                        "loo_delta": loo.get(it["item_id"]), "label": lab["label"], "text": it["text"],
                    }
                )
    return rows


def _rng(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "min": round(min(vals), 4), "median": round(statistics.median(vals), 4), "max": round(max(vals), 4), "mean": round(statistics.mean(vals), 4)}


def summarize(rows: list[dict]) -> dict:
    faithful = [r for r in rows if r["label"] == "FAITHFUL"]
    non_faithful = [r for r in rows if r["label"] != "FAITHFUL"]
    malformed = [r for r in rows if r["label"] == "MALFORMED_OR_UNUSABLE"]
    addition = [r for r in rows if r["label"] in ("ADDITION", "LOSS_AND_ADDITION")]

    # High-similarity drift: labeled ADDITION/LOSS(_AND_ADDITION) yet sls >= 0.7 (evades the drift signal).
    high_sim_drift = sorted(
        [r for r in rows if r["label"] != "FAITHFUL" and (r["sls"] or 0) >= 0.7], key=lambda r: -(r["sls"] or 0)
    )
    # Low-similarity faithful: labeled FAITHFUL yet sls < 0.5 (a faithful rewrite the drift signal underrates).
    low_sim_faithful = sorted([r for r in faithful if (r["sls"] or 1) < 0.5], key=lambda r: (r["sls"] or 1))
    # Very-low-sls items and whether they are actually drift (precision of the sls<0.30 rule).
    low_sls = [r for r in rows if (r["sls"] or 1) < 0.30]
    low_sls_drift = [r for r in low_sls if r["label"] != "FAITHFUL"]

    return {
        "n_rows": len(rows),
        "label_distribution": {name: sum(1 for r in rows if r["label"] == name) for name in fidelity.LABELS},
        "sls_faithful": _rng([r["sls"] for r in faithful]),
        "sls_non_faithful": _rng([r["sls"] for r in non_faithful]),
        "sls_malformed": _rng([r["sls"] for r in malformed]),
        "sls_addition": _rng([r["sls"] for r in addition]),
        "loo_faithful": _rng([r["loo_delta"] for r in faithful]),
        "loo_non_faithful": _rng([r["loo_delta"] for r in non_faithful]),
        "high_sim_drift_specimens": [{k: r[k] for k in ("case", "style", "item_id", "sls", "label", "text")} for r in high_sim_drift],
        "low_sim_faithful_specimens": [{k: r[k] for k in ("case", "style", "item_id", "sls", "label", "text")} for r in low_sim_faithful],
        "low_sls_rule": {
            "n_flagged": len(low_sls),
            "n_true_drift": len(low_sls_drift),
            "precision": round(len(low_sls_drift) / len(low_sls), 3) if low_sls else None,
            "note": "precision of the sls<0.30 'suspicious' rule against human non-FAITHFUL labels",
        },
    }
