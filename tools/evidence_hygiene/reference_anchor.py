"""Anchor the reference region to the paper's OWN known reference list, not to a shape heuristic.

Cliff's suggestion, and it is a much stronger signal than anything derivable from text shape:
Callosum already resolves real reference lists for a paper (Semantic Scholar, with an OpenAlex
fallback -- `api/routers/reference_integrity.py:291`). Crossref records carry the same list, and
**344 of 400 cached Crossref responses in this library already embed it**, so the anchor can be
built with ZERO egress from `external_api_cache`.

Why this beats the density heuristic it replaces:

* it bounds the region by the FIRST and LAST reference actually found in the text, so anything after
  the list -- an appendix, supplementary material, or a Nature-format Methods section printed after
  the references -- falls outside it by construction. The tail-fraction floor and the sustained
  density threshold both become unnecessary;
* it needs no assumption about citation style, which is what broke shape scoring on Vancouver-style
  lists;
* it is falsifiable per paper: either the paper's known titles are found in its text or they are not.

MATCHING IS ON TITLE N-GRAMS, NOT AUTHOR+YEAR. An in-text citation "(Smith, 2020)" carries the same
surname and year as its reference-list entry, so author+year cannot separate the two. A reference
list entry additionally reproduces the cited work's TITLE, which in-text citations never do.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

from sqlalchemy import text as sqltext

from tools.evidence_hygiene.corpus import Chunk
from tools.evidence_hygiene.store import LIBRARY_DB

NGRAM = 6          # consecutive title words that must appear verbatim
MIN_TITLE_WORDS = 8
MIN_HITS = 3       # a paper needs several matched references before a region is claimed
TAIL_FRACTION = 0.35  # a reference list lives in the paper's tail, never its opening

_WORD = re.compile(r"[a-z0-9]+")


def _norm_words(s: str) -> list[str]:
    return _WORD.findall((s or "").lower())


def _title_ngrams(title: str) -> set[str]:
    w = _norm_words(title)
    if len(w) < MIN_TITLE_WORDS:
        return set()
    return {" ".join(w[i : i + NGRAM]) for i in range(len(w) - NGRAM + 1)}


def load_reference_records() -> dict[int, list[dict]]:
    """{paper_id: [reference records in citation order]} from the local Crossref cache. No egress.

    Field coverage measured across the 31,122 cached reference entries in this library:
    DOI 89%, year 67%, author 67%, journal-title 62%, first-page 61%, article-title only 42%.
    So the DOI is both the most available and the most specific signal, and -- being a single
    token -- it is the one that survives this library's fragmentary chunking intact.
    """
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{LIBRARY_DB.as_posix()}")
    out: dict[int, list[dict]] = {}
    with engine.connect() as conn:
        dois = {
            (r[1] or "").lower().strip(): int(r[0])
            for r in conn.execute(
                sqltext("SELECT id, doi FROM papers WHERE doi IS NOT NULL AND deleted_at IS NULL")
            )
        }
        rows = conn.execute(
            sqltext("SELECT cache_key, response_json FROM external_api_cache WHERE provider = 'crossref'")
        ).fetchall()
    for key, payload in rows:
        paper_id = dois.get((key or "").lower().strip())
        if paper_id is None:
            continue
        try:
            doc = json.loads(payload)
        except Exception:
            continue
        msg = doc.get("message", doc) if isinstance(doc, dict) else {}
        refs = msg.get("reference") if isinstance(msg, dict) else None
        if isinstance(refs, list) and refs:
            out[paper_id] = [r for r in refs if isinstance(r, dict)]
    return out


def reference_signals(refs: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    """Build ({doi -> ordinal}, {title n-gram -> ordinal}) lookup tables."""
    doi_map: dict[str, int] = {}
    gram_map: dict[str, int] = {}
    for ordinal, r in enumerate(refs):
        doi = r.get("DOI")
        if isinstance(doi, str) and doi.strip():
            doi_map.setdefault(doi.strip().lower(), ordinal)
        t = r.get("article-title") or r.get("volume-title") or r.get("unstructured")
        if isinstance(t, str):
            for g in _title_ngrams(t):
                gram_map.setdefault(g, ordinal)
    return doi_map, gram_map


def load_reference_titles() -> dict[int, list[str]]:
    """{paper_id: [reference titles in citation order]} from the local Crossref cache. No egress."""
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{LIBRARY_DB.as_posix()}")
    out: dict[int, list[str]] = {}
    with engine.connect() as conn:
        dois = {
            (r[1] or "").lower().strip(): int(r[0])
            for r in conn.execute(
                sqltext("SELECT id, doi FROM papers WHERE doi IS NOT NULL AND deleted_at IS NULL")
            )
        }
        rows = conn.execute(
            sqltext(
                "SELECT cache_key, response_json FROM external_api_cache WHERE provider = 'crossref'"
            )
        ).fetchall()
    for key, payload in rows:
        paper_id = dois.get((key or "").lower().strip())
        if paper_id is None:
            continue
        try:
            doc = json.loads(payload)
        except Exception:
            continue
        msg = doc.get("message", doc) if isinstance(doc, dict) else {}
        refs = msg.get("reference") if isinstance(msg, dict) else None
        if not isinstance(refs, list):
            continue
        titles = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            # `unstructured` is a whole formatted citation; it still contains the title, and the
            # n-gram test tolerates the surrounding author/journal text.
            t = ref.get("article-title") or ref.get("volume-title") or ref.get("unstructured")
            if isinstance(t, str) and t.strip():
                titles.append(t.strip())
        if titles:
            out[paper_id] = titles
    return out


def anchored_regions(
    chunks: list[Chunk], titles_by_paper: dict[int, list[str]] | None = None
) -> tuple[dict[int, set[int]], dict[int, dict]]:
    """Return ({paper_id: chunk ids in the reference region}, {paper_id: diagnostics})."""
    titles_by_paper = titles_by_paper if titles_by_paper is not None else load_reference_titles()
    by_paper: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_paper[c.paper_id].append(c)

    regions: dict[int, set[int]] = {}
    diag: dict[int, dict] = {}
    for paper_id, cs in by_paper.items():
        titles = titles_by_paper.get(paper_id)
        if not titles:
            diag[paper_id] = {"status": "no_reference_list"}
            continue
        grams: set[str] = set()
        for t in titles:
            grams |= _title_ngrams(t)
        if not grams:
            diag[paper_id] = {"status": "titles_too_short", "n_refs": len(titles)}
            continue

        ordered = sorted(cs, key=lambda c: (c.page_start or 0, c.chunk_id))

        # Match over a ROLLING WINDOW of consecutive chunks, not per chunk. This library's median
        # chunk is 73 characters, so one reference entry is routinely split across several blocks
        # and a 6-word title n-gram straddles the boundary. Per-chunk matching recovered only ~14%
        # of each paper's known references; the window recovers the split entries too. A hit is
        # attributed to every chunk in the window that contributed words.
        # Which reference ORDINAL each window matched. Crossref returns references in citation
        # order and a printed reference list reproduces that order, so ordinals are what identify
        # the list: the bounds are simply where its first and last matched entry sit.
        gram_ordinal: dict[str, int] = {}
        for ordinal, t in enumerate(titles):
            for g in _title_ngrams(t):
                gram_ordinal.setdefault(g, ordinal)

        hits: list[tuple[int, int]] = []  # (chunk position, lowest matched ordinal)
        words_per: list[list[str]] = [_norm_words(c.text) for c in ordered]
        for i in range(len(ordered)):
            w: list[str] = []
            span_end = i
            while span_end < len(ordered) and len(w) < 60:
                w.extend(words_per[span_end])
                span_end += 1
            if len(w) < NGRAM:
                continue
            matched = {
                gram_ordinal[g]
                for g in (" ".join(w[j : j + NGRAM]) for j in range(len(w) - NGRAM + 1))
                if g in gram_ordinal
            }
            if matched:
                hits.append((i, min(matched)))
        if len(hits) < MIN_HITS:
            diag[paper_id] = {"status": "too_few_matches", "n_refs": len(titles), "hits": len(hits)}
            continue

        # Restrict to the paper's tail before taking bounds. A cited work's title can legitimately
        # appear in the body ("as X showed in <title>"); without this one paper's region spanned
        # 99% of its own chunks. Taking only the last dense cluster instead was over-tight -- it
        # captured just the end of the list (median 7% of a paper) whenever a stretch of entries
        # went unmatched, which is common because only ~1/3 of known titles match at all.
        tail_floor = int(TAIL_FRACTION * len(ordered))
        tail = [h for h in hits if h[0] >= tail_floor]
        if len(tail) < MIN_HITS:
            diag[paper_id] = {"status": "no_tail_cluster", "n_refs": len(titles), "hits": len(hits)}
            continue
        start, end = tail[0][0], tail[-1][0]
        # Ordinal monotonicity is a VALIDITY CHECK, not a filter: if the matched entries really are
        # a reference list they appear in roughly citation order. A low value means the anchor is
        # matching scattered body mentions and the region should be distrusted.
        ordinals = [o for _, o in tail]
        rises = sum(1 for a, b in zip(ordinals, ordinals[1:]) if b >= a)
        monotonicity = round(rises / max(len(ordinals) - 1, 1), 3)
        # Fragments between and just after matched entries belong to the list they sit in.
        while end + 1 < len(ordered) and len(_norm_words(ordered[end + 1].text)) < MIN_TITLE_WORDS:
            end += 1
        regions[paper_id] = {c.chunk_id for c in ordered[start : end + 1]}
        diag[paper_id] = {
            "status": "anchored",
            "n_refs": len(titles),
            "hits": len(hits),
            "tail_hits": len(tail),
            "ordinal_monotonicity": monotonicity,
            "start": start,
            "end": end,
            "n_chunks": len(ordered),
            "span_frac": round((end - start + 1) / len(ordered), 3),
        }
    return regions, diag


def main() -> None:
    from collections import Counter

    from tools.evidence_hygiene.corpus import load_chunks

    chunks = load_chunks()
    titles = load_reference_titles()
    print(f"papers with a cached Crossref reference list: {len(titles)}")
    print(f"  median references per paper: "
          f"{sorted(len(v) for v in titles.values())[len(titles) // 2] if titles else 0}")

    regions, diag = anchored_regions(chunks, titles)
    st = Counter(d["status"] for d in diag.values())
    print(f"\nanchoring status across {len(diag)} papers: {dict(st)}")
    anchored = [d for d in diag.values() if d["status"] == "anchored"]
    if anchored:
        spans = sorted(d["span_frac"] for d in anchored)
        print(f"  region span as a fraction of the paper: median {spans[len(spans) // 2]:.2f}  "
              f"min {spans[0]:.2f}  max {spans[-1]:.2f}")
        hits = sorted(d["hits"] / d["n_refs"] for d in anchored)
        print(f"  matched references / known references: median {hits[len(hits) // 2]:.2f}")
    print(f"  chunks in anchored regions: {sum(len(v) for v in regions.values())}")

    labeled = {c.chunk_id for c in chunks if (c.section or "") == "references"}
    detected = {cid for v in regions.values() for cid in v}
    covered = {c.paper_id for c in chunks if c.paper_id in regions}
    lab_in_covered = {c.chunk_id for c in chunks if c.paper_id in covered and (c.section or "") == "references"}
    print("\nreconciliation, restricted to the papers this anchor covers:")
    print(f"  label says references : {len(lab_in_covered)}")
    print(f"  anchor says references: {len(detected)}")
    print(f"  agree                 : {len(lab_in_covered & detected)}")
    print(f"  anchor only           : {len(detected - lab_in_covered)}")
    print(f"  label only            : {len(lab_in_covered - detected)}")


if __name__ == "__main__":
    main()
