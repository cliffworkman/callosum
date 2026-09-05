"""Chunk-type classification from deterministic signals only. No model, no PDF, no LLM.

Closed, deliberately small type set. Every extra type is an adjudication burden with no retrieval
payoff. `unknown` is a real answer and is NEVER excluded.

The `references` scope is a PRIOR, not a verdict: a clearly-prose chunk inside the reference region
is vetoed back to prose. That veto is load-bearing -- Nature-format papers place Methods AFTER the
reference list, so a contiguous-tail region otherwise swallows real methods prose.
"""

from __future__ import annotations

from dataclasses import dataclass

from tools.evidence_hygiene.corpus import Chunk, PaperCalibration
from tools.evidence_hygiene.features import Features

# Substantive types
BODY_PROSE = "body_prose"
ABSTRACT_PROSE = "abstract_prose"
CAPTION = "caption"
# Structural / non-propositional
HEADING_FRAGMENT = "heading_fragment"
TABLE_CELL_DEBRIS = "table_cell_debris"
REFERENCE_ENTRY = "reference_entry"
RUNNING_HEAD = "running_head"
KEYWORD_LINE = "keyword_line"
CITATION_INSTRUCTION = "citation_instruction"
PUBLICATION_METADATA = "publication_metadata"
MATH_OR_SYMBOL = "math_or_symbol"
UNKNOWN = "unknown"


@dataclass
class Label:
    chunk_id: int
    raw_sha: str
    chunk_type: str
    confidence: float
    rule_id: str
    evidence: dict


def _is_clear_prose(f: Features) -> bool:
    """Unambiguously running prose: long, stopword-rich, sentence-terminated, not bibliographic."""
    return (
        f.n_words >= 20
        and f.stop_frac >= 0.22
        and f.terminal_punct
        and f.biblio_score < 1.5
        and f.caps_frac < 0.45
    )


def classify(
    chunks: list[Chunk],
    feats: dict[int, Features],
    cal: dict[int, PaperCalibration],
    biblio: dict[int, set[int]],
    repeated: dict[int, dict],
) -> list[Label]:
    labels: list[Label] = []
    for c in chunks:
        f = feats.get(c.chunk_id)
        if f is None:
            continue
        pc = cal.get(c.paper_id)
        in_ref = c.chunk_id in biblio.get(c.paper_id, set())
        rep = repeated.get(c.chunk_id)
        ev: dict = {}
        t = c.text.strip()

        def emit(kind: str, conf: float, rule: str) -> None:
            labels.append(Label(c.chunk_id, f.raw_sha, kind, conf, rule, dict(ev)))

        # --- 1. Running head / footer. Position + x-stability across >=3 pages of ONE paper.
        # This is the half production's text-only detector lacks, and what makes exclusion
        # defensible rather than merely plausible.
        if rep and rep["y_band"] in ("top", "bottom"):
            ev = {"n_pages": rep["n_pages"], "x0_sigma": rep["x0_sigma"], "band": rep["y_band"]}
            emit(RUNNING_HEAD, 0.95, "rep.position+stability")
            continue
        if rep:
            ev = {"n_pages": rep["n_pages"], "x0_sigma": rep["x0_sigma"], "band": "middle"}
            # Repeated mid-page text is real but not obviously furniture; do not hard-classify.
            emit(UNKNOWN, 0.4, "rep.middle_band")
            continue

        # --- 2. Publisher furniture. Split, never one undifferentiated class: substantive abstract
        # prose must not be treated like a keyword line or a "please cite this article" banner.
        if f.cite_instruction:
            emit(CITATION_INSTRUCTION, 0.95, "text.cite_instruction")
            continue
        if f.keyword_line:
            emit(KEYWORD_LINE, 0.95, "text.keyword_line")
            continue
        if f.publication_meta and not _is_clear_prose(f):
            ev = {"n_words": f.n_words}
            emit(PUBLICATION_METADATA, 0.85, "text.publication_meta")
            continue

        # --- 3. Reference entry. Region membership is the prior; clear prose vetoes it.
        if in_ref:
            if _is_clear_prose(f) and not f.caption_match:
                ev = {"vetoed_from": REFERENCE_ENTRY, "biblio_score": f.biblio_score}
                emit(BODY_PROSE, 0.6, "ref_region.prose_veto")
                continue
            ev = {"biblio_score": f.biblio_score, "region": True}
            emit(REFERENCE_ENTRY, 0.85 if f.biblio_score >= 2.0 else 0.6, "ref_region.member")
            continue
        if f.biblio_score >= 3.0 and not _is_clear_prose(f):
            ev = {"biblio_score": f.biblio_score, "region": False}
            emit(REFERENCE_ENTRY, 0.7, "shape.biblio_score")
            continue

        # --- 4. Caption. Conservative: an explicit Table/Figure opener with real content.
        if f.caption_match and f.n_words >= 4:
            ev = {"n_words": f.n_words}
            emit(CAPTION, 0.85, "text.caption_prefix")
            continue

        # --- 5. Standalone heading fragment. The heading IS the whole chunk.
        if f.heading_only or (f.heading_prefix_key and f.n_words <= 6 and not f.terminal_punct):
            ev = {"heading": f.heading_prefix_key}
            emit(HEADING_FRAGMENT, 0.9, "text.heading_only")
            continue

        # --- 6. Table-cell debris. Narrow one-liner WITH grid siblings. The gregariousness
        # requirement is what stops this eating isolated short evidence such as a reported
        # effect size or a confidence interval.
        if (
            pc
            and pc.n_columns  # width rules need a calibrated column
            and f.n_lines == 1
            and f.n_spans <= 3
            and f.width_ratio is not None
            and f.width_ratio < 0.35
            and f.grid_support >= 3
            and (f.n_words <= 4 or f.alpha_ratio < 0.5)
        ):
            ev = {"width_ratio": f.width_ratio, "grid_support": f.grid_support}
            emit(TABLE_CELL_DEBRIS, 0.8, "geom.narrow+grid")
            continue

        # --- 7. Math / symbol soup. Kept only so it does not pollute the debris estimate.
        if f.alpha_ratio < 0.3 and f.n_words <= 6:
            emit(MATH_OR_SYMBOL, 0.7, "text.low_alpha")
            continue

        # --- 8. Abstract prose is evidence, and is called out explicitly so it can never be
        # swept into a generic front-matter exclusion.
        if (c.section or "") == "abstract" and f.n_words >= 20:
            emit(ABSTRACT_PROSE, 0.8, "section.abstract+len")
            continue

        # --- 9. Body prose, else unknown. `unknown` is never excluded.
        if f.n_words >= 25 and f.terminal_punct and (f.line_fill or 0) > 0.7:
            emit(BODY_PROSE, 0.85, "shape.long+terminal+fill")
            continue
        if _is_clear_prose(f):
            emit(BODY_PROSE, 0.7, "shape.clear_prose")
            continue
        emit(UNKNOWN, 0.3, "fallthrough")
    return labels


