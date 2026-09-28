"""Bounded NLI-only diagnostic batch (2026-09-28 authorization) -- forensic follow-up to the
`gate2-diagnostic-002` vs `gate-integration-live-002` screening discrepancy (c9 displayed at
support 0.81 in one run, withheld at support 0.24 in the other on the SAME premise; c11 withheld
in both runs regardless of whether its candidate included the omitted "and a better forager"
finding).

This module is split into a PURE half (`build_pairs`, no model/torch/network import, importable
and testable without touching a GPU/CPU model at all) and a real-inference half (`run_real`,
gated behind `--run`, making exactly ONE `model.predict()` batch call over every pair through the
SAME production scoring path `overview.py`'s `entail` callable uses:
`app.backend.summarization.verification.NLISupportScorer`, pinned to the same
`PINNED_MODEL_REVISIONS[DEFAULT_NLI_MODEL]` revision production uses).

Every base string is loaded VERBATIM from the two saved run records
(`callosum-data/contract-directed-slice/runs/{gate2-diagnostic-002,gate-integration-live-002}/
04_final_record.json`), not retyped by hand. Every derived/controlled variant is built by a single
documented, mechanical string operation on one of those base strings (marker add/remove, clause
restore, clause isolation, direction swap) -- see `build_pairs()`'s inline comments for exactly
which operation produced which pair. No substitute scientific evidence is invented; the three
freshly authored sanity controls (clear_entailment / clear_contradiction / unrelated_control) are
explicitly marked as such and test the scorer's general behavior, not this run's own candidates.

This authorizes AT MOST ONE batch of <=24 pairs. No retry, no adaptive expansion, no threshold
change, no production behavior change. Results land in
`callosum-data/contract-directed-slice/runs/nli-boundary-diagnostic-001/` (data workspace, not
git) -- this file and its test are the only things committed to the worktree.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

RUNS_DIR = Path(r"C:\Users\cliff\callosum-data\contract-directed-slice\runs")
DIAGNOSTIC_RUN_DIR = RUNS_DIR / "nli-boundary-diagnostic-001"
NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"


def _load_record(run_id: str) -> dict:
    with open(RUNS_DIR / run_id / "04_final_record.json", encoding="utf-8") as f:
        return json.load(f)["record"]


def _proposal_text(record: dict, unit_ids: list[str]) -> str:
    for p in record["proposals"]:
        if p["unit_ids"] == unit_ids:
            return p["text"]
    raise KeyError(f"no proposal with unit_ids={unit_ids}")


def _unit_passage(record: dict, unit_id: str) -> str:
    for u in record["units"]:
        if u["unit_id"] == unit_id:
            return u["passage"]
    raise KeyError(f"no unit {unit_id}")


def build_pairs() -> list[dict]:
    """<=24 distinct {id, desc, premise, hypothesis, historical} pairs. Pure -- no model import."""
    diag = _load_record("gate2-diagnostic-002")
    live = _load_record("gate-integration-live-002")

    U1 = _unit_passage(diag, "U1")
    U2 = _unit_passage(diag, "U2")
    U3 = _unit_passage(diag, "U3")
    assert U1 == _unit_passage(live, "U1") and U2 == _unit_passage(live, "U2") and U3 == _unit_passage(live, "U3"), (
        "unit passages differ between the two saved runs -- historical premises are not actually identical"
    )

    PREMISE_C9 = U1
    PREMISE_C11 = U2 + " " + U3

    HYP_A = _proposal_text(diag, ["U1"])  # c9, diagnostic-002, no marker -- support 0.8109
    HYP_B = _proposal_text(live, ["U1"])  # c9, live-002, +"(U1)" marker -- support 0.2352
    HYP_C = _proposal_text(diag, ["U2", "U3"])  # c11, diagnostic-002 -- support 0.2671
    HYP_D = _proposal_text(live, ["U2", "U3"])  # c11, live-002, +"(U2, U3)" marker -- support 0.0131

    marker_b = " (U1)"
    assert HYP_B == HYP_A[:-1] + marker_b + ".", (
        "HYP_B is not HYP_A with a trailing marker inserted before the final period -- "
        "the two candidates differ in more than the marker; do not treat this as a clean minimal pair"
    )
    # A "+marker" reproduces HYP_B byte-for-byte (just asserted), so that mirror-image construction
    # is NOT scored as a separate pair from "B" -- this assertion IS the finding: A and B are a
    # genuine, code-confirmed minimal pair differing in exactly one feature.

    marker_d = " (U2, U3)"
    assert HYP_D.endswith(marker_d + "."), "D does not end with the expected marker"
    d_stripped = HYP_D.replace(marker_d + ".", ".")
    c_with_marker = HYP_C[:-1] + marker_d + "."

    omission_c = "to be less moral."
    omission_d = "to be less moral (U2, U3)."
    assert HYP_C.endswith(omission_c), "C does not end with the expected omission clause"
    assert HYP_D.endswith(omission_d), "D does not end with the expected omission clause"
    c_restored = HYP_C[: -len(omission_c)] + "to be less moral and a better forager."
    d_restored = HYP_D[: -len(omission_d)] + "to be less moral and a better forager (U2, U3)."
    d_restored_stripped = d_restored.replace(marker_d + ".", ".")

    connective = "forager, noting that "
    idx = HYP_D.index(connective) + len(connective)
    clause2_omitted = HYP_D[idx:].replace(marker_d + ".", ".")
    clause2_omitted = clause2_omitted[0].upper() + clause2_omitted[1:]
    clause2_restored = clause2_omitted[:-1] + " and a better forager."

    clear_entailment = "The scarred face was judged less moral by participants with greater cultural exposure."
    clear_contradiction = "Hadza with greater exposure to other cultures expected the scarred face to be MORE moral."
    unrelated = "The central bank raised interest rates and the stock market fell sharply the same afternoon."

    generic_trailing = HYP_A[:-1] + " (see above)."
    marker_leading = "(U1) " + HYP_A

    pairs = [
        dict(
            id="A",
            desc="c9, diagnostic-002 candidate verbatim (no marker) -- historical repro",
            premise=PREMISE_C9,
            hypothesis=HYP_A,
            historical=dict(support=0.8108597993850708, contradiction=0.12746837735176086),
        ),
        dict(
            id="B",
            desc="c9, live-002 candidate verbatim (marker appended) -- historical repro",
            premise=PREMISE_C9,
            hypothesis=HYP_B,
            historical=dict(support=0.23521043360233307, contradiction=0.231438547372818),
        ),
        dict(
            id="C",
            desc="c11, diagnostic-002 candidate verbatim -- historical repro",
            premise=PREMISE_C11,
            hypothesis=HYP_C,
            historical=dict(support=0.2671320140361786, contradiction=0.1451309770345688),
        ),
        dict(
            id="D",
            desc="c11, live-002 candidate verbatim (marker appended) -- historical repro",
            premise=PREMISE_C11,
            hypothesis=HYP_D,
            historical=dict(support=0.013148654252290726, contradiction=0.3011533319950104),
        ),
        dict(
            id="D_minus_marker",
            desc="D with its marker removed (isolates the marker's effect on D alone)",
            premise=PREMISE_C11,
            hypothesis=d_stripped,
            historical=None,
        ),
        dict(
            id="C_plus_marker",
            desc="C with the marker appended (mirror of D, built from C not D)",
            premise=PREMISE_C11,
            hypothesis=c_with_marker,
            historical=None,
        ),
        dict(
            id="C_restored",
            desc="C with the forager clause restored, no marker",
            premise=PREMISE_C11,
            hypothesis=c_restored,
            historical=None,
        ),
        dict(
            id="D_restored",
            desc="D with the forager clause restored, marker KEPT",
            premise=PREMISE_C11,
            hypothesis=d_restored,
            historical=None,
        ),
        dict(
            id="D_restored_no_marker",
            desc="D fully corrected: omission restored AND marker removed",
            premise=PREMISE_C11,
            hypothesis=d_restored_stripped,
            historical=None,
        ),
        dict(
            id="clause1_procedure_only",
            desc="U2 procedure clause alone, scored against the full c11 premise",
            premise=PREMISE_C11,
            hypothesis=U2,
            historical=None,
        ),
        dict(
            id="clause2_omitted_only",
            desc="Result clause alone, omission-affected wording (from D), no marker",
            premise=PREMISE_C11,
            hypothesis=clause2_omitted,
            historical=None,
        ),
        dict(
            id="clause2_restored_only",
            desc="Result clause alone, complete wording, no marker",
            premise=PREMISE_C11,
            hypothesis=clause2_restored,
            historical=None,
        ),
        dict(
            id="self_entail_c9",
            desc="Self-entailment ceiling: U1 premise scored against itself verbatim",
            premise=PREMISE_C9,
            hypothesis=U1,
            historical=None,
        ),
        dict(
            id="self_entail_c11",
            desc="Self-entailment ceiling: c11 premise scored against itself verbatim",
            premise=PREMISE_C11,
            hypothesis=PREMISE_C11,
            historical=None,
        ),
        dict(
            id="clear_entailment",
            desc="Freshly authored clean paraphrase entailment control",
            premise=U3,
            hypothesis=clear_entailment,
            historical=None,
        ),
        dict(
            id="clear_contradiction",
            desc="Freshly authored negated/reversed contradiction control",
            premise=U3,
            hypothesis=clear_contradiction,
            historical=None,
        ),
        dict(
            id="unrelated_control",
            desc="Freshly authored off-topic hypothesis, unrelated to the premise",
            premise=PREMISE_C9,
            hypothesis=unrelated,
            historical=None,
        ),
        dict(
            id="reversed_B",
            desc="Pair-direction control: B's own pair with premise/hypothesis SWAPPED",
            premise=HYP_B,
            hypothesis=PREMISE_C9,
            historical=None,
        ),
        dict(
            id="generic_trailing_parenthetical",
            desc="A with a NON-citation trailing parenthetical appended",
            premise=PREMISE_C9,
            hypothesis=generic_trailing,
            historical=None,
        ),
        dict(
            id="marker_leading",
            desc="A with the marker moved to the START instead of the end",
            premise=PREMISE_C9,
            hypothesis=marker_leading,
            historical=None,
        ),
    ]
    assert len(pairs) <= 24, f"{len(pairs)} exceeds the authorized 24-pair cap"
    seen = set()
    for p in pairs:
        key = (p["premise"], p["hypothesis"])
        assert key not in seen, f"duplicate (premise, hypothesis) pair at id={p['id']}"
        seen.add(key)
    return pairs


def write_manifest(run_dir: Path, pairs: list[dict]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "00_manifest.json"
    payload = {
        "diagnostic": "nli-boundary-diagnostic-001",
        "purpose": "bounded, pre-registered NLI-only diagnostic on the c9/c11 gate2-diagnostic-002 vs "
        "gate-integration-live-002 screening discrepancy",
        "model": NLI_MODEL,
        "revision": NLI_REVISION,
        "pair_count": len(pairs),
        "pairs": pairs,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def read_manifest(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_real() -> None:
    """The one authorized live inference batch. Loads the SAME production scorer class, pinned to
    the SAME revision, and makes exactly one `model.predict()` call over every pair."""
    pairs = build_pairs()

    import psutil

    vm = psutil.virtual_memory()
    mem_report = {"available_gb": round(vm.available / 1e9, 2), "total_gb": round(vm.total / 1e9, 2)}
    print(
        f"Memory: {mem_report['available_gb']} GB available / {mem_report['total_gb']} GB total "
        "(general precaution only -- this is a ~90MB 6-layer CPU CrossEncoder, NOT the Qwen/Ollama "
        "LLM memory floor from prior stages; that guard and its override do not apply to this code "
        "path and neither is invoked here)"
    )

    manifest_path = write_manifest(DIAGNOSTIC_RUN_DIR, pairs)
    reread = read_manifest(manifest_path)
    assert reread["pairs"] == pairs, "pre-registration manifest did not round-trip before inference"
    print(f"Pre-registered {len(pairs)} pairs to {manifest_path} and confirmed read-back BEFORE inference.")

    from app.backend.model_runtime import PINNED_MODEL_REVISIONS
    from app.backend.summarization.stance import DEFAULT_NLI_MODEL
    from app.backend.summarization.verification import NLISupportScorer, _values_from_row

    assert DEFAULT_NLI_MODEL == NLI_MODEL
    pinned = PINNED_MODEL_REVISIONS.get(DEFAULT_NLI_MODEL)
    assert pinned == NLI_REVISION, f"pinned revision mismatch: code says {pinned}, expected {NLI_REVISION}"

    scorer = NLISupportScorer(revision=pinned, fallback_scorer=None)  # no silent fallback substitution
    model = scorer._load_model()
    print(f"Loaded model: {type(model).__name__}, revision={pinned}")
    id2label = getattr(getattr(model, "model", None), "config", None)
    id2label = getattr(id2label, "id2label", None)
    print(f"id2label (from the loaded model's own config): {id2label}")

    call_pairs = [(p["premise"], p["hypothesis"]) for p in pairs]
    raw_scores = model.predict(list(call_pairs), apply_softmax=True)  # THE ONE call
    print(f"ONE model.predict() call completed, {len(raw_scores)} rows returned.")
    assert len(raw_scores) == len(pairs)

    results = []
    for p, row in zip(pairs, raw_scores, strict=True):
        values = [float(v) for v in row]
        support, contradiction = _values_from_row(row, model=model)
        by_label = {label: values[int(idx)] for idx, label in id2label.items()} if isinstance(id2label, dict) else {}
        results.append(
            {
                "id": p["id"],
                "desc": p["desc"],
                "support": support,
                "contradiction": contradiction,
                "raw_softmax_by_label": by_label,
                "raw_softmax_row": values,
                "historical": p["historical"],
            }
        )

    out_path = DIAGNOSTIC_RUN_DIR / "01_raw_scores.json"
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", required=True)
    ap.parse_args()
    run_real()
