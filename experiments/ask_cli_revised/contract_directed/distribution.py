"""Distribution report: how do units and seam verification behave over EVERY chunk of the library, not just hand-picked cases?

Checks two things over all article-role attachments: (1) segmentation invariants (every piece is an exact, in-order,
non-overlapping slice of its chunk); (2) the seam verifier's verdicts on every candidate join (left unit open, right unit a
continuation), tallied by outcome and by failing reason, and by chunking strategy. Read-only; writes only a JSON receipt.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import freeze, units
from experiments.ask_cli_revised.contract_directed.store import Library


def analyze_attachment(library: Library, attachment_id: int) -> dict:
    chunks = library.attachment_chunks(attachment_id)
    verify = library.seam_verifier()
    tally = {
        "chunks": len(chunks),
        "pieces": 0,
        "invariant_failures": 0,
        "candidates": 0,
        "established": 0,
        "column_switch_established": 0,
        "reasons": Counter(),
        "chain_lengths": Counter(),
        "fragments": 0,
    }
    tally["strategy"] = chunks[0].get("chunking_strategy") if chunks else None
    for chunk in chunks:
        text = chunk["text"]
        last_end = -1
        for piece in units.chunk_pieces(chunk["chunk_id"], text):
            tally["pieces"] += 1
            if text[piece.start : piece.end] != piece.text or piece.start < last_end:
                tally["invariant_failures"] += 1
            last_end = piece.end
    out = units.build_units(chunks, verify)
    for unit in out:
        if unit.join == "verified_seam":
            tally["chain_lengths"][len(unit.pieces)] += 1
        if unit.open_left or unit.open_right:
            tally["fragments"] += 1
    # candidate accounting: every adjacent open-left/right pair that the builder asked the verifier about
    for a, b in zip(chunks, chunks[1:], strict=False):
        pa, pb = units.chunk_pieces(a["chunk_id"], a["text"]), units.chunk_pieces(b["chunk_id"], b["text"])
        if pa and pb and not units.ends_terminal(pa[-1].text) and units.starts_as_continuation(pb[0].text):
            tally["candidates"] += 1
            verdict = verify(a, b)
            if verdict.state == "established":
                tally["established"] += 1
                if verdict.checks.get("column_switch_verified"):
                    tally["column_switch_established"] += 1
            else:
                tally["reasons"].update(verdict.reasons or ("unspecified",))
    return tally


def run(library_path: Path | str, *, attachment_ids: list[int] | None = None) -> dict:
    library = Library(library_path)
    try:
        ids = attachment_ids or [
            r[0] for r in library.con.execute("SELECT DISTINCT attachment_id FROM chunks ORDER BY attachment_id")
        ]
        total = {
            "attachments": 0,
            "chunks": 0,
            "pieces": 0,
            "invariant_failures": 0,
            "candidates": 0,
            "established": 0,
            "column_switch_established": 0,
            "fragments": 0,
        }
        reasons: Counter = Counter()
        chains: Counter = Counter()
        by_strategy: dict[str, Counter] = {}
        for attachment_id in ids:
            t = analyze_attachment(library, attachment_id)
            total["attachments"] += 1
            for key in (
                "chunks",
                "pieces",
                "invariant_failures",
                "candidates",
                "established",
                "column_switch_established",
                "fragments",
            ):
                total[key] += t[key]
            reasons.update(t["reasons"])
            chains.update(t["chain_lengths"])
            bucket = by_strategy.setdefault(t["strategy"] or "unknown", Counter())
            bucket.update({"chunks": t["chunks"], "candidates": t["candidates"], "established": t["established"]})
        share = round(total["established"] / total["candidates"], 4) if total["candidates"] else None
        return {
            "totals": total,
            "established_share_of_candidates": share,
            "not_established_reasons": dict(reasons.most_common()),
            "verified_chain_length_histogram": {str(k): v for k, v in sorted(chains.items())},
            "by_chunking_strategy": {k: dict(v) for k, v in by_strategy.items()},
            "invariants_hold": total["invariant_failures"] == 0,
        }
    finally:
        library.close()


if __name__ == "__main__":
    out_path = freeze.SLICE_ROOT / "receipts" / "seam_distribution.json"
    result = run(freeze.SLICE_ROOT / "library.sqlite")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["invariants_hold"] else 1)
