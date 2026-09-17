"""Run 0.6 human report renderers: run_0_6_decomposition_review.md + RUN_0_6_REPORT.md.

Pure string assembly over the orchestrator's per-question output. No model, DB, or network.
"""

from __future__ import annotations


def _candidate_block(style: str, entry: dict) -> list[str]:
    a = entry["audit"]
    cs = entry["calls_summary"]
    lines = [
        f"- **{style}**: items={len(entry['items'])} global_recon={a['global_reconstruction']} "
        f"weakest_cov={a['weakest_coverage']} redundancy_pairs={len(a.get('redundancy', []))} "
        f"| calls={cs['calls']} schema_fail={cs['schema_failures']} trunc={cs['truncations']} "
        f"fb={cs['fallbacks']} lat={cs['latency_total_s']}s"
    ]
    for item in entry["items"]:
        lines.append(f"    - [{item['item_id']}] {item['text']!r}")
    return lines


def decomposition_review_md(questions_out: dict) -> list[str]:
    lines = ["# Run 0.6 — decomposition selection review", ""]
    lines.append(
        "Per question: source units, three Qwen candidates + source baseline, the audit diagnostics "
        "(global reconstruction PRIMARY; per-source-unit coverage = local omission veto/flag; LOO + "
        "source-local drift = diagnostic/repair only), any bounded repair, and the deterministic selection."
    )
    lines.append("")
    for cid, q in questions_out.items():
        lines.append(f"## {cid} ({q['split']}, {q['source']})")
        lines.append("")
        lines.append(f"Question: {q['question']!r}")
        lines.append("")
        lines.append(f"Source units ({len(q['units'])}):")
        for u in q["units"]:
            lines.append(f"  - {u['source_unit_id']}: {u['text']!r}")
        lines.append("")
        lines.append("### Candidates")
        for style in ("minimal", "relation", "multi", "baseline"):
            entry = q["candidates"].get(style)
            if entry:
                lines.extend(_candidate_block(style, entry))
        lines.append("")
        lines.append("### Per-source-unit coverage (selected candidate)")
        for c in q["selected_audit"]["source_unit_coverage"]:
            lines.append(
                f"  - {c['source_unit_id']}: best_match={c['best_match']} weak={c['weak']} "
                f"(best_item={c['best_item_id']})"
            )
        lines.append("")
        lines.append("### Leave-one-out (selected candidate; diagnostic only)")
        for d in q["selected_audit"]["leave_one_out"]:
            lines.append(f"  - {d['item_id']}: delta={d['delta']} suspicious={d['suspicious']}")
        if q["selected_audit"].get("redundancy"):
            lines.append("")
            lines.append("### Redundancy (selected candidate)")
            for r in q["selected_audit"]["redundancy"]:
                lines.append(f"  - {r['item_a']} ~ {r['item_b']}: {r['similarity']}")
        lines.append("")
        rep = q["repair"]
        if rep and rep.get("needed"):
            lines.append("### Repair (one bounded pass)")
            lines.append(f"  diagnosis: {rep['diagnosis']}")
            for d in rep["repair_details"]:
                lines.append(f"  - {d['item_id']}: changed={d['changed']}")
                lines.append(f"      before: {d['before']!r}")
                lines.append(f"      after:  {d['after']!r}")
            lines.append(f"  re-selection: {q['reselection_reason']}")
        else:
            lines.append("### Repair: not triggered")
        lines.append("")
        lines.append(f"### SELECTED: **{q['selected']}** — {q['selection']['reason']}")
        lines.append(f"decomposition_hash: `{q['decomposition_hash']}`")
        if cid == "q_aib":
            hits = q.get("aib_target_hits", {})
            missed = [k for k, v in hits.items() if not v]
            lines.append(f"AIB targets retained: {sum(hits.values())}/{len(hits)}; missed: {missed}")
        lines.append(f"source_loss: {q['source_loss']} · invention_flags: {q['invention_flags']}")
        if q.get("open_ended_units"):
            lines.append("open-ended units (confirm rewrite stayed open-ended, did not instantiate specifics):")
            for oe in q["open_ended_units"]:
                lines.append(f"  - {oe['source_unit_id']} {oe['source_text']!r} -> {oe['rewrite']!r}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return lines


def run_report_md(*, mode, smoke, thresholds, questions_out, walk_summary, frozen_hashes) -> list[str]:
    L = ["# Run 0.6 — self-auditing decomposition selection + upstream intent-lineage (report)", ""]
    L.append("## Structured output")
    for s in smoke:
        L.append(f"- mode `{s['mode']}`: enforced={s['enforced']}")
    L.append(f"- **chosen mode: `{mode}`**")
    L.append("")
    L.append("## Audit gates (empirical, from dev RELATION-candidate audits — descriptive/provisional)")
    L.append(f"- global readiness gate ≥ {thresholds['global_gate']}; coverage flag gate ≥ {thresholds['coverage_gate']}")
    L.append(f"- coverage veto floor < {questions_out and next(iter(questions_out.values()))['selection'].get('coverage_veto_floor')}")
    L.append("")
    L.append("## Decomposition selection (per question)")
    for cid, q in questions_out.items():
        L.append(
            f"- **{cid}** ({q['split']}): units={len(q['units'])} selected=**{q['selected']}** "
            f"global_recon={q['selected_audit']['global_reconstruction']} weakest_cov={q['selected_audit']['weakest_coverage']} "
            f"repaired={bool(q['repair'] and q['repair'].get('needed'))} source_loss={q['source_loss']}"
        )
        if cid == "q_aib":
            hits = q.get("aib_target_hits", {})
            L.append(f"    - AIB targets retained: {sum(hits.values())}/{len(hits)}; missed: {[k for k,v in hits.items() if not v]}")
    L.append("")
    L.append("## Frozen decomposition hashes")
    for cid, h in frozen_hashes.items():
        L.append(f"- {cid}: `{h}`")
    L.append("")
    L.append("## Upstream walk — stage-by-stage survival (rich questions)")
    for cid, summ in walk_summary.items():
        L.append(f"### {cid}")
        L.append(
            f"- source_units={summ['n_source_units']} starved={summ['starved_units']} "
            f"no_papers={summ['units_with_no_papers']} no_anchors={summ['units_with_no_anchors']} "
            f"no_non_e_envelope={summ['units_with_no_non_e_envelope']}"
        )
        L.append(f"- context A/B/C/D/E distribution={summ['context_choice_distribution']}")
    L.append("")
    L.append("## Success questions (fill during review)")
    L.append("1. intent preserved? 2. aggregate reconstruction sensible? 3. per-unit coverage adds info? ")
    L.append("4. LOO localizes? 5. repair improved without new requests? 6. selection interpretable? ")
    L.append("7. traceable once frozen? 8. where did intent drift/starve? 9. sensible context neighborhoods? ")
    L.append("10. ready to proceed to evidence screening?")
    L.append("")
    L.append("_Post-hoc human sections (PRESERVED/DRIFTED/STARVED per unit, drift/starvation first-stage, "
             "the 46-item handoff) are completed after reading run_0_6_request_lineage.md._")
    L.append("")
    return L
