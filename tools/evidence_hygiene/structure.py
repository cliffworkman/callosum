"""Paper-global structure: bibliography region, then layout repetition. Order matters.

BIBLIOGRAPHY MUST BE FENCED FIRST. Reference entries share heavy n-gram overlap (journal titles,
repeated author strings) and span many pages of one paper, so a repetition detector run over an
un-fenced bibliography nominates journal names and author strings as "boilerplate" -- and then
matches those same strings inside body prose. Production's whole-chunk exact matching is
*accidentally* immune to this; a substring-aware detector is not.

LAYOUT REPETITION IS SEPARATE FROM SEMANTIC REPETITION. Layout repetition (same string at a stable
page position across >=3 pages of ONE paper) may hard-exclude. Cross-paper near-duplicate content is
measured but NEVER enforced here: in a library containing replications and meta-analyses, excluding
near-duplicate Methods across papers would delete exactly the evidence a synthesis needs.

This module also fixes the scope defect behind backlog #79: production's
`exclude_repeated_boilerplate_chunks` groups per-paper but only over the candidate list it is
handed, which `pipeline.py:274-277` has already section-filtered. Measured on this library, a
`sections=['methods']` synthesis leaks 112 running-head chunks that whole-paper scope removes.
Detection here is always whole-paper, independent of any later section filter.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict

from app.backend.pdf_processing.extraction import _canonical_characters
from tools.evidence_hygiene.corpus import Chunk
from tools.evidence_hygiene.features import Features

_TRAILING_NUMBER = re.compile(r"\s*\d+\s*$")

BIBLIO_HOT = 2.0          # per-chunk score at which a chunk looks bibliographic
REGION_MIN_HOT = 5        # a real reference list is many entries, not one stray citation
REGION_MIN_DENSITY = 0.45 # tolerate interleaved page furniture inside the region
REGION_MIN_TAIL_FRACTION = 0.30  # a reference list lives in the paper's tail, never its opening
REGION_WINDOW = 8         # scoreable chunks per sliding density window
REPEAT_MIN_PAGES = 3
REPEAT_MAX_WORDS = 25
REPEAT_X_SIGMA = 6.0      # pt; a running head sits at a stable x across pages


def repetition_key(text: str) -> str:
    """Whitespace-collapsed, character-canonicalized, trailing-page-number stripped.

    Production's `_repetition_key` collapses whitespace and strips a trailing number but does NOT
    canonicalize characters. 865 chunks in this library contain U+00AD, so a running head rendered
    with a discretionary hyphen on one page and without it on another yields two distinct keys and
    is missed entirely. Only the CHARACTER half of normalization is applied here -- soft hyphen,
    ligature, dash, NFC -- so this creates no dependency on hyphen-break resolution.
    """
    canon = _canonical_characters(text or "")
    return _TRAILING_NUMBER.sub("", " ".join(canon.split()))


def bibliography_regions(
    chunks: list[Chunk],
    feats: dict[int, Features],
    repeated: dict[int, dict] | None = None,
) -> dict[int, set[int]]:
    """Per paper, the set of chunk ids inside the reference region.

    Anchored to the paper's tail and detected from SHAPE, never from `chunks.section`: 10 of 108
    papers have no references-labeled chunk at all, and 360 labeled-references chunks are real
    prose. The label is reconciled against this afterwards, never trusted as the detector.
    """
    by_paper: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_paper[c.paper_id].append(c)

    regions: dict[int, set[int]] = {}
    for paper_id, cs in by_paper.items():
        ordered = sorted(cs, key=lambda c: (c.page_start or 0, c.chunk_id))

        # The region is found as a BOUNDARY, then everything after it is in scope. Per-chunk
        # classification cannot work here: measured on this library, 43% of reference chunks are
        # under 8 words ('9', 'A.F. Bastos et al.', '408 CASSIDY AND KRENDL') with a median
        # bibliographic score of 0.40, because a single reference entry is split across several
        # tiny blocks interleaved with page furniture. Density is therefore measured only over
        # SCOREABLE chunks (>= 8 words); fragments ride along with the region they sit in.
        # Page furniture is excluded from the density signal. A reference region interleaved with
        # running heads and journal-footer lines ("Journal of Affective Disorders Reports 10 (2022)
        # 100380") was measured falling below the density floor and going undetected entirely.
        rep = repeated or {}
        scoreable = [
            i for i, c in enumerate(ordered)
            if c.chunk_id in feats
            and feats[c.chunk_id].n_words >= 8
            and c.chunk_id not in rep
            and not feats[c.chunk_id].publication_meta
        ]
        if len(scoreable) < REGION_MIN_HOT:
            regions[paper_id] = set()
            continue
        # A reference list is anchored to the paper's tail. Without this floor the density rule
        # produced catastrophic early starts (measured: one paper began at index 0 of 290, another
        # at 1 of 237) whenever dense author-year in-text citation made body prose score highly.
        earliest = int(REGION_MIN_TAIL_FRACTION * len(ordered))

        # Anchor 1: an explicit heading. Pure single-line heading blocks are dropped at ingest
        # (extraction.py:227-228), but a merged "References 1. Fusick AJ..." block survives and the
        # prefix scan recovers it.
        heading_at = next(
            (i for i, c in enumerate(ordered)
             if i >= earliest
             and c.chunk_id in feats
             and feats[c.chunk_id].heading_prefix_key == "references"),
            None,
        )

        # Anchor 2: a sustained bibliography-dense RUN, found with a sliding window.
        #
        # An earlier version required density to hold all the way to the paper's last chunk. That
        # silently failed on 47 papers whose reference chunks already scored 4.2-5.2: anything
        # following the reference list -- an appendix, supplementary material, or a stretch of body
        # prose the heuristic tracker had mislabeled as 'references' -- dragged the tail density
        # below the floor, so no valid start existed and the whole region went undetected. The
        # region must therefore be allowed to END before the paper does.
        hot_flags = [feats[ordered[j].chunk_id].biblio_score >= BIBLIO_HOT for j in scoreable]
        window = min(REGION_WINDOW, len(scoreable))
        marked = [
            k for k in range(len(scoreable) - window + 1)
            if scoreable[k] >= earliest
            and sum(hot_flags[k : k + window]) / window >= REGION_MIN_DENSITY
        ]
        density_span = None
        if marked:
            # Merge overlapping windows into runs; keep the last run, which is the reference list
            # (an early dense run is a citation-heavy Discussion, not a bibliography).
            runs: list[list[int]] = [[marked[0]]]
            for k in marked[1:]:
                if k - runs[-1][-1] <= window:
                    runs[-1].append(k)
                else:
                    runs.append([k])
            run = runs[-1]
            idxs = [scoreable[k] for k in range(run[0], min(run[-1] + window, len(scoreable)))]
            hot_idxs = [j for j in idxs if feats[ordered[j].chunk_id].biblio_score >= BIBLIO_HOT]
            if len(hot_idxs) >= REGION_MIN_HOT:
                density_span = (min(hot_idxs), max(hot_idxs))

        starts = [a for a in (heading_at, density_span[0] if density_span else None) if a is not None]
        if not starts:
            regions[paper_id] = set()
            continue
        # Prefer the earlier anchor: a heading preceding the dense run is the true boundary, and
        # starting late would leave the list's first entries mislabeled as body prose.
        start = min(starts)
        end = density_span[1] if density_span else len(ordered) - 1
        # Trailing fragments (page numbers, split entries) belong to the region they sit in.
        while end + 1 < len(ordered) and (
            ordered[end + 1].chunk_id not in feats or feats[ordered[end + 1].chunk_id].n_words < 8
        ):
            end += 1
        regions[paper_id] = {c.chunk_id for c in ordered[start : end + 1]}
    return regions


def layout_repetition(
    chunks: list[Chunk], feats: dict[int, Features], biblio: dict[int, set[int]]
) -> dict[int, dict]:
    """Whole-paper repeated short text at a stable page position -> running head / footer.

    Returns {chunk_id: {key, n_pages, x0_sigma, y_band}}. Bibliography-region chunks are excluded
    from the pass entirely (see the module docstring).
    """
    by_paper: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        if c.chunk_id in biblio.get(c.paper_id, set()):
            continue
        by_paper[c.paper_id].append(c)

    flagged: dict[int, dict] = {}
    for paper_id, cs in by_paper.items():
        groups: dict[str, list[Chunk]] = defaultdict(list)
        for c in cs:
            key = repetition_key(c.text)
            if key and len(key.split()) <= REPEAT_MAX_WORDS:
                groups[key].append(c)
        for key, members in groups.items():
            pages = {c.page_start for c in members if c.page_start is not None}
            if len(pages) < REPEAT_MIN_PAGES:
                continue
            boxes = [c.box for c in members if c.box]
            if not boxes:
                continue
            x0s = [b[0] for b in boxes]
            sigma = statistics.pstdev(x0s) if len(x0s) > 1 else 0.0
            # Position stability is the half production's text-only detector lacks; it is what
            # makes hard exclusion defensible rather than merely plausible.
            if sigma > REPEAT_X_SIGMA:
                continue
            tops = [feats[c.chunk_id].y_top_frac for c in members
                    if c.chunk_id in feats and feats[c.chunk_id].y_top_frac is not None]
            band = "middle"
            if tops:
                mt = statistics.median(tops)
                band = "top" if mt < 0.12 else ("bottom" if mt > 0.85 else "middle")
            for c in members:
                flagged[c.chunk_id] = {
                    "key": key, "n_pages": len(pages), "x0_sigma": round(sigma, 2), "y_band": band,
                }
    return flagged


def main() -> None:
    from tools.evidence_hygiene.corpus import calibrate, load_chunks
    from tools.evidence_hygiene.features import compute
    from tools.evidence_hygiene.store import connect, raw_sha

    chunks = load_chunks()
    cal = calibrate(chunks)
    feats = {f.chunk_id: f for f in compute(chunks, cal)}
    # ORDERING, refined empirically: EXACT-KEY layout repetition is safe to run BEFORE
    # bibliography fencing and is needed by it (page furniture otherwise depresses the density
    # signal below its floor). The fencing-first constraint in the module docstring applies to
    # SUBSTRING/shingle repetition, which can nominate journal and author strings drawn from
    # reference content and then match them inside body prose. A full reference entry is never
    # repeated verbatim across 3+ pages at a stable x, so exact-key detection cannot do that.
    rep0 = layout_repetition(chunks, feats, biblio={})
    biblio = bibliography_regions(chunks, feats, repeated=rep0)
    rep = layout_repetition(chunks, feats, biblio)

    n_bib = sum(len(v) for v in biblio.values())
    print(f"bibliography region: {n_bib} chunks across "
          f"{sum(1 for v in biblio.values() if v)}/{len(biblio)} papers")

    # Reconcile against the heuristic label -- the disagreements are the acceptance targets.
    labeled = {c.chunk_id for c in chunks if (c.section or "") == "references"}
    detected = {cid for v in biblio.values() for cid in v}
    print(f"  label says references : {len(labeled)}")
    print(f"  region detector says  : {len(detected)}")
    print(f"  agree                 : {len(labeled & detected)}")
    print(f"  detector only (label false negative): {len(detected - labeled)}")
    print(f"  label only  (detector says prose)   : {len(labeled - detected)}")

    print(f"\nlayout repetition: {len(rep)} chunks flagged across "
          f"{len({c.paper_id for c in chunks if c.chunk_id in rep})} papers")
    bands = defaultdict(int)
    for v in rep.values():
        bands[v["y_band"]] += 1
    print(f"  by page band: {dict(bands)}")
    seen = set()
    for c in chunks:
        if c.chunk_id in rep and rep[c.chunk_id]["key"] not in seen and len(seen) < 8:
            seen.add(rep[c.chunk_id]["key"])
            v = rep[c.chunk_id]
            print(f"    p{c.paper_id} x{v['n_pages']}pg sigma={v['x0_sigma']} {v['y_band']}: "
                  f"{v['key'][:80]}")

    conn = connect()
    conn.executemany(
        "INSERT OR REPLACE INTO repetition_layout VALUES (?,?,?,?,?,?,?)",
        [
            (c.paper_id, rep[c.chunk_id]["key"][:64], rep[c.chunk_id]["n_pages"],
             rep[c.chunk_id]["x0_sigma"], rep[c.chunk_id]["y_band"], str(c.chunk_id),
             rep[c.chunk_id]["key"][:200])
            for c in chunks if c.chunk_id in rep
        ],
    )
    conn.commit()


if __name__ == "__main__":
    main()