def build_all():
    """Run the full deterministic pipeline in dependency order and return every intermediate."""
    from tools.evidence_hygiene.corpus import calibrate, load_chunks
    from tools.evidence_hygiene.features import compute
    from tools.evidence_hygiene.structure import bibliography_regions, layout_repetition

    from collections import defaultdict

    from tools.evidence_hygiene.refregion import (
        build_index,
        infer_region,
        load_references,
        match_positions,
    )

    chunks = load_chunks()
    cal = calibrate(chunks)
    feats = {f.chunk_id: f for f in compute(chunks, cal)}
    rep0 = layout_repetition(chunks, feats, biblio={})

    # MULTI-PRONG WITH FALLBACK. The region is located from the paper's OWN known references --
    # DOI, then dense-key title match, then surname+year corroboration -- against locally cached
    # Crossref/OpenAlex/Meta-Reference metadata. Measured per prong on this library: DOI alone
    # fires on 32 of 96 eligible papers, title alone on 69 (median 90% of a paper's references
    # matched), combined on 77. Where no metadata is cached or too few entries match, the shape
    # heuristic still supplies a region, so a paper is never left unfenced for want of metadata.
    per_paper: dict[int, list] = defaultdict(list)
    for c in chunks:
        per_paper[c.paper_id].append(c)
    refs_by_paper = load_references()
    anchored: dict[int, set[int]] = {}
    anchor_diag: dict[int, dict] = {}
    for paper_id, cs in per_paper.items():
        refs = refs_by_paper.get(paper_id)
        if not refs:
            anchor_diag[paper_id] = {"status": "no_reference_metadata"}
            continue
        idx = build_index(cs)
        hits = match_positions(idx, refs, "combined")
        region = infer_region(idx, hits)
        if region is None:
            anchor_diag[paper_id] = {"status": "no_region", "n_refs": len(refs)}
            continue
        start, end = region
        anchored[paper_id] = {c.chunk_id for c in idx.ordered[start : end + 1]}
        anchor_diag[paper_id] = {
            "status": "anchored", "n_refs": len(refs), "start": start, "end": end,
            "matched": len({o for s in hits.values() for o in s}),
        }

    heuristic = bibliography_regions(chunks, feats, repeated=rep0)
    biblio = {
        paper_id: anchored.get(paper_id) or heuristic.get(paper_id, set())
        for paper_id in per_paper
    }
    rep = layout_repetition(chunks, feats, biblio)
    labels = classify(chunks, feats, cal, biblio, rep)
    return chunks, cal, feats, biblio, rep, labels, anchor_diag


def main() -> None:
    from collections import Counter

    from tools.evidence_hygiene.store import connect

    chunks, cal, feats, biblio, rep, labels, anchor_diag = build_all()
    counts = Counter(x.chunk_type for x in labels)
    total = len(labels)
    print(f"classified {total} chunks\n")
    print(f"  {'type':<24}{'n':>7}{'share':>8}")
    for k, v in counts.most_common():
        print(f"  {k:<24}{v:>7}{100 * v / total:>7.1f}%")

    byid = {c.chunk_id: c for c in chunks}
    print("\nsamples per type:")
    import random

    random.seed(5)
    for kind in counts:
        pool = [x for x in labels if x.chunk_type == kind]
        for x in random.sample(pool, min(2, len(pool))):
            c = byid[x.chunk_id]
            print(f"  [{kind}] p{c.paper_id} ({x.rule_id}) {' '.join(c.text.split())[:88]!r}")

    conn = connect()
    conn.executemany(
        "INSERT OR REPLACE INTO chunk_label VALUES (?,?,?,?,?,?)",
        [
            (x.chunk_id, x.raw_sha, x.chunk_type, x.confidence, x.rule_id, str(x.evidence))
            for x in labels
        ],
    )
    conn.commit()
    print(f"\nwrote {len(labels)} labels to the sidecar")


if __name__ == "__main__":
    main()
