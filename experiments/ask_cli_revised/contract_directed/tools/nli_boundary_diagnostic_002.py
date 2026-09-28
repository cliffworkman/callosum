"""Bounded NLI-only diagnostic, attempt 002 (2026-09-28 authorization) -- follow-up to
`nli_boundary_diagnostic.py` (attempt 001)'s most important, least-expected result: the c11 premise,
constructed as `U2 + " " + U3` (packet `d37854a6ea62`'s spans p2 and p4), scored 0.0070 entailment /
0.9809 contradiction when paired with a BYTE-IDENTICAL COPY OF ITSELF. That is a failed self-entailment
sanity check. This attempt does NOT assume the cause; it separately tests sentence identity, joining/
formatting, the "more moral"/"less moral" lexical-antonym adjacency between U2 and U3(=p4), and general
multi-sentence self-entailment behavior on unrelated content -- five previously-confounded variables.

Kept explicitly OUT of scope here (per the authorization; see the prior handback for what IS
established there): the c9 citation-marker finding, the "and a better forager" omission (already shown
in attempt 001 not to move c11's score), any threshold/production change, any second live batch.

Every VERBATIM-SOURCE string in this manifest is loaded from the frozen packet file
(`reconstructed_08_c11_d37854a6ea62.json`), not retyped by hand and not taken secondhand through
`04_final_record.json`'s mirror of it (cross-checked identical in the audit; the packet is the
authoritative source). Every SYNTHETIC string (Section C's reworded U2 variants, Section D's neutral
filler) is clearly marked `origin="synthetic_diagnostic"` in its own pair record and is never presented
as source evidence -- U3(=p4) is never edited in any condition.

This module is split into a PURE half (`build_pairs`, `write_manifest`, no model/torch/network import)
and a real-inference half (`run_real`, gated behind `--run`), exactly mirroring attempt 001's shape.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

SLICE_ROOT = Path(r"C:\Users\cliff\callosum-data\contract-directed-slice")
RUNS_DIR = SLICE_ROOT / "runs"
PACKET_PATH = RUNS_DIR / "replay-eligibility-001-offline-analysis" / "reconstructed_08_c11_d37854a6ea62.json"
DIAGNOSTIC_NAME = "nli-boundary-diagnostic-002"
DIAGNOSTIC_RUN_DIR = RUNS_DIR / DIAGNOSTIC_NAME
NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"

# Every directory that must never be written to by this attempt -- the complete listing of
# `runs/` at the time this attempt started, plus this attempt's own name (idempotent re-run
# guard: refuse a second write into an already-populated attempt-002 directory too).
PROTECTED_RUN_DIRS = frozenset(
    {
        "gate-integration-001",
        "gate-integration-live-001",
        "gate-integration-live-002",
        "gate2-diagnostic-001",
        "gate2-diagnostic-002",
        "nli-boundary-diagnostic-001",
        "pilot-001",
        "pilot-prep-003",
        "replay-eligibility-001",
        "replay-eligibility-001-offline-analysis",
    }
)


def _load_packet() -> dict:
    with open(PACKET_PATH, encoding="utf-8") as f:
        return json.load(f)


def _span_text(packet: dict, span_id: str) -> str:
    for part in packet["parts"]:
        if part["span_id"] == span_id:
            return part["text"]
    raise KeyError(f"no span {span_id} in packet {packet.get('packet_id')}")


def build_pairs() -> list[dict]:
    """14 distinct {id, desc, premise, hypothesis, origin, expects, historical} pairs. Pure -- no model import."""
    pkt = _load_packet()
    assert pkt["packet_id"] == "d37854a6ea62"
    assert pkt["paper_id"] == 68

    U2 = _span_text(pkt, "p2")  # procedure: "...asked who they expected to be more moral and a better forager."
    P3 = _span_text(pkt, "p3")  # the skipped middle sentence: minimal-exposure null result
    U3 = _span_text(pkt, "p4")  # finding: "...expected the scarred face to be less moral and a better forager."

    # Cross-checked against 04_final_record.json's own mirrored copies (both prior saved runs) -- identical.
    assert U2.startswith("We presented 123 Hadza")
    assert U3.startswith("Hadza with greater exposure")
    assert P3.startswith("Hadza with minimal exposure")

    premise_original = U2 + " " + U3  # == attempt 001's PREMISE_C11 exactly
    premise_reversed_order = U3 + " " + U2
    premise_newline = U2 + "\n" + U3
    premise_full_context = U2 + " " + P3 + " " + U3  # restores the TRUE source sentence adjacency (all verbatim)

    # ---- Section C: synthetic, question/antonym-isolating rewrites of U2 ONLY. U3 is NEVER edited. ----
    # Original U2 ends "...asked who they expected to be more moral and a better forager."
    c1_u2 = (
        "123 Hadza across ten camps were shown pairs of morphed Hadza faces, one face in each pair "
        "altered to include a scar, and asked a question: which face would be more moral and a better "
        "forager?"
    )  # explicit question mark; KEEPS the "more moral" bigram
    c2_u2 = (
        "We presented 123 Hadza across ten camps pairs of morphed Hadza faces\u2014each with one face "
        "altered to include a scar\u2014and asked who they expected to be judged more favorably for "
        "morality and foraging skill."
    )  # declarative, matches original framing; REMOVES the literal "more moral" bigram
    c3_u2 = (
        "123 Hadza across ten camps were shown pairs of morphed Hadza faces, one face in each pair "
        "altered to include a scar, and asked a question: which face would be judged more favorably for "
        "morality and foraging skill?"
    )  # explicit question mark AND removes the "more moral" bigram

    # ---- Section D: neutral, plainly non-contradictory, unrelated-content sentence-count ladder ----
    d_s1 = "The library added forty new books this spring."
    d_s2 = "Most of the donated titles were novels for young readers."
    d_s3 = "Staff catalogued the new arrivals over two weekends."

    pairs = [
        # -- A. Self-entailment and source composition --
        dict(
            id="A1_U2_self",
            desc="U2 (procedure sentence) alone, scored against itself",
            premise=U2,
            hypothesis=U2,
            origin="verbatim_source",
            expects="entailment (identical text)",
            historical=None,
        ),
        dict(
            id="A2_U3_self",
            desc="U3=p4 (finding sentence) alone, scored against itself",
            premise=U3,
            hypothesis=U3,
            origin="verbatim_source",
            expects="entailment (identical text)",
            historical=None,
        ),
        dict(
            id="A3_U2U3_self_REPRO",
            desc="U2+' '+U3 (the historical c11 premise) against itself "
            "-- REPRODUCTION CHECK of attempt 001's self_entail_c11 result",
            premise=premise_original,
            hypothesis=premise_original,
            origin="verbatim_source",
            expects="entailment (identical text); historically scored 0.0070/0.9809",
            historical=dict(support=0.0070, contradiction=0.9809),
        ),
        dict(
            id="A4_U3U2_self_reversed_order",
            desc="U3+' '+U2 (concatenation order REVERSED) against itself",
            premise=premise_reversed_order,
            hypothesis=premise_reversed_order,
            origin="verbatim_source",
            expects="entailment (identical text); isolates whether order-of-concatenation matters",
            historical=None,
        ),
        dict(
            id="A5_full_context_self",
            desc="U2+' '+P3(skipped middle sentence)+' '+U3, restoring the TRUE "
            "source sentence adjacency, against itself",
            premise=premise_full_context,
            hypothesis=premise_full_context,
            origin="verbatim_source",
            expects="entailment (identical text); tests whether the artificial p2-directly-adjacent-to-p4 "
            "juxtaposition (skipping p3) is what breaks self-entailment",
            historical=None,
        ),
        # -- B. Sentence boundaries and joining --
        dict(
            id="B1_newline_premise_vs_space_hyp",
            desc="Premise=U2+newline+U3; Hypothesis=U2+space+U3 (FIXED, "
            "the original). Isolates the premise-side separator alone.",
            premise=premise_newline,
            hypothesis=premise_original,
            origin="verbatim_source",
            expects="if formatting alone matters, this should differ from A3; if not, similar",
            historical=None,
        ),
        # -- C. Question-finding interaction (SYNTHETIC, U3 always verbatim/unedited) --
        dict(
            id="C1_explicit_question_keep_bigram",
            desc="U2 reworded as an EXPLICIT question, KEEPING the 'more moral' bigram, + verbatim U3, against itself",
            premise=c1_u2 + " " + U3,
            hypothesis=c1_u2 + " " + U3,
            origin="synthetic_diagnostic",
            expects="isolates question-explicitness alone, bigram held constant",
            historical=None,
        ),
        dict(
            id="C2_declarative_remove_bigram",
            desc="U2 reworded to REMOVE the 'more moral' bigram, keeping "
            "declarative framing, + verbatim U3, against itself",
            premise=c2_u2 + " " + U3,
            hypothesis=c2_u2 + " " + U3,
            origin="synthetic_diagnostic",
            expects="isolates antonym-bigram removal alone, question-framing held constant",
            historical=None,
        ),
        dict(
            id="C3_explicit_question_remove_bigram",
            desc="U2 reworded as an explicit question AND with the "
            "'more moral' bigram removed, + verbatim U3, against itself",
            premise=c3_u2 + " " + U3,
            hypothesis=c3_u2 + " " + U3,
            origin="synthetic_diagnostic",
            expects="both manipulations combined -- completes the 2x2 with the original (A3) as the "
            "declarative+bigram cell",
            historical=None,
        ),
        # -- D. General multi-sentence controls, neutral/unrelated content --
        dict(
            id="D1_neutral_1sentence_self",
            desc="One neutral, Hadza-unrelated sentence against itself",
            premise=d_s1,
            hypothesis=d_s1,
            origin="synthetic_diagnostic",
            expects="entailment (identical text, single sentence)",
            historical=None,
        ),
        dict(
            id="D2_neutral_2sentence_self",
            desc="Two neutral, non-contradictory sentences (space-joined) "
            "against itself -- same content family as D1/D3, isolates sentence-count",
            premise=d_s1 + " " + d_s2,
            hypothesis=d_s1 + " " + d_s2,
            origin="synthetic_diagnostic",
            expects="entailment (identical text); tests whether ANY 2-sentence premise fails self-entailment "
            "with this model, independent of Hadza/antonym content",
            historical=None,
        ),
        dict(
            id="D3_neutral_3sentence_self",
            desc="Three neutral, non-contradictory sentences (space-joined) against itself",
            premise=d_s1 + " " + d_s2 + " " + d_s3,
            hypothesis=d_s1 + " " + d_s2 + " " + d_s3,
            origin="synthetic_diagnostic",
            expects="entailment (identical text); tests whether failure worsens with more sentences",
            historical=None,
        ),
        # -- Cross-unit, non-concatenated (no self-entailment structure at all) --
        dict(
            id="X1_U2_premise_U3_hyp",
            desc="Premise=U2 (procedure) alone; Hypothesis=U3=p4 (finding) alone "
            "-- no concatenation, no self-comparison",
            premise=U2,
            hypothesis=U3,
            origin="verbatim_source",
            expects="tests whether the 'more moral'/'less moral' lexical adjacency alone drives high "
            "contradiction even with NO joining/self-entailment structure present",
            historical=None,
        ),
        dict(
            id="X2_U3_premise_U2_hyp",
            desc="Direction control for X1: Premise=U3; Hypothesis=U2",
            premise=U3,
            hypothesis=U2,
            origin="verbatim_source",
            expects="direction-sensitivity check on the cross pair",
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
    """Refuses to write into any protected prior-attempt directory, and refuses to overwrite an
    already-populated attempt-002 directory (idempotent-safety, not a retry mechanism)."""
    name = run_dir.name
    if name in PROTECTED_RUN_DIRS:
        raise RuntimeError(f"refusing to write into protected prior-attempt directory: {name}")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError(f"refusing to overwrite an already-populated directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "00_manifest.json"
    payload = {
        "diagnostic": DIAGNOSTIC_NAME,
        "purpose": "bounded NLI-only diagnostic of the c11 premise self-entailment failure found in "
        "nli-boundary-diagnostic-001 (support=0.0070, contradiction=0.9809 for the premise against a "
        "byte-identical copy of itself)",
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
    pairs = build_pairs()

    import psutil

    vm = psutil.virtual_memory()
    mem_report = {"available_gb": round(vm.available / 1e9, 2), "total_gb": round(vm.total / 1e9, 2)}
    print(
        f"Memory: {mem_report['available_gb']} GB available / {mem_report['total_gb']} GB total "
        "(general precaution; not the Qwen/Ollama memory floor -- that guard is not reused here)"
    )
    if mem_report["available_gb"] < 1.0:
        raise RuntimeError(
            f"only {mem_report['available_gb']} GB available -- stopping rather than proceeding under "
            "insufficient headroom; no override exists for this diagnostic and none is authorized"
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

    scorer = NLISupportScorer(revision=pinned, fallback_scorer=None)
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
                "origin": p["origin"],
                "expects": p["expects"],
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

    repro = next((r for r in results if r["id"] == "A3_U2U3_self_REPRO"), None)
    if repro and repro["historical"]:
        hs, hc = repro["historical"]["support"], repro["historical"]["contradiction"]
        ds, dc = repro["support"], repro["contradiction"]
        print(
            f"\nReproduction check A3: historical support={hs:.4f} contradiction={hc:.4f} | "
            f"reproduced support={ds:.4f} contradiction={dc:.4f} | "
            f"delta_support={ds - hs:+.4f} delta_contradiction={dc - hc:+.4f}"
        )

    print("\n--- all pairs ---")
    for r in results:
        print(
            f"  [{r['id']:32s}] support={r['support']:.4f} contradiction={r['contradiction']:.4f} "
            f"neutral={r['raw_softmax_by_label'].get('neutral', float('nan')):.4f}  ({r['origin']})"
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", required=True)
    ap.parse_args()
    run_real()
