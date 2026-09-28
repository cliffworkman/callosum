"""Prospective, source-derived NLI premise corpus -- offline inventory + candidate manifest (2026-09-28
authorization). **No inference call anywhere in this module.**

"Prospective" here means: strings assembled from real, saved, provenance-verified source passages for a NEW
diagnostic -- never premises production itself previously constructed, cited, screened or scored (that is the
separate, already-closed OBSERVED-PRODUCTION stratum, `nli_premise_population_eval.py`'s own 6 premises, which
this module imports and treats as read-only history, never re-derived).

## Source and stratification

The eligibility-replay arc's 8 frozen packets (`replay-eligibility-001/frozen_packet_0{1..8}_*.json`) plus
their live eligibility judgment (`03_results.jsonl`) are the source. Every packet `part` has real, verified
provenance: `paper_id` (packet-level), `chunk_id`/`start`/`end` (piece-level, the same canonical-locator shape
`evidence_identity.py` already establishes as the stable identity -- `span_id` is packet-local, never global).

Two strata, kept separate everywhere:

- **Stratum A (eligibility-decided, positive closure):** the exact 3 canonical spans already baked into
  `gate1_evidence_fixture.build_c9_c11_manifest()`'s `accepted_spans` (c9/M10's packet-01 p1; c11/M12+M13's
  packet-08 p2 and p4). These are EXCLUDED from prospective construction -- they already exist as the known
  historical c9/c11 premises and must not be double-counted as "new."
- **Stratum B (packetized, verified identity, not closed to source_supported):** every other distinct span
  across all 8 packets, after canonical-locator deduplication (a real, confirmed find: packet 03 and packet 04,
  both paper 20, share several identical (chunk_id, start, end) spans under different packet-local span_ids --
  packet 04 additionally aliases the SAME span under both p6 and p7 *within itself*). This is the pool
  prospective premises are drawn from.

## Construction rules (fixed, inspectable, independent of any NLI score)

- **Single-span:** every distinct Stratum-B canonical span, source-verbatim, unmodified.
- **`packet_full_order`:** a packet's own distinct (post-dedup) Stratum-B parts, in the packet's own original
  order, joined the same way `overview_guards.nli_pair`/`gate1_evidence_fixture._span_from_part` would (a
  single space). Only built when 2+ distinct Stratum-B parts remain in a packet after dropping Stratum-A
  members and cross-packet duplicates (kept at their FIRST packet appearance only). Every dropped/omitted part
  is recorded explicitly, never silently skipped.
- **`eligibility_slot_group`:** the exact span-id groups the live eligibility judgment's own `slot_spans`
  already grouped together for one unit's one slot (`03_results.jsonl`) -- a second, independently-justified
  "existing relationship," used only where 2+ span ids are grouped and every one resolves to a real part.

No premise here is rewritten, reordered to chase a score, or drawn from synthetic filler. A byte-exact overlap
against a historical (observed-production) premise is recorded, never silently absorbed as "new."
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

RUNS_DIR = Path(r"C:\Users\cliff\callosum-data\contract-directed-slice\runs")
ELIGIBILITY_DIR = RUNS_DIR / "replay-eligibility-001"

PACKET_FILES = sorted(ELIGIBILITY_DIR.glob("frozen_packet_*.json"))
RESULTS_PATH = ELIGIBILITY_DIR / "03_results.jsonl"

# The exact 3 canonical spans already in gate1_evidence_fixture.build_c9_c11_manifest()'s accepted_spans --
# verified directly against that module's own M10_PACKET_PATH/C11_PACKET_PATH + span_id selection ("p1" from
# packet 01; "p2"/"p4" from packet 08), converted to the canonical (paper_id, chunk_id, start, end) key.
STRATUM_A_KEYS = frozenset(
    {
        (67, 35019, 25, 392),  # c9/M10, packet 01, p1
        (68, 43327, 437, 617),  # c11/M12+M13, packet 08, p2
        (68, 43327, 700, 820),  # c11/M12+M13, packet 08, p4
    }
)

NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"


def canonical_key(paper_id: int, chunk_id: int, start: int, end: int) -> tuple:
    return (paper_id, chunk_id, start, end)


def load_packets() -> list[dict]:
    packets = []
    for path in PACKET_FILES:
        d = json.loads(path.read_text(encoding="utf-8"))
        parts = []
        for part in d["parts"]:
            pieces = part["pieces"]
            # every part in these 8 packets has exactly one piece except packet 02's p1 (two adjacent pieces
            # spanning a page/chunk boundary) -- canonical identity uses the first piece's chunk/offsets, the
            # SAME convention gate1_evidence_fixture._span_from_part already relies on (piece[0]).
            piece0 = pieces[0]
            parts.append(
                {
                    "span_id": part["span_id"],
                    "text": part["text"],
                    "paper_id": d["paper_id"],
                    "chunk_id": piece0["chunk_id"],
                    "start": piece0["start"],
                    "end": piece0["end"],
                }
            )
        packets.append({"path": str(path), "packet_id": d["packet_id"], "paper_id": d["paper_id"], "parts": parts})
    return packets


def load_results() -> list[dict]:
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def deduplicate(packets: list[dict]) -> dict[tuple, dict]:
    """canonical_key -> {text, paper_id, chunk_id, start, end, first_seen: (packet_id, span_id), aliases: [...]}"""
    distinct: dict[tuple, dict] = {}
    for pkt in packets:
        for part in pkt["parts"]:
            key = canonical_key(part["paper_id"], part["chunk_id"], part["start"], part["end"])
            alias = (pkt["packet_id"], part["span_id"])
            if key not in distinct:
                distinct[key] = {
                    "text": part["text"],
                    "paper_id": part["paper_id"],
                    "chunk_id": part["chunk_id"],
                    "start": part["start"],
                    "end": part["end"],
                    "first_seen": alias,
                    "aliases": [alias],
                }
            else:
                assert distinct[key]["text"] == part["text"], f"canonical key {key} has conflicting text"
                distinct[key]["aliases"].append(alias)
    return distinct


def single_span_premises(distinct: dict[tuple, dict]) -> list[dict]:
    out = []
    for key, entry in distinct.items():
        if key in STRATUM_A_KEYS:
            continue
        out.append(
            {
                "construction": "single_span",
                "unit_ids": None,
                "canonical_keys": [key],
                "premise": entry["text"],
                "aliases": entry["aliases"],
                "paper_ids": [entry["paper_id"]],
            }
        )
    return out


def packet_full_order_premises(packets: list[dict], distinct: dict[tuple, dict]) -> list[dict]:
    """One multi-span premise per packet: its own distinct, non-Stratum-A parts, in ORIGINAL order, joined by a
    single space (matching production's own join convention). A part is OMITTED (recorded, not silently
    dropped) if it is a Stratum-A member or a cross-packet duplicate already registered under an earlier
    packet's own full-order premise."""
    seen_elsewhere: set[tuple] = set()
    out = []
    for pkt in packets:
        kept_keys: list[tuple] = []
        omitted: list[dict] = []
        for part in pkt["parts"]:
            key = canonical_key(part["paper_id"], part["chunk_id"], part["start"], part["end"])
            if key in STRATUM_A_KEYS:
                omitted.append({"span_id": part["span_id"], "reason": "stratum_a_member"})
                continue
            if key in seen_elsewhere:
                omitted.append({"span_id": part["span_id"], "reason": "duplicate_of_earlier_packet_or_part"})
                continue
            kept_keys.append(key)
            seen_elsewhere.add(key)
        if len(kept_keys) < 2:
            continue
        premise = " ".join(distinct[k]["text"] for k in kept_keys)
        out.append(
            {
                "construction": "packet_full_order",
                "unit_ids": None,
                "canonical_keys": kept_keys,
                "premise": premise,
                "packet_id": pkt["packet_id"],
                "omitted_parts": omitted,
                "paper_ids": sorted({distinct[k]["paper_id"] for k in kept_keys}),
            }
        )
    return out


