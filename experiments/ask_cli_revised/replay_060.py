"""Freeze deterministic 0.6.0 receipts from existing benchmarks and historical run.

No provider, embeddings, retrieval or verification calls. Tokenizer-only inspection
is local. Semantic annotations are manual historical-block adjudications, not an
automatic entailment classifier. No frozen input is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from experiments.ask_cli_revised.calibration.run06.dataset06 import decomposition_cases_v06
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions, audit_original_request
from experiments.ask_cli_revised.ledger_renderer import render_ledger, audit_final

BASE = Path(__file__).resolve().parent
FROZEN = BASE / "calibration/runs/run06-20260908T041153Z"
HISTORICAL = BASE / "runs/revised-20260907T211542Z"
REFERENT_HASH = "d969bae01434c6491fd0bfbee26855a42dfbe857445c90d850b77e784c9a07da"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(out: Path, name: str, value):
    (out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def replay(out: Path, referent_path: Path, tokenizer_dir: Path | None = None):
    out.mkdir(parents=True, exist_ok=True)
    paths = [referent_path, FROZEN / "00_frozen.json", FROZEN / "04_frozen_decompositions.json",
             HISTORICAL / "00_question.json", HISTORICAL / "11_verified_ledger.json",
             HISTORICAL / "14a_final_answer.qwen.md", HISTORICAL / "08_evidence_packets.jsonl",
             HISTORICAL / "qwen_calls.jsonl", HISTORICAL / "09_propositions.jsonl",
             HISTORICAL / "10_verification.jsonl", HISTORICAL / "01_decomposition.json",
             HISTORICAL / "decisions.jsonl"]
    initial_hashes = {str(p): sha(p) for p in paths}
    if sha(referent_path) != REFERENT_HASH:
        raise ValueError("frozen 13/11 obligation referent hash mismatch")
    referent = read(referent_path)
    write(out, "frozen-referent.json", referent)
    frozen_cases = {c["case_id"]: c for c in read(FROZEN / "00_frozen.json")["cases"]}
    old_reps = read(FROZEN / "04_frozen_decompositions.json")
    receipts = {}
    tokenize = None
    if tokenizer_dir:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir), local_files_only=True)
        limit = read(tokenizer_dir / "sentence_bert_config.json")["max_seq_length"]
        tokenize = lambda text: tokenizer(" ".join(text.split()).lower(), truncation=False)["input_ids"]
    for case in decomposition_cases_v06():
        cid, question = case["case_id"], case["text"]
        started = time.perf_counter()
        contract = build_request_contract(question)
        sqs = request_subquestions(contract)
        duration = time.perf_counter() - started
        assert question == frozen_cases[cid]["text"]
        assert contract["question_hash"] == frozen_cases[cid]["question_hash"]
        for unit in contract["source_units"]:
            assert question[unit["start"]:unit["end"]] == unit["text"]
        rows = []
        units = {u["source_unit_id"]: u for u in contract["source_units"]}
        for obligation in referent.get(cid, {}).get("obligations", []):
            unit = units[obligation["source_unit"]]
            sq = next(s for s in sqs if s["source_unit_id"] == obligation["source_unit"])
            assert unit["text"] in sq["text"] and question in sq["text"]
            rows.append({"obligation_id": obligation["id"], "source_unit_id": unit["source_unit_id"],
                         "literal_source": unit["text"], "request_retention": "exact_with_original_context",
                         "semantic_basis": "original text retained verbatim; no candidate answer substituted",
                         "retrieval_support": "not_measured", "evidence_completion": "not_certified"})
        receipt = {"question_hash": contract["question_hash"], "source_units": len(sqs),
                   "literal_offsets_valid": True, "all_queries_contain_original": True,
                   "request_preparation_seconds": duration, "obligations": rows,
                   "generated_request_content": 0, "source_fidelity_not_retrieval_utility": True,
                   "original_coverage_with_no_evidence": audit_original_request(contract, sqs, []),
                   "before_run06_selected_candidate": old_reps.get(cid, {}).get("selected_candidate")}
        if tokenize:
            counts = [len(tokenize(s["text"])) for s in sqs]
            receipt["tokenizer_only"] = {"normalized_query_token_counts": counts, "max_seq_length": limit,
                                         "truncated_queries": sum(n > limit for n in counts)}
        receipts[cid] = receipt
        write(out, f"{cid}-request-after.json", {"contract": contract, "subquestions": sqs})
        if cid in old_reps:
            write(out, f"{cid}-request-before-run06.json", old_reps[cid])
    write(out, "request-results.json", {"basis": "literal representation retention, not independent evidence-completion scoring",
                                       "provenance_note": referent["provenance_note"], "cases": receipts})

    ledger = read(HISTORICAL / "11_verified_ledger.json")
    # Reconstruct only the source catalog from frozen offered spans. The verified
    # proposition objects remain byte-equivalent to the historical ledger.
    from experiments.ask_cli_revised.calibration.run06b.dataset import build_dataset
    dataset = build_dataset(HISTORICAL)
    ledger["evidence_spans"] = [
        {"paper_id": u["paper_id"], "chunk_id": u["containing_chunk_id"],
         "span_id": u["local_span_id"], "text": u["exact_span_text"]}
        for u in dataset["units"] if u.get("local_span_id") and u.get("containing_chunk_id")
    ]
    write(out, "historical-ledger-with-frozen-span-catalog.json", ledger)
    old_text = (HISTORICAL / "14a_final_answer.qwen.md").read_text(encoding="utf-8")
    started = time.perf_counter()
    new_text, manifest = render_ledger(ledger)
    render_seconds = time.perf_counter() - started
    (out / "terminal-before.md").write_text(old_text, encoding="utf-8")
    (out / "terminal-after.md").write_text(new_text, encoding="utf-8")
    write(out, "terminal-manifest.json", manifest)
    before_audit, after_audit = audit_final(ledger, old_text), audit_final(ledger, new_text)
    assert before_audit["nonexistent_ids"] == ["p27"]
    assert after_audit["constrained_render_match"] and not after_audit["nonexistent_ids"]
    span_checks = []
    for prop in ledger["verified_propositions"]:
        matches = [u for u in dataset["units"] if u.get("local_span_id") == prop["evidence_span_id"]
                   and u.get("containing_chunk_id") == prop["evidence_anchor_chunk_id"]
                   and u.get("paper_id") == prop["paper_id"] and u.get("exact_span_text") == prop["quote"]]
        assert matches
        span_checks.append({"proposition_id": prop["proposition_id"], "matches_frozen_offered_span": True,
                            "dataset_instance_ids": [u["dataset_instance_id"] for u in matches]})
    # Exhaustive nonempty-line inventory; scientific blocks may contain multiple assertions.
    scientific = {
        3: "ASD/atypical/RTPJ nucleus exists; spelled-out RTPJ expansion is absent from ledger.",
        4: "AIB-to-altered-brain/behavior bridge absent from ledger.",
        9: "AIB bridge, heightened direction and acronym expansions absent from ledger.",
        11: "Mixed coverage/gap prose; claims the answer explains AIB manifestation and cites nonexistent p27.",
        15: "Bias-to-altered-RTPJ-connectivity assertion absent from ledger.",
        18: "Psychological-theory evidence assertion absent from ledger and original request.",
        34: "Mixed gap/scientific prose; bias-to-specific-neurophysiology bridge absent from ledger.",
    }
    blocks = []
    for number, line in enumerate(old_text.splitlines(), 1):
        if not line.strip():
            continue
        kind = ("scientific_or_mixed_with_unsupported_addition" if number in scientific else
                "coverage_claim_not_certified" if number in {28, 29, 30, 31} else
                "gap_statement" if number in {6, 21} else
                "research_suggestion_with_unverified_premise" if number == 23 else "connective_or_structure")
        blocks.append({"line": number, "text": line, "manual_classification": kind,
                       "reason": scientific.get(number)})
    write(out, "terminal-results.json", {"before": before_audit, "after": after_audit,
                                         "historical_span_checks": span_checks, "historical_block_inventory": blocks,
                                         "unsupported_scientific_or_mixed_blocks": len(scientific),
                                         "block_count_is_not_atomic_claim_count": True,
                                         "renderer_seconds": render_seconds,
                                         "historical_verified_propositions_unchanged": True,
                                         "source_catalog_added_from_frozen_offered_spans": True})
    assert initial_hashes == {str(p): sha(p) for p in paths}
    write(out, "input-hashes.json", initial_hashes)
    write(out, "performance.json", {"provider_calls": 0, "infrastructure_calls": 0, "judge_calls": 0,
                                    "embedding_inference_calls": 0, "retrieval_calls": 0, "verifier_calls": 0,
                                    "tokenizer_only": bool(tokenizer_dir), "renderer_seconds": render_seconds})
    write(out, "receipt-hashes.json", {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "receipt-hashes.json"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--referent", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path)
    args = parser.parse_args()
    replay(args.out, args.referent, args.tokenizer_dir)
    print(f"Deterministic request/terminal receipts: {args.out}")


if __name__ == "__main__":
    main()
