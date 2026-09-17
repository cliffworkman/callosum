"""Run 0.6 candidate selection — interpretable, with the intended audit hierarchy (steering #2).

GLOBAL AGGREGATE RECONSTRUCTION is the PRIMARY readiness/ranking signal (does the decomposition as a whole
reconstruct the original question?). Per-source-unit coverage is a LOCAL omission detector: it may VETO a
candidate with a clearly-unrepresented unit, but it is NEVER a max-min ranking key (a short/anaphoric unit's
faithful reference-resolving rewrite can legitimately be less literally similar). Leave-one-out and
source-local drift are diagnostic/repair-only and never rank. No opaque scalar — every criterion is
separately inspectable. Pure: no DB, model, or network.
"""

from __future__ import annotations

# A source unit whose best-match cosine is below this is treated as essentially unrepresented -> the
# candidate is vetoed. Conservative (only CLEARLY unrepresented), descriptive/provisional on this small
# dataset — deliberately well below Run 0.5's empirical coverage FLAG gate (which triggers repair, not veto).
COVERAGE_VETO_FLOOR = 0.30


def hard_invariants(candidate: dict) -> tuple[bool, list[str]]:
    """Every source unit has >=1 item with provenance; no unsourced/empty item. (Fallback guarantees items.)"""
    units = candidate["units"]
    items = candidate["items"]
    covered = {i["source_unit_id"] for i in items}
    failures: list[str] = []
    if any(u["source_unit_id"] not in covered for u in units):
        failures.append("source_unit_loss")
    if any(not i.get("source_unit_id") or i.get("source_text") is None for i in items):
        failures.append("missing_provenance")
    if any(not str(i.get("text", "")).strip() for i in items):
        failures.append("empty_item")
    return (not failures), failures


def _row(candidate: dict, *, coverage_veto_floor: float) -> dict:
    ok, failures = hard_invariants(candidate)
    audit = candidate["audit"]
    coverage = [u["best_match"] for u in audit["source_unit_coverage"]]
    min_cov = min(coverage) if coverage else 0.0
    return {
        "candidate": candidate["style"],
        "qualifies": ok,
        "invariant_failures": failures,
        "global_reconstruction": audit["global_reconstruction"],
        "weakest_coverage": audit["weakest_coverage"],
        "min_coverage": round(min_cov, 4),
        "vetoed_low_coverage": bool(min_cov < coverage_veto_floor),
        "redundancy_pairs": len(audit.get("redundancy", [])),
        "n_items": len(candidate["items"]),
        "latency_total_s": candidate.get("calls_summary", {}).get("latency_total_s", 0.0),
    }


def _rank_key(row: dict):
    # PRIMARY global reconstruction (desc) -> SECONDARY fewer redundancy pairs -> TERTIARY simpler (fewer
    # items) -> lower model cost. LOO / source-local drift never enter ranking.
    return (-row["global_reconstruction"], row["redundancy_pairs"], row["n_items"], row["latency_total_s"])


def _reason(winner: dict, ranked: list[dict]) -> str:
    if len(ranked) == 1:
        return f"only eligible candidate; global_reconstruction={winner['global_reconstruction']}"
    runner = ranked[1]
    if winner["global_reconstruction"] != runner["global_reconstruction"]:
        return (
            f"highest global reconstruction ({winner['global_reconstruction']} vs {runner['global_reconstruction']} "
            f"for '{runner['candidate']}')"
        )
    if winner["redundancy_pairs"] != runner["redundancy_pairs"]:
        return f"tie on global reconstruction; fewer redundancy pairs ({winner['redundancy_pairs']} vs {runner['redundancy_pairs']})"
    if winner["n_items"] != runner["n_items"]:
        return f"tie on reconstruction+redundancy; simpler representation ({winner['n_items']} vs {runner['n_items']} items)"
    return "tie broken by lower model cost"


def select(qwen_candidates: list[dict], *, coverage_veto_floor: float = COVERAGE_VETO_FLOOR) -> dict:
    """Rank the Qwen candidates; return the decision (falls back to 'baseline' if none is eligible)."""
    rows = [_row(c, coverage_veto_floor=coverage_veto_floor) for c in qwen_candidates]
    eligible = [r for r in rows if r["qualifies"] and not r["vetoed_low_coverage"]]
    if not eligible:
        return {
            "selected": "baseline",
            "reason": "no eligible Qwen candidate (invariant failure or clearly-unrepresented source unit); "
            "falling back to exact source units",
            "ranked": [],
            "rows": rows,
            "coverage_veto_floor": coverage_veto_floor,
        }
    ranked = sorted(eligible, key=_rank_key)
    winner = ranked[0]
    return {
        "selected": winner["candidate"],
        "reason": _reason(winner, ranked),
        "ranked": [r["candidate"] for r in ranked],
        "rows": rows,
        "coverage_veto_floor": coverage_veto_floor,
    }
