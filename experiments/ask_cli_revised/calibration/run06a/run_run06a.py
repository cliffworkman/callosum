"""Run 0.6a orchestrator — offline reanalysis of the frozen Run 0.6 candidate material.

    python -m experiments.ask_cli_revised.calibration.run06a.run_run06a --run06 <run06-dir> --out <run06a-dir>

Order (steering #4): load+hash frozen inputs -> author+write fidelity_labels.json + record its sha256 ->
load the LOCAL embedder -> Phase 3 correlation -> Policy A sensitivity -> Policy B hybrids (H0/H1/H2/Hm) ->
write reports -> assert the fidelity hash + frozen input hashes + run06 dir digest are unchanged. No Qwen,
Juno, Ollama, Gemini, retrieval, discovery, context, evidence, verifier, or synthesis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ask_cli_revised.calibration.run06a import (  # noqa: E402
    fidelity,
    hybrid,
    inputs,
    metrics_audit,
    policy_a,
    report06a,
)
from experiments.ask_cli_revised.trace import TraceWriter  # noqa: E402

RUN06_SELECTED_BASE = {"q_aib": "multi", "q_depr": "minimal", "q_builtenv": "baseline"}
POLICY_A_BANDS = (0.005, 0.010, 0.020, 0.030, 0.050)


def _style_fidelity_counts(case: str, frozen) -> dict:
    """Fidelity counts if a whole question used one pure style (per-unit reps of that style)."""
    out = {}
    for style in ("minimal", "relation", "multi", "baseline"):
        reps = {}
        for u in inputs.source_units(frozen, case):
            rep = inputs.representation(frozen, case, style, u["source_unit_id"])
            if rep:
                reps[u["source_unit_id"]] = {"style": style, "items": rep["items"]}
        fc = hybrid.fidelity_counts(case, reps)["counts"]
        out[style] = {"counts": fc, "non_faithful": sum(v for k, v in fc.items() if k != "FAITHFUL")}
    return out


def _build_fidelity_labels(frozen) -> list[dict]:
    rows = []
    for case in inputs.RICH_CASES:
        cands = frozen["data"]["02_candidates.json"][case]["candidates"]
        units = {u["source_unit_id"]: u["text"] for u in inputs.source_units(frozen, case)}
        for style in ("minimal", "relation", "multi"):
            for it in cands[style]["items"]:
                lab = fidelity.item_label(case, style, it["item_id"])
                if lab:
                    rows.append({"case": case, "style": style, "unit": it["source_unit_id"], "item_id": it["item_id"],
                                 "scope": "item", "source_text": units[it["source_unit_id"]], "text": it["text"], **lab})
            # multi bundle labels
            if style == "multi":
                for uid, bl in fidelity.MULTI_BUNDLE.get(case, {}).items():
                    bundle_items = [i["text"] for i in cands["multi"]["items"] if i["source_unit_id"] == uid]
                    if len(bundle_items) > 1:
                        rows.append({"case": case, "style": "multi", "unit": uid, "item_id": f"{uid}-bundle",
                                     "scope": "bundle", "source_text": units[uid], "text": " || ".join(bundle_items), **bl})
        # repaired/selected items not in the 02 pool
        for iid, lab in fidelity.ITEM.get(case, {}).get("selected", {}).items():
            sel = inputs.frozen_selection(frozen, case)
            txt = next((i["text"] for i in sel["items"] if i["item_id"] == iid), "")
            uid = iid.split("-")[0]
            rows.append({"case": case, "style": "selected", "unit": uid, "item_id": iid, "scope": "item",
                         "source_text": units.get(uid, ""), "text": txt, **lab})
    return rows


def _hybrid_record(frozen, case, embed, reps, *, name, label, substitutions=None, interaction=None) -> dict:
    audit = hybrid.reaudit(frozen, case, embed, reps)
    fc = hybrid.fidelity_counts(case, reps)
    return {
        "name": name, "label": label,
        "metrics": {"global_reconstruction": audit["global_reconstruction"], "weakest_coverage": audit["weakest_coverage"],
                    "n_items": sum(len(r["items"]) for r in reps.values())},
        "fidelity": fc,
        "reps": {u: {"style": r["style"], "item_ids": [i["item_id"] for i in r["items"]]} for u, r in reps.items()},
        "substitutions": substitutions or [],
        "interaction": interaction,
    }


def run(run06_dir: str, out_dir: str) -> int:
    trace = TraceWriter(out_dir)
    frozen = inputs.load_frozen(run06_dir)
    inputs_rec = {"run06_dir": frozen["dir"], "hashes": frozen["hashes"], "dir_digest": frozen["dir_digest"]}

    # steering #4: author + freeze fidelity labels BEFORE any policy.
    labels = _build_fidelity_labels(frozen)
    trace.write_json("fidelity_labels.json", labels)
    fidelity_sha = hashlib.sha256((Path(out_dir) / "fidelity_labels.json").read_bytes()).hexdigest()
    inputs_rec["fidelity_sha256"] = fidelity_sha

    registry, embed, embed_id = inputs.load_embedder()
    inputs_rec["embedder"] = embed_id
    trace.write_json("00_inputs.json", inputs_rec)

    try:
        # Phase 3
        rows = metrics_audit.joined_rows(frozen)
        phase3 = metrics_audit.summarize(rows)

        # Phase 4 — Policy A sensitivity grid
        style_fid = {c: _style_fidelity_counts(c, frozen) for c in inputs.RICH_CASES}
        policy_a_grid: dict = {}
        for summary_name in policy_a.DRIFT_SUMMARIES:
            policy_a_grid[summary_name] = {}
            for band in POLICY_A_BANDS:
                per_case = {}
                for case in inputs.RICH_CASES:
                    res = policy_a.select_policy_a(frozen["data"]["02_candidates.json"][case]["candidates"], band=band, summary=summary_name)
                    sel = res["selected"]
                    entry = frozen["data"]["02_candidates.json"][case]["candidates"][sel]
                    per_case[case] = {
                        "selected": sel,
                        "differs_from_run06": sel != RUN06_SELECTED_BASE[case],
                        "global_reconstruction": entry["audit"]["global_reconstruction"],
                        "weakest_coverage": entry["audit"]["weakest_coverage"],
                        "selected_nonfaithful_units": style_fid[case][sel]["non_faithful"],
                        "band_members": res.get("band_members", []),
                    }
                policy_a_grid[summary_name][f"{band:.3f}"] = per_case
        trace.write_json("policy_a_sensitivity.json", policy_a_grid)

        # Phase 5-7 — hybrids
        hybrids: dict = {}
        assemblies: dict = {}
        for case in inputs.RICH_CASES:
            h0 = hybrid.h0_representations(frozen, case)
            h1 = hybrid.build_h1(frozen, case)
            h2 = hybrid.build_h2_oracle(frozen, case)
            hm = hybrid.build_hm(frozen, case, embed)
            assemblies[case] = {
                "H0": {u: r["style"] for u, r in h0.items()},
                "H1": {u: r["style"] for u, r in h1.items()},
                "H2_oracle": {u: r["style"] for u, r in h2.items()},
                "Hm_metric_only": {u: r["style"] for u, r in hm["reps"].items()},
                "Hm_decisions": hm["decisions"],
                "Hm_interaction": hm["interaction"],
                "drifted_units": sorted(hybrid.DRIFTED_UNITS[case]),
            }
            hybrids[case] = {
                "H0": _hybrid_record(frozen, case, embed, h0, name="H0", label="frozen Run 0.6 selection"),
                "H1": _hybrid_record(frozen, case, embed, h1, name="H1", label="drifted units -> baseline (label-based)",
                                     substitutions=sorted(hybrid.DRIFTED_UNITS[case])),
                "H2": _hybrid_record(frozen, case, embed, h2, name="H2", label="ORACLE (non-deployable): drifted -> best faithful Qwen else baseline",
                                     substitutions=sorted(hybrid.DRIFTED_UNITS[case])),
                "Hm": _hybrid_record(frozen, case, embed, hm["reps"], name="Hm", label="metric-only, order-independent, label-free",
                                     substitutions=[d["unit"] for d in hm["decisions"] if d["chosen"]], interaction=hm["interaction"]),
            }
        trace.write_json("hybrid_assemblies.json", assemblies)
        trace.write_json("hybrid_metrics.json", hybrids)

        # H0 self-consistency: recomputed global recon vs frozen 02 value for the selected style.
        consistency = {}
        for case in inputs.RICH_CASES:
            sel_base = RUN06_SELECTED_BASE[case]
            frozen_global = frozen["data"]["02_candidates.json"][case]["candidates"][sel_base]["audit"]["global_reconstruction"]
            # H0 for q_depr differs from pure minimal (u8 repaired); compare only where H0==pure style (q_aib multi, q_builtenv baseline)
            consistency[case] = {"h0_global": hybrids[case]["H0"]["metrics"]["global_reconstruction"], "frozen_style_global": frozen_global}
        trace.write_json("h0_consistency.json", consistency)

        # ---- reports ----
        trace.write_report("run_0_6a_fidelity_labels.md", report06a.fidelity_labels_md(labels))
        trace.write_report(
            "run_0_6a_policy_comparison.md",
            report06a.policy_comparison_md(
                run06_selection={c: RUN06_SELECTED_BASE[c] + ("+repair" if c == "q_depr" else "") for c in inputs.RICH_CASES},
                policy_a=policy_a_grid,
                hybrids={f"{case}:{k}": {**hybrids[case][k], "label": f"{case} {hybrids[case][k]['label']}"} for case in inputs.RICH_CASES for k in ("H0", "H1", "H2", "Hm")},
            ),
        )
        arch = _arch_section(frozen, style_fid, policy_a_grid, hybrids)
        trace.write_report(
            "RUN_0_6A_REPORT.md",
            report06a.main_report_md(inputs_rec=inputs_rec, phase3=report06a.phase3_md(phase3),
                                     policy_a_findings=_policy_a_findings(policy_a_grid), hybrids={f"{c}:{k}": hybrids[c][k] for c in inputs.RICH_CASES for k in ("H0", "H1", "H2", "Hm")}, arch=arch),
        )

        # ---- freeze assertions (steering #4 + #1) ----
        assert hashlib.sha256((Path(out_dir) / "fidelity_labels.json").read_bytes()).hexdigest() == fidelity_sha, "fidelity labels moved!"
        after = inputs.load_frozen(run06_dir)
        assert after["hashes"] == frozen["hashes"], "frozen input hashes changed!"
        assert after["dir_digest"] == frozen["dir_digest"], "run06 dir changed!"
        print(f"[run0.6a] done -> {out_dir}")
        return 0
    finally:
        registry.close()


def _policy_a_findings(grid: dict) -> list[str]:
    L = []
    changed = []
    for summary_name, per_band in grid.items():
        for band, per_case in per_band.items():
            for case, res in per_case.items():
                if res["differs_from_run06"]:
                    changed.append(f"{summary_name}@{band}: {case} -> {res['selected']} (nf_units={res['selected_nonfaithful_units']})")
    if changed:
        L.append("Selections that DIFFER from Run 0.6 under some (summary, band):")
        L.extend(f"- {c}" for c in changed)
    else:
        L.append("No (summary, band) combination changed any question's selection vs Run 0.6.")
    L.append("")
    return L


def _arch_section(frozen, style_fid, grid, hybrids) -> list[str]:
    L = []
    # H1<->H2 gap: units where H2 kept a faithful Qwen but H1 used baseline
    for case in inputs.RICH_CASES:
        h1 = hybrids[case]["H1"]["reps"]
        h2 = hybrids[case]["H2"]["reps"]
        gap = [u for u in h2 if h2[u]["style"] != "baseline" and h1.get(u, {}).get("style") == "baseline"]
        hm_subs = hybrids[case]["Hm"]["substitutions"]
        L.append(f"- **{case}**: H0 faithful_units={hybrids[case]['H0']['fidelity']['counts']['FAITHFUL']}/"
                 f"{sum(hybrids[case]['H0']['fidelity']['counts'].values())}; "
                 f"H1 faithful={hybrids[case]['H1']['fidelity']['counts']['FAITHFUL']}; "
                 f"H2(oracle) faithful={hybrids[case]['H2']['fidelity']['counts']['FAITHFUL']}; "
                 f"Hm faithful={hybrids[case]['Hm']['fidelity']['counts']['FAITHFUL']}; "
                 f"H1↔H2 gap units (faithful-Qwen kept only by oracle)={gap}; Hm substituted={hm_subs}")
    # Q8: q_builtenv units with a faithful Qwen representation discarded by whole-question baseline fallback
    discarded = []
    for u in inputs.source_units(frozen, "q_builtenv"):
        uid = u["source_unit_id"]
        for style in ("minimal", "relation", "multi"):
            rep = inputs.representation(frozen, "q_builtenv", style, uid)
            if rep and fidelity.representation_label("q_builtenv", style, rep["items"])["label"] == "FAITHFUL":
                discarded.append(f"{uid}:{style}")
                break
    L.append(f"- **Q8 (q_builtenv baseline fallback discarded faithful Qwen rewrites):** units with an available "
             f"FAITHFUL Qwen representation = {discarded}")
    L.append("")
    return L


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run06", required=True, help="the frozen Run 0.6 run directory")
    p.add_argument("--out", required=True, help="Run 0.6a output directory")
    args = p.parse_args(argv)
    return run(args.run06, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
