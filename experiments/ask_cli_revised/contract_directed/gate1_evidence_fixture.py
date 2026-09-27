"""The c9+c11 evidence manifest this arc's Gate 2 diagnostics were built and run against (2026-09-27).

Reads only already-frozen packet files -- never a live packet-build, never a model, NLI, or embedding call.
Extracted here (from what was previously inline in the throwaway diagnostic drivers for
`runs/gate2-diagnostic-001/` and `runs/gate2-diagnostic-002/`) so the same, exact manifest is reusable and
testable rather than retyped per script."""

from __future__ import annotations

import json

from experiments.ask_cli_revised.contract_directed import freeze
from experiments.ask_cli_revised.contract_directed import overview_bridge as bridge

SLICE_ROOT = freeze.SLICE_ROOT

M10_PACKET_PATH = SLICE_ROOT / "runs" / "replay-eligibility-001" / "frozen_packet_01_c9_1606c9d7970d.json"
C11_PACKET_PATH = (
    SLICE_ROOT / "runs" / "replay-eligibility-001-offline-analysis" / "reconstructed_08_c11_d37854a6ea62.json"
)

W21_CONSTRAINT_TEXT = (
    "The admitted evidence names the scales used but does not establish that they are tied to the specific "
    "personality traits that relate to the anomalous is bad bias's manifestation. This describes a limit of "
    "the admitted evidence only -- a scope boundary of what was checked here, not a scientific finding about "
    "whether such a tie is real or absent."
)


def build_c9_c11_manifest() -> list[dict]:
    """The three `source_supported` rows (c9/M10; c11/M12, M13) plus one `unresolved_obligation` row (c9/W21) --
    mechanically diffed against the real packet files, never hand-retyped. Identical to the manifest used for
    both `runs/gate2-diagnostic-001/` (lost) and `runs/gate2-diagnostic-002/` (succeeded). Reads only the two
    already-frozen packet files above -- no library connection, no model, NLI, or embedding call."""
    pkt67 = json.loads(M10_PACKET_PATH.read_text(encoding="utf-8"))
    m10_part = next(p for p in pkt67["parts"] if p["span_id"] == "p1")

    pkt68 = json.loads(C11_PACKET_PATH.read_text(encoding="utf-8"))
    by_sid = {p["span_id"]: p for p in pkt68["parts"]}
    p2, p4 = by_sid["p2"], by_sid["p4"]

    m10_span = {
        "paper_id": pkt67["paper_id"],
        "chunk_id": m10_part["pieces"][0]["chunk_id"],
        "span_id": m10_part["span_id"],
        "text": m10_part["text"],
        "attribution_state": "own_established",
        "slots_accepted_for": ["instrument_named", "paired_with_construct", "on_topic"],
    }
    p2_span = {
        "paper_id": pkt68["paper_id"],
        "chunk_id": p2["pieces"][0]["chunk_id"],
        "span_id": p2["span_id"],
        "text": p2["text"],
        "attribution_state": "own_established",
        "slots_accepted_for": [
            "population_named",
            "manner_described",
            "tied_to_subject",
            "on_topic",
            "pairing_expressed",
        ],
    }
    p4_span = {
        "paper_id": pkt68["paper_id"],
        "chunk_id": p4["pieces"][0]["chunk_id"],
        "span_id": p4["span_id"],
        "text": p4["text"],
        "attribution_state": "own_established",
        "slots_accepted_for": ["tied_to_finding", "pairing_expressed"],
    }

    bridge.validate_constraint_text(W21_CONSTRAINT_TEXT)

    return [
        {
            "child_id": "c9",
            "unit_id": "M10",
            "kind": "operation",
            "status": "source_supported",
            "accepted_spans": [m10_span],
        },
        {
            "child_id": "c9",
            "unit_id": "W21",
            "kind": "requested_item",
            "status": "unresolved_obligation",
            "accepted_spans": [],
            "constraint_text": W21_CONSTRAINT_TEXT,
        },
        {
            "child_id": "c11",
            "unit_id": "M12",
            "kind": "population",
            "status": "source_supported",
            "accepted_spans": [p2_span, p4_span],
        },
        {
            "child_id": "c11",
            "unit_id": "M13",
            "kind": "manner",
            "status": "source_supported",
            "accepted_spans": [p2_span],
        },
    ]


def available() -> bool:
    return M10_PACKET_PATH.is_file() and C11_PACKET_PATH.is_file()