def eligibility_slot_group_premises(
    packets: list[dict], results: list[dict], distinct: dict[tuple, dict]
) -> list[dict]:
    """One multi-span premise per (packet, unit, slot) where the live eligibility judgment's own slot_spans
    grouped 2+ span ids together -- a second, independently-justified real relationship."""
    by_packet_span = {
        (pkt["packet_id"], part["span_id"]): canonical_key(
            part["paper_id"], part["chunk_id"], part["start"], part["end"]
        )
        for pkt in packets
        for part in pkt["parts"]
    }
    out = []
    for r in results:
        packet_id = r["packet_id"]
        per_unit = r["result"]["per_unit"]
        for unit_id, unit_result in per_unit.items():
            for slot, span_ids in unit_result.get("slot_spans", {}).items():
                if len(span_ids) < 2:
                    continue
                keys = []
                for sid in span_ids:
                    k = by_packet_span.get((packet_id, sid))
                    if k is None:
                        keys = None
                        break
                    keys.append(k)
                if keys is None or any(k in STRATUM_A_KEYS for k in keys) or len(set(keys)) != len(keys):
                    continue  # unresolvable span id, a Stratum-A member, or an internally duplicate group
                premise = " ".join(distinct[k]["text"] for k in keys)
                out.append(
                    {
                        "construction": "eligibility_slot_group",
                        "unit_ids": None,
                        "canonical_keys": keys,
                        "premise": premise,
                        "packet_id": packet_id,
                        "unit_id": unit_id,
                        "slot": slot,
                        "paper_ids": sorted({distinct[k]["paper_id"] for k in keys}),
                    }
                )
    return out


def historical_premise_texts() -> set[str]:
    """The 6 observed-production premise strings, read from the ALREADY-BUILT population-eval inventory --
    never re-derived, imported read-only."""
    from experiments.ask_cli_revised.contract_directed.tools import nli_premise_population_eval as observed

    inv = observed.inventory()
    return {p["premise"] for p in inv["premises"]}


