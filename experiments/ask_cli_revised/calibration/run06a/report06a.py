"""Run 0.6a human-readable report renderers. Pure string assembly; no model/DB/network."""

from __future__ import annotations

from experiments.ask_cli_revised.calibration.run06a import fidelity


def fidelity_labels_md(labels: list[dict]) -> list[str]:
    L = ["# Run 0.6a — human fidelity labels (frozen before policy evaluation)", ""]
    L.append("Textual fidelity only (no domain knowledge, no answer targets). Baselines are FAITHFUL by "
             "construction and omitted. Label set: FAITHFUL | LOSS | ADDITION | LOSS_AND_ADDITION | "
             "MALFORMED_OR_UNUSABLE.")
    L.append("")
    cur_case = None
    for row in labels:
        if row["case"] != cur_case:
            cur_case = row["case"]
            L.append(f"## {cur_case}")
            L.append("")
        scope = row.get("scope", "item")
        head = f"- **{row['style']} {row['unit']}" + (f"/{row['item_id']}" if scope == "item" else " (bundle)") + f"** → **{row['label']}**"
        L.append(head)
        if scope == "item":
            L.append(f"    - src: {row['source_text']!r}")
            L.append(f"    - cand: {row['text']!r}")
        L.append(f"    - reason: {row['reason']}")
    L.append("")
    return L


def phase3_md(summary: dict) -> list[str]:
    L = ["# Run 0.6a — Phase 3: frozen metrics vs human fidelity", ""]
    L.append(f"Rows (Qwen candidate items, 3 rich questions): {summary['n_rows']}")
    L.append(f"Label distribution: {summary['label_distribution']}")
    L.append("")
    L.append("## Source-local similarity by fidelity class")
    L.append(f"- FAITHFUL: {summary['sls_faithful']}")
    L.append(f"- non-FAITHFUL: {summary['sls_non_faithful']}")
    L.append(f"- ADDITION/LOSS_AND_ADDITION: {summary['sls_addition']}")
    L.append(f"- MALFORMED_OR_UNUSABLE: {summary['sls_malformed']}")
    L.append("")
    L.append("## Leave-one-out delta by fidelity class")
    L.append(f"- FAITHFUL: {summary['loo_faithful']}")
    L.append(f"- non-FAITHFUL: {summary['loo_non_faithful']}")
    L.append("")
    L.append("## High-similarity drift specimens (non-FAITHFUL yet sls ≥ 0.7 — evade the drift signal)")
    for r in summary["high_sim_drift_specimens"]:
        L.append(f"- {r['case']} {r['style']}/{r['item_id']} sls={r['sls']} [{r['label']}]: {r['text']!r}")
    L.append("")
    L.append("## Low-similarity faithful specimens (FAITHFUL yet sls < 0.5 — the drift signal underrates)")
    for r in summary["low_sim_faithful_specimens"]:
        L.append(f"- {r['case']} {r['style']}/{r['item_id']} sls={r['sls']} [{r['label']}]: {r['text']!r}")
    L.append("")
    lr = summary["low_sls_rule"]
    L.append(f"## The sls<0.30 'suspicious' rule: flagged={lr['n_flagged']} true-drift={lr['n_true_drift']} "
             f"precision={lr['precision']} ({lr['note']})")
    L.append("")
    return L


def policy_comparison_md(*, run06_selection, policy_a, hybrids) -> list[str]:
    L = ["# Run 0.6a — policy comparison", ""]
    L.append("## Run 0.6 policy (recap)")
    for cid, s in run06_selection.items():
        L.append(f"- {cid}: selected **{s}**")
    L.append("")
    L.append("## Policy A — bounded question-level drift tie-break (sensitivity)")
    L.append("Directions: worst/mean/per-unit-worst SLS → HIGHER better; low-SLS count/fraction → LOWER better; "
             "all compared as burden (LOWER better).")
    for summary_name, per_band in policy_a.items():
        L.append(f"\n### drift summary: {summary_name}")
        for band, per_case in per_band.items():
            parts = []
            for cid, res in per_case.items():
                diff = "≠06" if res["differs_from_run06"] else "=06"
                parts.append(f"{cid}={res['selected']}({diff},nf={res['selected_nonfaithful_units']})")
            L.append(f"- band {band}: " + " · ".join(parts))
    L.append("")
    L.append("## Policy B — hybrid assemblies (per-source-unit substitution)")
    for name, h in hybrids.items():
        m = h["metrics"]
        fc = h["fidelity"]["counts"]
        L.append(f"\n### {name} — {h['label']}")
        L.append(f"- global_recon={m['global_reconstruction']} weakest_cov={m['weakest_coverage']} items={m['n_items']}")
        L.append(f"- fidelity counts: {fc}")
        if h.get("substitutions"):
            L.append(f"- substituted units: {h['substitutions']}")
        if h.get("interaction"):
            L.append(f"- simultaneous-apply interaction: {h['interaction']}")
    L.append("")
    return L


def main_report_md(*, inputs_rec, phase3, policy_a_findings, hybrids, arch) -> list[str]:
    L = ["# Run 0.6a — offline decomposition-fidelity + selection-policy reanalysis (report)", ""]
    L.append("Deterministic reanalysis of the FROZEN Run 0.6 candidate material. **No new model inference** "
             "(no Qwen/Juno/Ollama/Gemini), no retrieval, no discovery, no context selection. The only model "
             "used is the local all-MiniLM embedder for the cosine re-audit of assembled hybrids.")
    L.append("")
    L.append("## Terminology correction to the interpretation of Run 0.6 (does NOT modify the Run 0.6 dir)")
    L.append("Run 0.6 established: **zero canonical source-unit invention, zero canonical source-unit loss, "
             "automated `invention_flags` = 0.** It did **not** establish zero *rewrite-level* invention — the "
             "human lineage review (and this run's fidelity labels) found real rewrite-level semantic additions "
             "the automated invention audit did not detect (e.g. q_aib u1 multi instantiated "
             "'aggression, impulsivity, decision-making' at source-local similarity 0.91). This is a Run 0.6a "
             "correction to the *interpretation* of the frozen result, not a rewrite of the prior artifact; "
             "every Run 0.6 file is byte-for-byte unchanged (dir digest asserted).")
    L.append("")
    L.append("## Inputs (frozen; hashes asserted unchanged)")
    for name, h in inputs_rec["hashes"].items():
        L.append(f"- {name}: `{h[:16]}`")
    L.append(f"- run06 dir digest: `{inputs_rec['dir_digest'][:16]}`")
    L.append(f"- embedder: {inputs_rec.get('embedder')}")
    L.append(f"- fidelity_labels.json sha256 (frozen before policies): `{inputs_rec.get('fidelity_sha256','')[:16]}`")
    L.append("")
    L.extend(phase3)
    L.append("## Policy A findings")
    L.extend(policy_a_findings)
    L.append("## Policy B findings (H0 / H1 / H2-oracle / Hm-metric-only)")
    for name, h in hybrids.items():
        m = h["metrics"]; fc = h["fidelity"]["counts"]
        L.append(f"- **{name}** ({h['label']}): global={m['global_reconstruction']} weakest_cov={m['weakest_coverage']} "
                 f"faithful_units={fc['FAITHFUL']} non_faithful={sum(v for k,v in fc.items() if k!='FAITHFUL')}")
    L.append("")
    L.append("## Architecture assessment + success questions")
    L.extend(arch)
    L.append("")
    L.append("## STOP")
    L.append("No new inference, retrieval, context, evidence, verifier, synthesis, or Run 0.7. Handing back.")
    return L
