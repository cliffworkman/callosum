"""The authorized four-span self-entailment ablation of `prospective_7e44a7f4226a`, the severe failure found
by `nli-prospective-pilot-001` (2026-09-28 authorization).

Target: paper 20, packet `36da02d416d1` (eligibility replay), unit `M7`, slot `relatum_a` -- the exact
`eligibility_slot_group` construction that scored support=0.0005305781378410757,
contradiction=0.9970700740814209 in the pilot (more severe than c11's own known failure).

The 4 canonical locators are resolved from the frozen packet file itself -- **never reconstructed from
memory or from an authorization prompt**:

1. (20, 25269, 945, 1060)
2. (20, 25269, 1061, 1180)
3. (20, 25269, 1181, 1320)
4. (20, 25269, 1478, 1613)

`assert_full_premise_reproduces_pilot_baseline()` joins all 4 resolved texts with the SAME production join
convention (`" ".join(...)`) and asserts the result is byte-for-byte identical to the pilot's own frozen
`prospective_7e44a7f4226a` premise -- if this fails, nothing downstream should be trusted, and this module
raises rather than proceeding.

## The 15 combinations

Every nonempty subset of {1,2,3,4}, spans kept in their **original relative order** (never rearranged), joined
by a single space (the same convention `nli_pair`/`_span_from_part` use elsewhere in this arc): 4 singles + 6
pairs + 4 triples + 1 complete four-span = 15. No alternate punctuation, no text inserted to fill the real gap
between span 3 (ends 1320) and span 4 (starts 1478) -- that gap is a documented, preserved property of every
combination that includes span 4, not something this ablation fills in.

Plus the 2 historical controls (c9, c11), for **17 pairs total**. These 15 combinations are deliberately
related perturbations of ONE source-derived premise, not 15 independent examples -- never used here to
estimate a general failure rate or calibrate anything.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

RUNS_DIR = Path(r"C:\Users\cliff\callosum-data\contract-directed-slice\runs")
PACKET_PATH = RUNS_DIR / "replay-eligibility-001" / "frozen_packet_03_c6_36da02d416d1.json"
PILOT_RAW_PATH = RUNS_DIR / "nli-prospective-pilot-001" / "01_raw_scores.json"
DIAGNOSTIC_001_RAW = RUNS_DIR / "nli-boundary-diagnostic-001" / "01_raw_scores.json"

NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"

TARGET_LOCATORS = [
    (20, 25269, 945, 1060),
    (20, 25269, 1061, 1180),
    (20, 25269, 1181, 1320),
    (20, 25269, 1478, 1613),
]

CONTROL_REPRODUCTION_TOLERANCE = 1e-3  # same justification as the pilot: repeated exact reproduction historically


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_span_texts() -> list[str]:
    """Resolves the 4 target locators' exact text from the frozen packet file, in TARGET_LOCATORS order."""
    pkt = _load(PACKET_PATH)
    assert pkt["packet_id"] == "36da02d416d1"
    assert pkt["paper_id"] == 20
    by_offset = {}
    for part in pkt["parts"]:
        p0 = part["pieces"][0]
        by_offset[(pkt["paper_id"], p0["chunk_id"], p0["start"], p0["end"])] = part["text"]
    missing = [loc for loc in TARGET_LOCATORS if loc not in by_offset]
    assert not missing, f"target locator(s) not found in the packet: {missing}"
    return [by_offset[loc] for loc in TARGET_LOCATORS]


def pilot_full_premise_baseline() -> dict:
    """The EXACT, unrounded historical score for the complete 4-span premise, from the pilot's own saved raw
    output -- never the rounded '0.0005' figure from prose."""
    raw = _load(PILOT_RAW_PATH)
    r = next(x for x in raw["results"] if x["pair_id"] == "prospective_7e44a7f4226a")
    return {"premise": r["premise"], "support": r["support"], "contradiction": r["contradiction"]}


def assert_full_premise_reproduces_pilot_baseline(span_texts: list[str]) -> str:
    joined = " ".join(span_texts)
    baseline = pilot_full_premise_baseline()
    assert joined == baseline["premise"], (
        "joining all 4 resolved spans does NOT reproduce the pilot's frozen full premise byte-for-byte -- "
        "stopping before inference, per the authorization's explicit instruction"
    )
    return joined


