"""Build the frozen adjudicated case corpus (study section 4).

Deterministic sampling, seed 20260905, stratified across every class the brief lists plus a
challenge subset. Each case carries the fields needed to answer the two questions that matter:

  1. Is this unit proposition-bearing AS IT STANDS?  (the H1a governing principle)
  2. If not, is the missing context RECOVERABLE from data callosum already stores?

Question 2 is answered mechanically -- by attempting the reconstruction and re-running the same
proposition test on the result -- so "recoverable" is a measured outcome rather than an opinion.
Whether the attempted join is CORRECT is the separate, hand-adjudicated question, because a
confident wrong join is the harmful failure and no automatic check can certify against it.

Sampling is by stable hash of (chunk_id, seed), not by RNG state, so the corpus is reproducible
regardless of iteration order or how many strata are requested.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".local" / "evidence-units-geom"
DB = OUT / "h1a.sqlite"
SEED = 20260905

from tools.evidence_units_geom.proposition import (  # noqa: E402
    UNRESOLVED,
    YES,
    classify,
    unresolved_reason,
)
from tools.evidence_units_geom.reading_order import (  # noqa: E402
    Unit,
    load_page_units,
    reading_order,
)


def rank(chunk_id: int) -> str:
    """Stable per-chunk sort key. Same corpus every run, on any machine."""
    return hashlib.sha256(f"{SEED}:{chunk_id}".encode()).hexdigest()


def stratum_of(kind: str, verdict, reason: str) -> str:
    """The class a case belongs to. Strata mirror the brief's listed populations."""
    if verdict.status == YES:
        return f"bearing::{kind}"
    if verdict.status == UNRESOLVED:
        return f"unresolved::{reason}"
    return f"not_bearing::{verdict.reason.split(';')[0][:28]}"


def join_with_neighbours(unit: Unit, ordered: list[Unit]) -> tuple[str, list[int]]:
    """Attempt the minimal reconstruction: absorb reading-order neighbours in the same column.

    Deliberately naive and deliberately BOUNDED -- it takes at most one neighbour on each side.
    The point is not to build the best joiner; it is to measure how much of the missing context
    sits immediately adjacent, which is the cheapest possible repair. A more aggressive joiner
    would recover more and be far harder to trust.
    """
    idx = next((i for i, u in enumerate(ordered) if u.chunk_id == unit.chunk_id), None)
    if idx is None:
        return unit.text, [unit.chunk_id]
    parts, ids = [], []
    if idx > 0:
        parts.append(ordered[idx - 1].text)
        ids.append(ordered[idx - 1].chunk_id)
    parts.append(unit.text)
    ids.append(unit.chunk_id)
    if idx + 1 < len(ordered):
        parts.append(ordered[idx + 1].text)
        ids.append(ordered[idx + 1].chunk_id)
    return " ".join(p.strip() for p in parts if p and p.strip()), ids


def main() -> None:
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 160
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)

    types = {cid: kind for cid, kind in conn.execute("SELECT chunk_id, chunk_type FROM chunk_structure")}
    pages = load_page_units(conn)
    ordered_pages = {key: reading_order(units) for key, units in pages.items()}
    page_of = {u.chunk_id: key for key, units in pages.items() for u in units}

    # Every chunk, classified and assigned a stratum.
    strata: dict[str, list[tuple[str, int, str, str]]] = defaultdict(list)
    for cid, text in conn.execute("SELECT id, text FROM chunks"):
        verdict = classify(text)
        reason = unresolved_reason(text) if verdict.status == UNRESOLVED else ""
        kind = types.get(cid, "(unclassified)")
        strata[stratum_of(kind, verdict, reason)].append((rank(cid), cid, kind, reason))

    # Proportional allocation with a floor, so small-but-important classes are not sampled away.
    total = sum(len(v) for v in strata.values())
    floor = 3
    alloc: dict[str, int] = {}
    for name, members in strata.items():
        want = max(floor, round(target * len(members) / total))
        alloc[name] = min(want, len(members))

    cases = []
    for name in sorted(strata):
        for _r, cid, kind, reason in sorted(strata[name])[: alloc[name]]:
            key = page_of.get(cid)
            unit = None
            if key:
                unit = next((u for u in pages[key] if u.chunk_id == cid), None)
            row = conn.execute("SELECT paper_id, page_start, text FROM chunks WHERE id = ?", (cid,)).fetchone()
            paper_id, page, text = row
            joined, join_ids = join_with_neighbours(unit, ordered_pages[key]) if unit else (text, [cid])
            before = classify(text)
            after = classify(joined)
            cases.append(
                {
                    "chunk_id": cid,
                    "paper_id": paper_id,
                    "page": page,
                    "stratum": name,
                    "chunk_type": kind,
                    "unresolved_reason": reason,
                    "text": text,
                    "verdict": before.status,
                    "verdict_reason": before.reason,
                    "has_referent": before.has_referent,
                    "has_assertion": before.has_assertion,
                    "has_statistic": before.has_statistic,
                    "join_ids": join_ids,
                    "joined_text": joined if joined != text else "",
                    "verdict_after_join": after.status,
                    # Mechanical recoverability: did the cheapest possible repair change the answer?
                    "mechanically_recovered": before.status != YES and after.status == YES,
                    # Hand-adjudicated fields, filled in during adjudication.
                    "adjudicated_bearing": None,
                    "adjudicated_join_correct": None,
                    "adjudication_note": "",
                }
            )

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fixtures.json").write_text(
        json.dumps({"seed": SEED, "n": len(cases), "cases": cases}, indent=1), encoding="utf-8"
    )
    print(f"strata: {len(strata)}   sampled: {len(cases)}   corpus: {total}\n")
    print(f"  {'stratum':<44}{'pop':>7}{'n':>5}")
    for name in sorted(strata, key=lambda k: -len(strata[k])):
        print(f"  {name:<44}{len(strata[name]):>7}{alloc[name]:>5}")
    rec = sum(1 for c in cases if c["mechanically_recovered"])
    print(f"\nmechanically recovered by a bounded 1-neighbour join: {rec}/{len(cases)}")
    print("wrote fixtures.json")


if __name__ == "__main__":
    main()
