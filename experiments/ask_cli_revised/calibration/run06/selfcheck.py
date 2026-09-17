"""Deterministic Run 0.6 self-checks — no DB, Qwen, or network. Proves the load-bearing invariants:
source preservation (incl. AIB freeze parity + cue-gated splitting), audit diagnostics, the corrected
selection hierarchy (global reconstruction PRIMARY; coverage veto/flag only; LOO/drift never rank), bounded
non-destructive repair, freeze immutability, lineage/STARVED, context freeze, and global freezes.
"""

from __future__ import annotations

import hashlib

import numpy as np

from experiments.ask_cli_revised.calibration import context_windows as cw
from experiments.ask_cli_revised.calibration.datasets import segment_source_units
from experiments.ask_cli_revised.calibration.decomposition import apply_source_fallback
from experiments.ask_cli_revised.calibration.run06 import candidates as cand
from experiments.ask_cli_revised.calibration.run06 import freeze as frz
from experiments.ask_cli_revised.calibration.run06 import lineage as lin
from experiments.ask_cli_revised.calibration.run06 import selection
from experiments.ask_cli_revised.calibration.run06.audit_ext import audit_candidate
from experiments.ask_cli_revised.calibration.run06.dataset06 import (
    BUILT_ENV_QUESTION,
    DEPRESSION_QUESTION,
    decomposition_cases_v06,
    frozen_manifest,
)
from experiments.ask_cli_revised.calibration.run06.repair import diagnose
from experiments.ask_cli_revised.calibration.run06.segment import segment_source_units_v2
from experiments.ask_cli_revised.calibration.audit import AuditThresholds
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION, question_hash

_FROZEN_AIB_HASH = "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"
_ANSWER_LEAK_TOKENS = ("amygdala", "dictator game", "empathic concern", "just-world", "hadza", "iat")


class _FakeEmbed:
    def encode_texts(self, texts):
        vectors = []
        for text in texts:
            vec = np.zeros(64, dtype=float)
            for token in text.lower().split():
                vec[int(hashlib.sha1(token.encode()).hexdigest(), 16) % 64] += 1.0
            vectors.append(vec)
        return np.asarray(vectors)


def _check(name, cond):
    if not cond:
        raise AssertionError(f"FAILED: {name}")
    print(f"  ok: {name}")


def _synthetic(style, *, global_recon, min_cov, redundancy=0, n_items=3, latency=1.0):
    units = [{"source_unit_id": f"u{i}", "text": f"src {i}"} for i in range(1, n_items + 1)]
    items = [
        {"item_id": f"u{i}-r1", "source_unit_id": f"u{i}", "source_text": f"src {i}", "text": f"rw {i}"}
        for i in range(1, n_items + 1)
    ]
    coverage = [{"source_unit_id": f"u{i}", "best_match": (min_cov if i == 1 else 0.9), "weak": False, "best_item_id": f"u{i}-r1"} for i in range(1, n_items + 1)]
    audit = {
        "global_reconstruction": global_recon,
        "weakest_coverage": min_cov,
        "source_unit_coverage": coverage,
        "leave_one_out": [{"item_id": it["item_id"], "delta": 0.1, "suspicious": False} for it in items],
        "redundancy": [{"item_a": "a", "item_b": "b", "similarity": 0.9}] * redundancy,
        "source_local_drift": [{"item_id": it["item_id"], "source_unit_id": it["source_unit_id"], "source_local_similarity": 0.8} for it in items],
    }
    return {"style": style, "units": units, "items": items, "audit": audit, "calls_summary": {"latency_total_s": latency}}


