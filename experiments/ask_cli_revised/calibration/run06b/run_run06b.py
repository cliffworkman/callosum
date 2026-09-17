"""Run 0.6b orchestrator — frozen span -> P1 proposition screen -> P2 source-local claim -> UNCHANGED
verifier -> diagnostic review. STOP.

    python -m experiments.ask_cli_revised.calibration.run06b.run_run06b --out <dir>

Never runs responsiveness, obligation mapping, retrieval, coverage, recovery, terminal synthesis, Run
0.7, or production integration. Fails closed (BLOCKED/STOPPED) if Qwen/Juno is unavailable or structured
output is not enforced, and STOPs before verifier replay if the RTPJ wiring validation does not reproduce
the frozen scores within the predeclared tolerance.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ask_cli_revised.calibration.run06b import dataset as ds  # noqa: E402
from experiments.ask_cli_revised.calibration.run06b import qwen_primitives as qp  # noqa: E402
from experiments.ask_cli_revised.calibration.run06b import review as rv  # noqa: E402
from experiments.ask_cli_revised.calibration.run06b import verifier_replay as vr  # noqa: E402
from experiments.ask_cli_revised.calibration.run06b.inputs import (  # noqa: E402
    BASELINE_RUN_DIR,
    baseline_input_receipt,
    identity_receipt,
)
from experiments.ask_cli_revised.calibration.structured_output import choose_enforcing_mode  # noqa: E402
from experiments.ask_cli_revised.runtime import QwenUnavailableError, build_runtime  # noqa: E402
from experiments.ask_cli_revised.trace import TraceWriter  # noqa: E402

RTPJ_CHUNK_ID = 26831


def _call_record(primitive: str, unit: dict, prompt: str, call, parsed_value, prompt_version: str) -> dict:
    return {
        "primitive": primitive,
        "prompt_version": prompt_version,
        "dataset_instance_id": unit["dataset_instance_id"],
        "duplicate_group_id": unit["duplicate_group_id"],
        "stratum": unit["stratum"],
        "containing_chunk_id": unit["containing_chunk_id"],
        "local_span_id": unit["local_span_id"],
        "paper_id": unit["paper_id"],
        "evidence_role": unit["evidence_role"],
        "exact_span": unit["exact_span_text"],
        "context_text": unit["context_text"],
        "prompt_text": prompt,
        "raw_output": call.raw_text,
        "parsed": call.parsed,
        "parsed_value": parsed_value,
        "provider_ok": call.provider_ok,
        "schema_ok": call.schema_ok,
        "truncated": call.truncated,
        "failure_reason": call.failure_reason,
        "elapsed_seconds": round(call.elapsed_seconds, 3),
        "output_cap": call.output_cap,
        "mode": call.mode,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def run(out_dir: str) -> int:
    trace = TraceWriter(out_dir)
    print(f"[run0.6b] out: {out_dir}")

    # ---- Phase 0: freeze inputs + dataset (BEFORE any inference) ----
    input_receipt = baseline_input_receipt(BASELINE_RUN_DIR)
    payload = ds.build_dataset(BASELINE_RUN_DIR)
    units = payload["units"]
    dev_frozen = rv.freeze_dev_annotations(units)
    trace.write_json("01_frozen_dataset.json", payload)
    reps = [u for u in units if u["is_group_representative"]]

    # ---- throwaway replay DB (schema only for now) + runtime (STOP if Qwen unavailable) ----
    tmp = tempfile.mkdtemp(prefix="run06b-replay-")
    replay_db = str(Path(tmp) / "replay.sqlite")
    vr.build_replay_schema(replay_db)
    try:
        rt = build_runtime(replay_db, want_gemini=False, want_verifier=True)
    except QwenUnavailableError as exc:
        trace.write_json(
            "00_inputs.json",
            {
                "baseline_input_receipt": input_receipt,
                "dataset_hash": payload["dataset_hash"],
                "dev_annotation_freeze": dev_frozen,
            },
        )
        trace.write_json("BLOCKED.json", {"blocked": True, "reason": str(exc)})
        print(f"[run0.6b] BLOCKED: {exc}")
        return 2

    try:
        base = rt.qwen_config
        trace.write_json(
            "00_inputs.json",
            {
                "created": datetime.now(timezone.utc).isoformat(),
                "baseline_input_receipt": input_receipt,
                "dataset_hash": payload["dataset_hash"],
                "dataset_counts": payload["counts"],
                "identity_receipt": identity_receipt(base),
                "dev_annotation_freeze": dev_frozen,
                "prompt_versions": {"p1": qp.P1_PROMPT_VERSION, "p2": qp.P2_PROMPT_VERSION},
                "no_retrieval_no_decomposition_no_context_growth": True,
            },
        )

        # ---- Phase 1: structured-output smoke (mode + claim schema) ----
        print("[run0.6b] structured-output smoke")
        mode, smoke = choose_enforcing_mode(base)
        claim_schema_name, claim_smoke = (None, [])
        if mode is not None:
            claim_schema_name, claim_smoke = qp.choose_claim_schema(base, mode)
        trace.write_json(
            "02_structured_output_smoke.json",
            {
                "chosen_mode": mode,
                "results": [{"mode": s.mode, "enforced": s.enforced, "calls": list(s.calls)} for s in smoke],
                "claim_schema_chosen": claim_schema_name or None,
                "claim_schema_probes": claim_smoke,
            },
        )
        if mode is None:
            trace.write_json("STOPPED.json", {"stopped": True, "reason": "structured output not enforced"})
            print("[run0.6b] STOPPED: structured output not enforced")
            return 3
        if not claim_schema_name:
            trace.write_json(
                "STOPPED.json",
                {"stopped": True, "reason": "no claim schema enforced (string|null and gated both failed)"},
            )
            print("[run0.6b] STOPPED: claim schema not enforceable")
            return 3
        print(f"[run0.6b] enforced mode={mode} claim_schema={claim_schema_name}")

        # ---- Phase 2: P1 proposition screen (once per representative, fanned out) ----
        print(f"[run0.6b] P1 proposition screen over {len(reps)} representatives")
        p1_calls: list[dict] = []
        p1_answer_by_group: dict[str, str | None] = {}
        for i, u in enumerate(reps, 1):
            prompt = qp.build_p1_prompt(
                span_text=u["exact_span_text"], context_text=u["context_text"], context_available=u["context_available"]
            )
            call, answer = qp.run_proposition_screen(
                base,
                span_text=u["exact_span_text"],
                context_text=u["context_text"],
                context_available=u["context_available"],
                mode=mode,
                prompt=prompt,
            )
            p1_answer_by_group[u["duplicate_group_id"]] = answer
            p1_calls.append(_call_record("proposition_screen", u, prompt, call, answer, qp.P1_PROMPT_VERSION))
            if i % 20 == 0:
                print(f"  P1 {i}/{len(reps)}")
        trace.write_jsonl("03_proposition_calls.jsonl", p1_calls)
        p1_by_id = {
            u["dataset_instance_id"]: {
                "answer": p1_answer_by_group[u["duplicate_group_id"]],
                "schema_ok": None,
                "truncated": None,
            }
            for u in units
        }
        for rec in p1_calls:  # enrich the representative rows with schema/truncation detail
            p1_by_id[rec["dataset_instance_id"]].update({"schema_ok": rec["schema_ok"], "truncated": rec["truncated"]})
        trace.write_json("04_proposition_results.json", _p1_results(units, p1_by_id, p1_calls))

        # ---- Phase 3: P2 claim formation (only where P1 == YES) ----
        yes_reps = [u for u in reps if p1_answer_by_group.get(u["duplicate_group_id"]) == "YES"]
        print(f"[run0.6b] P2 claim formation over {len(yes_reps)} YES representatives")
        p2_calls: list[dict] = []
        p2_claim_by_group: dict[str, str | None] = {}
        for i, u in enumerate(yes_reps, 1):
            prompt = qp.build_p2_prompt(
                span_text=u["exact_span_text"], context_text=u["context_text"], context_available=u["context_available"]
            )
            call, claim = qp.run_claim_form(
                base,
                span_text=u["exact_span_text"],
                context_text=u["context_text"],
                context_available=u["context_available"],
                mode=mode,
                schema_name=claim_schema_name,
                prompt=prompt,
            )
            p2_claim_by_group[u["duplicate_group_id"]] = claim
            p2_calls.append(_call_record("claim_form", u, prompt, call, claim, qp.P2_PROMPT_VERSION))
            if i % 20 == 0:
                print(f"  P2 {i}/{len(yes_reps)}")
        trace.write_jsonl("05_claim_calls.jsonl", p2_calls)
        trace.write_json("06_claim_results.json", _p2_results(units, p1_answer_by_group, p2_claim_by_group, p2_calls))

        # ---- Phase 4: verifier replay (P1/P2 artifacts already persisted above) ----
        chunk_records = [
            {
                "chunk_id": u["containing_chunk_id"],
                "paper_id": u["paper_id"],
                "text": u["context_text"] or u["exact_span_text"],
            }
            for u in units
            if u["containing_chunk_id"] is not None
        ]
        seeds = vr.seed_chunks(rt.engine, chunk_records)

        wiring, verifier_by_id = None, {}
        rtpj = next((u for u in units if u["containing_chunk_id"] == RTPJ_CHUNK_ID and u.get("old_verifier")), None)
        with rt.engine.begin() as conn:
            if rtpj is not None:
                fr = rtpj["old_verifier"]
                wiring = vr.wiring_validation(
                    rt.verifier,
                    conn,
                    old_claim=rtpj["old_form_claim_text"] or rtpj["exact_span_text"],
                    old_quote=rtpj["exact_span_text"],
                    seed=seeds[RTPJ_CHUNK_ID],
                    frozen={
                        "retrieval": fr["retrieval"],
                        "quote": fr["quote"],
                        "support": fr["support"],
                        "contradiction": fr["contradiction"],
                        "status": fr["status"],
                    },
                )
                trace.write_json("wiring_validation.json", wiring)
                if not wiring["passed"]:
                    trace.write_json(
                        "STOPPED.json", {"stopped": True, "reason": "RTPJ wiring validation failed", "wiring": wiring}
                    )
                    print("[run0.6b] STOPPED: RTPJ wiring validation failed (P1/P2 artifacts preserved)")
                    return 4
                print("[run0.6b] RTPJ wiring validation PASSED")

            for u in yes_reps:
                claim = p2_claim_by_group.get(u["duplicate_group_id"])
                if not claim or u["containing_chunk_id"] is None:
                    continue
                if not vr.containment_ok(u["exact_span_text"], seeds[u["containing_chunk_id"]]["text"]):
                    verifier_by_id[u["dataset_instance_id"]] = {"skipped": "FROZEN_EXTRACTION_MISMATCH"}
                    continue
                verifier_by_id[u["duplicate_group_id"]] = vr.replay_one(
                    rt.verifier, conn, claim=claim, span_text=u["exact_span_text"], seed=seeds[u["containing_chunk_id"]]
                )

        # fan verifier results out to every unit in a YES group with a non-null claim
        verifier_units: dict[str, dict] = {}
        for u in units:
            gid = u["duplicate_group_id"]
            if (
                gid in verifier_by_id
                and isinstance(verifier_by_id[gid], dict)
                and "retrieval_confidence" in verifier_by_id[gid]
            ):
                verifier_units[u["dataset_instance_id"]] = verifier_by_id[gid]
        trace.write_json("07_verifier_results.json", _verifier_results(units, verifier_units, wiring))

        # ---- Phase 5: review + old-vs-new ----
        rv.assert_dev_annotations_unchanged(dev_frozen, units)
        trace.write_json(
            "08_old_vs_new.json", _old_vs_new(units, p1_answer_by_group, p2_claim_by_group, verifier_units)
        )
        trace.write_json(
            "09_review_annotations.json",
            {
                "dev_prefrozen": dev_frozen,
                "note": "DEV = pre-registered before inference; EVAL has no pre-registered labels (post-hoc qualitative only).",
            },
        )
        trace.write_report("run_0_6b_proposition_screen_review.md", rv.proposition_review_md(units, p1_by_id))
        yes_units = [u for u in units if p1_answer_by_group.get(u["duplicate_group_id"]) == "YES"]
        p2_full = {
            u["dataset_instance_id"]: {"claim": p2_claim_by_group.get(u["duplicate_group_id"])} for u in yes_units
        }
        trace.write_report("run_0_6b_claim_review.md", rv.claim_review_md(yes_units, p2_full, verifier_units))
        trace.write_report(
            "run_0_6b_regression_specimens.md",
            _specimen_md(units, p1_answer_by_group, p2_claim_by_group, verifier_units, payload),
        )
        trace.write_report(
            "RUN_0_6B_REPORT.md",
            _report_md(
                out_dir,
                payload,
                mode,
                claim_schema_name,
                identity_receipt(base),
                p1_answer_by_group,
                p2_claim_by_group,
                verifier_units,
                wiring,
                reps,
                p1_calls,
                p2_calls,
            ),
        )
        print(f"[run0.6b] done -> {out_dir}")
        return 0
    finally:
        rt.close()


# ---- result/report assembly -------------------------------------------------------------------------
def _dist(units, key, pred=None):
    return dict(Counter(u[key] for u in units if (pred is None or pred(u))))


def _p1_results(units, p1_by_id, p1_calls) -> dict:
    def counts(stratum):
        su = [u for u in units if u["stratum"] == stratum]
        ans = Counter(p1_by_id[u["dataset_instance_id"]]["answer"] for u in su)
        by_role = {}
        for role in sorted({str(u["evidence_role"]) for u in su}):
            ru = [u for u in su if str(u["evidence_role"]) == role]
            by_role[role] = dict(Counter(p1_by_id[u["dataset_instance_id"]]["answer"] for u in ru))
        return {"total": len(su), "answers": dict(ans), "by_evidence_role": by_role}

    return {
        "calls": len(p1_calls),
        "schema_success": sum(1 for c in p1_calls if c["schema_ok"]),
        "truncations": sum(1 for c in p1_calls if c["truncated"]),
        "unparsed_answer": sum(1 for c in p1_calls if c["parsed_value"] is None),
        "stratum_1": counts("select_evidence_span"),
        "stratum_2": counts("pre_selection_chunk"),
        "latency_seconds": round(sum(c["elapsed_seconds"] for c in p1_calls), 2),
    }


def _p2_results(units, p1_answer_by_group, p2_claim_by_group, p2_calls) -> dict:
    yes_units = [u for u in units if p1_answer_by_group.get(u["duplicate_group_id"]) == "YES"]
    claims = [p2_claim_by_group.get(u["duplicate_group_id"]) for u in yes_units]
    non_null = [c for c in claims if c]

    def by_stratum(stratum):
        su = [u for u in yes_units if u["stratum"] == stratum]
        return {"yes_units": len(su), "non_null": sum(1 for u in su if p2_claim_by_group.get(u["duplicate_group_id"]))}

    return {
        "calls": len(p2_calls),
        "schema_success": sum(1 for c in p2_calls if c["schema_ok"]),
        "truncations": sum(1 for c in p2_calls if c["truncated"]),
        "yes_units_total": len(yes_units),
        "non_null_claims_units": len(non_null),
        "null_claims_units": len(yes_units) - len(non_null),
        "claim_len_chars": {
            "min": min((len(c) for c in non_null), default=0),
            "max": max((len(c) for c in non_null), default=0),
        },
        "stratum_1": by_stratum("select_evidence_span"),
        "stratum_2": by_stratum("pre_selection_chunk"),
        "latency_seconds": round(sum(c["elapsed_seconds"] for c in p2_calls), 2),
    }


def _verifier_results(units, verifier_units, wiring) -> dict:
    rows = []
    for u in units:
        v = verifier_units.get(u["dataset_instance_id"])
        if v is None:
            continue
        rows.append(
            {
                "dataset_instance_id": u["dataset_instance_id"],
                "stratum": u["stratum"],
                "containing_chunk_id": u["containing_chunk_id"],
                "evidence_role": u["evidence_role"],
                "regression_specimen": u.get("regression_specimen"),
                **v,
            }
        )
    return {
        "wiring_validation": wiring,
        "replayed": len(rows),
        "status_distribution": dict(Counter(r["status"] for r in rows)),
        "retrieval_below_threshold": sum(1 for r in rows if r["retrieval_confidence"] < 0.7),
        "quote_below_1": sum(1 for r in rows if r["quote_confidence"] < 1.0),
        "support_below_threshold": sum(1 for r in rows if r["support_confidence"] < 0.55),
        "contradiction_at_or_above_threshold": sum(1 for r in rows if (r["contradiction_confidence"] or 0.0) >= 0.55),
        "rows": rows,
    }


def _old_vs_new(units, p1_answer_by_group, p2_claim_by_group, verifier_units) -> dict:
    rows = []
    for u in units:
        gid = u["duplicate_group_id"]
        v = verifier_units.get(u["dataset_instance_id"])
        rows.append(
            {
                "dataset_instance_id": u["dataset_instance_id"],
                "stratum": u["stratum"],
                "containing_chunk_id": u["containing_chunk_id"],
                "local_span_id": u["local_span_id"],
                "evidence_role": u["evidence_role"],
                "regression_specimen": u.get("regression_specimen"),
                "old_select_evidence_status": u["old_select_evidence_status"],
                "old_model_selected": u.get("old_model_selected"),
                "old_effective_selected": u.get("old_effective_selected"),
                "old_fallback_used": u.get("old_fallback_used"),
                "old_call_failure_reason": u.get("old_call_failure_reason"),
                "old_form_claim_status": u.get("old_form_claim_status"),
                "new_p1_answer": p1_answer_by_group.get(gid),
                "new_p2_claim": p2_claim_by_group.get(gid),
                "new_verifier_status": v["status"] if v else None,
            }
        )
    return {"rows": rows}


def _specimen_md(units, p1a, p2c, ver, payload) -> list[str]:
    lines = [
        "# Run 0.6b — Named regression specimens",
        "",
        "Side-by-side old-vs-new for every named specimen present in the frozen dataset.",
        "",
    ]
    specimens = sorted({u["regression_specimen"] for u in units if u.get("regression_specimen")})
    for spec in specimens:
        lines += [f"## {spec}", ""]
        for u in [x for x in units if x.get("regression_specimen") == spec]:
            gid = u["duplicate_group_id"]
            v = ver.get(u["dataset_instance_id"])
            lines += [
                f"- **{u['dataset_instance_id']}** chunk {u['containing_chunk_id']} span {u['local_span_id']} role={u['evidence_role']} split={u['split']}",
                f"  - span: {rv._trunc(u['exact_span_text'], 180)}",
                f"  - OLD: status={u['old_select_evidence_status']} model_selected={u.get('old_model_selected')} effective={u.get('old_effective_selected')} fallback={u.get('old_fallback_used')} failure={u.get('old_call_failure_reason')} form_claim={u.get('old_form_claim_status')}",
                f"  - NEW: P1={p1a.get(gid)} claim={rv._trunc(str(p2c.get(gid)), 160)} verifier={(v['status'] if v else None)}"
                + (f" (retrieval={v['retrieval_confidence']:.4f} support={v['support_confidence']:.4f})" if v else ""),
                f"  - model-authored annotation: {(rv.dev_proposition_annotation(u) or {}).get('label', '(none/EVAL)')}",
                "",
            ]
    lines += ["## Requested specimens ABSENT from the frozen dataset", ""]
    for a in payload["absent_specimens"]:
        lines.append(f"- {a}: NOT PRESENT IN FROZEN DATASET")
    return lines


def _report_md(
    out_dir, payload, mode, claim_schema, identity, p1a, p2c, ver, wiring, reps, p1_calls, p2_calls
) -> list[str]:
    c = payload["counts"]
    p1_yes = sum(1 for u in payload["units"] if p1a.get(u["duplicate_group_id"]) == "YES")
    p1_no = sum(1 for u in payload["units"] if p1a.get(u["duplicate_group_id"]) == "NO")
    ver_rows = [ver[k] for k in ver]
    status_dist = dict(Counter(r["status"] for r in ver_rows))
    return [
        "# RUN 0.6b REPORT — frozen evidence-screen + source-local claim-formation calibration",
        "",
        "Bounded downstream-component calibration. Frozen span -> P1 proposition screen -> P2 source-local "
        "claim (YES only) -> UNCHANGED verifier (diagnostic) -> review. No responsiveness, obligation "
        "mapping, retrieval, coverage, recovery, or terminal synthesis. Hand back to Cliff.",
        "",
        "## Setup",
        f"- run dir: `{out_dir}`",
        f"- baseline: `{payload['baseline_run_dir']}`",
        f"- dataset hash: `{payload['dataset_hash']}`",
        f"- units: {c['total_units']} ({c['stratum_1_spans']} Stratum-1 e# spans + {c['stratum_2_chunks']} Stratum-2 chunks)",
        f"- unique inference representatives: {c['unique_inference_representatives']} (byte-identical duplicates deduped for inference, fanned back out)",
        f"- DEV (named specimens) / EVAL: {c['dev_units']} / {c['eval_units']}",
        f"- frozen-extraction mismatches: {c['frozen_extraction_mismatch']}",
        f"- model identity: alias={identity.get('config_model_alias')} digest_ok={identity.get('digest_ok')} "
        f"revision={identity.get('descriptor_model_artifact_revision')} bytes={identity.get('descriptor_model_artifact_bytes')} "
        f"gpu_layers={(identity.get('descriptor_observed_execution') or {}).get('gpu_layers') if identity.get('descriptor_observed_execution') else '?'} "
        f"fingerprint={str(identity.get('stable_identity_fingerprint'))[:16]}",
        f"- structured output: mode={mode} claim_schema={claim_schema}",
        "- no retrieval / decomposition / context growth executed (frozen material only)",
        "",
        "## Proposition screen (P1) — strata reported SEPARATELY",
        f"- calls={len(p1_calls)} schema_success={sum(1 for x in p1_calls if x['schema_ok'])} truncations={sum(1 for x in p1_calls if x['truncated'])}",
        f"- fanned-out unit answers: YES={p1_yes} NO={p1_no}",
        f"- Stratum-1: {_answer_line(payload, p1a, 'select_evidence_span')}",
        f"- Stratum-2: {_answer_line(payload, p1a, 'pre_selection_chunk')}",
        "",
        "## Claim formation (P2)",
        f"- calls={len(p2_calls)} schema_success={sum(1 for x in p2_calls if x['schema_ok'])} truncations={sum(1 for x in p2_calls if x['truncated'])}",
        f"- non-null claims (units)={sum(1 for u in payload['units'] if p1a.get(u['duplicate_group_id']) == 'YES' and p2c.get(u['duplicate_group_id']))}",
        "",
        "## Verifier (UNCHANGED, diagnostic)",
        f"- RTPJ wiring validation: {'PASS' if (wiring and wiring['passed']) else ('N/A' if wiring is None else 'FAIL')}"
        + (
            f" (reproduced retrieval={wiring['reproduced']['retrieval_confidence']:.4f} support={wiring['reproduced']['support_confidence']:.4f} vs frozen {wiring['frozen']['retrieval']:.4f}/{wiring['frozen']['support']:.4f}, tol={wiring['abs_tol']})"
            if wiring
            else ""
        ),
        f"- replayed rows: {len(ver_rows)}  status distribution: {status_dist}",
        f"- weak/unverified rows retained (not dropped): {sum(1 for r in ver_rows if r['status'] != 'verified')}",
        "",
        "## Interpretation guardrails",
        "- retrieval failure != library absence; verifier support != user responsiveness; verifier failure "
        "!= the claim is false. Higher verified count is NOT the objective. UNKNOWN role is not debris.",
        "",
        "See run_0_6b_proposition_screen_review.md, run_0_6b_claim_review.md, and "
        "run_0_6b_regression_specimens.md for per-unit detail, and 00..09 JSON for the machine-readable trace.",
    ]


def _answer_line(payload, p1a, stratum) -> str:
    su = [u for u in payload["units"] if u["stratum"] == stratum]
    return str(dict(Counter(p1a.get(u["duplicate_group_id"]) for u in su)))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", help="run output directory (default: runs/run06b-<UTC>)")
    args = p.parse_args(argv)
    out = args.out or str(
        ROOT
        / "experiments"
        / "ask_cli_revised"
        / "calibration"
        / "runs"
        / f"run06b-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    )
    return run(out)


if __name__ == "__main__":
    raise SystemExit(main())
