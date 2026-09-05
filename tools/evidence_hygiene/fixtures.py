"""G1: build the stratified hygiene fixture corpus for adjudication, then freeze it.

Sampling is deliberately TWO-SIDED so the frozen set can measure more than precision:

* per predicted class -- supports precision (are the classifier's positives correct?);
* a uniform random draw -- supports recall (what does it miss?), and is the only way a false
  negative can ever enter the corpus.

Adjudication is INDEPENDENT of the classifier wherever possible. A fixture whose expected type is
copied from the thing being measured proves nothing, so mechanical adjudication uses structural
tests that do not reuse the classifier's own rule (a literal "Keywords:" opener, a verbatim repeat
at a stable page position, a title that matches the paper's own cited-reference metadata), and
everything else is marked contestable for maintainer review or left unresolved.
"""

from __future__ import annotations

import json
import random
import re
from collections import defaultdict

from tools.evidence_hygiene import classify as C
from tools.evidence_hygiene.store import study_dir

TARGET_PER_CLASS = 6
RANDOM_DRAW = 30

# --- independent mechanical adjudicators -------------------------------------------------------
# Each returns (expected_type, rationale) or None. None means "not mechanically decidable".

_KEYWORDS = re.compile(r"^\s*(key\s*words?|keywords)\s*[:.–-]", re.I)
_CITE_INSTR = re.compile(r"(please|how to|to)\s+cite this article|this is a pdf file", re.I)
_COPYRIGHT = re.compile(r"©|copyright|all rights reserved|creative\s?commons", re.I)
_CAPTION_OPEN = re.compile(r"^\s*(table|fig(?:ure)?\.?|figs?\.)\s*[0-9ivx]+\b", re.I)
_NUMERIC_ONLY = re.compile(r"^[\s\d.,;:%()\-–—+/]*$")
_HYPHEN_ARTIFACT = re.compile(r"\b[a-z]{2,}-\s+[a-z]{2,}\b")


def adjudicate_mechanical(chunk, feats, repeated, ref_titles_hit) -> tuple[str, str] | None:
    t = (chunk.text or "").strip()
    if not t:
        return None
    if _KEYWORDS.match(t):
        return C.KEYWORD_LINE, "Opens with a literal 'Keywords:' label; a keyword list states no finding."
    if _CITE_INSTR.search(t):
        return C.CITATION_INSTRUCTION, "Contains a verbatim publisher citation instruction."
    if _COPYRIGHT.search(t) and feats.n_words <= 40:
        return C.PUBLICATION_METADATA, "Short chunk carrying a copyright/licence notice; publisher furniture."
    if ref_titles_hit:
        return C.REFERENCE_ENTRY, (
            "Text reproduces the title/DOI of a work this paper is independently known to cite "
            "(cached Crossref/OpenAlex reference metadata), which body prose does not do."
        )
    rep = repeated.get(chunk.chunk_id)
    if rep and rep["n_pages"] >= 3 and rep["x0_sigma"] <= 3.0 and rep["y_band"] in ("top", "bottom"):
        return C.RUNNING_HEAD, (
            f"Identical text repeats on {rep['n_pages']} pages at a stable x "
            f"(sigma={rep['x0_sigma']}pt) in the {rep['y_band']} margin band."
        )
    if _NUMERIC_ONLY.match(t) and len(t) <= 12:
        return C.TABLE_CELL_DEBRIS, "Chunk is a bare numeric/symbol token carrying no proposition."
    return None


