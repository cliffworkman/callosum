"""Deterministic self-checks for the Run 0.5 calibration harness — no DB, Qwen, or network.

Proves the invariants the steering + task enumerate: decomposition provenance/non-invention, Design-C
non-destructiveness, context envelope construction from real neighbors with a marked central chunk and
deterministic boundaries, E != discard, structured-output failure-class separability, frozen split, and
the frozen benchmark question/hash.
"""

from __future__ import annotations

import hashlib

import numpy as np

from experiments.ask_cli_revised.calibration import context_windows as cw
from experiments.ask_cli_revised.calibration.audit import AuditThresholds, audit_decomposition
from experiments.ask_cli_revised.calibration.datasets import (
    SPECIMEN_ANCHOR,
    context_split,
    decomposition_cases,
    segment_source_units,
)
from experiments.ask_cli_revised.calibration.decomposition import apply_source_fallback
from experiments.ask_cli_revised.calibration.structured_output import classify, extract_json
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION, question_hash

_FROZEN_QUESTION_HASH = "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"


class _FakeEmbed:
    """Deterministic bag-of-words hashing embedder (no model download); enough to exercise the audit."""

    def encode_texts(self, texts):
        vectors = []
        for text in texts:
            vec = np.zeros(64, dtype=float)
            for token in text.lower().split():
                vec[int(hashlib.sha1(token.encode()).hexdigest(), 16) % 64] += 1.0
            vectors.append(vec)
        return np.asarray(vectors)


def _check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"FAILED: {name}")
    print(f"  ok: {name}")


