"""The authorized 29-pair prospective NLI reliability pilot (2026-09-28 authorization).

Reconstructs the frozen selection from two already-frozen records -- **never regenerates, expands, reorders,
paraphrases or resamples**:

- **27 prospective premises**: every premise in `nli-prospective-corpus-eval-001/00_prospective_corpus.json`
  with `would_truncate == False`, EXCLUDING the one degenerate "TABLE 1." table-caption fragment (flagged, not
  silently included, in `NLI_PROSPECTIVE_CORPUS_EVAL_001_HANDBACK.md` Section 2.4).
- **2 historical controls**: c9's and c11's own premises, read from `nli_premise_population_eval.inventory()`
  (imported, never re-derived) -- `unit_ids == ("U1",)` for c9, `unit_ids == ("U2", "U3")` for c11.

Every evaluation pair is `(premise, premise)` -- a self-entailment pair, the SAME construction every diagnostic
in this arc has used. The two controls are compared against their REAL historical SELF-PAIR baselines (recovered
below directly from the saved `nli-boundary-diagnostic-001/01_raw_scores.json`, ids `self_entail_c9`/
`self_entail_c11`) -- explicitly NOT c9's ~0.81 candidate-versus-premise score, which is a different pair
entirely (candidate text vs. its cited passage, not the passage against itself).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

RUNS_DIR = Path(r"C:\Users\cliff\callosum-data\contract-directed-slice\runs")
PROSPECTIVE_CORPUS_PATH = RUNS_DIR / "nli-prospective-corpus-eval-001" / "00_prospective_corpus.json"
DIAGNOSTIC_001_RAW = RUNS_DIR / "nli-boundary-diagnostic-001" / "01_raw_scores.json"

NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"

# Recovered directly from the saved diagnostic-001 raw output (re-verified, not retyped from prose) --
# reproduced EXACTLY (to 15+ significant figures) in nli-boundary-diagnostic-002's own A3_U2U3_self_REPRO
# reproduction check for c11. This exact-reproduction precedent is what justifies the tight tolerance below.
HISTORICAL_SELF_PAIR_BASELINES = {
    "c9": {"support": 0.8874918222427368, "contradiction": 0.07401907444000244, "source_id": "self_entail_c9"},
    "c11": {"support": 0.007013050373643637, "contradiction": 0.9809232950210571, "source_id": "self_entail_c11"},
}
# Frozen BEFORE inference. Justified by the exact-reproduction precedent above (two independent diagnostic runs
# on different days reproduced c11's self-pair to 15+ significant figures) -- any discrepancy beyond ordinary
# floating-point jitter across a fresh process/model load would itself be a reportable finding, not noise.
CONTROL_REPRODUCTION_TOLERANCE = 1e-3


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_execution_manifest() -> dict:
    corpus = _load(PROSPECTIVE_CORPUS_PATH)
    safe = [p for p in corpus["prospective_premises"] if not p["would_truncate"]]
    prospective_27 = [p for p in safe if p["premise"].strip() != "TABLE 1."]
    assert len(safe) == 28, f"expected 28 safe premises in the frozen corpus, found {len(safe)}"
    assert len(prospective_27) == 27, f"expected 27 non-degenerate safe premises, found {len(prospective_27)}"

    # verify every one of the 27 premise hashes matches its stored text -- the frozen record must not have
    # drifted since it was written
    for p in prospective_27:
        recomputed = hashlib.sha256(p["premise"].encode("utf-8")).hexdigest()
        assert recomputed == p["sha256"], f"hash mismatch for a prospective premise: {p['sha256']}"

    from experiments.ask_cli_revised.contract_directed.tools import nli_premise_population_eval as observed

    inv = observed.inventory()
    by_unit_ids = {tuple(p["unit_ids"]): p for p in inv["premises"]}
    c9_hist = by_unit_ids[("U1",)]
    c11_hist = by_unit_ids[("U2", "U3")]

    pairs = []
    for p in prospective_27:
        pairs.append(
            {
                "pair_id": f"prospective_{p['sha256'][:12]}",
                "stratum": "prospective",
                "premise": p["premise"],
                "sha256": p["sha256"],
                "construction": p["ancestry"],
                "span_count": p["span_count"],
                "paper_ids": p["paper_ids"],
                "char_len": p["char_len"],
            }
        )
    pairs.append(
        {
            "pair_id": "control_c9",
            "stratum": "historical_control",
            "premise": c9_hist["premise"],
            "sha256": hashlib.sha256(c9_hist["premise"].encode("utf-8")).hexdigest(),
            "construction": ["historical_observed_production"],
            "span_count": c9_hist["span_count"],
            "paper_ids": None,
            "char_len": c9_hist["char_len"],
            "historical_baseline": HISTORICAL_SELF_PAIR_BASELINES["c9"],
        }
    )
    pairs.append(
        {
            "pair_id": "control_c11",
            "stratum": "historical_control",
            "premise": c11_hist["premise"],
            "sha256": hashlib.sha256(c11_hist["premise"].encode("utf-8")).hexdigest(),
            "construction": ["historical_observed_production"],
            "span_count": c11_hist["span_count"],
            "paper_ids": None,
            "char_len": c11_hist["char_len"],
            "historical_baseline": HISTORICAL_SELF_PAIR_BASELINES["c11"],
        }
    )

    assert len(pairs) == 29, f"expected exactly 29 pairs, built {len(pairs)}"
    seen_sha = {p["sha256"] for p in pairs}
    assert len(seen_sha) == 29, "expected 29 distinct premise strings, found a collision"

    return {
        "authorization": "2026-09-28 29-pair prospective NLI reliability pilot",
        "source_corpus": str(PROSPECTIVE_CORPUS_PATH),
        "prospective_count": len(prospective_27),
        "control_count": 2,
        "total_pairs": len(pairs),
        "control_reproduction_tolerance": CONTROL_REPRODUCTION_TOLERANCE,
        "pairs": pairs,
    }


def tokenize_and_verify(pairs: list[dict]) -> list[dict]:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(NLI_MODEL, revision=NLI_REVISION, local_files_only=True)
    for p in pairs:
        enc = tok(p["premise"], p["premise"], truncation=False)
        p["self_entailment_pair_tokens"] = len(enc["input_ids"])
        p["model_max_length"] = tok.model_max_length
        p["would_truncate"] = len(enc["input_ids"]) > tok.model_max_length
        assert not p["would_truncate"], f"pair {p['pair_id']} would truncate -- must not reach the manifest"
    return pairs


EVAL_DIR = RUNS_DIR / "nli-prospective-pilot-001"

PROTECTED_RUN_DIRS = frozenset(
    {
        "gate-integration-001",
        "gate-integration-live-001",
        "gate-integration-live-002",
        "gate2-diagnostic-001",
        "gate2-diagnostic-002",
        "nli-boundary-diagnostic-001",
        "nli-boundary-diagnostic-002",
        "nli-candidate-reliability-study-001",
        "nli-candidate-reliability-review-prep-001",
        "nli-candidate-review-reconciliation-001",
        "nli-four-span-ablation-001",
        "nli-clause-count-experiment-001",
        "nli-polarity-lexical-experiment-001",
        "nli-premise-population-eval-001",
        "nli-prospective-corpus-eval-001",
        "nli-repair-demo-001",
        "pilot-001",
        "pilot-prep-003",
        "replay-eligibility-001",
        "replay-eligibility-001-offline-analysis",
    }
)


def write_manifest(run_dir: Path, manifest: dict) -> Path:
    name = run_dir.name
    if name in PROTECTED_RUN_DIRS:
        raise RuntimeError(f"refusing to write into protected prior-attempt directory: {name}")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError(f"refusing to overwrite an already-populated directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "00_execution_manifest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return path


def read_manifest(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_real() -> None:
    """The one authorized live inference batch: 29 self-pairs, one model.predict() call."""
    manifest = build_execution_manifest()
    tokenize_and_verify(manifest["pairs"])

    import psutil

    vm = psutil.virtual_memory()
    mem_report = {"available_gb": round(vm.available / 1e9, 2), "total_gb": round(vm.total / 1e9, 2)}
    print(
        f"Memory: {mem_report['available_gb']} GB available / {mem_report['total_gb']} GB total "
        "(general precaution; not the Qwen/Ollama memory floor -- not reused here)"
    )
    if mem_report["available_gb"] < 1.0:
        raise RuntimeError(f"only {mem_report['available_gb']} GB available -- stopping, no override authorized")

    manifest_path = write_manifest(EVAL_DIR, manifest)
    reread = read_manifest(manifest_path)
    assert reread["pairs"] == manifest["pairs"], "execution manifest did not round-trip before inference"
    print(f"Pre-registered {len(manifest['pairs'])} pairs to {manifest_path} and confirmed read-back BEFORE inference.")

    from app.backend.model_runtime import PINNED_MODEL_REVISIONS
    from app.backend.summarization.stance import DEFAULT_NLI_MODEL
    from app.backend.summarization.verification import NLISupportScorer, _values_from_row

    assert DEFAULT_NLI_MODEL == NLI_MODEL
    pinned = PINNED_MODEL_REVISIONS.get(DEFAULT_NLI_MODEL)
    assert pinned == NLI_REVISION, f"pinned revision mismatch: code says {pinned}, expected {NLI_REVISION}"

    scorer = NLISupportScorer(revision=pinned, fallback_scorer=None)
    model = scorer._load_model()
    print(f"Loaded model: {type(model).__name__}, revision={pinned}")
    id2label = getattr(getattr(model, "model", None), "config", None)
    id2label = getattr(id2label, "id2label", None)
    print(f"id2label (from the loaded model's own config): {id2label}")

    call_pairs = [(p["premise"], p["premise"]) for p in manifest["pairs"]]
    raw_scores = model.predict(list(call_pairs), apply_softmax=True)  # THE ONE call
    print(f"ONE model.predict() call completed, {len(raw_scores)} rows returned.")
    assert len(raw_scores) == len(manifest["pairs"])

    results = []
    for p, row in zip(manifest["pairs"], raw_scores, strict=True):
        values = [float(v) for v in row]
        support, contradiction = _values_from_row(row, model=model)
        by_label = {label: values[int(idx)] for idx, label in id2label.items()} if isinstance(id2label, dict) else {}
        results.append(
            {
                **p,
                "support": support,
                "contradiction": contradiction,
                "raw_softmax_by_label": by_label,
                "raw_softmax_row": values,
            }
        )

    out_path = EVAL_DIR / "01_raw_scores.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": NLI_MODEL,
                "revision": pinned,
                "id2label": id2label,
                "memory_at_run": mem_report,
                "inference_call_count": 1,
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Wrote raw results to {out_path}")

    print("\n--- control reproduction check ---")
    for r in results:
        if r["stratum"] == "historical_control":
            base = r["historical_baseline"]
            ds, dc = r["support"] - base["support"], r["contradiction"] - base["contradiction"]
            within = abs(ds) <= CONTROL_REPRODUCTION_TOLERANCE and abs(dc) <= CONTROL_REPRODUCTION_TOLERANCE
            print(
                f"  {r['pair_id']}: historical support={base['support']:.6f} contradiction={base['contradiction']:.6f} "
                f"| reproduced support={r['support']:.6f} contradiction={r['contradiction']:.6f} "
                f"| delta_support={ds:+.6f} delta_contradiction={dc:+.6f} | within_tolerance={within}"
            )

    print("\n--- all 29 results ---")
    for r in results:
        print(
            f"  [{r['pair_id']:28s}] support={r['support']:.4f} contradiction={r['contradiction']:.4f} "
            f"neutral={r['raw_softmax_by_label'].get('neutral', float('nan')):.4f} stratum={r['stratum']}"
        )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", required=True)
    ap.parse_args()
    run_real()
