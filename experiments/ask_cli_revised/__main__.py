"""CLI orchestrator for the isolated staged-synthesis experiment.

    python -m experiments.ask_cli_revised --db <copy.sqlite> --out <run-dir> [--terminal render|qwen|gemini|both|none]

The default terminal is a verbatim ledger renderer. Explicit model modes add unvalidated comparison
candidates. Intermediate inference is managed-local Qwen. Use a caller-supplied COPY of the DB.
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

from experiments.ask_cli_revised import coverage as coverage_mod  # noqa: E402
from experiments.ask_cli_revised import discovery, retrieval, synthesis  # noqa: E402
from experiments.ask_cli_revised.propositions import marshal_and_verify, _candidate_spans  # noqa: E402
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION  # noqa: E402
from experiments.ask_cli_revised.qwen import QwenTasks  # noqa: E402
from experiments.ask_cli_revised.runtime import QwenUnavailableError, build_runtime  # noqa: E402
from experiments.ask_cli_revised.trace import TraceWriter  # noqa: E402
from experiments.ask_cli_revised.request_contract import (  # noqa: E402
    build_request_contract, request_subquestions, audit_original_request,
)
from experiments.ask_cli_revised.ledger_renderer import render_ledger, audit_final  # noqa: E402


def _git_sha() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=10,
        ).stdout.strip()[:40]
    except Exception:  # noqa: BLE001
        return "unknown"


def _paper_record(nomination) -> dict:
    return {
        "paper_id": nomination.paper_id,
        "reasons": nomination.reasons,
        "score": nomination.best_score,
        "direct_score": nomination.direct_score,
        "axis_score": nomination.axis_score,
        "axis_hits": nomination.axis_hits,
    }


def _process_hits(
    conn,
    *,
    rt,
    qwen,
    subquestion: dict,
    hits,
    reason_by_paper: dict[int, list[str]],
    origin: str,
    trace: TraceWriter,
    all_records: list[dict],
    chunk_hits: list[dict],
    context_growth: list[dict],
    evidence_packets: list[dict],
    propositions: list[dict],
    verifications: list[dict],
    map_claims: bool = True,
) -> int:
    sid = subquestion["subquestion_id"]
    sq_text = subquestion["text"]
    obligations = subquestion.get("obligations", [])
    verified_before = sum(1 for record in all_records if record["verification"]["status"] == "verified")

    for hit in hits:
        chunk_hits.append(
            {
                "origin": origin,
                "subquestion_id": sid,
                "chunk_id": hit.chunk.chunk_id,
                "paper_id": hit.chunk.paper_id,
                "score": hit.score,
                "section": hit.section,
                "chunk_type": hit.chunk_type,
                "evidence_role": hit.evidence_role,
            }
        )
        packet = retrieval.grow_context(
            conn,
            hit=hit,
            gate=qwen.context_gate,
            subquestion_text=sq_text,
        )
        context_growth.append(
            {
                "origin": origin,
                "subquestion_id": sid,
                "retrieval_anchor_chunk_id": packet.retrieval_anchor_chunk_id,
                "grown": packet.grown,
                "discarded": packet.discarded,
                "discard_reason": getattr(packet, "discard_reason", None),
                "decisions": packet.decisions,
                "packet_chunks": [chunk["chunk_id"] for chunk in packet.chunks],
            }
        )
        candidate_spans = [] if packet.discarded else _candidate_spans(packet, trace)
        evidence_packets.append(
            {
                "origin": origin,
                "subquestion_id": sid,
                "paper_id": packet.paper_id,
                "retrieval_anchor_chunk_id": packet.retrieval_anchor_chunk_id,
                "retrieval_score": packet.retrieval_score,
                "discarded": packet.discarded,
                "chunks": packet.chunks,
                "candidate_spans": candidate_spans,
            }
        )
        records = marshal_and_verify(
            conn,
            verifier=rt.verifier,
            qwen=qwen,
            packet=packet,
            subquestion_text=sq_text,
            obligations=obligations,
            nomination_reason=reason_by_paper.get(hit.chunk.paper_id, []),
            origin=origin,
            trace=trace,
            candidate_spans=candidate_spans,
            map_claims=map_claims,
        )
        all_records.extend(records)
        for record in records:
            record["provenance"]["request"] = {
                key: subquestion[key] for key in
                ("source_unit_id", "source_text", "source_start", "source_end", "question_hash")
                if key in subquestion
            }
            propositions.append(
                {
                    key: record[key]
                    for key in (
                        "subquestion_id",
                        "obligation_ids",
                        "paper_id",
                        "retrieval_anchor_chunk_id",
                        "evidence_anchor_chunk_id",
                        "evidence_span_id",
                        "proposition_text",
                        "quote",
                        "provenance",
                    )
                }
            )
            verifications.append(
                {
                    "origin": origin,
                    "subquestion_id": sid,
                    "evidence_anchor_chunk_id": record["evidence_anchor_chunk_id"],
                    "proposition_text": record["proposition_text"],
                    **record["verification"],
                }
            )

    verified_after = sum(1 for record in all_records if record["verification"]["status"] == "verified")
    return verified_after - verified_before


def run(db_path: str, out_dir: str, terminal: str = "render", *, question: str = BENCHMARK_QUESTION) -> int:
    request_contract = build_request_contract(question)
    question_digest = request_contract["question_hash"]
    trace = TraceWriter(out_dir)
    started = time.monotonic()
    print(f"[ask-cli] run dir: {out_dir}")

    try:
        rt = build_runtime(db_path, want_gemini=(terminal in {"both", "gemini"}))
    except QwenUnavailableError as exc:
        trace.write_json("00_question.json", {"question": question, "hash": question_digest})
        trace.write_json("BLOCKED.json", {"blocked": True, "reason": str(exc)})
        print(f"[ask-cli] BLOCKED: {exc}")
        return 2

    qwen = QwenTasks(config=rt.qwen_config, trace=trace)
    all_records: list[dict] = []
    try:
        with rt.engine.connect() as conn:
            trace.write_json("00_question.json", {"question": question, "hash": question_digest})
            stats = discovery.corpus_stats(conn, model=rt.model)

            print("[ask-cli] stage 1: literal original-request contract")
            subquestions = request_subquestions(request_contract)
            interp_fallback = False
            trace.write_json("01_request_contract.json", request_contract)
            trace.write_json(
                "01_decomposition.json",
                {
                    "subquestions": subquestions,
                    "qwen_fallback_used": interp_fallback,
                },
            )

            trace.write_json("04_graph_rescue.json", discovery.graph_rescue_stage(conn))

            axis_cache: dict = {}
            direct_papers: list[dict] = []
            axis_noms: list[dict] = []
            candidate_papers: list[dict] = []
            nominations_by_subq: dict[str, list] = {}
            chunk_hits: list[dict] = []
            context_growth: list[dict] = []
            evidence_packets: list[dict] = []
            propositions: list[dict] = []
            verifications: list[dict] = []

            for subquestion in subquestions:
                sid = subquestion["subquestion_id"]
                sq_text = subquestion["text"]
                print(f"[ask-cli] {sid}: discovery + retrieval")
                nominations, nomination_log = discovery.nominate_papers(
                    conn,
                    subquestion_text=sq_text,
                    model=rt.model,
                    vector_store=rt.vector_store,
                    axis_cache=axis_cache,
                )
                nominations_by_subq[sid] = nominations
                for row in nomination_log:
                    target = axis_noms if str(row.get("reason", "")).startswith("axis:") else direct_papers
                    target.append({**row, "subquestion_id": sid})
                reason_by_paper = {nom.paper_id: nom.reasons for nom in nominations}
                candidate_papers.append(
                    {
                        "subquestion_id": sid,
                        "papers": [_paper_record(nom) for nom in nominations],
                    }
                )

                hits = retrieval.within_paper_retrieve(
                    conn,
                    subquestion_id=sid,
                    subquestion_text=sq_text,
                    paper_ids=[nom.paper_id for nom in nominations],
                    model=rt.model,
                    vector_store=rt.vector_store,
                )
                _process_hits(
                    conn,
                    rt=rt,
                    qwen=qwen,
                    subquestion=subquestion,
                    hits=hits,
                    reason_by_paper=reason_by_paper,
                    origin="initial",
                    trace=trace,
                    all_records=all_records,
                    chunk_hits=chunk_hits,
                    context_growth=context_growth,
                    evidence_packets=evidence_packets,
                    propositions=propositions,
                    verifications=verifications,
                )

            trace.write_json("02_direct_papers.json", direct_papers)
            trace.write_json("03_axis_nominations.json", axis_noms)
            trace.write_json("05_candidate_papers.json", candidate_papers)

            initial_audit = coverage_mod.audit_coverage(subquestions, all_records)
            initial_audit["original_request"] = audit_original_request(request_contract, subquestions, all_records)
            trace.write_json("12_coverage_audit.initial.json", initial_audit)

            print(f"[ask-cli] stage 10: gap recovery ({len(initial_audit['gaps'])} gaps)")
            recovery_log = _recover(
                conn,
                rt=rt,
                qwen=qwen,
                subquestions=subquestions,
                gaps=initial_audit["gaps"],
                initial_nominations=nominations_by_subq,
                all_records=all_records,
                axis_cache=axis_cache,
                trace=trace,
                chunk_hits=chunk_hits,
                context_growth=context_growth,
                evidence_packets=evidence_packets,
                propositions=propositions,
                verifications=verifications,
            )
            trace.write_json("13_gap_recovery.json", recovery_log)
            # Recovery-only dedup markers (see _new_unique_verified) exclude a rediscovered item
            # from the authoritative coverage/ledger view while it stays fully visible in the raw
            # trace below (all_records / propositions.jsonl / verifications.jsonl are untouched).
            # The PRE-recovery initial_audit call above correctly used all_records: no markers exist
            # yet at that point, so effective_records would be identical there.
            effective_records = [
                r for r in all_records if not r["provenance"].get("duplicate_of_existing_evidence")
            ]
            audit = coverage_mod.audit_coverage(subquestions, effective_records)
            audit["original_request"] = audit_original_request(request_contract, subquestions, effective_records)
            trace.write_json("12_coverage_audit.json", audit)

            trace.write_jsonl("06_chunk_retrieval.jsonl", chunk_hits)
            trace.write_jsonl("07_context_growth.jsonl", context_growth)
            trace.write_jsonl("08_evidence_packets.jsonl", evidence_packets)
            trace.write_jsonl("09_propositions.jsonl", propositions)
            trace.write_jsonl("10_verification.jsonl", verifications)

        verified_raw = [record for record in effective_records if record["verification"]["status"] == "verified"]
        verified = [
            {"proposition_id": f"p{index}", **record}
            for index, record in enumerate(verified_raw, start=1)
        ]
        sealed = {
            "request_contract": request_contract,
            "subquestions": subquestions,
            "verified_propositions": verified,
            "evidence_spans": [
                {"paper_id": packet["paper_id"], "chunk_id": span["chunk_id"],
                 "span_id": span["span_id"], "text": span["text"]}
                for packet in evidence_packets for span in packet["candidate_spans"]
            ],
            "coverage": audit,
        }
        sealed_bytes = json.dumps(sealed, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ledger_hash = hashlib.sha256(sealed_bytes).hexdigest()
        trace.write_json("11_verified_ledger.json", {**sealed, "sealed_hash": ledger_hash})
        print(f"[ask-cli] sealed ledger: {len(verified)} verified propositions (hash {ledger_hash[:12]})")

        if terminal != "none":
            text, render_manifest = render_ledger(sealed)
            final_path = trace.write_report("14_final_answer.md", [text.rstrip("\n")])
            trace.write_json("14_render_manifest.json", render_manifest)
            trace.write_json("14_final_audit.json", audit_final(sealed, final_path.read_text(encoding="utf-8")))

        if terminal in {"both", "qwen"}:
            print("[ask-cli] stage 12A: Qwen terminal synthesis")
            text, _ = synthesis.terminal_synthesis(rt.qwen_config, sealed)
            trace.write_report("14a_UNVALIDATED_candidate.qwen.md", [text])
            trace.write_json("14a_candidate_audit.json", audit_final(sealed, text))
        if terminal in {"both", "gemini"}:
            if rt.gemini_config is None:
                trace.write_report(
                    "14b_final_answer.gemini.md",
                    ["[Gemini terminal synthesis skipped: no API key resolved.]"],
                )
            else:
                print("[ask-cli] stage 12B: Gemini terminal synthesis")
                text, _ = synthesis.terminal_synthesis(rt.gemini_config, sealed)
                trace.write_report("14b_UNVALIDATED_candidate.gemini.md", [text])
                trace.write_json("14b_candidate_audit.json", audit_final(sealed, text))

        trace.flush_qwen()
        trace.flush_events()
        trace.write_json(
            "15_run_manifest.json",
            {
                "created": datetime.now(timezone.utc).isoformat(),
                "question_hash": question_digest,
                "db_path": str(Path(db_path).resolve()),
                "corpus_stats": stats,
                "git_sha": _git_sha(),
                "platform": platform.platform(),
                "verifier_thresholds": {
                    "retrieval": 0.70,
                    "quote": 1.0,
                    "support": 0.55,
                    "contradiction": 0.55,
                },
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
                "terminal": terminal,
                "counts": {
                    "subquestions": len(subquestions),
                    "propositions_total": len(all_records),
                    "verified": len(verified),
                    "recovery_records": sum(
                        1 for record in all_records if record["provenance"]["origin"] == "recovery"
                    ),
                },
                "elapsed_seconds": round(time.monotonic() - started, 1),
            },
        )
        print(f"[ask-cli] done in {round(time.monotonic() - started, 1)}s -> {out_dir}")
        return 0
    finally:
        rt.close()


def _new_unique_verified(all_records: list[dict], since_index: int) -> int:
    """Recovery-only dedup. Mark (never delete) a newly-verified record at/after ``since_index`` as
    a duplicate of pre-existing evidence when its (paper_id, evidence_anchor_chunk_id, exact claim
    text) identity already exists among records present before this call. Mirrors
    propositions.py::marshal_and_verify's own existing same-call duplicate-claim identity,
    ``(chunk_id, claim.casefold())``, extended with paper_id for explicitness -- the smallest exact
    identity that distinguishes the demonstrated duplicate (same paper+chunk+scientific claim), no
    fuzzy/semantic matching. A marked record stays in ``all_records`` (the full trace --
    propositions.jsonl/verifications.jsonl -- shows it and what it duplicates); callers decide what
    counts as authoritative via ``effective_records`` in ``run()``. Never called by the initial
    pass -- ``_process_hits`` itself is not modified, so first-pass behavior is unchanged by
    construction, not merely because its return value used to go unused."""

    def identity(record: dict) -> tuple:
        return (record["paper_id"], record["evidence_anchor_chunk_id"], record["proposition_text"].casefold())

    seen = {identity(r) for r in all_records[:since_index] if r["verification"]["status"] == "verified"}
    new_unique = 0
    for record in all_records[since_index:]:
        if record["verification"]["status"] != "verified":
            continue
        key = identity(record)
        if key in seen:
            record["provenance"]["duplicate_of_existing_evidence"] = True
            continue
        seen.add(key)
        new_unique += 1
    return new_unique


# Plan actions that search. Everything else (MARK_COVERED:<claim>, NO_RECOVERY_NEEDED, PRESERVE_UNRESOLVED) creates
# no search state: coverage is never written by the planner, only by the coverage authority.
_SEARCH_ACTIONS = frozenset({"DEEPEN", "NOMINATE", "LEGACY"})


def _recover(
    conn,
    *,
    rt,
    qwen,
    subquestions,
    gaps,
    initial_nominations,
    all_records,
    axis_cache,
    trace,
    chunk_hits,
    context_growth,
    evidence_packets,
    propositions,
    verifications,
    plan: dict[str, str] | None = None,
    map_claims: bool = True,
) -> list[dict]:
    """One recovery pass.

    Without a plan (the shipped behavior, action ``LEGACY``): existing candidate papers first, then one new nomination
    pass if that added nothing. With a plan, each obligation runs exactly the planned action: ``DEEPEN`` re-searches only
    the existing candidates, ``NOMINATE`` searches only papers that are not already candidates, and any other planned
    action (or an obligation absent from the plan) creates no search state. ``map_claims=False`` defers claim ->
    obligation mapping until after source verification.
    """
    sq_by_id = {subquestion["subquestion_id"]: subquestion for subquestion in subquestions}
    log: list[dict] = []
    for gap in gaps:
        subquestion = sq_by_id.get(gap["subquestion_id"])
        if subquestion is None:
            continue
        action = "LEGACY" if plan is None else plan.get(gap["field_id"])
        if action is None:
            continue
        if action not in _SEARCH_ACTIONS:
            log.append(
                {
                    "gap": gap,
                    "action": action,
                    "recovery_query": None,
                    "existing_candidate_papers": 0,
                    "existing_hits": 0,
                    "new_papers_nominated": [],
                    "new_hits": 0,
                    "new_verified": 0,
                    "reason_code": "plan_no_search",
                }
            )
            continue
        # Always reformulate via the existing recovery-query mechanism -- the previous
        # `subquestion["text"] if subquestion.get("source_unit_id") else ...` shortcut meant every
        # subquestion in the current request-contract decomposition (all of which carry
        # source_unit_id) skipped qwen.recovery_query() entirely and reused the literal original
        # text verbatim, guaranteeing byte-identical retrieval against the same papers below.
        query = qwen.recovery_query(
            subquestion=subquestion["text"], obligation_note=gap.get("display") or gap.get("note", "")
        )
        if query is None:
            # NO ANSWER (mechanical): no search state was created, so none is claimed as recovery.
            log.append(
                {
                    "gap": gap,
                    "action": action,
                    "recovery_query": None,
                    "existing_candidate_papers": 0,
                    "existing_hits": 0,
                    "new_papers_nominated": [],
                    "new_hits": 0,
                    "new_verified": 0,
                    "reason_code": "recovery_query_no_answer",
                }
            )
            continue
        original_noms = initial_nominations.get(subquestion["subquestion_id"], [])
        original_ids = [nom.paper_id for nom in original_noms]
        original_reasons = {nom.paper_id: nom.reasons for nom in original_noms}
        gap_subquestion = {
            **subquestion,
            "obligations": [
                obligation
                for obligation in subquestion.get("obligations", [])
                if obligation["field_id"] == gap["field_id"]
            ],
        }

        existing_hits: list = []
        existing_added = 0
        if action in {"DEEPEN", "LEGACY"}:
            existing_hits = retrieval.within_paper_retrieve(
                conn,
                subquestion_id=subquestion["subquestion_id"],
                subquestion_text=query,
                paper_ids=original_ids,
                model=rt.model,
                vector_store=rt.vector_store,
            )
            existing_before = len(all_records)
            _process_hits(
                conn,
                rt=rt,
                qwen=qwen,
                subquestion=gap_subquestion,
                hits=existing_hits,
                reason_by_paper=original_reasons,
                origin="recovery",
                trace=trace,
                all_records=all_records,
                chunk_hits=chunk_hits,
                context_growth=context_growth,
                evidence_packets=evidence_packets,
                propositions=propositions,
                verifications=verifications,
                map_claims=map_claims,
            )
            # Recovery-only: a record identical (by paper+chunk+exact claim text) to evidence already
            # verified before this call does not count as progress -- it's marked in place (visible in
            # the full trace) and excluded here, rather than trusting _process_hits's own raw delta
            # (which would count a 100%-duplicate re-verification as "added"). _process_hits itself is
            # unmodified; the initial pass never calls this helper.
            existing_added = _new_unique_verified(all_records, existing_before)

        new_noms = []
        new_hits = []
        new_added = 0
        if action == "NOMINATE" or (action == "LEGACY" and existing_added == 0):
            nominated, _ = discovery.nominate_papers(
                conn,
                subquestion_text=query,
                model=rt.model,
                vector_store=rt.vector_store,
                axis_cache=axis_cache,
            )
            new_noms = [nom for nom in nominated if nom.paper_id not in set(original_ids)]
            new_reasons = {nom.paper_id: nom.reasons for nom in new_noms}
            new_hits = retrieval.within_paper_retrieve(
                conn,
                subquestion_id=subquestion["subquestion_id"],
                subquestion_text=query,
                paper_ids=[nom.paper_id for nom in new_noms],
                model=rt.model,
                vector_store=rt.vector_store,
            )
            new_before = len(all_records)
            _process_hits(
                conn,
                rt=rt,
                qwen=qwen,
                subquestion=gap_subquestion,
                hits=new_hits,
                reason_by_paper=new_reasons,
                origin="recovery",
                trace=trace,
                all_records=all_records,
                chunk_hits=chunk_hits,
                context_growth=context_growth,
                evidence_packets=evidence_packets,
                propositions=propositions,
                verifications=verifications,
                map_claims=map_claims,
            )
            new_added = _new_unique_verified(all_records, new_before)

        total_added = existing_added + new_added
        log.append(
            {
                "gap": gap,
                "action": action,
                "recovery_query": query,
                "existing_candidate_papers": len(original_ids),
                "existing_hits": len(existing_hits),
                "new_papers_nominated": [_paper_record(nom) for nom in new_noms],
                "new_hits": len(new_hits),
                "new_verified": total_added,
                "reason_code": "recovery_added_evidence" if total_added else "recovery_no_new_evidence",
            }
        )
    return log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="path to a COPY of a library sqlite (never the live demo DB)")
    parser.add_argument("--out", default=None, help="run output directory (default: experiments/ask_cli_revised/runs/<ts>)")
    parser.add_argument("--question-file", help="optional UTF-8 original request, read without stripping or rewriting")
    parser.add_argument(
        "--terminal",
        choices=["render", "qwen", "gemini", "both", "none"],
        default="render",
        help="verbatim renderer by default; model modes add UNVALIDATED comparison candidates only",
    )
    args = parser.parse_args(argv)
    out = args.out or str(ROOT / "experiments" / "ask_cli_revised" / "runs" / datetime.now().strftime("%Y%m%dT%H%M%S"))
    question = Path(args.question_file).read_bytes().decode("utf-8") if args.question_file else BENCHMARK_QUESTION
    return run(args.db, out, args.terminal, question=question)


if __name__ == "__main__":
    raise SystemExit(main())
