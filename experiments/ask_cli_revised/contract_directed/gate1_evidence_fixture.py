"""The c9+c11 evidence manifest this arc's Gate 2 diagnostics were built and run against (2026-09-27).

Reads only already-frozen packet files -- never a live packet-build, never a model, NLI, or embedding call.
Extracted here (from what was previously inline in the throwaway diagnostic drivers for
`runs/gate2-diagnostic-001/` and `runs/gate2-diagnostic-002/`) so the same, exact manifest is reusable and
testable rather than retyped per script.

**Each row's `provenance` preserves exactly how its closure status was actually established -- never smoothed
into "a model judged this":**

- c9/M10's packet was built entirely offline (the deterministic instrument-pattern candidate, zero model
  calls); its `directly_establishes` closure came from a genuine **live** Qwen call in the 8-call eligibility
  replay (`runs/replay-eligibility-001/`) -- the packet was schema-clean, so no reconstruction was needed.
- c11/M12 and M13's packet is the *same* one judged in that same live replay, but that original judgment was
  confounded by a stale attribution-schema bug (fixed in commit `ee73c8bd`). The `directly_establishes` status
  this fixture actually uses for M12/M13 comes from the **offline rehydration audit**
  (`runs/replay-eligibility-001-offline-analysis/`) -- a deterministic re-evaluation of the model's own
  *already-saved* slot selections against corrected, fresh attribution, never a new live judgment. This
  ancestry is exactly what `GATE1_AUDIT_HANDBACK.md` Part 1 documents and what this fixture's `provenance`
  field is required to preserve, not represent as a fresh model call.
- c9/W21's `constraint_text` is **researcher-authored** (Cliff's own wording, reviewed and validated by
  `overview_bridge.validate_constraint_text`) -- a description of a coverage limit, not a machine-derived
  receipt of any kind. Its `provenance` says so explicitly.
"""

from __future__ import annotations

import json

from experiments.ask_cli_revised.contract_directed import freeze
from experiments.ask_cli_revised.contract_directed import overview_bridge as bridge

SLICE_ROOT = freeze.SLICE_ROOT

M10_PACKET_PATH = SLICE_ROOT / "runs" / "replay-eligibility-001" / "frozen_packet_01_c9_1606c9d7970d.json"
C11_PACKET_PATH = (
    SLICE_ROOT / "runs" / "replay-eligibility-001-offline-analysis" / "reconstructed_08_c11_d37854a6ea62.json"
)
C11_AUDIT_REPORT_PATH = SLICE_ROOT / "runs" / "replay-eligibility-001-offline-analysis" / "00_audit_report.json"

W21_CONSTRAINT_TEXT = (
    "The admitted evidence names the scales used but does not establish that they are tied to the specific "
    "personality traits that relate to the anomalous is bad bias's manifestation. This describes a limit of "
    "the admitted evidence only -- a scope boundary of what was checked here, not a scientific finding about "
    "whether such a tie is real or absent."
)

LIVE_REPLAY_PROVENANCE = {
    "closure_source": "live_replay_call",
    "source_run_dir": "runs/replay-eligibility-001",
    "note": "packet built offline (zero model calls); its closure status came from a genuine live Qwen call",
}
OFFLINE_REHYDRATION_PROVENANCE = {
    "closure_source": "offline_rehydration_audit_reconstruction",
    "source_run_dir": "runs/replay-eligibility-001-offline-analysis",
    "note": (
        "the original live judgment on this packet was confounded by a stale attribution-schema bug; this "
        "status is a deterministic re-evaluation of that SAME saved model response against corrected "
        "attribution -- not a new live model judgment"
    ),
}
RESEARCHER_AUTHORED_PROVENANCE = {
    "closure_source": "not_applicable_unresolved",
    "constraint_text_provenance": "researcher_authored_reviewed",
    "note": "constraint_text is Cliff's own wording, validated by overview_bridge.validate_constraint_text",
}


def _span_from_part(pkt: dict, part: dict, *, attribution_state: str, slots_accepted_for: list[str]) -> dict:
    piece = part["pieces"][0]
    return {
        "paper_id": pkt["paper_id"],
        "chunk_id": piece["chunk_id"],
        "span_id": part["span_id"],
        "start": piece["start"],
        "end": piece["end"],
        "text": part["text"],
        "attribution_state": attribution_state,
        "slots_accepted_for": slots_accepted_for,
    }


def build_c9_c11_manifest() -> list[dict]:
    """The three `source_supported` rows (c9/M10; c11/M12, M13) plus one `unresolved_obligation` row (c9/W21) --
    mechanically diffed against the real packet files, never hand-retyped. Identical evidence to what was used
    for both `runs/gate2-diagnostic-001/` (lost) and `runs/gate2-diagnostic-002/` (succeeded), now additionally
    carrying each span's `start`/`end` piece offsets (see `evidence_identity.py` for why `span_id` alone is not
    a stable identity) and each row's `provenance` (see this module's own docstring). Reads only the two
    already-frozen packet files above -- no library connection, no model, NLI, or embedding call."""
    pkt67 = json.loads(M10_PACKET_PATH.read_text(encoding="utf-8"))
    m10_part = next(p for p in pkt67["parts"] if p["span_id"] == "p1")

    pkt68 = json.loads(C11_PACKET_PATH.read_text(encoding="utf-8"))
    by_sid = {p["span_id"]: p for p in pkt68["parts"]}
    p2, p4 = by_sid["p2"], by_sid["p4"]

    m10_span = _span_from_part(
        pkt67, m10_part,
        attribution_state="own_established",
        slots_accepted_for=["instrument_named", "paired_with_construct", "on_topic"],
    )  # fmt: skip
    p2_span = _span_from_part(
        pkt68, p2,
        attribution_state="own_established",
        slots_accepted_for=["population_named", "manner_described", "tied_to_subject", "on_topic", "pairing_expressed"],
    )  # fmt: skip
    p4_span = _span_from_part(
        pkt68, p4,
        attribution_state="own_established",
        slots_accepted_for=["tied_to_finding", "pairing_expressed"],
    )  # fmt: skip

    bridge.validate_constraint_text(W21_CONSTRAINT_TEXT)

    return [
        {
            "child_id": "c9",
            "unit_id": "M10",
            "kind": "operation",
            "status": "source_supported",
            "accepted_spans": [m10_span],
            "packet_id": pkt67["packet_id"],
            "provenance": LIVE_REPLAY_PROVENANCE,
        },
        {
            "child_id": "c9",
            "unit_id": "W21",
            "kind": "requested_item",
            "status": "unresolved_obligation",
            "accepted_spans": [],
            "constraint_text": W21_CONSTRAINT_TEXT,
            "packet_id": None,
            "provenance": RESEARCHER_AUTHORED_PROVENANCE,
        },
        {
            "child_id": "c11",
            "unit_id": "M12",
            "kind": "population",
            "status": "source_supported",
            "accepted_spans": [p2_span, p4_span],
            "packet_id": pkt68["packet_id"],
            "provenance": OFFLINE_REHYDRATION_PROVENANCE,
        },
        {
            "child_id": "c11",
            "unit_id": "M13",
            "kind": "manner",
            "status": "source_supported",
            "accepted_spans": [p2_span],
            "packet_id": pkt68["packet_id"],
            "provenance": OFFLINE_REHYDRATION_PROVENANCE,
        },
    ]


def available() -> bool:
    return M10_PACKET_PATH.is_file() and C11_PACKET_PATH.is_file()
