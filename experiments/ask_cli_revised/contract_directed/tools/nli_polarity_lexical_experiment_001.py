"""The authorized controlled lexical-polarity experiment (2026-09-28 authorization), following up
`nli-four-span-ablation-001`'s finding that span 3 ("a negative correlation was found...") combined with span 1
and/or span 2 ("a positive correlation... was found/detected") produces catastrophic self-entailment failure.

Per `NLI_FOUR_SPAN_ABLATION_001_ADDENDUM.md`: this experiment does NOT test a complete explanation of every
depressed score in that ablation (`1+2+4`'s own depression is a separate, unexplained anomaly, retained here
only as a reproduction control, never re-interpreted).

## Three text conditions, span 3 only ever edited, spans 1/2 and everything else byte-identical to source

- **A -- source-verbatim.** No edits.
- **B -- polarity-preserving lexical paraphrase.** "A negative correlation was found" -> "An inverse
  correlation was found" (the grammatical article changes A->An because "inverse" starts with a vowel sound;
  every other character of span 3, and all of spans 1/2, is untouched). SYNTHETIC DIAGNOSTIC TEXT -- never
  source-verbatim evidence.
- **C -- meaning-changing sign-flip control.** "A negative correlation was found" -> "A positive correlation
  was found". **COUNTERFACTUAL, SCIENTIFICALLY UNFAITHFUL.** Must never be treated as, or enter, evidence
  fixtures, eligibility judgments, source-supported claims, or researcher-facing synthesis as a finding from
  paper 20 -- it asserts the opposite of what paper 20 actually reports.

Every replacement is recorded as a machine-checkable edit receipt (`build_edit_receipt`), asserting the
replaced phrase is exactly what changed and everything else is byte-identical.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

RUNS_DIR = Path(r"C:\Users\cliff\callosum-data\contract-directed-slice\runs")
PACKET_PATH = RUNS_DIR / "replay-eligibility-001" / "frozen_packet_03_c6_36da02d416d1.json"
ABLATION_RAW_PATH = RUNS_DIR / "nli-four-span-ablation-001" / "01_raw_scores.json"
DIAGNOSTIC_001_RAW = RUNS_DIR / "nli-boundary-diagnostic-001" / "01_raw_scores.json"

NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"
CONTROL_REPRODUCTION_TOLERANCE = 1e-3  # same justification as every prior pass: repeated exact reproduction

TARGET_LOCATORS = {
    "span1": (20, 25269, 945, 1060),
    "span2": (20, 25269, 1061, 1180),
    "span3": (20, 25269, 1181, 1320),
}

ORIGINAL_PHRASE = "A negative correlation was found"
PHRASE_B = "An inverse correlation was found"  # polarity-preserving paraphrase; article A->An
PHRASE_C = "A positive correlation was found"  # counterfactual sign-flip


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_source_spans() -> dict[str, str]:
    """span1/span2/span3 verbatim text, resolved from the real frozen packet -- never from this module's own
    docstring or any prompt."""
    pkt = _load(PACKET_PATH)
    assert pkt["packet_id"] == "36da02d416d1" and pkt["paper_id"] == 20
    by_offset = {}
    for part in pkt["parts"]:
        p0 = part["pieces"][0]
        by_offset[(pkt["paper_id"], p0["chunk_id"], p0["start"], p0["end"])] = part["text"]
    spans = {}
    for name, loc in TARGET_LOCATORS.items():
        assert loc in by_offset, f"locator for {name} not found in the packet"
        spans[name] = by_offset[loc]
    return spans


def build_edit_receipt(original: str, replacement_phrase: str) -> dict:
    """Asserts ORIGINAL_PHRASE is a literal, unique substring of `original`, and that replacing it with
    `replacement_phrase` changes NOTHING else. Returns a machine-checkable receipt."""
    assert original.count(ORIGINAL_PHRASE) == 1, f"expected exactly one occurrence of {ORIGINAL_PHRASE!r}"
    idx = original.index(ORIGINAL_PHRASE)
    edited = original[:idx] + replacement_phrase + original[idx + len(ORIGINAL_PHRASE) :]
    # everything before and after the replaced phrase must be byte-identical
    assert original[:idx] == edited[:idx]
    assert original[idx + len(ORIGINAL_PHRASE) :] == edited[idx + len(replacement_phrase) :]
    return {
        "original_phrase": ORIGINAL_PHRASE,
        "replacement_phrase": replacement_phrase,
        "position": idx,
        "prefix_unchanged": original[:idx],
        "suffix_unchanged": original[idx + len(ORIGINAL_PHRASE) :],
        "edited_text": edited,
    }


def build_span3_variants(span3_verbatim: str) -> dict[str, dict]:
    receipt_b = build_edit_receipt(span3_verbatim, PHRASE_B)
    receipt_c = build_edit_receipt(span3_verbatim, PHRASE_C)
    return {
        "A": {"text": span3_verbatim, "receipt": None},
        "B": {"text": receipt_b["edited_text"], "receipt": receipt_b},
        "C": {"text": receipt_c["edited_text"], "receipt": receipt_c},
    }


def ablation_baseline(pair_id: str) -> dict:
    raw = _load(ABLATION_RAW_PATH)
    r = next(x for x in raw["results"] if x["pair_id"] == pair_id)
    return {"premise": r["premise"], "support": r["support"], "contradiction": r["contradiction"]}


def historical_control_baselines() -> dict:
    raw = _load(DIAGNOSTIC_001_RAW)
    by_id = {r["id"]: r for r in raw["results"]}
    return {
        "c9": {
            "support": by_id["self_entail_c9"]["support"],
            "contradiction": by_id["self_entail_c9"]["contradiction"],
        },
        "c11": {
            "support": by_id["self_entail_c11"]["support"],
            "contradiction": by_id["self_entail_c11"]["contradiction"],
        },
    }


def control_premises() -> dict:
    from experiments.ask_cli_revised.contract_directed.tools import nli_premise_population_eval as observed

    inv = observed.inventory()
    by_unit_ids = {tuple(p["unit_ids"]): p for p in inv["premises"]}
    return {"c9": by_unit_ids[("U1",)]["premise"], "c11": by_unit_ids[("U2", "U3")]["premise"]}


def build_execution_manifest() -> dict:
    spans = resolve_source_spans()
    span3_variants = build_span3_variants(spans["span3"])

    # A-condition reproduction: verify byte-for-byte against the ablation's own frozen A premises
    a13 = spans["span1"] + " " + spans["span3"]
    a23 = spans["span2"] + " " + spans["span3"]
    a123 = spans["span1"] + " " + spans["span2"] + " " + spans["span3"]
    baseline_13 = ablation_baseline("combo_1+3")
    baseline_23 = ablation_baseline("combo_2+3")
    baseline_123 = ablation_baseline("combo_1+2+3")
    assert a13 == baseline_13["premise"], "A/1+3 does not reproduce the ablation's frozen premise byte-for-byte"
    assert a23 == baseline_23["premise"], "A/2+3 does not reproduce the ablation's frozen premise byte-for-byte"
    assert a123 == baseline_123["premise"], "A/1+2+3 does not reproduce the ablation's frozen premise byte-for-byte"

    constructions = {
        "1+3": {"spans": ["span1", "span3"], "baseline": baseline_13},
        "2+3": {"spans": ["span2", "span3"], "baseline": baseline_23},
        "1+2+3": {"spans": ["span1", "span2", "span3"], "baseline": baseline_123},
    }

    pairs = []
    for construction_id, info in constructions.items():
        for condition in ("A", "B", "C"):
            parts = []
            for span_name in info["spans"]:
                parts.append(span3_variants[condition]["text"] if span_name == "span3" else spans[span_name])
            premise = " ".join(parts)
            pairs.append(
                {
                    "pair_id": f"{construction_id}_{condition}",
                    "stratum": "primary",
                    "construction": construction_id,
                    "condition": condition,
                    "premise": premise,
                    "sha256": hashlib.sha256(premise.encode("utf-8")).hexdigest(),
                    "edit_receipt": span3_variants[condition]["receipt"],
                    "origin": "source_verbatim" if condition == "A" else "synthetic_diagnostic",
                    "counterfactual": condition == "C",
                    "historical_baseline": (
                        {"support": info["baseline"]["support"], "contradiction": info["baseline"]["contradiction"]}
                        if condition == "A"
                        else None
                    ),
                }
            )

    # three single-span-3 controls (A/B/C), isolating whether the edited span self-entails ALONE
    for condition in ("A", "B", "C"):
        premise = span3_variants[condition]["text"]
        pairs.append(
            {
                "pair_id": f"span3_alone_{condition}",
                "stratum": "single_span_control",
                "construction": "span3_alone",
                "condition": condition,
                "premise": premise,
                "sha256": hashlib.sha256(premise.encode("utf-8")).hexdigest(),
                "edit_receipt": span3_variants[condition]["receipt"],
                "origin": "source_verbatim" if condition == "A" else "synthetic_diagnostic",
                "counterfactual": condition == "C",
                "historical_baseline": None,
            }
        )

    # three reproduction controls: c9, c11 (from diagnostic-001), and 1+2+4 (from the four-span ablation)
    hist = historical_control_baselines()
    ctrl_premises = control_premises()
    combo_124 = ablation_baseline("combo_1+2+4")
    pairs.append(
        {
            "pair_id": "reproduction_c9",
            "stratum": "reproduction_control",
            "construction": "c9",
            "condition": None,
            "premise": ctrl_premises["c9"],
            "sha256": hashlib.sha256(ctrl_premises["c9"].encode("utf-8")).hexdigest(),
            "edit_receipt": None,
            "origin": "source_verbatim",
            "counterfactual": False,
            "historical_baseline": hist["c9"],
        }
    )
    pairs.append(
        {
            "pair_id": "reproduction_c11",
            "stratum": "reproduction_control",
            "construction": "c11",
            "condition": None,
            "premise": ctrl_premises["c11"],
            "sha256": hashlib.sha256(ctrl_premises["c11"].encode("utf-8")).hexdigest(),
            "edit_receipt": None,
            "origin": "source_verbatim",
            "counterfactual": False,
            "historical_baseline": hist["c11"],
        }
    )
    pairs.append(
        {
            "pair_id": "reproduction_1+2+4",
            "stratum": "reproduction_control",
            "construction": "1+2+4",
            "condition": None,
            "premise": combo_124["premise"],
            "sha256": hashlib.sha256(combo_124["premise"].encode("utf-8")).hexdigest(),
            "edit_receipt": None,
            "origin": "source_verbatim",
            "counterfactual": False,
            "historical_baseline": {"support": combo_124["support"], "contradiction": combo_124["contradiction"]},
        }
    )

    assert len(pairs) == 15, f"expected exactly 15 pairs, built {len(pairs)}"
    assert len({p["sha256"] for p in pairs}) == 15, "expected 15 distinct premise strings, found a collision"

    return {
        "authorization": "2026-09-28 controlled lexical-polarity experiment",
        "original_phrase": ORIGINAL_PHRASE,
        "phrase_b": PHRASE_B,
        "phrase_c": PHRASE_C,
        "control_reproduction_tolerance": CONTROL_REPRODUCTION_TOLERANCE,
        "total_pairs": len(pairs),
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


EVAL_DIR = RUNS_DIR / "nli-polarity-lexical-experiment-001"

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
        "nli-premise-population-eval-001",
        "nli-prospective-corpus-eval-001",
        "nli-prospective-pilot-001",
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
    manifest = build_execution_manifest()
    tokenize_and_verify(manifest["pairs"])

    import psutil

    vm = psutil.virtual_memory()
    mem_report = {"available_gb": round(vm.available / 1e9, 2), "total_gb": round(vm.total / 1e9, 2)}
    print(f"Memory: {mem_report['available_gb']} GB available / {mem_report['total_gb']} GB total")
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

    print("\n--- reproduction checks ---")
    for r in results:
        if r["historical_baseline"] is not None:
            base = r["historical_baseline"]
            ds, dc = r["support"] - base["support"], r["contradiction"] - base["contradiction"]
            within = abs(ds) <= CONTROL_REPRODUCTION_TOLERANCE and abs(dc) <= CONTROL_REPRODUCTION_TOLERANCE
            print(
                f"  {r['pair_id']}: historical support={base['support']:.6f} contradiction={base['contradiction']:.6f} "
                f"| reproduced support={r['support']:.6f} contradiction={r['contradiction']:.6f} "
                f"| delta_support={ds:+.6f} delta_contradiction={dc:+.6f} | within_tolerance={within}"
            )

    print("\n--- all 15 results ---")
    for r in results:
        print(
            f"  [{r['pair_id']:16s}] support={r['support']:.4f} contradiction={r['contradiction']:.4f} "
            f"neutral={r['raw_softmax_by_label'].get('neutral', float('nan')):.4f} stratum={r['stratum']}"
        )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", required=True)
    ap.parse_args()
    run_real()
