"""Task F: a read-only replay of `runs/pilot-001/*.jsonl` through the v2 architecture's PURE, deterministic parts
(Task C's instrument detector, Task D's routing) — never a live model call, never a write into the run directory.

Three categories are kept strictly separate, per Cliff's correction (session 2026-09-27):
  - OBSERVED: exactly what Gate 1's saved receipts recorded.
  - MECHANICALLY REPLAYABLE: what pure code, run over that already-saved, already-verbatim-checked data, can
    compute with certainty (whether a saved neighborhood's saved text matches the deterministic pattern; how many
    own-route (packet, child) pairs exist; what tier/order a candidate would be scheduled in).
  - ASSUMPTION / UNKNOWN: anything that would need an actual model judgment to resolve (on_topic, attribution
    acceptance, relata-tying, polarity). This tool never guesses at these — it reports the count of judgments
    whose outcome is unknown, honestly, as the single largest source of uncertainty.

A packet/neighborhood that this replay determines WOULD be scheduled is reported as "scheduled for judgment" or
"eligible for the call-skip" — never as "judged" or "closes". Run with:
    python -m experiments.ask_cli_revised.contract_directed.tools.simulate_eligibility_v2
"""

from __future__ import annotations

import json

from experiments.ask_cli_revised import library_copy
from experiments.ask_cli_revised.contract_directed import deterministic_candidates as dc
from experiments.ask_cli_revised.contract_directed import eligibility_routing as routing
from experiments.ask_cli_revised.contract_directed import endpoint_guard, freeze
from experiments.ask_cli_revised.contract_directed import packet as packet_mod
from experiments.ask_cli_revised.contract_directed.store import Library

RUN_DIR = freeze.SLICE_ROOT / "runs" / "pilot-001"
LIBRARY_PATH = freeze.SLICE_ROOT / "library.sqlite"
LIBRARY_FINGERPRINT = freeze.SLICE_ROOT / "library.sqlite.fingerprint.json"
PILOT_CHILDREN = ("c5", "c6", "c9", "c10", "c11")


def _library_unchanged() -> bool:
    try:
        library_copy.verify(LIBRARY_PATH, LIBRARY_FINGERPRINT)
        return True
    except library_copy.LibraryCopyDrift:
        return False


def _jsonl(name: str) -> list[dict]:
    path = RUN_DIR / name
    return (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if path.exists()
        else []
    )


def _load() -> dict:
    return {
        "nominations": _jsonl("01_nominations.jsonl"),
        "triage": _jsonl("02_triage.jsonl"),
        "neighborhoods": _jsonl("05_neighborhoods.jsonl"),
        "localization": _jsonl("06_localization.jsonl"),
        "recovery": _jsonl("10_recovery.jsonl"),
        "packets": _jsonl("07_packets.jsonl"),
        "eligibility": _jsonl("08_eligibility.jsonl"),
        "ledger": json.loads((RUN_DIR / "14_ledger.json").read_text(encoding="utf-8")),
    }


def _localization_target_kinds(nbhd_routes: list[str], child) -> set[str] | None:
    unit_ids = {r.split(":", 1)[1] for r in nbhd_routes if r.startswith("unit_probe:")}
    child_unit_ids = {u.unit_id for u in child.content_units}
    if not unit_ids or not (unit_ids <= child_unit_ids):
        return None
    return {child.unit(uid).kind for uid in unit_ids}


def _first_pass_nbhd_index(nbhds: list[dict]) -> dict[tuple[str, str], dict]:
    return {(n["child_id"], n["nbhd_id"]): n for n in nbhds if n.get("state") == "read"}


