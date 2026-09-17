"""Run 0.5 calibration orchestrator (replay-only; no Ask pipeline, no re-retrieval).

    python -m experiments.ask_cli_revised.calibration.run_calibration --db <library-copy.sqlite> --out <dir>

Order: verify structured-output enforcement (STOP if unenforceable) -> decomposition designs A/B/C on the
frozen questions -> minimum-sufficient-context controller on the frozen replay set (dev then held-out
once) -> write machine traces + the human window-review artifact + RUN_0_5_REPORT.md. Gemini/3B/full Ask
are never invoked.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ask_cli_revised.calibration import context_windows as cw  # noqa: E402
from experiments.ask_cli_revised.calibration import decomposition as dec  # noqa: E402
from experiments.ask_cli_revised.calibration.audit import AuditThresholds, audit_decomposition  # noqa: E402
from experiments.ask_cli_revised.calibration.datasets import (  # noqa: E402
    context_split,
    decomposition_cases,
    load_context_anchors,
)
from experiments.ask_cli_revised.calibration.labels import LABELS, ordinal  # noqa: E402
from experiments.ask_cli_revised.calibration.structured_output import choose_enforcing_mode  # noqa: E402
from experiments.ask_cli_revised.question import question_hash  # noqa: E402
from experiments.ask_cli_revised.runtime import QwenUnavailableError, build_runtime  # noqa: E402
from experiments.ask_cli_revised.trace import TraceWriter  # noqa: E402

PACKETS = ROOT / "experiments/ask_cli_revised/runs/revised-20260907T211542Z/08_evidence_packets.jsonl"

# A5 evaluation targets (post-hoc ONLY; never placed in a Qwen prompt). Each target is a list of
# alternative CLAUSES; a target is retained if ANY clause matches (all of that clause's tokens present in
# the aggregate decomposition text). Synonyms are alternatives (OR), co-occurrences are within a clause.
AIB_TARGETS = {
    "brain_manifestation": [("brain",), ("neural",), ("amygdala",)],
    "specific_brain_areas": [("brain area",), ("brain region",), ("region of the brain",), ("areas of the brain",), ("anatomical area",), ("specific", "brain")],
    "brain_behavior_relation": [("brain", "behav"), ("region", "behav"), ("neural", "behav")],
    "kinds_of_behaviors": [("kind", "behav"), ("type", "behav"), ("which", "behav"), ("what", "behav"), ("kinds of behav",)],
    "brain_attitude_relation": [("brain", "attitude"), ("region", "attitude"), ("neural", "attitude")],
    "kinds_of_attitudes": [("kind", "attitude"), ("type", "attitude"), ("which", "attitude"), ("what", "attitude"), ("forms of attitude",), ("different", "attitude")],
    "personality_traits": [("personality",), ("trait",)],
    "scales_instruments": [("scale",), ("instrument",), ("questionnaire",), ("assessment tool",), ("measure",)],
    "cross_cultural_evidence": [("cross-cultural",), ("cross cultural",), ("cross culture",), ("across cultures",), ("cultural",)],
    "cultures": [("culture",), ("cultural",)],
    "cross_cultural_measurement": [("measure", "culture"), ("assess", "culture"), ("validated", "culture"), ("evaluated", "culture"), ("measure", "cultural"), ("how was",)],
    "interventions": [("intervention",), ("reduc",), ("mitigat",)],
    "intervention_effectiveness": [("effective",), ("efficac",)],
}
# Known invented-request specimen from the diagnostic pilot: a "psychological theories" subquestion the
# user never asked. Scanned post-hoc, never in a prompt.
_INVENTION_MARKERS = ("psychological theor", "theories explain", "what theor")


def _aib_target_hits(items: list[dict]) -> dict:
    text = "\n".join(i["text"] for i in items).lower()
    hits = {}
    for name, clauses in AIB_TARGETS.items():
        hits[name] = any(all(tok in text for tok in clause) for clause in clauses)
    return hits


def _invention_flags(items: list[dict]) -> list[dict]:
    flags = []
    for item in items:
        low = item["text"].lower()
        for marker in _INVENTION_MARKERS:
            if marker in low:
                flags.append({"item_id": item["item_id"], "marker": marker, "text": item["text"]})
    return flags


def _source_loss(units: list[dict], items: list[dict]) -> list[str]:
    """Deterministic no-silent-loss check: which source_unit_ids have no surviving item."""
    covered = {i["source_unit_id"] for i in items}
    return [u["source_unit_id"] for u in units if u["source_unit_id"] not in covered]


def _design_calls_summary(result: dict) -> dict:
    calls = result["calls"]
    n = len(calls)
    schema_fail = sum(1 for c in calls if not c["schema_ok"])
    trunc = sum(1 for c in calls if c["truncated"])
    fb = sum(1 for c in calls if c["fallback_used"])
    lat = [c["elapsed_seconds"] for c in calls]
    return {
        "calls": n,
        "schema_failures": schema_fail,
        "truncations": trunc,
        "fallbacks": fb,
        "latency_total_s": round(sum(lat), 2),
        "latency_mean_s": round(statistics.mean(lat), 3) if lat else 0.0,
    }


def _derive_thresholds(dev_audits: list[dict]) -> AuditThresholds:
    """Empirical gates from the dev design-A distribution (documented rule): flag the weak tail.

    global_gate = min dev global reconstruction (so a dev question at/above its own norm never trips it
    spuriously; a genuinely worse decomposition trips it); coverage_gate = 20th percentile of dev
    per-source-unit coverage (repair the weakest ~fifth of units). Both floored at 0.30.
    """
    globals_ = [a["global_reconstruction"] for a in dev_audits]
    covs = [c["best_match"] for a in dev_audits for c in a["source_unit_coverage"]]
    global_gate = max(0.30, round(min(globals_) - 0.02, 4)) if globals_ else 0.5
    if covs:
        covs_sorted = sorted(covs)
        idx = max(0, int(0.20 * (len(covs_sorted) - 1)))
        coverage_gate = max(0.30, round(covs_sorted[idx], 4))
    else:
        coverage_gate = 0.5
    return AuditThresholds(global_gate=global_gate, coverage_gate=coverage_gate)


def run(db_path: str, out_dir: str, *, old_controller: bool) -> int:
    trace = TraceWriter(out_dir)
    print(f"[run0.5] out: {out_dir}")
    trace.write_json("00_frozen.json", {"question_hash": question_hash(), "db_path": str(Path(db_path).resolve())})

    try:
        rt = build_runtime(db_path, want_gemini=False, want_verifier=False)
    except QwenUnavailableError as exc:
        trace.write_json("BLOCKED.json", {"blocked": True, "reason": str(exc)})
        print(f"[run0.5] BLOCKED: {exc}")
        return 2

    try:
        base = rt.qwen_config
        embed = rt.model

        # ---- structured-output enforcement smoke test (STOP gate) ----
        print("[run0.5] structured-output smoke test")
        mode, smoke = choose_enforcing_mode(base)
        trace.write_json(
            "01_structured_output_smoke.json",
            {
                "chosen_mode": mode,
                "results": [{"mode": s.mode, "enforced": s.enforced, "calls": list(s.calls)} for s in smoke],
            },
        )
        if mode is None:
            trace.write_json(
                "STOPPED.json",
                {
                    "stopped": True,
                    "reason": "structured output not enforced through the Juno/ollama topology",
                    "smoke": [s.mode for s in smoke],
                },
            )
            print(
                "[run0.5] STOPPED: structured output not enforced (neither top_level nor response_format). See 01_structured_output_smoke.json"
            )
            return 3
        print(f"[run0.5] structured output enforced via mode={mode}")

        # ---- A. decomposition designs A/B/C ----
        dcases = decomposition_cases()
        dev = [c for c in dcases if c["split"] == "dev"]

        design_a = {c["case_id"]: dec.run_design_a(base, c["text"], mode=mode) for c in dcases}
        design_b = {c["case_id"]: dec.run_design_b(base, c["text"], mode=mode) for c in dcases}

        dev_a_audits = [
            audit_decomposition(
                c["text"],
                design_a[c["case_id"]]["units"],
                design_a[c["case_id"]]["items"],
                embed,
                thresholds=AuditThresholds(global_gate=1.0, coverage_gate=1.0),
            )
            for c in dev
        ]
        thresholds = _derive_thresholds(dev_a_audits)
        print(
            f"[run0.5] Design-C gates (from dev design-A): global>={thresholds.global_gate} coverage>={thresholds.coverage_gate}"
        )

        design_c = {
            c["case_id"]: dec.run_design_c(base, c["text"], mode=mode, embed_model=embed, thresholds=thresholds)
            for c in dcases
        }

        decomposition_out = _assemble_decomposition(dcases, design_a, design_b, design_c, embed, thresholds)
        trace.write_json("02_decomposition.json", decomposition_out)

        # ---- B. minimum-sufficient-context ----
        anchors = load_context_anchors(PACKETS)
        context_out, review_lines = _run_context(
            rt, base, anchors, mode=mode, old_controller=old_controller, trace=trace
        )
        trace.write_json("03_context.json", context_out)
        trace.write_report("run_0_5_context_review.md", review_lines)

        # ---- final report ----
        report = _final_report(mode, smoke, decomposition_out, context_out, thresholds)
        trace.write_report("RUN_0_5_REPORT.md", report)
        trace.flush_qwen()
        print(f"[run0.5] done -> {out_dir}")
        return 0
    finally:
        rt.close()


def _assemble_decomposition(dcases, design_a, design_b, design_c, embed, thresholds) -> dict:
    per_design = {}
    for name, results in (("A", design_a), ("B", design_b), ("C", design_c)):
        cases = {}
        for c in dcases:
            res = results[c["case_id"]]
            audit = res.get("final_audit") or audit_decomposition(
                c["text"], res["units"], res["items"], embed, thresholds=thresholds
            )
            entry = {
                "split": c["split"],
                "source": c["source"],
                "units": res["units"],
                "items": [
                    {k: v for k, v in i.items() if k != "source_text"} | {"source_text": i["source_text"]}
                    for i in res["items"]
                ],
                "source_loss": _source_loss(res["units"], res["items"]),
                "global_reconstruction": audit["global_reconstruction"],
                "weakest_coverage": audit["weakest_coverage"],
                "source_unit_coverage": audit["source_unit_coverage"],
                "leave_one_out": audit["leave_one_out"],
                "redundancy": audit["redundancy"],
                "calls_summary": _design_calls_summary(res),
            }
            if name == "C":
                entry["repaired"] = res["repaired"]
                entry["repair_details"] = res["repair_details"]
                entry["fell_back_units"] = res["fell_back_units"]
                entry["initial_global_reconstruction"] = res["initial_audit"]["global_reconstruction"]
                entry["initial_weakest_coverage"] = res["initial_audit"]["weakest_coverage"]
            if c["case_id"] == "q_aib":
                entry["aib_target_hits"] = _aib_target_hits(res["items"])
                entry["invention_flags"] = _invention_flags(res["items"])
            cases[c["case_id"]] = entry
        per_design[name] = cases
    return {
        "thresholds": {"global_gate": thresholds.global_gate, "coverage_gate": thresholds.coverage_gate},
        "designs": per_design,
    }


def _run_context(rt, base, anchors, *, mode, old_controller, trace) -> tuple[dict, list[str]]:
    records = []
    review = ["# Run 0.5 — minimum-sufficient-context review artifact", ""]
    review.append(
        "Window definitions (fixed for this run): A=central only, B=+/-1, C=+/-2, D=+/-3. "
        "E = even D is insufficient (NOT discard). Central chunk marked [ CENTRAL CHUNK <id> ]."
    )
    review.append("")
    agg = {label: {"chars": [], "tokens": []} for label in "ABCD"}
    boundary_reduced = {label: 0 for label in "ABCD"}
    with rt.engine.connect() as conn:
        for a in anchors:
            case = cw.build_window_case(
                conn, case_id=a["case_id"], anchor_chunk_id=a["anchor_chunk_id"], paper_id=a["paper_id"]
            )
            if case is None:
                continue
            split = context_split(a["case_id"], a["anchor_chunk_id"])
            label = LABELS.get(a["case_id"], {})
            for lbl in "ABCD":
                agg[lbl]["chars"].append(case.windows[lbl]["chars"])
                agg[lbl]["tokens"].append(case.windows[lbl]["approx_tokens"])
                if case.windows[lbl]["boundary_reduced"]:
                    boundary_reduced[lbl] += 1
            choice, call, prompt = cw.select_window(base, case, mode=mode)
            trace.qwen_call(
                stage="context",
                task="select_window",
                input_text=f"case {a['case_id']} anchor {a['anchor_chunk_id']}",
                prompt_text=prompt,
                raw_output=call.raw_text,
                provider_ok=call.provider_ok,
                parse_ok=call.parsed is not None,
                validation_ok=choice is not None,
                failure_reason=call.failure_reason,
                deterministic_fallback_used=choice is None,
                downstream_consequence=f"window={choice}",
                elapsed_seconds=call.elapsed_seconds,
                output_cap=call.output_cap,
            )
            classification = _classify_choice(choice, label)
            rec = {
                "case_id": a["case_id"],
                "anchor_chunk_id": a["anchor_chunk_id"],
                "paper_id": a["paper_id"],
                "split": split,
                "baseline_discarded": a["baseline_discarded"],
                "human_label": label.get("label"),
                "acceptable": label.get("acceptable"),
                "uncertain": label.get("uncertain"),
                "type": label.get("type"),
                "model_choice": choice,
                "schema_ok": call.schema_ok,
                "truncated": call.truncated,
                "classification": classification,
                "elapsed_seconds": round(call.elapsed_seconds, 3),
                "window_sizes": {
                    lbl: {
                        "n_chunks": case.windows[lbl]["n_chunks"],
                        "chars": case.windows[lbl]["chars"],
                        "approx_tokens": case.windows[lbl]["approx_tokens"],
                        "boundary_reduced": case.windows[lbl]["boundary_reduced"],
                        "section_crossings": case.windows[lbl]["section_crossings"],
                        "page_crossings": case.windows[lbl]["page_crossings"],
                    }
                    for lbl in "ABCD"
                },
            }
            records.append(rec)
            review.extend(_review_block(a, case, label, choice, classification, split))

            if old_controller and split == "dev":
                rec["old_controller"] = _old_gate(base, case, mode=mode, trace=trace)

    metrics = _context_metrics(records)
    agg_stats = {}
    for lbl in "ABCD":
        ch = agg[lbl]["chars"]
        tk = agg[lbl]["tokens"]
        agg_stats[lbl] = {
            "chars": {"min": min(ch), "median": int(statistics.median(ch)), "max": max(ch)},
            "approx_tokens": {"min": min(tk), "median": int(statistics.median(tk)), "max": max(tk)},
            "boundary_reduced_cases": boundary_reduced[lbl],
        }
    return {"records": records, "metrics": metrics, "window_size_stats": agg_stats}, review


def _classify_choice(choice, label) -> str:
    if choice is None:
        return "no_choice"
    human = label.get("label")
    acceptable = label.get("acceptable") or ([human] if human else [])
    if human is None:
        return "unlabeled"
    if choice in acceptable:
        return "acceptable"
    if ordinal(choice) == ordinal(human):
        return "exact"
    return "under_expanded" if ordinal(choice) < ordinal(human) else "over_expanded"


def _context_metrics(records) -> dict:
    def metrics_for(rows):
        n = len(rows)
        if not n:
            return {}
        valid = [r for r in rows if r["model_choice"] is not None]
        exact = sum(1 for r in valid if ordinal(r["model_choice"]) == ordinal(r["human_label"]))
        acceptable = sum(1 for r in valid if r["classification"] in ("acceptable", "exact"))
        suff = sum(1 for r in valid if ordinal(r["model_choice"]) >= ordinal(r["human_label"]))
        under = [
            ordinal(r["human_label"]) - ordinal(r["model_choice"])
            for r in valid
            if ordinal(r["model_choice"]) < ordinal(r["human_label"])
        ]
        over = [
            ordinal(r["model_choice"]) - ordinal(r["human_label"])
            for r in valid
            if ordinal(r["model_choice"]) > ordinal(r["human_label"]) and r["classification"] != "acceptable"
        ]
        from collections import Counter

        return {
            "n": n,
            "valid_choices": len(valid),
            "schema_compliance": round(sum(1 for r in rows if r["schema_ok"]) / n, 3),
            "truncations": sum(1 for r in rows if r["truncated"]),
            "exact_match_rate": round(exact / len(valid), 3) if valid else 0.0,
            "acceptable_rate": round(acceptable / len(valid), 3) if valid else 0.0,
            "sufficient_or_larger_rate": round(suff / len(valid), 3) if valid else 0.0,
            "under_expansion_rate": round(len(under) / len(valid), 3) if valid else 0.0,
            "mean_under_expansion_distance": round(statistics.mean(under), 3) if under else 0.0,
            "mean_over_expansion_distance": round(statistics.mean(over), 3) if over else 0.0,
            "choice_distribution": dict(Counter(r["model_choice"] for r in valid)),
            "latency_mean_s": round(statistics.mean([r["elapsed_seconds"] for r in rows]), 3),
        }

    dev = [r for r in records if r["split"] == "dev"]
    held = [r for r in records if r["split"] == "held_out"]
    specimen = next((r for r in records if r["anchor_chunk_id"] == 34974), None)
    return {
        "dev": metrics_for(dev),
        "held_out": metrics_for(held),
        "all": metrics_for(records),
        "specimen_c34974": {
            "human_label": specimen["human_label"],
            "model_choice": specimen["model_choice"],
            "classification": specimen["classification"],
        }
        if specimen
        else None,
    }


def _review_block(a, case, label, choice, classification, split) -> list[str]:
    rendered = cw.render_all_windows(case)
    lines = [f"### {a['case_id']}", ""]
    lines.append(
        f"Paper {a['paper_id']} · central chunk {a['anchor_chunk_id']} · split={split} · "
        f"baseline_discarded={a['baseline_discarded']}"
    )
    lines.append(
        f"Human label: **{label.get('label')}** (acceptable {label.get('acceptable')}, "
        f"type={label.get('type')}, uncertain={label.get('uncertain')})"
    )
    lines.append(f"Qwen choice: **{choice}** → {classification}")
    lines.append("")
    for lbl in "ABCD":
        w = case.windows[lbl]
        note = " · ".join(
            filter(
                None,
                [
                    f"chunks={w['n_chunks']}",
                    f"chars={w['chars']}",
                    f"~tok={w['approx_tokens']}",
                    "boundary_reduced" if w["boundary_reduced"] else "",
                    f"section_crossings={w['section_crossings']}" if w["section_crossings"] else "",
                    f"page_crossings={w['page_crossings']}" if w["page_crossings"] else "",
                ],
            )
        )
        lines.append(f"#### {lbl} — {note}")
        lines.append("```")
        lines.append(rendered[lbl])
        lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def _old_gate(base, case, *, mode, trace):
    """Optional descriptive replay of the old 5-way accept/before/after/both/discard gate on the central chunk."""
    from experiments.ask_cli_revised.calibration.structured_output import run_schema_call

    schema = {
        "type": "object",
        "required": ["action"],
        "additionalProperties": False,
        "properties": {"action": {"type": "string", "enum": ["accept", "before", "after", "both", "discard"]}},
    }
    central_text = case.windows["A"]["chunks"][0]["text"]
    prompt = (
        "You are reading a passage from a scholarly paper. Choose what to do next: accept (already a "
        "complete claim), before/after/both (needs neighboring context), or discard (unlikely to help).\n\n"
        'Return only JSON: {"action":"accept|before|after|both|discard"}\n\n'
        f"Current text:\n{central_text}"
    )
    call = run_schema_call(base, prompt, output_cap=32, json_schema=schema, mode=mode)
    action = call.parsed.get("action") if isinstance(call.parsed, dict) else None
    return {"action": action, "schema_ok": call.schema_ok, "truncated": call.truncated}


def _final_report(mode, smoke, decomposition_out, context_out, thresholds) -> list[str]:
    L = ["# Run 0.5 — component calibration report", ""]
    L.append(f"Frozen question hash: `{question_hash()}`")
    L.append("")
    L.append("## Structured output")
    for s in smoke:
        L.append(f"- mode `{s.mode}`: enforced={s.enforced}")
    L.append(f"- **chosen mode: `{mode}`**")
    L.append("")
    L.append("## A. Decomposition (designs A/B/C)")
    L.append(
        f"Design-C audit gates (empirical, from dev design-A): global≥{thresholds.global_gate}, coverage≥{thresholds.coverage_gate}"
    )
    L.append("")
    for name in ("A", "B", "C"):
        cases = decomposition_out["designs"][name]
        L.append(f"### Design {name}")
        for cid, e in cases.items():
            L.append(
                f"- **{cid}** ({e['split']}): items={len(e['items'])} source_loss={e['source_loss']} "
                f"global_recon={e['global_reconstruction']} weakest_cov={e['weakest_coverage']} "
                f"| calls={e['calls_summary']['calls']} schema_fail={e['calls_summary']['schema_failures']} "
                f"trunc={e['calls_summary']['truncations']} fb={e['calls_summary']['fallbacks']} "
                f"lat={e['calls_summary']['latency_total_s']}s"
            )
            if name == "C" and e.get("repaired"):
                L.append(
                    f"    - repaired: {[d['item_id'] for d in e['repair_details']]}; "
                    f"initial_global={e.get('initial_global_reconstruction')} -> final={e['global_reconstruction']}; "
                    f"fell_back={e['fell_back_units']}"
                )
            if cid == "q_aib":
                hits = e.get("aib_target_hits", {})
                missed = [k for k, v in hits.items() if not v]
                L.append(f"    - AIB targets retained: {sum(hits.values())}/{len(hits)}; missed: {missed}")
                L.append(f"    - invention flags: {e.get('invention_flags')}")
        L.append("")
    L.append("## B. Minimum-sufficient-context")
    m = context_out["metrics"]
    for split in ("dev", "held_out", "all"):
        d = m.get(split, {})
        if not d:
            continue
        L.append(f"### {split}")
        L.append(
            f"- n={d['n']} valid_choices={d['valid_choices']} schema_compliance={d['schema_compliance']} truncations={d['truncations']}"
        )
        L.append(
            f"- exact_match={d['exact_match_rate']} acceptable={d['acceptable_rate']} sufficient_or_larger={d['sufficient_or_larger_rate']}"
        )
        L.append(
            f"- under_expansion_rate={d['under_expansion_rate']} mean_under_dist={d['mean_under_expansion_distance']} mean_over_dist={d['mean_over_expansion_distance']}"
        )
        L.append(f"- choice_distribution={d['choice_distribution']} latency_mean={d['latency_mean_s']}s")
        L.append("")
    L.append(f"Specimen c34974 (AIB abstract): {m.get('specimen_c34974')}")
    L.append("")
    L.append("## Window-size statistics (A/B/C/D)")
    for lbl, st in context_out["window_size_stats"].items():
        L.append(
            f"- {lbl}: chars {st['chars']} · ~tokens {st['approx_tokens']} · boundary_reduced_cases={st['boundary_reduced_cases']}"
        )
    L.append("")
    return L


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", required=True, help="path to a COPY of library.sqlite")
    p.add_argument("--out", required=True, help="run output directory")
    p.add_argument(
        "--old-controller", action="store_true", help="also replay the old 5-way gate on dev cases (descriptive)"
    )
    args = p.parse_args(argv)
    return run(args.db, args.out, old_controller=args.old_controller)


if __name__ == "__main__":
    raise SystemExit(main())