def build() -> list[dict]:
    from tools.evidence_hygiene.refregion import (
        build_index,
        load_references,
        match_positions,
    )

    chunks, cal, feats, biblio, rep, labels, _diag = C.build_all()
    byid = {c.chunk_id: c for c in chunks}
    label_of = {x.chunk_id: x for x in labels}

    # Independent evidence that a chunk reproduces a known cited work.
    per_paper: dict[int, list] = defaultdict(list)
    for c in chunks:
        per_paper[c.paper_id].append(c)
    refs_by = load_references()
    ref_hit: set[int] = set()
    for paper_id, cs in per_paper.items():
        refs = refs_by.get(paper_id)
        if not refs:
            continue
        idx = build_index(cs)
        for pos in match_positions(idx, refs, "combined"):
            ref_hit.add(idx.ordered[pos].chunk_id)

    random.seed(2026)
    picked: dict[int, str] = {}
    for kind in {x.chunk_type for x in labels}:
        pool = [x.chunk_id for x in labels if x.chunk_type == kind]
        for cid in random.sample(pool, min(TARGET_PER_CLASS, len(pool))):
            picked.setdefault(cid, f"predicted:{kind}")
    for cid in random.sample([c.chunk_id for c in chunks], RANDOM_DRAW):
        picked.setdefault(cid, "random_draw")

    # Targeted strata the random/per-class draws would under-sample.
    def targeted(name: str, pred, limit: int) -> None:
        hits = [c.chunk_id for c in chunks if pred(c)]
        for cid in random.sample(hits, min(limit, len(hits))):
            picked.setdefault(cid, name)

    targeted("hyphen_artifact", lambda c: _HYPHEN_ARTIFACT.search(c.text or ""), 8)
    targeted("null_section_prose",
             lambda c: c.section is None and len((c.text or "").split()) >= 40, 6)
    targeted("label_says_references_but_prose",
             lambda c: (c.section or "") == "references"
             and len((c.text or "").split()) >= 30
             and feats[c.chunk_id].biblio_score < 1.0, 6)
    targeted("unlabeled_bibliography",
             lambda c: (c.section or "") != "references" and c.chunk_id in ref_hit, 6)
    targeted("short_but_substantive",
             lambda c: 4 <= len((c.text or "").split()) <= 14
             and re.search(r"\bp\s*[<=>]|\bd\s*=|95%\s*CI|\br\s*=", c.text or ""), 6)

    out: list[dict] = []
    for cid, stratum in picked.items():
        c, f = byid[cid], feats[cid]
        lab = label_of.get(cid)
        mech = adjudicate_mechanical(c, f, rep, cid in ref_hit)
        box = c.box
        out.append({
            "fixture_id": f"F{cid}",
            "stratum": stratum,
            "paper_id": c.paper_id,
            "attachment_id": c.attachment_id,
            "chunk_id": cid,
            "page": c.page_start,
            "raw_text": c.text,
            "current_section": c.section,
            "geometry": None if not box else {
                "n_spans": f.n_spans, "n_lines": f.n_lines,
                "width_ratio": f.width_ratio, "y_top_frac": f.y_top_frac,
                "grid_support": f.grid_support,
            },
            "in_reference_region": cid in biblio.get(c.paper_id, set()),
            "matches_known_citation": cid in ref_hit,
            "predicted_type": lab.chunk_type if lab else None,
            "predicted_rule": lab.rule_id if lab else None,
            "expected_type": mech[0] if mech else None,
            "rationale": mech[1] if mech else None,
            "adjudication": "mechanical" if mech else "contestable",
            "expected_claim_eligible": None,
            "expected_normalization": None,
        })
    return out


def main() -> None:
    fixtures = build()
    path = study_dir() / "fixtures_draft.json"
    path.write_text(json.dumps(fixtures, indent=1), encoding="utf-8")
    mech = [f for f in fixtures if f["adjudication"] == "mechanical"]
    cont = [f for f in fixtures if f["adjudication"] == "contestable"]
    print(f"drafted {len(fixtures)} fixtures -> {path.name}")
    print(f"  mechanically adjudicated : {len(mech)}")
    print(f"  contestable (need review): {len(cont)}")
    from collections import Counter
    print(f"  strata: {dict(Counter(f['stratum'] for f in fixtures))}")
    print(f"  mechanical expected types: {dict(Counter(f['expected_type'] for f in mech))}")


if __name__ == "__main__":
    main()