def main() -> int:
    # ---- global freezes ----
    _check("AIB question hash unchanged", question_hash() == _FROZEN_AIB_HASH)
    m = frozen_manifest()
    hashes = {c["case_id"]: c["question_hash"] for c in m["cases"]}
    _check("frozen manifest hashes stable", frozen_manifest()["cases"][0]["question_hash"] == hashes["q_aib"])
    _check("q_depr + q_builtenv hashed", "q_depr" in hashes and "q_builtenv" in hashes)

    # ---- source preservation: AIB freeze parity ----
    v05 = segment_source_units(BENCHMARK_QUESTION)
    v06 = segment_source_units_v2(BENCHMARK_QUESTION)
    _check("AIB v2 segmentation == Run 0.5 (6 units, byte-identical)", v06 == v05 and len(v06) == 6)

    # ---- source preservation: cue-gated declarative splitting ----
    depr = segment_source_units_v2(DEPRESSION_QUESTION)
    _check("q_depr -> 8 source units", len(depr) == 8)
    _check("every q_depr unit is an exact substring", all(u["text"] in DEPRESSION_QUESTION for u in depr))
    _check("open-ended 'and other relevant' preserved as its own unit", any("and other relevant" in u["text"] for u in depr))
    _check("compound qualifier 'mixed, null, or uncertain' NOT split", any("mixed, null, or uncertain findings" in u["text"] for u in depr))
    be = segment_source_units_v2(BUILT_ENV_QUESTION)
    _check("q_builtenv -> 8 source units", len(be) == 8)
    _check("'and more' preserved", any("and more" in u["text"] for u in be))
    _check("simple question not over-split", len(segment_source_units_v2("what is the anomalous is bad bias?")) == 1)

    # ---- source baseline is pure + provenance-complete ----
    baseline = cand.source_baseline(DEPRESSION_QUESTION)
    _check("baseline item per source unit", len(baseline["items"]) == len(depr))
    _check("baseline items are the exact source units", all(i["text"] == i["source_text"] for i in baseline["items"]))
    _check("baseline flagged is_baseline", all(i.get("is_baseline") for i in baseline["items"]))

    # ---- non-destructive fallback (Run 0.5 primitive, still holds) ----
    items = [
        {"item_id": "u1-r1", "source_unit_id": "u1", "source_text": "S1", "text": "rw1", "from_fallback": False},
        {"item_id": "u2-r1", "source_unit_id": "u2", "source_text": "S2", "text": "rw2", "from_fallback": False},
    ]
    out, fell = apply_source_fallback(items, {"u2"})
    _check("fallback never deletes an item", len(out) == 2 and fell == ["u2"])
    _check("fallback resets only the weak unit to exact source", out[1]["text"] == "S2" and out[0]["text"] == "rw1")

    # ---- audit is diagnostic + non-mutating; has all five measures ----
    embed = _FakeEmbed()
    units = segment_source_units_v2(DEPRESSION_QUESTION)
    a_items = [{"item_id": f"{u['source_unit_id']}-r1", "source_unit_id": u["source_unit_id"], "source_text": u["text"], "text": u["text"]} for u in units]
    before = [dict(i) for i in a_items]
    audit = audit_candidate(DEPRESSION_QUESTION, units, a_items, embed, thresholds=AuditThresholds(0.5, 0.5))
    _check("audit does not mutate items", a_items == before)
    _check("audit exposes global reconstruction", "global_reconstruction" in audit and "passes_global" in audit)
    _check("coverage covers every source unit", len(audit["source_unit_coverage"]) == len(units))
    _check("LOO removes exactly one item at a time (one row per item)", len(audit["leave_one_out"]) == len(a_items))
    _check("source-local drift per item", len(audit["source_local_drift"]) == len(a_items))

    # ---- selection hierarchy: global reconstruction PRIMARY, not max-min coverage ----
    high_global_low_cov = _synthetic("A", global_recon=0.95, min_cov=0.50)
    low_global_high_cov = _synthetic("B", global_recon=0.90, min_cov=0.90)
    dec = selection.select([high_global_low_cov, low_global_high_cov])
    _check("primary = global reconstruction (not max-min coverage)", dec["selected"] == "A")

    # ---- coverage VETO for a clearly-unrepresented unit ----
    vetoed = _synthetic("V", global_recon=0.99, min_cov=0.10)  # below 0.30 floor
    ok_cand = _synthetic("W", global_recon=0.80, min_cov=0.80)
    dec2 = selection.select([vetoed, ok_cand])
    _check("clearly-unrepresented candidate is vetoed despite top global recon", dec2["selected"] == "W")
    dec3 = selection.select([vetoed])
    _check("all-vetoed -> baseline fallback", dec3["selected"] == "baseline")

    # ---- redundancy is a SECONDARY tiebreak only (equal global recon) ----
    a_red = _synthetic("A", global_recon=0.90, min_cov=0.8, redundancy=3)
    b_clean = _synthetic("B", global_recon=0.90, min_cov=0.8, redundancy=0)
    _check("tie on global -> fewer redundancy pairs wins", selection.select([a_red, b_clean])["selected"] == "B")

    # ---- repair diagnosis: bounded + non-destructive path ----
    ready_audit = {"passes_global": True, "source_unit_coverage": [{"source_unit_id": "u1", "best_match": 0.9, "weak": False}], "source_local_drift": [{"item_id": "u1-r1", "source_local_similarity": 0.9}]}
    _check("repair not needed when ready", diagnose(ready_audit)["needed"] is False)
    weak_audit = {"passes_global": True, "source_unit_coverage": [{"source_unit_id": "u1", "best_match": 0.2, "weak": True}], "source_local_drift": [{"item_id": "u1-r1", "source_local_similarity": 0.9}]}
    _check("repair flags a weak source unit", diagnose(weak_audit)["needed"] and diagnose(weak_audit)["weak_units"] == ["u1"])

    # ---- freeze immutability ----
    frozen = frz.freeze_decomposition(case_id="q_x", question="Q?", selected="minimal", items=a_items, selection={"reason": "t"}, repair=None)
    frz.assert_unchanged(frozen, a_items)
    _check("freeze hash present + stable", frozen["decomposition_hash"] == frz.decomposition_hash(a_items))
    changed = [dict(i) for i in a_items]
    changed[0]["text"] = changed[0]["text"] + " EDITED"
    try:
        frz.assert_unchanged(frozen, changed)
        raise AssertionError("assert_unchanged should have raised on edited items")
    except AssertionError as exc:
        _check("edited frozen decomposition is caught", "changed during the walk" in str(exc))

    # ---- lineage + deterministic STARVED ----
    frozen_lin = {"case_id": "q_x", "selected_candidate": "minimal", "items": [
        {"item_id": "u1-r1", "source_unit_id": "u1", "source_text": "S1", "text": "rw1"},
        {"item_id": "u2-r1", "source_unit_id": "u2", "source_text": "S2", "text": "rw2"},
    ]}
    audit_lin = audit_candidate("Q about S1 S2", [{"source_unit_id": "u1", "text": "S1"}, {"source_unit_id": "u2", "text": "S2"}], frozen_lin["items"], embed, thresholds=AuditThresholds(0.5, 0.5))
    walk_records = [
        {"source_unit_id": "u1", "item_id": "u1-r1", "retrieval_query": "rw1", "n_papers": 2, "axis_nomination_count": 1,
         "nominations": [{"paper_id": 5, "score": 0.8}], "hits": [], "anchors": [{"anchor_chunk_id": 10, "paper_id": 5, "retrieval_score": 0.8, "window_choice": "B"}]},
        {"source_unit_id": "u2", "item_id": "u2-r1", "retrieval_query": "rw2", "n_papers": 0, "axis_nomination_count": 0,
         "nominations": [], "hits": [], "anchors": []},
    ]
    lineage = lin.build_lineage(frozen_lin, walk_records, audit_lin)
    u1 = next(u for u in lineage["units"] if u["source_unit_id"] == "u1")
    u2 = next(u for u in lineage["units"] if u["source_unit_id"] == "u2")
    _check("STARVED computed: u1 not starved (paper+anchor+non-E)", u1["starved"] is False)
    _check("STARVED computed: u2 starved (no papers/anchors)", u2["starved"] is True)
    _check("lineage assessment is null (post-hoc human)", all(u["assessment"] is None for u in lineage["units"]))
    _check("every retrieval query maps to a canonical source unit", all(u["source_unit_id"] for u in lineage["units"]))

    # ---- context primitive frozen: A..E, no DISCARD ----
    _check("context labels A..E (E present, no discard)", cw.WINDOW_LABELS == ("A", "B", "C", "D", "E"))
    _check("window schema enum exactly A..E", cw.WINDOW_SCHEMA["properties"]["window"]["enum"] == ["A", "B", "C", "D", "E"])
    _check("no destructive 'discard' in context primitive", "discard" not in cw.window_prompt({lbl: "x" for lbl in ("A", "B", "C", "D")}).lower())

    # ---- no expected-answer tokens injected into decomposition prompts ----
    prompt = cand.minimal_prompt(BENCHMARK_QUESTION, "and using which scales?")
    _check("minimal prompt contains no injected AIB answer tokens", not any(tok in prompt.lower() for tok in _ANSWER_LEAK_TOKENS))

    # ---- dataset wiring ----
    cases = decomposition_cases_v06()
    _check("7 frozen questions", len(cases) == 7)
    _check("3 rich questions (dev + walked)", sum(1 for c in cases if c["rich"]) == 3)
    _check("held-out split preserved (q_h3/q_h4)", {c["case_id"] for c in cases if c["split"] == "held_out"} == {"q_h3", "q_h4"})

    print("ALL RUN 0.6 SELF-CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
