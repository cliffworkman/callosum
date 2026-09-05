"""Does hygiene-before-reconstruction actually fix the false joins? (study sections 6A, 14, 15)

The adjudication found a 59% false-join rate for a bounded one-neighbour join, and that 62% of
those false joins are running heads, running footers and publication metadata -- boilerplate H1a
ALREADY detects and deliberately does not act on.

That is a hypothesis, not a result. It predicts something specific and falsifiable: if the
boilerplate is removed from the neighbour pool BEFORE joining, those 16 joins should become clean
and no currently-correct join should break.

This measures exactly that, and reports the joins that are still wrong afterwards -- because the
residue is what determines whether reconstruction is safe to ship at all.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".local" / "evidence-units-geom"
DB = OUT / "h1a.sqlite"

from tools.evidence_units_geom.adjudicate import ADJ, CORRECT, FALSE, wilson  # noqa: E402
from tools.evidence_units_geom.fixtures import join_with_neighbours  # noqa: E402
from tools.evidence_units_geom.proposition import YES, classify  # noqa: E402
from tools.evidence_units_geom.reading_order import load_page_units, reading_order  # noqa: E402

# What H1a already knows is not scientific evidence. Note `table_cell_debris` is NOT in this set:
# a table cell is real evidence that has lost its context, which is the opposite problem.
BOILERPLATE = {"running_head", "running_footer", "publication_metadata"}


def main() -> None:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    types = dict(conn.execute("SELECT chunk_id, chunk_type FROM chunk_structure"))
    data = json.loads((OUT / "fixtures.json").read_text(encoding="utf-8"))

    pages = load_page_units(conn)
    # Two neighbour pools: the raw one, and one with H1a-detected boilerplate removed.
    clean_pages = {key: [u for u in units if types.get(u.chunk_id) not in BOILERPLATE] for key, units in pages.items()}
    clean_ordered = {key: reading_order(units) for key, units in clean_pages.items()}
    page_of = {u.chunk_id: key for key, units in pages.items() for u in units}

    rows = []
    for case in data["cases"]:
        if not case["mechanically_recovered"]:
            continue
        cid = case["chunk_id"]
        verdict_before = ADJ.get(cid, (None, "", ""))[0]
        mechanism = ADJ.get(cid, (None, "", ""))[1]
        key = page_of.get(cid)
        unit = next((u for u in clean_pages.get(key, []) if u.chunk_id == cid), None)
        if unit is None:
            # The case chunk is itself boilerplate: hygiene removes it outright rather than joining.
            rows.append((cid, verdict_before, mechanism, "removed_as_boilerplate", False))
            continue
        joined, _ids = join_with_neighbours(unit, clean_ordered[key])
        still_bears = classify(joined).status == YES
        rows.append((cid, verdict_before, mechanism, "rejoined", still_bears))

    removed = [r for r in rows if r[3] == "removed_as_boilerplate"]
    rejoined = [r for r in rows if r[3] == "rejoined"]
    print(f"COUNTERFACTUAL: hygiene applied BEFORE the one-neighbour join (n = {len(rows)})\n")
    print(f"  case chunk was itself boilerplate -> dropped, never joined : {len(removed)}")
    print(f"  case chunk survives, rejoined against a clean pool        : {len(rejoined)}")

    # The load-bearing question: do the boilerplate-caused false joins go away, and does any
    # correct join break?
    boiler_false = [r for r in rows if r[1] == FALSE and r[2] == "boilerplate"]
    fixed = [r for r in boiler_false if r[3] == "removed_as_boilerplate" or not r[4]]
    print(f"\n  boilerplate-caused false joins             : {len(boiler_false)}")
    print(
        f"    no longer produce a bearing unit          : {len(fixed)} "
        f"({100 * len(fixed) / max(len(boiler_false), 1):.0f}%)"
    )

    correct_before = [r for r in rows if r[1] == CORRECT]
    kept = [r for r in correct_before if r[3] == "rejoined" and r[4]]
    print(f"\n  previously-correct joins                   : {len(correct_before)}")
    print(
        f"    survive hygiene unchanged                 : {len(kept)} "
        f"({100 * len(kept) / max(len(correct_before), 1):.0f}%)"
    )
    broken = [r for r in correct_before if r not in kept]
    for cid, *_ in broken:
        print(f"      BROKEN by hygiene: F{cid}")

    # Residual false-join rate over the joins hygiene still permits.
    residual_false = [r for r in rows if r[3] == "rejoined" and r[4] and r[1] == FALSE and r[2] != "boilerplate"]
    permitted = [r for r in rows if r[3] == "rejoined" and r[4]]
    n = len(permitted)
    k = len(residual_false)
    lo, hi = wilson(k, n)
    print(
        f"\n  RESIDUAL false-join rate after hygiene: {k}/{n} = {100 * k / max(n, 1):.1f}%"
        f"  95% CI [{100 * lo:.0f}%, {100 * hi:.0f}%]"
    )
    print("  residual mechanisms:", sorted({r[2] for r in residual_false}))

    (OUT / "counterfactual.json").write_text(
        json.dumps(
            {
                "n": len(rows),
                "removed_as_boilerplate": len(removed),
                "boilerplate_false_before": len(boiler_false),
                "boilerplate_false_fixed": len(fixed),
                "correct_before": len(correct_before),
                "correct_surviving": len(kept),
                "residual_false": k,
                "permitted_joins": n,
                "rows": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print("\nwrote counterfactual.json")


if __name__ == "__main__":
    main()