def historical_control_baselines() -> dict:
    """c9/c11 self-pair baselines, recovered from the actual saved diagnostic-001 raw output (not rounded
    handback prose, not the candidate-vs-premise score)."""
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


def build_combinations(span_texts: list[str]) -> list[dict]:
    """All 15 nonempty subsets of the 4 spans, indices kept in original order, joined by a single space."""
    combos = []
    for size in (1, 2, 3, 4):
        for idx_tuple in itertools.combinations(range(4), size):  # combinations() already yields ascending order
            texts = [span_texts[i] for i in idx_tuple]
            premise = " ".join(texts)
            label = "+".join(str(i + 1) for i in idx_tuple)
            combos.append(
                {
                    "pair_id": f"combo_{label}",
                    "spans_included": [i + 1 for i in idx_tuple],
                    "span_count": size,
                    "premise": premise,
                    "sha256": hashlib.sha256(premise.encode("utf-8")).hexdigest(),
                    "includes_gap_after_span3": 3 in [i + 1 for i in idx_tuple] and 4 in [i + 1 for i in idx_tuple],
                }
            )
    assert len(combos) == 15, f"expected exactly 15 combinations, built {len(combos)}"
    assert len({c["sha256"] for c in combos}) == 15, "expected 15 distinct combination premises, found a collision"
    return combos


def build_execution_manifest() -> dict:
    span_texts = resolve_span_texts()
    full_premise = assert_full_premise_reproduces_pilot_baseline(span_texts)
    combos = build_combinations(span_texts)
    full_combo = next(c for c in combos if c["span_count"] == 4)
    assert full_combo["premise"] == full_premise

    baseline = pilot_full_premise_baseline()
    hist = historical_control_baselines()
    ctrl_premises = control_premises()

    pairs = []
    for c in combos:
        pairs.append(
            {
                "pair_id": c["pair_id"],
                "stratum": "ablation",
                "premise": c["premise"],
                "sha256": c["sha256"],
                "spans_included": c["spans_included"],
                "span_count": c["span_count"],
                "construction": "eligibility_slot_group_ablation",
                "includes_gap_after_span3": c["includes_gap_after_span3"],
                "historical_baseline": (
                    {"support": baseline["support"], "contradiction": baseline["contradiction"]}
                    if c["span_count"] == 4
                    else None
                ),
            }
        )
    for cid in ("c9", "c11"):
        pairs.append(
            {
                "pair_id": f"control_{cid}",
                "stratum": "historical_control",
                "premise": ctrl_premises[cid],
                "sha256": hashlib.sha256(ctrl_premises[cid].encode("utf-8")).hexdigest(),
                "spans_included": None,
                "span_count": 1 if cid == "c9" else 2,
                "construction": "historical_observed_production",
                "includes_gap_after_span3": None,
                "historical_baseline": hist[cid],
            }
        )

    assert len(pairs) == 17, f"expected exactly 17 pairs, built {len(pairs)}"
    assert len({p["sha256"] for p in pairs}) == 17, "expected 17 distinct premise strings, found a collision"

    return {
        "authorization": "2026-09-28 four-span self-entailment ablation",
        "target_pair_id": "prospective_7e44a7f4226a",
        "target_locators": TARGET_LOCATORS,
        "source_packet": str(PACKET_PATH),
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


EVAL_DIR = RUNS_DIR / "nli-four-span-ablation-001"

PROTECTED_RUN_DIRS = frozenset(
    {
        "gate-integration-001",
        "gate-integration-live-001",
        "gate-integration-live-002",
        "gate2-diagnostic-001",
        "gate2-diagnostic-002",
        "nli-boundary-diagnostic-001",
        "nli-boundary-diagnostic-002",
        "nli-clause-count-experiment-001",
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

    print("\n--- all 17 results ---")
    for r in results:
        spans = r["spans_included"] if r["spans_included"] else "-"
        print(
            f"  [{r['pair_id']:12s}] spans={spans} support={r['support']:.4f} contradiction={r['contradiction']:.4f} "
            f"neutral={r['raw_softmax_by_label'].get('neutral', float('nan')):.4f}"
        )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", required=True)
    ap.parse_args()
    run_real()
