"""Frozen Run 0.5 calibration datasets + deterministic source-unit segmentation and dev/held-out split.

Decomposition set: the frozen AIB benchmark (imported, never re-typed, so its hash is unchanged) plus a
small number of *existing* single-clause questions taken from the app's own Ask history (they test that
a simple question is NOT over-split or embellished — the "psychological theories" invention risk).

Context set: the unique retrieval-anchor chunks the completed baseline actually read
(`08_evidence_packets.jsonl`). Envelope text is built from a library.sqlite copy in `context_windows.py`;
this module only enumerates the anchors and owns the deterministic split.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

# The anomalous-is-bad abstract packet the baseline gate wrongly discarded despite direct on-topic
# findings (amygdala / economic-game behavior / attitudes). Mandatory dev regression specimen; never
# moved to held-out, never encoded into a prompt.
SPECIMEN_ANCHOR = 34974

# Existing app-history questions (from prior real Ask synthesis records) — all single-clause; provenance
# preserved. NOT invented for this experiment.
_APP_HISTORY_QUESTIONS = (
    ("q_h1", "what is the anomalous is bad bias?"),
    ("q_h2", "how is the anomalous-is-bad bias expressed?"),
    ("q_h3", "what are some key findings on the psychology of face perception?"),
    ("q_h4", "is art therapy an effective intervention for ptsd in military veterans?"),
)


def decomposition_cases() -> list[dict]:
    """The frozen decomposition question set. AIB is dev (mandatory hard case, 13-target audit)."""
    cases = [{"case_id": "q_aib", "text": BENCHMARK_QUESTION, "source": "frozen-benchmark", "split": "dev"}]
    # Two app-history questions held out (evaluated once on the chosen design to confirm a simple question
    # is not over-split); two in dev.
    held = {"q_h3", "q_h4"}
    for cid, text in _APP_HISTORY_QUESTIONS:
        cases.append(
            {"case_id": cid, "text": text, "source": "app-history", "split": "held_out" if cid in held else "dev"}
        )
    return cases


def segment_source_units(question: str) -> list[dict]:
    """Deterministic, conservative ordered source units: split on '?', keep each clause's exact text.

    A '?'-terminated span is one unit; a trailing declarative span with no '?' becomes its own final
    unit. This never invents or deletes a request, and (for the AIB question) it places each of the
    requests the baseline dropped — scales, cross-cultural evidence, cultures+measurement, interventions
    — in its own unit, so per-source-unit coverage can detect their loss.
    """
    q = question.strip()
    units: list[str] = []
    buf = ""
    for ch in q:
        buf += ch
        if ch == "?":
            text = buf.strip()
            if text:
                units.append(text)
            buf = ""
    tail = buf.strip()
    if tail:
        units.append(tail)
    return [{"source_unit_id": f"u{i}", "text": text} for i, text in enumerate(units, start=1)]


def load_context_anchors(packets_path: str | Path) -> list[dict]:
    """Unique (anchor_chunk_id, paper_id) from the baseline evidence packets, deterministically ordered.

    First occurrence wins for the subquestion/origin provenance; the anchor id is the stable key.
    """
    seen: dict[int, dict] = {}
    with Path(packets_path).open(encoding="utf-8") as handle:
        for line in handle:
            packet = json.loads(line)
            anchor = int(packet["retrieval_anchor_chunk_id"])
            if anchor not in seen:
                seen[anchor] = {
                    "case_id": f"c{anchor}",
                    "anchor_chunk_id": anchor,
                    "paper_id": int(packet["paper_id"]),
                    "baseline_subquestion_id": packet.get("subquestion_id"),
                    "baseline_origin": packet.get("origin"),
                    "baseline_discarded": bool(packet.get("discarded")),
                }
    return [seen[key] for key in sorted(seen)]


def context_split(case_id: str, anchor_chunk_id: int, *, held_out_pct: int = 30) -> str:
    """Deterministic dev/held-out assignment. The AIB discard specimen is always dev."""
    if anchor_chunk_id == SPECIMEN_ANCHOR:
        return "dev"
    bucket = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest(), 16) % 100
    return "held_out" if bucket < held_out_pct else "dev"