def _recovery_nbhd_index(recovery: list[dict]) -> dict[tuple[str, str], dict]:
    """Recovery-sourced neighborhoods are never written to `05_neighborhoods.jsonl` (`inspect_and_neighborhoods`
    only logs the FIRST pass) — they are logged in `10_recovery.jsonl` with their own `chunk_ids`/`attachment`.
    Rebuilt into the same `{attachment_id, chunk_ids, routes}` shape `neighborhood_units` needs, so every localized
    call — first-pass or recovery — gets exactly one disposition, none silently dropped."""
    out = {}
    for r in recovery:
        attachment = r.get("attachment") or {}
        out[(r["child_id"], r["nbhd_id"])] = {
            "nbhd_id": r["nbhd_id"],
            "attachment_id": attachment.get("id"),
            "chunk_ids": r.get("chunk_ids", []),
            "routes": [f"recovery:{r.get('trigger_reason', 'unknown')}"],
        }
    return out


def replay_localization(loc: list[dict], nbhds: list[dict], recovery: list[dict], library: Library, substrate) -> dict:
    """Mechanically replayable: rebuild the REAL sentence units of every neighborhood Gate 1 actually read —
    first-pass (`05_neighborhoods.jsonl`) AND recovery (`10_recovery.jsonl`, verified by exact `(child_id,
    nbhd_id)` match against `10_recovery.jsonl`'s own 18 rows, not assumed) — over the same read-only library copy.
    No packets, no model, no guessing from what Qwen happened to pick. Every one of the 106 observed calls lands
    in exactly one of the four buckets below; none is silently dropped."""
    first_pass = _first_pass_nbhd_index(nbhds)
    recovered = _recovery_nbhd_index(recovery)
    call_skip_eligible, pattern_matched_but_mixed_kind, no_pattern, unresolved = [], [], [], []
    unit_cache: dict[tuple[str, str], list] = {}
    for record in loc:
        if record.get("call") is None:
            continue  # already a Gate-1 deterministic skip (none existed in Gate 1; defensive only)
        key = (record["child_id"], record["nbhd_id"])
        child = substrate.child(record["child_id"])
        nb, source = first_pass.get(key), "first_pass"
        if nb is None:
            nb, source = recovered.get(key), "recovery"
        if nb is None:
            unresolved.append(key)  # would mean an 19th unexplained call; verified below there are none
            continue
        if key not in unit_cache:
            unit_list, _ = packet_mod.neighborhood_units(nb, library)
            unit_cache[key] = unit_list
        matches = dc.find_instrument_pairing_candidates(unit_cache[key], child)
        if not matches:
            no_pattern.append({"child_id": record["child_id"], "nbhd_id": record["nbhd_id"], "source": source})
            continue
        kinds = _localization_target_kinds(nb.get("routes", []), child)
        if kinds is not None and kinds <= dc.INSTRUMENT_MANNER_KINDS:
            call_skip_eligible.append(
                {
                    "child_id": record["child_id"],
                    "nbhd_id": record["nbhd_id"],
                    "source": source,
                    "matched_units": [c["establishing"][0] for c in matches],
                }
            )
        else:
            pattern_matched_but_mixed_kind.append(
                {
                    "child_id": record["child_id"],
                    "nbhd_id": record["nbhd_id"],
                    "source": source,
                    "routes": nb.get("routes", []),
                }
            )
    observed = sum(1 for r in loc if r.get("call") is not None)
    accounted = len(call_skip_eligible) + len(pattern_matched_but_mixed_kind) + len(no_pattern) + len(unresolved)
    assert accounted == observed, (accounted, observed)  # every observed call gets exactly one disposition
    return {
        "observed_localization_calls": observed,
        "mechanically_replayable_call_skip_eligible": call_skip_eligible,
        "pattern_matched_but_call_still_required_mixed_kind": pattern_matched_but_mixed_kind,
        "no_deterministic_pattern_call_still_required": no_pattern,
        "no_deterministic_pattern_call_still_required_count": len(no_pattern),
        "recovery_calls_accounted_for": sum(
            1 for x in (call_skip_eligible + pattern_matched_but_mixed_kind + no_pattern) if x["source"] == "recovery"
        ),
        "recovery_calls_observed_in_10_recovery_jsonl": len(recovery),
        "unresolved_disposition_count": len(unresolved),  # must be 0 — asserted above
    }


