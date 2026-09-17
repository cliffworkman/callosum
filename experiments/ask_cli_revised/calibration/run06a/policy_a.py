"""Policy A (Phase 4): bounded question-level drift tie-break, over FROZEN candidate audits only.

Keeps Run 0.6 qualification (hard invariants + per-source-unit coverage veto at COVERAGE_VETO_FLOOR). Among
eligible Qwen candidates within a small reconstruction BAND of the global-reconstruction leader, pick the one
with the lowest DRIFT BURDEN. No new embedding: global reconstruction and per-item source-local similarity
come straight from the frozen 02_candidates audits. baseline is excluded from ranking (as in Run 0.6) and is
the fallback only when no Qwen candidate qualifies.

steering #3 — every drift summary documents its optimization direction, and all are converted to a BURDEN
(LOWER is better) before comparison; raw similarities and burdens are never compared under one direction.
"""

from __future__ import annotations

from experiments.ask_cli_revised.calibration.run06.selection import COVERAGE_VETO_FLOOR

LOW_SLS_THRESHOLD = 0.30  # descriptive (reuses the repair drift floor); "very-low" source-local similarity
QWEN_STYLES = ("minimal", "relation", "multi")

# name -> (human direction on the RAW summary, callable(items)->raw summary). Burden is derived below so that
# LOWER burden is always better, regardless of the raw direction.
DRIFT_SUMMARIES = {
    "worst_item_sls": "HIGHER_SIM_BETTER",
    "mean_item_sls": "HIGHER_SIM_BETTER",
    "low_sls_count": "LOWER_COUNT_BETTER",
    "low_sls_fraction": "LOWER_COUNT_BETTER",
    "mean_unit_worst_sls": "HIGHER_SIM_BETTER",
}


def items_with_sls(entry: dict) -> list[dict]:
    """Attach each item's source-local similarity (which lives in the entry's audit, not on the item)."""
    sls = {d["item_id"]: d["source_local_similarity"] for d in entry["audit"].get("source_local_drift", [])}
    return [{**i, "source_local_similarity": sls.get(i["item_id"])} for i in entry["items"]]


def _sls_values(items: list[dict]) -> list[float]:
    return [i["source_local_similarity"] for i in items if i.get("source_local_similarity") is not None]


def _per_unit_worst(items: list[dict]) -> list[float]:
    by_unit: dict[str, float] = {}
    for i in items:
        s = i.get("source_local_similarity")
        if s is None:
            continue
        uid = i["source_unit_id"]
        by_unit[uid] = min(by_unit.get(uid, 1.0), s)
    return list(by_unit.values())


def drift_burden(items: list[dict], summary: str) -> float:
    """Return the drift BURDEN for a candidate's items under `summary`. LOWER burden = less drift = better."""
    sls = _sls_values(items)
    if summary == "worst_item_sls":
        return 1.0 - (min(sls) if sls else 0.0)
    if summary == "mean_item_sls":
        return 1.0 - (sum(sls) / len(sls) if sls else 0.0)
    if summary == "low_sls_count":
        return float(sum(1 for s in sls if s < LOW_SLS_THRESHOLD))
    if summary == "low_sls_fraction":
        return (sum(1 for s in sls if s < LOW_SLS_THRESHOLD) / len(sls)) if sls else 0.0
    if summary == "mean_unit_worst_sls":
        worsts = _per_unit_worst(items)
        return 1.0 - (sum(worsts) / len(worsts) if worsts else 0.0)
    raise ValueError(f"unknown drift summary: {summary}")


def _min_coverage(entry: dict) -> float:
    cov = [c["best_match"] for c in entry["audit"]["source_unit_coverage"]]
    return min(cov) if cov else 0.0


def eligible_candidates(case_candidates: dict) -> list[dict]:
    """Qwen candidates that pass Run 0.6 qualification (coverage veto). Returns [{style, entry, global, ...}]."""
    out = []
    for style in QWEN_STYLES:
        entry = case_candidates[style]
        min_cov = _min_coverage(entry)
        if min_cov < COVERAGE_VETO_FLOOR:
            continue  # vetoed exactly as in Run 0.6
        out.append({"style": style, "entry": entry, "global": entry["audit"]["global_reconstruction"], "min_cov": min_cov})
    return out


def select_policy_a(case_candidates: dict, *, band: float, summary: str) -> dict:
    """Run 0.6 qualification -> within `band` of the global leader -> lowest drift burden."""
    elig = eligible_candidates(case_candidates)
    if not elig:
        return {"selected": "baseline", "reason": "no eligible Qwen candidate (coverage veto) -> baseline fallback", "band_members": []}
    leader_global = max(e["global"] for e in elig)
    band_members = [e for e in elig if e["global"] >= leader_global - band]
    for e in band_members:
        e["burden"] = drift_burden(items_with_sls(e["entry"]), summary)
    # lowest burden -> highest global -> fewer items -> stable style order
    order = {s: i for i, s in enumerate(QWEN_STYLES)}
    ranked = sorted(band_members, key=lambda e: (e["burden"], -e["global"], len(e["entry"]["items"]), order[e["style"]]))
    winner = ranked[0]
    return {
        "selected": winner["style"],
        "reason": f"within {band} of leader (global {leader_global:.4f}); lowest {summary} burden {winner['burden']:.4f}",
        "leader_global": round(leader_global, 4),
        "band_members": [{"style": e["style"], "global": round(e["global"], 4), "burden": round(e["burden"], 4)} for e in ranked],
    }
