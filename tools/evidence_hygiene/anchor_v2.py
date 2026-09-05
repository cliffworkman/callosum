"""Reference-region anchoring from DOI + title signals, bounded by spatial proximity.

Cliff's refinement, and the measurements support it: of the 31,122 cached reference entries in this
library **89% carry a DOI** but only 42% carry an `article-title`. A DOI is also a single token, so
it survives fragmentary chunking that splits a 6-word title n-gram across block boundaries -- the
failure that held title-only matching to ~31% of each paper's known references.

The region is then the hit cluster matching the MOST DISTINCT references. That is a definition
rather than a heuristic: a reference list is exactly the part of a document that reproduces many
different references close together. It needs no tail-fraction floor, no density threshold, and no
assumption about citation style, and it naturally excludes an appendix, supplementary material, or
a Nature-format Methods section printed after the list.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict

from tools.evidence_hygiene.corpus import Chunk
from tools.evidence_hygiene.reference_anchor import (
    NGRAM,
    _norm_words,
    _title_ngrams,
    load_reference_records,
    reference_signals,
)

MIN_DISTINCT_REFS = 4   # a cluster must reproduce several different works to be a reference list
CLUSTER_GAP = 25        # chunk positions; a reference list tolerates unmatched entries between hits
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>,;)\]]+", re.I)
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def _doi_tokens(text: str) -> set[str]:
    return {m.group(0).lower().rstrip(".") for m in DOI_RE.finditer(text or "")}


def _surname_year_map(refs: list[dict]) -> dict[tuple[str, str], int]:
    """Third prong: first-author surname + year.

    A DOI's presence in Crossref does not mean it is PRINTED in the paper -- measured here, only
    627 of 4,243 matched references were found by DOI even though 89% of the records carry one.
    Pre-web works are the clearest case: OpenAlex or Crossref may hold a DOI that the printed
    reference list never had. Titles cover 42% of records and DOIs the printed subset, so this
    prong exists for the entries that have neither.

    Weaker than a DOI or a title n-gram -- an in-text citation carries the same surname and year --
    so it is admitted only as CORROBORATION inside an already-anchored cluster, never on its own.
    """
    out: dict[tuple[str, str], int] = {}
    for ordinal, r in enumerate(refs):
        author = r.get("author")
        year = r.get("year")
        if not isinstance(author, str) or not isinstance(year, (str, int)):
            continue
        surname = _norm_words(author)
        if not surname:
            continue
        out.setdefault((surname[0], str(year).strip()), ordinal)
    return out


def anchored_regions(chunks: list[Chunk]) -> tuple[dict[int, set[int]], dict[int, dict]]:
    records = load_reference_records()
    by_paper: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_paper[c.paper_id].append(c)

    regions: dict[int, set[int]] = {}
    diag: dict[int, dict] = {}
    for paper_id, cs in by_paper.items():
        refs = records.get(paper_id)
        if not refs:
            diag[paper_id] = {"status": "no_reference_list"}
            continue
        doi_map, gram_map = reference_signals(refs)
        if not doi_map and not gram_map:
            diag[paper_id] = {"status": "no_usable_signal", "n_refs": len(refs)}
            continue

        ordered = sorted(cs, key=lambda c: (c.page_start or 0, c.chunk_id))
        words_per = [_norm_words(c.text) for c in ordered]

        # Per position, which reference ordinals are evidenced. DOIs match on the chunk itself;
        # title n-grams need a rolling window because entries are split across blocks.
        hits: list[tuple[int, set[int], str]] = []
        for i, c in enumerate(ordered):
            found: set[int] = set()
            kind = ""
            for d in _doi_tokens(c.text):
                if d in doi_map:
                    found.add(doi_map[d])
                    kind = "doi"
            w: list[str] = []
            j = i
            while j < len(ordered) and len(w) < 60:
                w.extend(words_per[j])
                j += 1
            if len(w) >= NGRAM and gram_map:
                for g in (" ".join(w[k : k + NGRAM]) for k in range(len(w) - NGRAM + 1)):
                    if g in gram_map:
                        found.add(gram_map[g])
                        kind = kind or "title"
            if found:
                hits.append((i, found, kind))
        if not hits:
            diag[paper_id] = {"status": "no_matches", "n_refs": len(refs)}
            continue

        # Cluster by proximity, then keep the cluster evidencing the most DISTINCT references.
        clusters: list[list[tuple[int, set[int], str]]] = [[hits[0]]]
        for h in hits[1:]:
            if h[0] - clusters[-1][-1][0] <= CLUSTER_GAP:
                clusters[-1].append(h)
            else:
                clusters.append([h])
        scored = [(len({o for _, s, _ in cl for o in s}), cl) for cl in clusters]
        n_distinct, best = max(scored, key=lambda t: t[0])
        if n_distinct < MIN_DISTINCT_REFS:
            diag[paper_id] = {
                "status": "no_dense_cluster", "n_refs": len(refs), "best_distinct": n_distinct
            }
            continue

        start, end = best[0][0], best[-1][0]

        # Third prong, applied only as CORROBORATION to extend an already-anchored cluster:
        # surname+year entries with neither a printed DOI nor a matchable title. Extension walks
        # outward from the anchored bounds and stops at the first non-corroborating chunk, so an
        # in-text citation elsewhere in the paper can never pull the region toward it.
        sy_map = _surname_year_map(refs)
        if sy_map:
            def corroborates(pos: int) -> bool:
                t = ordered[pos].text or ""
                years = set(_YEAR_RE.findall(t))
                if not years:
                    return False
                names = set(_norm_words(t))
                return any((s, y) in sy_map for s in names for y in years)

            while start - 1 >= 0 and corroborates(start - 1):
                start -= 1
            while end + 1 < len(ordered) and corroborates(end + 1):
                end += 1

        # Trailing fragments (page numbers, split entries) belong to the list they sit in.
        while end + 1 < len(ordered) and len(words_per[end + 1]) < 8:
            end += 1
        regions[paper_id] = {c.chunk_id for c in ordered[start : end + 1]}
        pages = {ordered[i].page_start for i in range(start, end + 1)}
        diag[paper_id] = {
            "status": "anchored",
            "n_refs": len(refs),
            "distinct_matched": n_distinct,
            "coverage": round(n_distinct / len(refs), 3),
            "by_doi": sum(1 for _, _, k in best if k == "doi"),
            "start": start,
            "end": end,
            "n_chunks": len(ordered),
            "span_frac": round((end - start + 1) / len(ordered), 3),
            "pages": len(pages),
        }
    return regions, diag


def main() -> None:
    from collections import Counter

    from tools.evidence_hygiene.corpus import load_chunks

    chunks = load_chunks()
    regions, diag = anchored_regions(chunks)
    st = Counter(d["status"] for d in diag.values())
    print(f"anchoring status across {len(diag)} papers: {dict(st)}")
    ok = [d for d in diag.values() if d["status"] == "anchored"]
    if ok:
        cov = sorted(d["coverage"] for d in ok)
        span = sorted(d["span_frac"] for d in ok)
        print(f"  distinct references matched / known: median {cov[len(cov) // 2]:.2f}  "
              f"min {cov[0]:.2f}  max {cov[-1]:.2f}")
        print(f"  region span as a fraction of paper : median {span[len(span) // 2]:.2f}  "
              f"min {span[0]:.2f}  max {span[-1]:.2f}")
        print(f"  hits carried by DOI: {sum(d['by_doi'] for d in ok)} of "
              f"{sum(d['distinct_matched'] for d in ok)} matched references")
    print(f"  chunks in anchored regions: {sum(len(v) for v in regions.values())}")

    labeled = {c.chunk_id for c in chunks if (c.section or "") == "references"}
    detected = {cid for v in regions.values() for cid in v}
    covered = set(regions)
    lab = {c.chunk_id for c in chunks if c.paper_id in covered and (c.section or "") == "references"}
    print("\nreconciliation, restricted to the papers this anchor covers:")
    print(f"  label references : {len(lab)}   anchor references: {len(detected)}")
    print(f"  agree            : {len(lab & detected)}")
    print(f"  anchor only      : {len(detected - lab)}")
    print(f"  label only       : {len(lab - detected)}")

    byid = {c.chunk_id: c for c in chunks}
    import random

    random.seed(3)
    print("\nsample ANCHOR-ONLY chunks (label missed them):")
    for cid in random.sample(sorted(detected - lab), min(5, len(detected - lab))):
        c = byid[cid]
        print(f"   p{c.paper_id} [{c.section or 'NULL'}] {' '.join(c.text.split())[:100]}")
    print("\nsample LABEL-ONLY chunks (anchor says not in the list):")
    for cid in random.sample(sorted(lab - detected), min(5, len(lab - detected))):
        c = byid[cid]
        print(f"   p{c.paper_id} {' '.join(c.text.split())[:100]}")


if __name__ == "__main__":
    main()