def main() -> int:
    # ---- global freeze ----
    _check("frozen question hash unchanged", question_hash() == _FROZEN_QUESTION_HASH)

    # ---- decomposition segmentation: provenance + no invention ----
    units = segment_source_units(BENCHMARK_QUESTION)
    _check("AIB -> 6 source units", len(units) == 6)
    _check(
        "source unit ids are code-owned + ordered",
        [u["source_unit_id"] for u in units] == [f"u{i}" for i in range(1, 7)],
    )
    _check(
        "every source unit text is verbatim from the question",
        all(u["text"].rstrip("?").rstrip() in BENCHMARK_QUESTION or u["text"] in BENCHMARK_QUESTION for u in units),
    )
    joined = " ".join(u["text"].lower() for u in units)
    for target in ("scales", "cross-cultural", "cultures", "interventions"):
        _check(f"dropped-in-baseline request '{target}' is its own/covered unit", target in joined)
    _check("single-clause question -> 1 unit", len(segment_source_units("what is the anomalous is bad bias?")) == 1)

    # ---- Design-C non-destructive fallback (pure) ----
    items = [
        {
            "item_id": "u1-r1",
            "source_unit_id": "u1",
            "source_text": "SRC1",
            "text": "rewrite-1",
            "from_fallback": False,
        },
        {
            "item_id": "u2-r1",
            "source_unit_id": "u2",
            "source_text": "SRC2",
            "text": "rewrite-2",
            "from_fallback": False,
        },
    ]
    out, fell = apply_source_fallback(items, {"u2"})
    _check("fallback preserves item count (never deletes)", len(out) == len(items))
    _check(
        "fallback resets only the weak unit to exact source text",
        out[1]["text"] == "SRC2" and out[0]["text"] == "rewrite-1",
    )
    _check("fallback reports which units fell back", fell == ["u2"])

    # ---- audit is diagnostic only: it must not mutate the items it inspects ----
    audit_items = [dict(i) for i in items]
    before = [dict(i) for i in audit_items]
    result = audit_decomposition(
        "some question about SRC1 SRC2",
        units[:2],
        audit_items,
        _FakeEmbed(),
        thresholds=AuditThresholds(global_gate=0.5, coverage_gate=0.5),
    )
    _check("audit does not mutate items", audit_items == before)
    _check("audit exposes global reconstruction", "global_reconstruction" in result and "passes_global" in result)
    _check("audit exposes per-source-unit coverage", len(result["source_unit_coverage"]) == 2)
    _check("audit exposes leave-one-out", len(result["leave_one_out"]) == 2 and "delta" in result["leave_one_out"][0])

    # ---- context envelopes: real neighbors, marked central, order, deterministic boundaries ----
    ordered = [
        {"chunk_id": 10 + i, "char_start": i * 100, "page_start": 1, "section": None, "text": f"chunk-{10 + i}"}
        for i in range(7)
    ]
    central = 3  # chunk 13, interior
    windows = cw.windows_from_ordered(ordered, central)
    _check("A is central only", windows["A"]["chunk_ids"] == [13])
    _check("B is +/-1 (<=3)", windows["B"]["chunk_ids"] == [12, 13, 14])
    _check("C is +/-2 (<=5)", windows["C"]["chunk_ids"] == [11, 12, 13, 14, 15])
    _check("D is +/-3 (<=7)", windows["D"]["chunk_ids"] == [10, 11, 12, 13, 14, 15, 16])
    _check("central appears in every window", all(13 in windows[lbl]["chunk_ids"] for lbl in ("A", "B", "C", "D")))
    _check(
        "source order preserved (ascending)",
        all(windows[lbl]["chunk_ids"] == sorted(windows[lbl]["chunk_ids"]) for lbl in ("A", "B", "C", "D")),
    )
    # boundary: central at document start -> deterministic missing_before, no fake symmetry
    start_windows = cw.windows_from_ordered(ordered, 0)
    _check(
        "doc-start boundary is deterministic",
        start_windows["B"]["missing_before"] == 1 and start_windows["B"]["chunk_ids"] == [10, 11],
    )
    rendered = cw.render_window(start_windows["B"], 10, radius=1)
    _check("missing neighbor stated, not faked", "NO PREVIOUS CHUNK EXISTS" in rendered)
    _check(
        "central chunk marked in render", "[ CENTRAL CHUNK 10 ]" in rendered and "[ END CENTRAL CHUNK 10 ]" in rendered
    )

    # ---- E != discard; only A..E allowed ----
    _check("labels are A..E (E present, no discard)", cw.WINDOW_LABELS == ("A", "B", "C", "D", "E"))
    _check(
        "window schema enum is exactly A..E",
        cw.WINDOW_SCHEMA["properties"]["window"]["enum"] == ["A", "B", "C", "D", "E"],
    )
    _check(
        "no destructive 'discard' token in context primitive",
        "discard" not in cw.window_prompt({lbl: "x" for lbl in ("A", "B", "C", "D")}).lower(),
    )

    # ---- structured-output failure classes separable ----
    _check("json object parsed", extract_json('noise {"window":"B"} tail') == {"window": "B"})
    _check("json none", extract_json("no json here") is None)
    _, ok1, r1 = classify('{"window":"B"}', False)
    _check("clean structured output", ok1 and r1 is None)
    _, ok2, r2 = classify("Sure! Here is a friendly greeting.", False)
    _check("no-structured-output distinguishable", (not ok2) and r2 == "no_structured_output")
    _, _, r3 = classify('{"window":"B"', True)
    _check("truncation distinguishable from schema failure", r3 == "truncated_at_output_cap")

    # ---- frozen split ----
    _check("specimen anchor is always dev", context_split(f"c{SPECIMEN_ANCHOR}", SPECIMEN_ANCHOR) == "dev")
    _check("split is deterministic", context_split("c99999", 99999) == context_split("c99999", 99999))
    dcases = decomposition_cases()
    _check(
        "AIB decomposition case is dev + frozen-benchmark",
        any(c["case_id"] == "q_aib" and c["split"] == "dev" for c in dcases),
    )
    _check("some decomposition held-out exists", any(c["split"] == "held_out" for c in dcases))

    print("ALL CALIBRATION SELF-CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
