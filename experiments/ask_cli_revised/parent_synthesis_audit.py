"""Phase 26: the minimal deterministic re-derivation audit for a parent-synthesis construction
record. Mirrors ``overview_audit.py``'s own discipline exactly: everything deterministic is
RE-DERIVED from the authoritative inputs and compared to the stored record, byte-for-byte; a
record that breaks a re-derivation is a FAILED check, never an audit crash.

This is the deterministic-only half the Phase-26 brief asked for (Section 23): it audits the
claim ledger, the gap report, and the record's own hash. Realization-stage auditing (did a model
sentence actually trace to its claimed claim?) is explicitly Phase 27's concern -- this module
contains no realization vocabulary at all.
"""

from __future__ import annotations

from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_render as psr


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

    def _hash_matches() -> bool:
        rebuilt = psr.construction_record(
            record["claim_ledger"],
            record["gap_report"],
            sealed_hash=record["sealed_ledger_hash"],
            sufficiency_map_hash=record["sufficiency_map_final_hash"],
        )
        return rebuilt["parent_synthesis_hash"] == record["parent_synthesis_hash"]

    _check("parent_synthesis_hash_matches_content", _hash_matches)

    return {"ok": all(checks.values()), "checks": checks, "problems": problems}