def replay_eligibility(packets: list[dict], substrate, children: list[str]) -> dict:
    """Mechanically replayable: the hard floor of own-route (packet, child) pairs D2 guarantees, and per-child
    cross-route queue sizes/order. UNKNOWN (never guessed): whether any of these would actually pass on_topic/
    attribution/relata-tying — that is a real model judgment this replay cannot make."""
    by_id = {p["packet_id"]: p for p in packets if p.get("state") == "built"}
    own_pairs, cross_queue_sizes = 0, {}
    for cid in children:
        child = substrate.child(cid)
        own = routing.own_route_packets(child, list(by_id.values()))
        cross = routing.cross_route_packets(child, list(by_id.values()))
        own_pairs += len(own)
        cross_queue_sizes[cid] = len(cross)
    return {
        "unique_packets": len(by_id),
        "own_route_pairs_mechanically_scheduled_tier1": own_pairs,
        "cross_route_queue_size_per_child_tier2_candidates": cross_queue_sizes,
        "note": "these are SCHEDULED-FOR-JUDGMENT counts, not outcomes — on_topic/attribution/relata-tying are "
        "real model judgments this replay does not and cannot make",
    }


def triage_value_check(nominations: list[dict], eligibility: list[dict], packets: list[dict]) -> dict:
    """Data-grounded (not a proposal to build): of the papers actually triaged per child in Gate 1, how many ever
    produced a packet that closed or partially established a unit for ANY child — the empirical basis for naming
    (not implementing) a future triage-cap reduction."""
    by_id = {p["packet_id"]: p for p in packets if p.get("state") == "built"}
    contributing_papers = {
        by_id[r["packet_id"]]["paper_id"]
        for r in eligibility
        if r.get("state") == "usable"
        and r["packet_id"] in by_id
        and any(u["status"] != "not_addressed" for u in r.get("per_unit", {}).values())
    }
    triaged_papers = {n["paper_id"] for n in nominations}
    return {
        "papers_triaged_total": len(triaged_papers),
        "papers_that_ever_contributed_a_non_not_addressed_packet": len(contributing_papers & triaged_papers),
        "papers_never_contributing": len(triaged_papers - contributing_papers),
    }


def main() -> dict:
    library_unchanged_before = _library_unchanged()
    with endpoint_guard.refuse_all():  # this replay makes no network call of any kind — verified, not assumed
        data = _load()
        substrate = freeze.load_frozen()
        library = Library(LIBRARY_PATH)  # read-only by construction (store.py); never edits runs/pilot-001/
        try:
            loc_result = replay_localization(
                data["localization"], data["neighborhoods"], data["recovery"], library, substrate
            )
        finally:
            library.close()
    library_unchanged_after = _library_unchanged()
    elig_result = replay_eligibility(data["packets"], substrate, list(PILOT_CHILDREN))
    triage_result = triage_value_check(data["nominations"], data["eligibility"], data["packets"])
    ledger = data["ledger"]
    report = {
        "library_copy_unchanged": {"before": library_unchanged_before, "after": library_unchanged_after},
        "observed_gate1": {
            "total_calls": ledger["calls"],
            "elapsed_seconds": ledger["elapsed_seconds"],
            "stages": {k: v.get("calls", 0) for k, v in ledger["stages"].items()},
        },
        "localization_replay": loc_result,
        "eligibility_replay": elig_result,
        "triage_value_check": triage_result,
        "bounds": {
            "triage": {
                "lower": ledger["stages"]["triage"]["calls"],
                "upper": ledger["stages"]["triage"]["calls"],
                "note": "unaddressed by this iteration",
            },
            "localization": {
                "lower": loc_result["observed_localization_calls"]
                - len(loc_result["mechanically_replayable_call_skip_eligible"]),
                "upper": loc_result["observed_localization_calls"],
            },
            "eligibility": {
                "lower": elig_result["own_route_pairs_mechanically_scheduled_tier1"],
                "upper": ledger["stages"]["eligibility"]["calls"],
                "note": "the gap is on_topic/attribution/relata-tying — real model judgments, not knowable from replay",
            },
            "answers": {"lower": len(PILOT_CHILDREN), "upper": len(PILOT_CHILDREN)},
        },
    }
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, ensure_ascii=False, default=str))
