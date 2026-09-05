"""Per-prong evaluation of reference-region inference, with a manually adjudicated gold set.

Prongs tested independently and combined: doi | title | title_author | combined.

The section label is NOT ground truth -- adjudication showed 11 of 12 chunks it calls "references"
are acknowledgments, captions, running heads, copyright lines, or table data, because the stateful
tracker labels everything after the first "References" heading. It is reported alongside as a
comparator only.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict

from tools.evidence_hygiene.corpus import load_chunks
from tools.evidence_hygiene.refregion import (
    build_index,
    infer_region,
    load_references,
    match_positions,
)
from tools.evidence_hygiene.store import study_dir

PRONGS = ["doi", "title", "title_author", "combined"]


def main() -> None:
    chunks = load_chunks()
    refs_by_paper = load_references()
    by_paper: dict[int, list] = defaultdict(list)
    for c in chunks:
        by_paper[c.paper_id].append(c)

    refs_by_paper = {p: v for p, v in refs_by_paper.items() if p in by_paper}
    print(f"papers with cached reference metadata AND chunks: {len(refs_by_paper)} of {len(by_paper)}")
    have_doi = sum(1 for v in refs_by_paper.values() if any(r.doi for r in v))
    have_title = sum(1 for v in refs_by_paper.values() if any(r.title_key for r in v))
    print(f"  with >=1 reference DOI          : {have_doi}")
    print(f"  with >=1 usable reference title : {have_title}")

    results: dict[str, dict] = {}
    regions_by_prong: dict[str, dict[int, tuple[int, int]]] = {}
    for prong in PRONGS:
        fired = 0
        spans: list[float] = []
        matched: list[float] = []
        regions: dict[int, tuple[int, int]] = {}
        for paper_id, cs in by_paper.items():
            refs = refs_by_paper.get(paper_id)
            if not refs:
                continue
            idx = build_index(cs)
            hits = match_positions(idx, refs, prong)
            # Corroboration-only prongs may not establish a region alone.
            if prong == "title_author" and not any(
                match_positions(idx, refs, "title").values()
            ):
                continue
            region = infer_region(idx, hits)
            if region is None:
                continue
            fired += 1
            regions[paper_id] = region
            spans.append((region[1] - region[0] + 1) / len(idx.ordered))
            matched.append(len({o for s in hits.values() for o in s}) / len(refs))
        regions_by_prong[prong] = regions
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0.0  # noqa: E731
        results[prong] = {
            "papers_fired": fired,
            "median_span_frac": round(med(spans), 3),
            "median_refs_matched": round(med(matched), 3),
        }
        print(f"\nprong={prong:<13} fired on {fired}/{len(refs_by_paper)} papers | "
              f"median region span {med(spans):.2f} of paper | "
              f"median references matched {med(matched):.2f}")

    # ---- gold set: papers stratified by the conditions Cliff asked to be covered ----
    gold_ids = _stratified_gold(by_paper, refs_by_paper, regions_by_prong["combined"])
    print("\n" + "=" * 78)
    print("GOLD-SET CANDIDATES for manual adjudication (region bounds printed for inspection)")
    print("=" * 78)
    for paper_id, why in gold_ids:
        cs = by_paper[paper_id]
        idx = build_index(cs)
        region = regions_by_prong["combined"].get(paper_id)
        n = len(idx.ordered)
        print(f"\n--- p{paper_id}  [{why}]  {n} chunks  region={region}")
        if region:
            start, end = region
            for probe, tag in ((start - 1, "BEFORE"), (start, "FIRST "), (end, "LAST  "), (end + 1, "AFTER ")):
                if 0 <= probe < n:
                    txt = " ".join((idx.ordered[probe].text or "").split())[:96]
                    print(f"    {tag} #{probe:<4} [{idx.ordered[probe].section or 'NULL'}] {txt}")

    out = study_dir() / "refregion_prongs.json"
    out.write_text(
        json.dumps(
            {
                "prongs": results,
                "gold_candidates": [{"paper_id": p, "stratum": w} for p, w in gold_ids],
                "regions_combined": {str(k): v for k, v in regions_by_prong["combined"].items()},
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {out.name}")


def _stratified_gold(by_paper, refs_by_paper, regions) -> list[tuple[int, str]]:
    """Sample papers covering the hard conditions, not just the easy ones."""
    random.seed(17)
    strata: dict[str, list[int]] = defaultdict(list)
    for paper_id, cs in by_paper.items():
        refs = refs_by_paper.get(paper_id) or []
        if not refs:
            strata["no_reference_metadata"].append(paper_id)
            continue
        doi_frac = sum(1 for r in refs if r.doi) / len(refs)
        labeled = any((c.section or "") == "references" for c in cs)
        if doi_frac == 0:
            strata["no_reference_DOIs"].append(paper_id)
        elif doi_frac < 0.5:
            strata["sparse_DOIs"].append(paper_id)
        if not labeled:
            strata["no_references_label"].append(paper_id)
        if paper_id not in regions:
            strata["region_not_inferred"].append(paper_id)
        if doi_frac >= 0.9 and labeled and paper_id in regions:
            strata["easy_case"].append(paper_id)
    picked: list[tuple[int, str]] = []
    for name, ids in strata.items():
        for p in random.sample(ids, min(2, len(ids))):
            picked.append((p, name))
    print(f"\ngold strata sizes: { {k: len(v) for k, v in strata.items()} }")
    return picked


if __name__ == "__main__":
    main()
