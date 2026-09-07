"""CLI orchestrator: runs the frozen benchmark through the staged pipeline and writes the full trace.

    python -m experiments.ask_cli --db <copy.sqlite> --out experiments/ask_cli/runs/<ts> [--terminal both|qwen|gemini]

Intermediate stages are managed-local Qwen ONLY (no cloud, no fallback flags). Cloud (Gemini) is used only
for the terminal-synthesis fork. Requires a provisioned Qwen (`python tools/run_local_ai.py` +
CALLOSUM_APP_DATA_DIR); if unavailable the run is BLOCKED, never silently downgraded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ask_cli import coverage as coverage_mod  # noqa: E402
from experiments.ask_cli import discovery, retrieval, synthesis  # noqa: E402
from experiments.ask_cli.propositions import marshal_and_verify  # noqa: E402
from experiments.ask_cli.question import BENCHMARK_QUESTION, question_hash  # noqa: E402
from experiments.ask_cli.qwen import QwenTasks  # noqa: E402
from experiments.ask_cli.runtime import QwenUnavailableError, build_runtime  # noqa: E402
from experiments.ask_cli.trace import TraceWriter  # noqa: E402


def _git_sha() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(ROOT), timeout=10
        ).stdout.strip()[:40]
    except Exception:  # noqa: BLE001
        return "unknown"


def run(db_path: str, out_dir: str, terminal: str) -> int:
    trace = TraceWriter(out_dir)
    started = time.monotonic()
    print(f"[ask-cli] run dir: {out_dir}")

    try:
        rt = build_runtime(db_path, want_gemini=(terminal in {"both", "gemini"}))
    except QwenUnavailableError as exc:
        trace.write_json("00_question.json", {"question": BENCHMARK_QUESTION, "hash": question_hash()})
        trace.write_json("BLOCKED.json", {"blocked": True, "reason": str(exc)})
        print(f"[ask-cli] BLOCKED: {exc}")
        return 2

    qwen = QwenTasks(config=rt.qwen_config, trace=trace)
    all_records: list[dict] = []
    try:
        with rt.engine.connect() as conn:
            # Stage 0
            trace.write_json("00_question.json", {"question": BENCHMARK_QUESTION, "hash": question_hash()})
            stats = discovery.corpus_stats(conn, model=rt.model)

            # Stage 1 (Qwen)
            print("[ask-cli] stage 1: interpretation (Qwen)")
            subquestions, interp_fallback = qwen.interpret(BENCHMARK_QUESTION)
            trace.write_json(
                "01_decomposition.json", {"subquestions": subquestions, "qwen_fallback_used": interp_fallback}
            )

            # Stage 3 (disabled + logged)
            trace.write_json("04_graph_rescue.json", discovery.graph_rescue_stage(conn))

            axis_cache: dict = {}
            direct_papers, axis_noms, candidate_papers = [], [], []
            chunk_hits, context_growth, propositions, verifications = [], [], [], []

            for sq in subquestions:
                sid, sq_text, obligations = sq["subquestion_id"], sq["text"], sq.get("obligations", [])
                print(f"[ask-cli] {sid}: discovery + retrieval")
                # Stage 2
                noms, nom_log = discovery.nominate_papers(
                    conn, subquestion_text=sq_text, model=rt.model, vector_store=rt.vector_store, axis_cache=axis_cache
                )
                for row in nom_log:
                    (axis_noms if str(row.get("reason", "")).startswith("axis:") else direct_papers).append(
                        {**row, "subquestion_id": sid}
                    )
                reason_by_paper = {n.paper_id: n.reasons for n in noms}
                candidate_papers.append(
                    {
                        "subquestion_id": sid,
                        "papers": [{"paper_id": n.paper_id, "reasons": n.reasons, "score": n.best_score} for n in noms],
                    }
                )

                # Stage 4
                hits = retrieval.within_paper_retrieve(
                    conn,
                    subquestion_id=sid,
                    subquestion_text=sq_text,
                    paper_ids=[n.paper_id for n in noms],
                    model=rt.model,
                    vector_store=rt.vector_store,
                )
                for h in hits:
                    chunk_hits.append(
                        {
                            "subquestion_id": sid,
                            "chunk_id": h.chunk.chunk_id,
                            "paper_id": h.chunk.paper_id,
                            "score": h.score,
                            "section": h.section,
                            "chunk_type": h.chunk_type,
                            "evidence_role": h.evidence_role,
                        }
                    )

                # Stage 5 + 6 + 7 per hit
                for h in hits:
                    packet = retrieval.grow_context(conn, hit=h, gate=qwen.context_gate, subquestion_text=sq_text)
                    context_growth.append(
                        {
                            "subquestion_id": sid,
                            "retrieval_anchor_chunk_id": packet.retrieval_anchor_chunk_id,
                            "grown": packet.grown,
                            "packet_chunks": [c["chunk_id"] for c in packet.chunks],
                        }
                    )
                    recs = marshal_and_verify(
                        conn,
                        verifier=rt.verifier,
                        qwen=qwen,
                        packet=packet,
                        subquestion_text=sq_text,
                        obligations=obligations,
                        nomination_reason=reason_by_paper.get(h.chunk.paper_id, []),
                        origin="initial",
                        trace=trace,
                    )
                    all_records.extend(recs)
                    for r in recs:
                        propositions.append(
                            {
                                k: r[k]
                                for k in (
                                    "subquestion_id",
                                    "obligation_ids",
                                    "paper_id",
                                    "retrieval_anchor_chunk_id",
                                    "evidence_anchor_chunk_id",
                                    "proposition_text",
                                    "quote",
                                    "provenance",
                                )
                            }
                        )
                        verifications.append(
                            {
                                "subquestion_id": sid,
                                "evidence_anchor_chunk_id": r["evidence_anchor_chunk_id"],
                                "proposition_text": r["proposition_text"],
                                **r["verification"],
                            }
                        )

            # persist initial-pass artifacts
            trace.write_json("02_direct_papers.json", direct_papers)
            trace.write_json("03_axis_nominations.json", axis_noms)
            trace.write_json("05_candidate_papers.json", candidate_papers)
            trace.write_jsonl("06_chunk_retrieval.jsonl", chunk_hits)
            trace.write_jsonl("07_context_growth.jsonl", context_growth)
            trace.write_jsonl("09_propositions.jsonl", propositions)
            trace.write_jsonl("10_verification.jsonl", verifications)

            # Stage 8 + 9
            trace.write_json("08_evidence_packets.jsonl", context_growth)  # packets already captured
            audit = coverage_mod.audit_coverage(subquestions, all_records)
            trace.write_json("12_coverage_audit.json", audit)

            # Stage 10: ONE bounded gap-directed recovery pass
            print(f"[ask-cli] stage 10: gap recovery ({len(audit['gaps'])} gaps)")
            recovery_log = _recover(conn, rt, qwen, subquestions, audit["gaps"], all_records, axis_cache, trace)
            trace.write_json("13_gap_recovery.json", recovery_log)
            audit = coverage_mod.audit_coverage(subquestions, all_records)  # re-audit after recovery
            trace.write_json("12_coverage_audit.json", audit)

        # Stage 11: seal (verified only) + hash
        verified = [r for r in all_records if r["verification"]["status"] == "verified"]
        sealed = {"subquestions": subquestions, "verified_propositions": verified, "coverage": audit}
        sealed_bytes = json.dumps(sealed, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ledger_hash = hashlib.sha256(sealed_bytes).hexdigest()
        trace.write_json("11_verified_ledger.json", {**sealed, "sealed_hash": ledger_hash})
        print(f"[ask-cli] sealed ledger: {len(verified)} verified propositions (hash {ledger_hash[:12]})")

        # Stage 12: terminal fork (cloud terminal-only)
        if terminal in {"both", "qwen"}:
            print("[ask-cli] stage 12A: Qwen terminal synthesis")
            text, ok = synthesis.terminal_synthesis(rt.qwen_config, sealed)
            trace.write_report("14a_final_answer.qwen.md", [text])
        if terminal in {"both", "gemini"}:
            if rt.gemini_config is None:
                trace.write_report(
                    "14b_final_answer.gemini.md", ["[Gemini terminal synthesis skipped: no API key resolved.]"]
                )
            else:
                print("[ask-cli] stage 12B: Gemini terminal synthesis")
                text, ok = synthesis.terminal_synthesis(rt.gemini_config, sealed)
                trace.write_report("14b_final_answer.gemini.md", [text])

        trace.flush_qwen()
        trace.flush_events()
        trace.write_json(
            "15_run_manifest.json",
            {
                "created": datetime.now(timezone.utc).isoformat(),
                "question_hash": question_hash(),
                "db_path": str(Path(db_path).resolve()),
                "corpus_stats": stats,
                "git_sha": _git_sha(),
                "platform": platform.platform(),
                "verifier_thresholds": {"retrieval": 0.70, "quote": 1.0, "support": 0.55, "contradiction": 0.55},
                "caps": {
                    "paper_knn_top_k": discovery.PAPER_KNN_TOP_K,
                    "axis_top_k": discovery.AXIS_TOP_K,
                    "per_subq_paper_cap": discovery.PER_SUBQ_PAPER_CAP,
                    "within_paper_top_k": retrieval.WITHIN_PAPER_TOP_K,
                    "per_paper_chunk_cap": retrieval.PER_PAPER_CHUNK_CAP,
                    "max_growth_iters": retrieval.MAX_GROWTH_ITERS,
                    "max_packet_chars": retrieval.MAX_PACKET_CHARS,
                },
                "ledger_hash": ledger_hash,
                "counts": {
                    "subquestions": len(subquestions),
                    "propositions_total": len(all_records),
                    "verified": len(verified),
                    "recovery_records": sum(1 for r in all_records if r["provenance"]["origin"] == "recovery"),
                },
                "elapsed_seconds": round(time.monotonic() - started, 1),
            },
        )
        print(f"[ask-cli] done in {round(time.monotonic() - started, 1)}s -> {out_dir}")
        return 0
    finally:
        rt.close()


def _recover(conn, rt, qwen, subquestions, gaps, all_records, axis_cache, trace) -> list[dict]:
    """ONE bounded pass: for each uncovered obligation, reuse S2/S4/S5/S6/S7 scoped to that gap. No recursion."""
    sq_by_id = {sq["subquestion_id"]: sq for sq in subquestions}
    log: list[dict] = []
    for gap in gaps:
        sq = sq_by_id.get(gap["subquestion_id"])
        if sq is None:
            continue
        rq = qwen.recovery_query(
            subquestion=sq["text"], obligation_kind=gap["kind"], obligation_note=gap.get("note", "")
        )
        noms, _ = discovery.nominate_papers(
            conn, subquestion_text=rq, model=rt.model, vector_store=rt.vector_store, axis_cache=axis_cache
        )
        reason_by_paper = {n.paper_id: n.reasons for n in noms}
        hits = retrieval.within_paper_retrieve(
            conn,
            subquestion_id=sq["subquestion_id"],
            subquestion_text=rq,
            paper_ids=[n.paper_id for n in noms],
            model=rt.model,
            vector_store=rt.vector_store,
        )
        added = 0
        for h in hits:
            packet = retrieval.grow_context(conn, hit=h, gate=qwen.context_gate, subquestion_text=sq["text"])
            recs = marshal_and_verify(
                conn,
                verifier=rt.verifier,
                qwen=qwen,
                packet=packet,
                subquestion_text=sq["text"],
                obligations=[o for o in sq["obligations"] if o["field_id"] == gap["field_id"]],
                nomination_reason=reason_by_paper.get(h.chunk.paper_id, []),
                origin="recovery",
                trace=trace,
            )
            all_records.extend(recs)
            added += sum(1 for r in recs if r["verification"]["status"] == "verified")
        log.append(
            {
                "gap": gap,
                "recovery_query": rq,
                "candidate_papers": len(noms),
                "hits": len(hits),
                "new_verified": added,
                "reason_code": "recovery_added_evidence" if added else "recovery_no_new_evidence",
            }
        )
    return log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="path to a COPY of a library sqlite (never the live demo DB)")
    parser.add_argument("--out", default=None, help="run output directory (default: experiments/ask_cli/runs/<ts>)")
    parser.add_argument(
        "--terminal", choices=["both", "qwen", "gemini"], default="both", help="terminal-synthesis provider(s)"
    )
    args = parser.parse_args(argv)
    out = args.out or str(ROOT / "experiments" / "ask_cli" / "runs" / datetime.now().strftime("%Y%m%dT%H%M%S"))
    return run(args.db, out, args.terminal)


if __name__ == "__main__":
    raise SystemExit(main())