def build_corpus() -> dict:
    packets = load_packets()
    results = load_results()
    distinct = deduplicate(packets)

    singles = single_span_premises(distinct)
    packet_multi = packet_full_order_premises(packets, distinct)
    slot_multi = eligibility_slot_group_premises(packets, results, distinct)

    historical = historical_premise_texts()

    # deduplicate the prospective set itself (a slot-group premise can be byte-identical to a packet-full-order
    # premise, e.g. a 2-span packet where the slot group covers the same 2 spans) -- keep first, preserve ancestry
    seen_premise_text: dict[str, dict] = {}
    all_candidates = singles + packet_multi + slot_multi
    for c in all_candidates:
        c["overlaps_historical"] = c["premise"] in historical
        text = c["premise"]
        if text not in seen_premise_text:
            c["ancestry"] = [c["construction"]]
            seen_premise_text[text] = c
        else:
            seen_premise_text[text]["ancestry"].append(c["construction"])

    prospective = list(seen_premise_text.values())

    distinct_papers = sorted({p for c in prospective for p in c["paper_ids"]})
    distinct_chunks = sorted({k[1] for c in prospective for k in c["canonical_keys"]})
    distinct_packets = sorted({pkt["packet_id"] for pkt in packets})

    return {
        "stratum_a_keys_excluded": [list(k) for k in sorted(STRATUM_A_KEYS)],
        "packets_examined": len(packets),
        "distinct_canonical_spans_all_packets": len(distinct),
        "prospective_premise_count": len(prospective),
        "prospective_premises": prospective,
        "distinct_papers_represented": distinct_papers,
        "distinct_chunks_represented": distinct_chunks,
        "distinct_packets_represented": distinct_packets,
        "historical_overlap_count": sum(1 for c in prospective if c["overlaps_historical"]),
        "construction_counts": {
            "single_span": sum(1 for c in prospective if "single_span" in c["ancestry"]),
            "packet_full_order": sum(1 for c in prospective if "packet_full_order" in c["ancestry"]),
            "eligibility_slot_group": sum(1 for c in prospective if "eligibility_slot_group" in c["ancestry"]),
        },
    }


def tokenize_and_hash(prospective: list[dict]) -> list[dict]:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(NLI_MODEL, revision=NLI_REVISION, local_files_only=True)
    for p in prospective:
        enc = tok(p["premise"], p["premise"], truncation=False)
        p["self_entailment_pair_tokens"] = len(enc["input_ids"])
        p["model_max_length"] = tok.model_max_length
        p["would_truncate"] = len(enc["input_ids"]) > tok.model_max_length
        p["char_len"] = len(p["premise"])
        p["span_count"] = len(p["canonical_keys"])
        p["sha256"] = hashlib.sha256(p["premise"].encode("utf-8")).hexdigest()
    return prospective


def manifest_candidates(prospective: list[dict]) -> list[dict]:
    """The subset safe to ever include in a real inference batch: not truncated. Requires `tokenize_and_hash`
    to have already run (raises KeyError otherwise -- deliberately, rather than silently tokenizing again)."""
    return [p for p in prospective if not p["would_truncate"]]


EVAL_DIR = RUNS_DIR / "nli-prospective-corpus-eval-001"

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
        "nli-premise-population-eval-001",
        "nli-prospective-pilot-001",
        "nli-repair-demo-001",
        "pilot-001",
        "pilot-prep-003",
        "replay-eligibility-001",
        "replay-eligibility-001-offline-analysis",
    }
)


def write_manifest(run_dir: Path, corpus: dict) -> Path:
    name = run_dir.name
    if name in PROTECTED_RUN_DIRS:
        raise RuntimeError(f"refusing to write into protected prior-attempt directory: {name}")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError(f"refusing to overwrite an already-populated directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "00_prospective_corpus.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)
    return path


if __name__ == "__main__":
    corpus = build_corpus()
    tokenize_and_hash(corpus["prospective_premises"])
    safe = manifest_candidates(corpus["prospective_premises"])
    corpus["manifest_safe_count"] = len(safe)
    corpus["truncating_count"] = corpus["prospective_premise_count"] - len(safe)

    print(f"Distinct canonical spans across all 8 packets: {corpus['distinct_canonical_spans_all_packets']}")
    print(f"Prospective premise count (deduplicated): {corpus['prospective_premise_count']}")
    print(f"  by construction: {corpus['construction_counts']}")
    print(f"Distinct papers represented: {corpus['distinct_papers_represented']}")
    print(f"Distinct chunks represented: {len(corpus['distinct_chunks_represented'])}")
    print(f"Distinct packets represented: {corpus['distinct_packets_represented']}")
    print(f"Historical overlap count: {corpus['historical_overlap_count']}")
    print(f"Would truncate at the model's 512-token limit: {corpus['truncating_count']}")
    print(f"Manifest-safe (non-truncating) prospective premises: {corpus['manifest_safe_count']}")
    out = write_manifest(EVAL_DIR, corpus)
    print(f"Wrote corpus to {out}")
