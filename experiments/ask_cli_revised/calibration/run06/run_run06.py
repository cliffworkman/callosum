"""Run 0.6 orchestrator (replay/upstream-only; no downstream Ask stages, no Gemini, no 3B).

    python -m experiments.ask_cli_revised.calibration.run06.run_run06 --db <library-copy.sqlite> --out <dir>

Order: build runtime (STOP if Qwen unprovisioned) -> structured-output smoke test (STOP if unenforceable)
-> per question: 3 Qwen candidates + source baseline -> audit -> select -> <=1 bounded repair if flagged ->
re-select -> FREEZE -> post-hoc target/invention audit -> walk the 3 rich frozen decompositions through
discovery/within-paper-retrieval/the FROZEN context controller -> assert freeze hashes unchanged -> lineage
+ reports. STOP. Never invokes evidence selection, claim formation, verification, coverage, recovery, or
terminal synthesis.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ask_cli_revised.calibration.audit import AuditThresholds  # noqa: E402
from experiments.ask_cli_revised.calibration.run06 import candidates as cand  # noqa: E402
from experiments.ask_cli_revised.calibration.run06 import freeze as frz  # noqa: E402
from experiments.ask_cli_revised.calibration.run06 import lineage as lin  # noqa: E402
from experiments.ask_cli_revised.calibration.run06 import report06, selection  # noqa: E402
from experiments.ask_cli_revised.calibration.run06 import walk as walk_mod  # noqa: E402
from experiments.ask_cli_revised.calibration.run06.audit_ext import audit_candidate  # noqa: E402
from experiments.ask_cli_revised.calibration.run06.dataset06 import (  # noqa: E402
    DEPRESSION_QUESTION,
    RICH_CASE_IDS,
    decomposition_cases_v06,
    frozen_manifest,
)
from experiments.ask_cli_revised.calibration.run06.repair import repair_candidate  # noqa: E402
from experiments.ask_cli_revised.calibration.run_calibration import (  # noqa: E402
    _aib_target_hits,
    _derive_thresholds,
    _design_calls_summary,
    _invention_flags,
    _source_loss,
)
from experiments.ask_cli_revised.calibration.structured_output import choose_enforcing_mode  # noqa: E402
from experiments.ask_cli_revised.runtime import QwenUnavailableError, build_runtime  # noqa: E402
from experiments.ask_cli_revised.trace import TraceWriter  # noqa: E402

# Source units whose open-endedness must be confirmed (not instantiated) in review. Keyed by question text.
_OPEN_ENDED_SUBSTR = {
    DEPRESSION_QUESTION: "and other relevant",
    # built-env "and more" rides its last comma item; confirmed in review from the lineage rewrite.
}


def _attach_audit(candidate: dict, question: str, embed, thresholds: AuditThresholds) -> dict:
    candidate = dict(candidate)
    candidate["audit"] = audit_candidate(question, candidate["units"], candidate["items"], embed, thresholds=thresholds)
    candidate["calls_summary"] = _design_calls_summary(candidate)
    return candidate


def _open_ended_units(question: str, items: list[dict]) -> list[dict]:
    marker = _OPEN_ENDED_SUBSTR.get(question)
    out = []
    for i in items:
        if (marker and marker in i["source_text"]) or "and more" in i["source_text"]:
            out.append({"source_unit_id": i["source_unit_id"], "source_text": i["source_text"], "rewrite": i["text"]})
    return out


def run(db_path: str, out_dir: str) -> int:
    trace = TraceWriter(out_dir)
    print(f"[run0.6] out: {out_dir}")
    trace.write_json("00_frozen.json", {"db_path": str(Path(db_path).resolve()), **frozen_manifest()})

    try:
        rt = build_runtime(db_path, want_gemini=False, want_verifier=False)
    except QwenUnavailableError as exc:
        trace.write_json("BLOCKED.json", {"blocked": True, "reason": str(exc)})
        print(f"[run0.6] BLOCKED: {exc}")
        return 2

    try:
        base = rt.qwen_config
        embed = rt.model

        print("[run0.6] structured-output smoke test")
        mode, smoke = choose_enforcing_mode(base)
        smoke_payload = [{"mode": s.mode, "enforced": s.enforced, "calls": list(s.calls)} for s in smoke]
        trace.write_json("01_structured_output_smoke.json", {"chosen_mode": mode, "results": smoke_payload})
        if mode is None:
            trace.write_json("STOPPED.json", {"stopped": True, "reason": "structured output not enforced (Juno/ollama)"})
            print("[run0.6] STOPPED: structured output not enforced. See 01_structured_output_smoke.json")
            return 3
        print(f"[run0.6] structured output enforced via mode={mode}")

        cases = decomposition_cases_v06()

        # ---- run raw candidates (no audit yet; thresholds need dev RELATION audits) ----
        raw = {}
        for c in cases:
            print(f"[run0.6] candidates: {c['case_id']}")
            raw[c["case_id"]] = {
                "minimal": cand.run_candidate(base, c["text"], style="minimal", mode=mode),
                "relation": cand.run_candidate(base, c["text"], style="relation", mode=mode),
                "multi": cand.run_candidate(base, c["text"], style="multi", mode=mode),
                "baseline": cand.source_baseline(c["text"]),
            }

        # ---- derive empirical gates from dev RELATION candidates (measure-only audit) ----
        measure_only = AuditThresholds(global_gate=1.0, coverage_gate=1.0)
        dev = [c for c in cases if c["split"] == "dev"]
        dev_relation_audits = [
            audit_candidate(c["text"], raw[c["case_id"]]["relation"]["units"], raw[c["case_id"]]["relation"]["items"], embed, thresholds=measure_only)
            for c in dev
        ]
        thresholds = _derive_thresholds(dev_relation_audits)
        print(f"[run0.6] gates: global>={thresholds.global_gate} coverage_flag>={thresholds.coverage_gate}")

        questions_out: dict = {}
        frozen_by_case: dict = {}
        for c in cases:
            cid, question = c["case_id"], c["text"]
            qwen_styles = {
                style: _attach_audit(raw[cid][style], question, embed, thresholds) for style in cand.QWEN_STYLES
            }
            baseline = _attach_audit(raw[cid]["baseline"], question, embed, thresholds)

            decision = selection.select(list(qwen_styles.values()))
            repair_info = None
            reselection_reason = None
            if decision["selected"] == "baseline":
                chosen = baseline
                selected_label = "baseline"
            else:
                chosen = qwen_styles[decision["selected"]]
                rep = repair_candidate(base, question, chosen, mode=mode, thresholds=thresholds)
                repair_info = {"needed": rep["needed"], "diagnosis": rep["diagnosis"], "repair_details": rep["repair_details"]}
                if not rep["needed"]:
                    selected_label = chosen["style"]
                else:
                    repaired = _attach_audit(rep["candidate"], question, embed, thresholds)
                    reselect = selection.select([chosen, repaired])
                    reselection_reason = reselect["reason"]
                    if reselect["selected"] == "baseline":
                        chosen, selected_label = baseline, "baseline"
                    elif reselect["selected"] == repaired["style"]:
                        chosen, selected_label = repaired, repaired["style"]
                    else:
                        chosen, selected_label = chosen, chosen["style"]

            frozen = frz.freeze_decomposition(
                case_id=cid,
                question=question,
                selected=selected_label,
                items=chosen["items"],
                selection=decision,
                repair=repair_info,
            )
            frozen_by_case[cid] = frozen

            questions_out[cid] = {
                "case_id": cid,
                "split": c["split"],
                "source": c["source"],
                "rich": c["rich"],
                "question": question,
                "units": chosen["units"],
                "candidates": {**qwen_styles, "baseline": baseline},
                "selection": decision,
                "selected": selected_label,
                "selected_audit": chosen["audit"],
                "repair": repair_info,
                "reselection_reason": reselection_reason,
                "decomposition_hash": frozen["decomposition_hash"],
                "source_loss": _source_loss(chosen["units"], chosen["items"]),
                "invention_flags": _invention_flags(chosen["items"]),
                "open_ended_units": _open_ended_units(question, chosen["items"]),
            }
            if cid == "q_aib":
                questions_out[cid]["aib_target_hits"] = _aib_target_hits(chosen["items"])

        trace.write_json("02_candidates.json", _candidates_dump(questions_out))
        trace.write_json("03_selection.json", {cid: q["selection"] for cid, q in questions_out.items()})
        trace.write_json("04_frozen_decompositions.json", frozen_by_case)

        # ---- walk the rich frozen decompositions ----
        all_lineage = []
        walk_summary = {}
        walk_rows_all = []
        with rt.engine.connect() as conn:
            for cid in RICH_CASE_IDS:
                frozen = frozen_by_case[cid]
                frz.assert_unchanged(frozen, frozen["items"])
                print(f"[run0.6] walk: {cid} ({len(frozen['items'])} items)")
                walk_records = walk_mod.walk_decomposition(conn, rt=rt, base_config=base, frozen=frozen, mode=mode, trace=trace)
                frz.assert_unchanged(frozen, frozen["items"])
                for r in walk_records:
                    walk_rows_all.append(r)
                lineage = lin.build_lineage(frozen, walk_records, questions_out[cid]["selected_audit"])
                all_lineage.append(lineage)
                walk_summary[cid] = lin.aggregate_survival(lineage["units"])

        trace.write_jsonl("05_walk.jsonl", walk_rows_all)
        trace.write_jsonl("lineage.jsonl", [u for lg in all_lineage for u in lg["units"]])
        trace.write_json("lineage_graph.json", {"lineage": all_lineage, "survival": walk_summary})
        trace.write_report("run_0_6_request_lineage.md", lin.lineage_markdown(all_lineage))

        # ---- reports ----
        trace.write_report("run_0_6_decomposition_review.md", report06.decomposition_review_md(questions_out))
        trace.write_report(
            "RUN_0_6_REPORT.md",
            report06.run_report_md(
                mode=mode,
                smoke=smoke_payload,
                thresholds={"global_gate": thresholds.global_gate, "coverage_gate": thresholds.coverage_gate},
                questions_out=questions_out,
                walk_summary=walk_summary,
                frozen_hashes={cid: f["decomposition_hash"] for cid, f in frozen_by_case.items()},
            ),
        )
        trace.flush_qwen()
        print(f"[run0.6] done -> {out_dir}")
        return 0
    finally:
        rt.close()


def _candidates_dump(questions_out: dict) -> dict:
    out = {}
    for cid, q in questions_out.items():
        out[cid] = {
            "question": q["question"],
            "units": q["units"],
            "candidates": {
                style: {
                    "items": entry["items"],
                    "audit": entry["audit"],
                    "calls_summary": entry["calls_summary"],
                    "calls": entry["calls"],
                }
                for style, entry in q["candidates"].items()
            },
        }
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", required=True, help="path to a COPY of library.sqlite")
    p.add_argument("--out", required=True, help="run output directory")
    args = p.parse_args(argv)
    return run(args.db, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
