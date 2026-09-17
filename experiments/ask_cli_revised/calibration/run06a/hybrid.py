"""Policy B (Phases 5-7): per-source-unit hybrid decompositions, assembled from FROZEN same-unit
representations only, then re-audited with the local embedder.

H0  = exact frozen Run 0.6 selection (control).
H1  = replace each reference-DRIFTED unit with its exact-source baseline (label-based).
H2  = ORACLE (non-deployable): replace each DRIFTED unit with the best reference-FAITHFUL frozen Qwen
      representation for that unit, else baseline. Upper bound of the candidate pool.
Hm  = metric-only, ORDER-INDEPENDENT, label-free: suspicious units (by H0's re-audited source-local drift /
      coverage) each get their best same-unit substitution evaluated INDEPENDENTLY against H0; accepted
      decisions are frozen and applied simultaneously; the assembly is re-audited once; a guardrail
      interaction is reported, never silently reordered/undone.

Every substitution uses a frozen representation of the SAME source_unit_id; no candidate text is generated.
Phase 8 caveat: baseline trivially dominates source-local fidelity because it IS the source language, so a
worst-SLS metric pushes Hm toward baseline; this measures representational fidelity, NOT retrieval optimality.
"""

from __future__ import annotations

from experiments.ask_cli_revised.calibration.audit import AuditThresholds
from experiments.ask_cli_revised.calibration.run06.audit_ext import audit_candidate
from experiments.ask_cli_revised.calibration.run06a import fidelity, inputs

# Run 0.6 reference-lineage (model-authored) DRIFTED source units (the only label-based input to H1/H2).
DRIFTED_UNITS = {"q_aib": {"u1", "u3", "u5"}, "q_depr": {"u2"}, "q_builtenv": set()}

SUSPICIOUS_SLS = 0.30       # Hm: a unit whose H0 worst source-local similarity is below this is "suspicious"
SUSPICIOUS_COVERAGE = 0.30  # Hm: or whose H0 per-unit coverage best-match is below this
GLOBAL_GUARDRAIL_BAND = 0.02  # Hm: a swap must not drop whole-question global reconstruction by more than this
_MEASURE_ONLY = AuditThresholds(global_gate=1.0, coverage_gate=1.0)
_LABEL_ORDER = {name: i for i, name in enumerate(fidelity.LABELS)}


def _units_order(frozen, case):
    return [u["source_unit_id"] for u in inputs.source_units(frozen, case)]


def _recover_style(frozen, case, unit_id, items):
    """The frozen Run 0.6 provenance of this unit's H0 items, reconstructed AUTHORITATIVELY from the
    frozen decomposition's own metadata — never by matching candidate text.

    Text-matching is unsound here. q_builtenv fell back to a whole-question BASELINE, yet its u7 baseline
    item ("visuospatial processing and more.") is byte-identical to the `relation` candidate for the same
    unit — so matching text in STYLES order (minimal, relation, multi, baseline) mislabeled u7 as
    "relation" before "baseline" was ever tried. Provenance must win over text identity.

    The freeze is whole-question (run06/freeze.py): one `selected_candidate` per question, plus per-item
    repair, or a whole baseline fallback. So each unit's provenance is:
      every item is_baseline -> "baseline"  (exact source unit)
      any item repaired      -> "selected"  (repaired item, absent from the 02 candidate pool)
      otherwise              -> the question's selected_candidate base style.
    """
    if items and all(i.get("is_baseline") for i in items):
        return "baseline"
    if any(i.get("repaired") for i in items):
        return "selected"
    return inputs.frozen_selection(frozen, case)["selected_candidate"].split("+")[0]


def h0_representations(frozen, case) -> dict[str, dict]:
    """unit_id -> {style, items} for the frozen Run 0.6 selection (H0)."""
    sel = inputs.frozen_selection(frozen, case)
    by_unit: dict[str, list[dict]] = {}
    for it in sel["items"]:
        by_unit.setdefault(it["source_unit_id"], []).append(dict(it))
    out = {}
    for uid, items in by_unit.items():
        style = _recover_style(frozen, case, uid, items)
        out[uid] = {"style": style, "items": items}
    return out


def assemble(reps_by_unit: dict[str, dict], units_order: list[str]) -> list[dict]:
    items = []
    for uid in units_order:
        items.extend(dict(i) for i in reps_by_unit[uid]["items"])
    return items


def reaudit(frozen, case, embed, reps_by_unit: dict[str, dict]) -> dict:
    question = frozen["data"]["02_candidates.json"][case]["question"]
    units = inputs.source_units(frozen, case)
    items = assemble(reps_by_unit, _units_order(frozen, case))
    return audit_candidate(question, units, items, embed, thresholds=_MEASURE_ONLY)


def fidelity_counts(case, reps_by_unit: dict[str, dict]) -> dict:
    counts = {name: 0 for name in fidelity.LABELS}
    per_unit = {}
    for uid, rep in reps_by_unit.items():
        lab = fidelity.representation_label(case, rep["style"], rep["items"])
        counts[lab["label"]] += 1
        per_unit[uid] = {"style": rep["style"], **lab}
    return {"counts": counts, "per_unit": per_unit}


