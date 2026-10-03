"""Re-derivation audit for a parent-synthesis construction record. Mirrors ``overview_audit.py``'s discipline: everything
deterministic is RE-DERIVED from the authoritative inputs and compared with the stored record; a record that breaks a
re-derivation FAILS the audit, it never crashes it.

Phase 26 checks (ledger, gap report, hashes) run for every record. Phase 27 realization checks run only when the record
carries ``realized_segments``, so a Phase-26 record audits exactly as it did. The pure lexical screens are cheap, so
they are RE-RUN. The NLI scores are recorded values from a model run, so their structure and coverage are audited, not
re-computed (the same stance ``overview_audit`` takes toward source verification's stored scores).
"""

from __future__ import annotations

from experiments.ask_cli_revised import parent_synthesis as ps
from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_render as psr


def _realization_checks(record: dict, sealed: dict, checks: dict, problems: list[str]) -> None:
    segments = record["realized_segments"]
    ledger = {c["claim_id"]: c for c in record["claim_ledger"]}

    def _check(name: str, fn) -> None:
        try:
            checks[name] = bool(fn())
        except Exception as exc:  # noqa: BLE001 - a malformed segment fails its check, never the audit
            checks[name] = False
            problems.append(f"{name}: could not be re-derived from the stored record ({type(exc).__name__})")

    def covers_each_claim_once() -> bool:
        ids = [s["claim_id"] for s in segments]
        return sorted(ids) == sorted(ledger) and len(ids) == len(set(ids))

    def grounded_segments_are_single_claims() -> bool:
        return all(
            s["claim_id"] in ledger and s["final_text"] == s["proposed_text"]
            for s in segments
            if s["status"] == "grounded"
        )

    def citations_are_admissible_ids() -> bool:
        return all(s["cited_proposition_ids"] == ledger[s["claim_id"]]["admissible_proposition_ids"] for s in segments)

    def fallback_mapping_is_honest() -> bool:
        for s in segments:
            grounded = s["status"] == "grounded"
            if s["fallback_used"] == grounded:
                return False
            if not grounded and s["final_text"] != psr.literal_statement(ledger[s["claim_id"]]):
                return False
        return True

    def lexical_screens_rederive() -> bool:
        claim_ledger = record["claim_ledger"]
        for s in segments:
            if s["proposed_text"] is None:
                continue
            fresh = ps.lexical_screens(ledger[s["claim_id"]], s["proposed_text"], claim_ledger, sealed)
            if (fresh["claim"], fresh["evidence"], fresh["heterogeneity"]) != (
                s["claim_screen_reasons"],
                s["evidence_screen_reasons"],
                s["heterogeneity_reasons"],
            ):
                return False
            if s["status"] == "grounded" and (fresh["claim"] or fresh["evidence"] or fresh["heterogeneity"]):
                return False
        return True

    def nli_structure_recorded() -> bool:
        for s in segments:
            if s["status"] not in ("grounded", "withheld"):
                continue
            if s["nli_error"] is None and not (
                isinstance(s["nli"], dict) and "claim" in s["nli"] and "evidence" in s["nli"]
            ):
                return False
        return True

    def counts_match() -> bool:
        grounded = sum(1 for s in segments if s["status"] == "grounded")
        return record["grounded_count"] == grounded and record["fallback_count"] == len(segments) - grounded

    def state_matches_segments() -> bool:
        grounded = sum(1 for s in segments if s["status"] == "grounded")
        state = record["realization_state"]
        if state == "declined":
            return not segments and not record["claim_ledger"]
        if not record["claim_ledger"]:
            return state == "no_claims" and not segments
        if not record["call_attempted"]:
            return state == "deterministic_fallback" and grounded == 0
        if grounded == len(segments):
            return state == "model_realized"
        return state == ("deterministic_fallback" if grounded == 0 else "mixed_model_and_fallback")

    def model_metadata_iff_call_attempted() -> bool:
        return ("model" in record) == bool(record["call_attempted"])

    _check("realized_segments_cover_each_claim_exactly_once", covers_each_claim_once)
    _check("grounded_segment_is_exactly_one_claim", grounded_segments_are_single_claims)
    _check("citations_are_exactly_the_claims_admissible_ids", citations_are_admissible_ids)
    _check("fallback_mapping_is_honest", fallback_mapping_is_honest)
    _check("lexical_screens_rederive", lexical_screens_rederive)
    _check("nli_structure_recorded", nli_structure_recorded)
    _check("realization_counts_match_segments", counts_match)
    _check("realization_state_matches_segments", state_matches_segments)
    _check("model_metadata_present_iff_call_attempted", model_metadata_iff_call_attempted)


def audit_parent_synthesis(
    sufficiency_map_final: dict, sealed: dict, sufficiency_recovery_targets: dict, record: dict
) -> dict:
    checks: dict[str, bool] = {}
    problems: list[str] = []

    def _check(name: str, fn) -> None:
        try:
            checks[name] = bool(fn())
        except Exception as exc:  # noqa: BLE001 - a record that breaks a re-derivation has failed the audit
            checks[name] = False
            problems.append(f"{name}: could not be re-derived from the stored record ({type(exc).__name__})")

    rederived_claims = psl.build_claim_ledger(sufficiency_map_final, sealed)
    rederived_gaps = psl.build_gap_report(sufficiency_recovery_targets, sufficiency_map_final=sufficiency_map_final)
    rederived_map_hash = psl.sufficiency_map_hash(sufficiency_map_final)

    _check("claim_ledger_matches_rederivation", lambda: record["claim_ledger"] == rederived_claims)
    _check("gap_report_matches_rederivation", lambda: record["gap_report"] == rederived_gaps)
    _check("sufficiency_map_final_hash_matches", lambda: record["sufficiency_map_final_hash"] == rederived_map_hash)
    _check("parent_synthesis_hash_matches_content", lambda: psr.record_hash(record) == record["parent_synthesis_hash"])

    if "realized_segments" in record:
        _realization_checks(record, sealed, checks, problems)

    return {"ok": all(checks.values()), "checks": checks, "problems": problems}
