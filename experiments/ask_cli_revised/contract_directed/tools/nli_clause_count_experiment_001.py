"""The authorized clause-count/placement follow-up (2026-09-28), testing why `1+2+3` resisted the prior
lexical interventions (`nli-polarity-lexical-experiment-001`) more strongly than `1+3`/`2+3`. Span 3 stays
completely source-verbatim in every condition here; span 1 and/or span 2 are counterfactually flipped instead.

## Two edits, span 3 never touched

- **F1 -- flip span 1.** "A positive correlation was found" -> "An inverse correlation was found" (article
  A->An). Reverses span 1's reported direction.
- **F2 -- flip span 2.** "a positive correlation between" -> "an inverse correlation between" (article a->an,
  lowercase because the phrase is mid-sentence in span 2, not sentence-initial). Reverses span 2's reported
  direction.

**Both are counterfactual and scientifically unfaithful** -- they reverse what paper 20 actually reports.
Every F1/F2-touched pair is `origin="synthetic_diagnostic"`, `counterfactual=True`, backed by a machine-
checkable edit receipt. Neither is a paraphrase attempt (unlike the prior experiment's condition B); no
"negative" wording variant is introduced here, per the authorization's explicit exclusion.

The prior experiment's `1+2+3_C` score (span 3 counterfactually flipped instead) is retained here only as
**external saved context** -- never re-scored, never counted among this pass's 13 pairs.
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
LEXICAL_EXPERIMENT_RAW_PATH = RUNS_DIR / "nli-polarity-lexical-experiment-001" / "01_raw_scores.json"
DIAGNOSTIC_001_RAW = RUNS_DIR / "nli-boundary-diagnostic-001" / "01_raw_scores.json"

NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"
CONTROL_REPRODUCTION_TOLERANCE = 1e-3  # same justification as every prior pass: repeated exact reproduction

TARGET_LOCATORS = {
    "span1": (20, 25269, 945, 1060),
    "span2": (20, 25269, 1061, 1180),
    "span3": (20, 25269, 1181, 1320),
}

F1_ORIGINAL = "A positive correlation was found"
F1_REPLACEMENT = "An inverse correlation was found"
F2_ORIGINAL = "a positive correlation between"
F2_REPLACEMENT = "an inverse correlation between"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_source_spans() -> dict[str, str]:
    """span1/span2/span3 verbatim text, resolved from the real frozen packet -- never from this prompt."""
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


def build_edit_receipt(original: str, target_phrase: str, replacement_phrase: str) -> dict:
    assert original.count(target_phrase) == 1, f"expected exactly one occurrence of {target_phrase!r}"
    idx = original.index(target_phrase)
    edited = original[:idx] + replacement_phrase + original[idx + len(target_phrase) :]
    assert original[:idx] == edited[:idx]
    assert original[idx + len(target_phrase) :] == edited[idx + len(replacement_phrase) :]
    return {
        "original_phrase": target_phrase,
        "replacement_phrase": replacement_phrase,
        "position": idx,
        "prefix_unchanged": original[:idx],
        "suffix_unchanged": original[idx + len(target_phrase) :],
        "edited_text": edited,
    }


def build_flipped_spans(spans: dict[str, str]) -> dict[str, dict]:
    r1 = build_edit_receipt(spans["span1"], F1_ORIGINAL, F1_REPLACEMENT)
    r2 = build_edit_receipt(spans["span2"], F2_ORIGINAL, F2_REPLACEMENT)
    return {
        "span1_F1": {"text": r1["edited_text"], "receipt": r1},
        "span2_F2": {"text": r2["edited_text"], "receipt": r2},
    }


def ablation_baseline(pair_id: str) -> dict:
    raw = _load(ABLATION_RAW_PATH)
    r = next(x for x in raw["results"] if x["pair_id"] == pair_id)
    return {"premise": r["premise"], "support": r["support"], "contradiction": r["contradiction"]}


def lexical_experiment_external_comparison(pair_id: str) -> dict:
    """Reads (never re-scores) a result from the prior nli-polarity-lexical-experiment-001 batch."""
    raw = _load(LEXICAL_EXPERIMENT_RAW_PATH)
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
    flipped = build_flipped_spans(spans)

    baseline_123 = ablation_baseline("combo_1+2+3")
    baseline_13 = ablation_baseline("combo_1+3")
    baseline_23 = ablation_baseline("combo_2+3")
    baseline_124 = ablation_baseline("combo_1+2+4")
    hist = historical_control_baselines()
    ctrl_premises = control_premises()

    # reproduce the historical A-condition premises byte-for-byte as an assertion before proceeding
    a123 = spans["span1"] + " " + spans["span2"] + " " + spans["span3"]
    a13 = spans["span1"] + " " + spans["span3"]
    a23 = spans["span2"] + " " + spans["span3"]
    assert a123 == baseline_123["premise"]
    assert a13 == baseline_13["premise"]
    assert a23 == baseline_23["premise"]

    def _pair(pair_id, construction, premise, edited_spans, baseline=None):
        return {
            "pair_id": pair_id,
            "construction": construction,
            "premise": premise,
            "sha256": hashlib.sha256(premise.encode("utf-8")).hexdigest(),
            "edited_spans": edited_spans,
            "origin": "source_verbatim" if not edited_spans else "synthetic_diagnostic",
            "counterfactual": bool(edited_spans),
            "historical_baseline": baseline,
        }

    pairs = [
        # 4 three-span conditions
        _pair("1+2+3_A", "triple", a123, [], baseline_123),
        _pair(
            "1(F1)+2+3", "triple", flipped["span1_F1"]["text"] + " " + spans["span2"] + " " + spans["span3"], ["span1"]
        ),
        _pair(
            "1+2(F2)+3", "triple", spans["span1"] + " " + flipped["span2_F2"]["text"] + " " + spans["span3"], ["span2"]
        ),
        _pair(
            "1(F1)+2(F2)+3",
            "triple",
            flipped["span1_F1"]["text"] + " " + flipped["span2_F2"]["text"] + " " + spans["span3"],
            ["span1", "span2"],
        ),
        # 2 edited two-span conditions
        _pair("1(F1)+3", "pair_edited", flipped["span1_F1"]["text"] + " " + spans["span3"], ["span1"]),
        _pair("2(F2)+3", "pair_edited", flipped["span2_F2"]["text"] + " " + spans["span3"], ["span2"]),
        # 2 source-verbatim two-span reproduction controls
        _pair("1+3", "pair_verbatim", a13, [], baseline_13),
        _pair("2+3", "pair_verbatim", a23, [], baseline_23),
        # 2 edited single-span controls
        _pair("1(F1)", "single_edited", flipped["span1_F1"]["text"], ["span1"]),
        _pair("2(F2)", "single_edited", flipped["span2_F2"]["text"], ["span2"]),
    ]
    # attach edit receipts to every pair that has edited_spans
    for p in pairs:
        if "span1" in p["edited_spans"] and "span2" in p["edited_spans"]:
            p["edit_receipt"] = {"F1": flipped["span1_F1"]["receipt"], "F2": flipped["span2_F2"]["receipt"]}
        elif "span1" in p["edited_spans"]:
            p["edit_receipt"] = {"F1": flipped["span1_F1"]["receipt"]}
        elif "span2" in p["edited_spans"]:
            p["edit_receipt"] = {"F2": flipped["span2_F2"]["receipt"]}
        else:
            p["edit_receipt"] = None

    # 3 additional historical reproduction controls
    pairs.append(_pair("reproduction_c9", "reproduction_control", ctrl_premises["c9"], [], hist["c9"]))
    pairs.append(_pair("reproduction_c11", "reproduction_control", ctrl_premises["c11"], [], hist["c11"]))
    pairs.append(
        _pair(
            "reproduction_1+2+4",
            "reproduction_control",
            baseline_124["premise"],
            [],
            {"support": baseline_124["support"], "contradiction": baseline_124["contradiction"]},
        )
    )
    for p in pairs[-3:]:
        p["edit_receipt"] = None

    assert len(pairs) == 13, f"expected exactly 13 pairs, built {len(pairs)}"
    assert len({p["sha256"] for p in pairs}) == 13, "expected 13 distinct premise strings, found a collision"

    return {
        "authorization": "2026-09-28 clause-count/placement follow-up",
        "f1": {"original": F1_ORIGINAL, "replacement": F1_REPLACEMENT},
        "f2": {"original": F2_ORIGINAL, "replacement": F2_REPLACEMENT},
        "external_comparison_1_2_3_C": lexical_experiment_external_comparison("1+2+3_C"),
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


EVAL_DIR = RUNS_DIR / "nli-clause-count-experiment-001"

PROTECTED_RUN_DIRS = frozenset(
    {
        "gate-integration-001",
        "gate-integration-live-001",
        "gate-integration-live-002",
        "gate2-diagnostic-001",
        "gate2-diagnostic-002",
        "nli-boundary-diagnostic-001",
        "nli-boundary-diagnostic-002",
        "nli-four-span-ablation-001",
        "nli-polarity-lexical-experiment-001",
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

    print("\n--- all 13 results ---")
    for r in results:
        print(
            f"  [{r['pair_id']:18s}] support={r['support']:.4f} contradiction={r['contradiction']:.4f} "
            f"neutral={r['raw_softmax_by_label'].get('neutral', float('nan')):.4f}"
        )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", required=True)
    ap.parse_args()
    run_real()