def _baseline_rep(frozen, case, unit_id) -> dict:
    rep = inputs.representation(frozen, case, "baseline", unit_id)
    return {"style": "baseline", "items": rep["items"]}


def build_h1(frozen, case) -> dict[str, dict]:
    h0 = h0_representations(frozen, case)
    for uid in DRIFTED_UNITS[case]:
        h0[uid] = _baseline_rep(frozen, case, uid)
    return h0


def build_h2_oracle(frozen, case) -> dict[str, dict]:
    """ORACLE / NON-DEPLOYABLE: uses the model-authored reference fidelity labels. Best FAITHFUL frozen Qwen for a drifted unit."""
    h0 = h0_representations(frozen, case)
    for uid in DRIFTED_UNITS[case]:
        best = None
        for style in ("minimal", "relation", "multi"):
            rep = inputs.representation(frozen, case, style, uid)
            if rep is None:
                continue
            lab = fidelity.representation_label(case, style, rep["items"])
            if lab["label"] == "FAITHFUL":
                # prefer higher worst-SLS among faithful Qwen options (tie-break only, still label-gated)
                score = inputs.worst_sls(rep["items"])
                if best is None or score > best[0]:
                    best = (score, style, rep["items"])
        h0[uid] = {"style": best[1], "items": best[2]} if best else _baseline_rep(frozen, case, uid)
    return h0


def build_hm(frozen, case, embed) -> dict:
    """Metric-only, order-independent. Returns {reps, decisions, interaction}."""
    units_order = _units_order(frozen, case)
    h0 = h0_representations(frozen, case)
    h0_audit = reaudit(frozen, case, embed, h0)
    h0_global = h0_audit["global_reconstruction"]
    sls_by_item = {d["item_id"]: d["source_local_similarity"] for d in h0_audit["source_local_drift"]}
    cov_by_unit = {c["source_unit_id"]: c["best_match"] for c in h0_audit["source_unit_coverage"]}

    def unit_worst_sls(items):
        vals = [sls_by_item.get(i["item_id"], 1.0) for i in items]
        return min(vals) if vals else 1.0

    decisions = []
    accepted: dict[str, dict] = {}
    for uid in units_order:
        cur = h0[uid]
        cur_worst = unit_worst_sls(cur["items"])
        suspicious = (cur_worst < SUSPICIOUS_SLS) or (cov_by_unit.get(uid, 1.0) < SUSPICIOUS_COVERAGE)
        if not suspicious:
            continue
        # Evaluate every same-unit alternative INDEPENDENTLY against H0 (never a moving reference).
        best_alt = None
        for style in ("minimal", "relation", "multi", "baseline"):  # Qwen first; baseline is the fallback
            rep = inputs.representation(frozen, case, style, uid)
            if rep is None or [i["text"] for i in rep["items"]] == [i["text"] for i in cur["items"]]:
                continue
            alt_worst = inputs.worst_sls(rep["items"])
            if alt_worst <= cur_worst:  # must strictly improve the unit's worst source-local similarity
                continue
            trial = {**h0, uid: {"style": style, "items": rep["items"]}}
            trial_global = reaudit(frozen, case, embed, trial)["global_reconstruction"]
            passes_guardrail = trial_global >= h0_global - GLOBAL_GUARDRAIL_BAND
            cand = {
                "style": style, "items": rep["items"], "alt_worst": alt_worst,
                "trial_global": round(trial_global, 4), "passes_guardrail": passes_guardrail,
                "is_qwen": style != "baseline",
            }
            if passes_guardrail:
                # prefer a Qwen alternative over baseline; among same class, higher worst-SLS
                key = (cand["is_qwen"], alt_worst)
                if best_alt is None or key > (best_alt["is_qwen"], best_alt["alt_worst"]):
                    best_alt = cand
        decision = {"unit": uid, "cur_worst": round(cur_worst, 4), "coverage": round(cov_by_unit.get(uid, 1.0), 4), "chosen": None}
        if best_alt is not None:
            accepted[uid] = {"style": best_alt["style"], "items": best_alt["items"]}
            decision["chosen"] = {"style": best_alt["style"], "alt_worst": round(best_alt["alt_worst"], 4), "trial_global": best_alt["trial_global"]}
        decisions.append(decision)

    # Freeze decisions; apply ALL accepted simultaneously; re-audit once; report interaction.
    hm = {uid: (accepted[uid] if uid in accepted else h0[uid]) for uid in units_order}
    hm_global = reaudit(frozen, case, embed, hm)["global_reconstruction"]
    interaction = {
        "h0_global": round(h0_global, 4),
        "hm_global": round(hm_global, 4),
        "combined_drop": round(h0_global - hm_global, 4),
        "guardrail_band": GLOBAL_GUARDRAIL_BAND,
        "violates_after_simultaneous_apply": (h0_global - hm_global) > GLOBAL_GUARDRAIL_BAND,
        "n_substitutions": len(accepted),
    }
    return {"reps": hm, "decisions": decisions, "interaction": interaction}
