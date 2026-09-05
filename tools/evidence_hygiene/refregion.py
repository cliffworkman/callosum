"""Reference-REGION detection by dense-key matching against the paper's own known references.

The goal is not to identify every individual reference. It is to locate the span of the document
that is overwhelmingly likely to be the bibliography.

REUSE AUDIT (done before writing anything new). Everything below is composed from existing code:

  * reference metadata -- `OpenAlexClient.fetch_referenced_works`/`fetch_work_meta` (cache-backed;
    `adapter.py:180` notes no extra HTTP once populated), `SemanticScholarClient.
    fetch_reference_contexts`, and the Crossref `reference` arrays already sitting in
    `external_api_cache`. The canonical record shape is `ReferenceCandidate`
    (`methods/reference_integrity.py:27`).
  * character canonicalization -- `extraction._canonical_characters` (ligatures, soft hyphen, NFC,
    dash unification).
  * punctuation/case/whitespace -- `embeddings.models.strip_punctuation` + `normalize_text`, the
    same pair duplicate-PAPER detection already uses (`clustering/duplicate_detection.py:110`).

The ONE new thing is `dense_key`: after those, remove whitespace entirely.

WHY THAT MATTERS. A dense key makes line-break artifacts irrelevant *without* first solving the
general hyphenation problem:

    "Functional connectiv-\\nity in late-life depression"  -> functionalconnectivityinlatelifedepression
    "Functional Connectivity in Late-Life Depression"      -> functionalconnectivityinlatelifedepression

Token-based n-gram matching cannot do this: it sees ["connectiv", "ity"] and never recovers the
word. Measured here, that limitation alone held title matching to ~31% of known references.

REGION INFERENCE IS DENSITY-BASED, NOT FIRST-MATCH. A cited title can legitimately appear in the
body, and in-text citations carry the same author and year as their list entry. So the region is
the sustained cluster where bibliographic matches are far denser than the paper's own baseline.

EVIDENCE ROLE, NOT DELETION. A reference-region chunk is `bibliographic`:
`scientific_claim_eligible = False`, but it remains real evidence for "what does this paper cite?"
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy import text as sqltext

from app.backend.embeddings.models import normalize_text, strip_punctuation
from app.backend.pdf_processing.extraction import _canonical_characters
from tools.evidence_hygiene.corpus import Chunk
from tools.evidence_hygiene.store import LIBRARY_DB

MIN_TITLE_KEY = 28      # dense chars; shorter titles collide with ordinary prose
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>,;)\]]+", re.I)
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_NONALNUM = re.compile(r"[^a-z0-9]+")


def dense_key(text: str) -> str:
    """Aggressively normalized, whitespace-free comparison key. Reuses existing utilities."""
    canon = _canonical_characters(text or "")                 # ligatures, soft hyphen, NFC, dashes
    canon = unicodedata.normalize("NFKD", canon)
    canon = normalize_text(strip_punctuation(canon))          # punctuation -> space, lower, collapse
    return _NONALNUM.sub("", canon)                           # the one new step


@dataclass
class Reference:
    ordinal: int
    title: str | None
    doi: str | None
    surname: str | None
    year: str | None

    @property
    def title_key(self) -> str:
        k = dense_key(self.title or "")
        return k if len(k) >= MIN_TITLE_KEY else ""


def load_references() -> dict[int, list[Reference]]:
    """Union of every locally cached reference list. No egress.

    Crossref and OpenAlex are merged rather than one preferred, because their coverage differs per
    paper and the region only needs enough matches to see a density spike.
    """
    engine = create_engine(f"sqlite:///{LIBRARY_DB.as_posix()}")
    with engine.connect() as conn:
        by_doi = {
            (r[1] or "").lower().strip(): int(r[0])
            for r in conn.execute(
                sqltext("SELECT id, doi FROM papers WHERE doi IS NOT NULL AND deleted_at IS NULL")
            )
        }
        rows = conn.execute(
            sqltext("SELECT provider, cache_key, response_json FROM external_api_cache "
                    "WHERE provider IN ('crossref', 'openalex')")
        ).fetchall()
        inst = conn.execute(
            sqltext("SELECT citing_paper_id, source_ordinal, title, doi, authors_json, year "
                    "FROM reference_instances")
        ).fetchall()

    out: dict[int, list[Reference]] = defaultdict(list)
    for provider, key, payload in rows:
        paper_id = by_doi.get((key or "").lower().strip())
        if paper_id is None:
            continue
        try:
            doc = json.loads(payload)
        except Exception:
            continue
        msg = doc.get("message", doc) if isinstance(doc, dict) else {}
        if provider == "crossref" and isinstance(msg, dict):
            for ordinal, r in enumerate(msg.get("reference") or []):
                if not isinstance(r, dict):
                    continue
                author = r.get("author")
                out[paper_id].append(
                    Reference(
                        ordinal=ordinal,
                        title=r.get("article-title") or r.get("volume-title") or r.get("unstructured"),
                        doi=(r.get("DOI") or "").lower().strip() or None,
                        surname=(dense_key(author) or None) if isinstance(author, str) else None,
                        year=str(r["year"]).strip() if r.get("year") else None,
                    )
                )

    # `reference_instances` is the persisted Meta-Reference product. Sparse in this library
    # (5 papers), but it is the authoritative local record where it exists.
    for citing, ordinal, title, doi, authors_json, year in inst:
        surname = None
        try:
            authors = json.loads(authors_json) if authors_json else []
            if authors:
                surname = dense_key(str(authors[0]).split()[-1])
        except Exception:
            pass
        out[int(citing)].append(
            Reference(
                ordinal=int(ordinal or 0),
                title=title,
                doi=(doi or "").lower().strip() or None,
                surname=surname,
                year=str(year) if year else None,
            )
        )
    return dict(out)


@dataclass
class PaperIndex:
    """A paper's chunks flattened into one dense string, with an offset -> chunk-position map."""

    ordered: list[Chunk]
    dense: str
    starts: list[int]      # dense-string offset where each chunk begins

    def position_of(self, offset: int) -> int:
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo


def build_index(chunks: list[Chunk]) -> PaperIndex:
    ordered = sorted(chunks, key=lambda c: (c.page_start or 0, c.chunk_id))
    parts, starts, cursor = [], [], 0
    for c in ordered:
        k = dense_key(c.text)
        starts.append(cursor)
        parts.append(k)
        cursor += len(k)
    return PaperIndex(ordered=ordered, dense="".join(parts), starts=starts)


def match_positions(
    idx: PaperIndex, refs: list[Reference], prong: str
) -> dict[int, set[int]]:
    """{chunk position -> matched reference ordinals} for one prong."""
    hits: dict[int, set[int]] = defaultdict(set)

    if prong in ("doi", "combined"):
        # DOIs are matched on RAW text: the dense key would destroy the '10.xxxx/yyy' structure.
        for pos, c in enumerate(idx.ordered):
            found = {m.group(0).lower().rstrip(".") for m in DOI_RE.finditer(c.text or "")}
            for r in refs:
                if r.doi and r.doi in found:
                    hits[pos].add(r.ordinal)

    if prong in ("title", "title_author", "combined"):
        for r in refs:
            key = r.title_key
            if not key:
                continue
            start = idx.dense.find(key)
            while start != -1:
                hits[idx.position_of(start)].add(r.ordinal)
                start = idx.dense.find(key, start + 1)

    if prong in ("title_author", "combined"):
        # Corroboration only: an in-text citation carries the same surname and year, so this prong
        # is never allowed to establish a region on its own (see `infer_region`).
        sy = {(r.surname, r.year): r.ordinal for r in refs if r.surname and r.year}
        if sy:
            for pos, c in enumerate(idx.ordered):
                t = c.text or ""
                years = set(_YEAR_RE.findall(t))
                if not years:
                    continue
                key = dense_key(t)
                for (surname, year), ordinal in sy.items():
                    if year in years and surname in key:
                        hits[pos].add(ordinal)
    return dict(hits)


def infer_region(
    idx: PaperIndex, hits: dict[int, set[int]], *, min_distinct: int = 4
) -> tuple[int, int] | None:
    """The sustained cluster where bibliographic density spikes above the paper's own baseline."""
    n = len(idx.ordered)
    if not hits or n == 0:
        return None
    # A FIXED-WIDTH window, capped. `n // 20` gave a 21-chunk window on a 424-chunk paper and 62 on
    # a 1,253-chunk one, diluting the density of a real reference list until it vanished.
    window = min(15, max(5, n // 20))
    density = [0.0] * n
    for i in range(n):
        lo, hi = max(0, i - window // 2), min(n, i + window // 2 + 1)
        density[i] = sum(1 for j in range(lo, hi) if j in hits) / (hi - lo)
    peak = max(density)
    if peak <= 0:
        return None
    # A PURELY RELATIVE floor, so a paper with sparse reference metadata is judged on its own scale.
    # An absolute 0.25 floor rejected a correctly-located region -- 8 matched entries spanning
    # positions 284-322 of a 424-chunk paper, first and last both unmistakable numbered reference
    # entries -- because its local density was 0.238. Two hits in a window is the real minimum;
    # `min_distinct` remains the safeguard against a spurious cluster.
    floor = max(peak * 0.35, 2.0 / window)
    inside = [i for i in range(n) if density[i] >= floor]
    if not inside:
        return None
    runs: list[list[int]] = [[inside[0]]]
    for i in inside[1:]:
        if i - runs[-1][-1] <= window:
            runs[-1].append(i)
        else:
            runs.append([i])
    best = max(runs, key=lambda r: len({o for i in r if i in hits for o in hits[i]}))
    if len({o for i in best if i in hits for o in hits[i]}) < min_distinct:
        return None

    # Trim to ACTUAL hit positions inside the cluster. The smoothing window that finds the cluster
    # necessarily bleeds half a window past the real bounds, which was placing a figure caption and
    # a block of table data inside inspected regions. The cluster locates the bibliography; the
    # outermost real matches inside it are its edges.
    real = [i for i in range(best[0], best[-1] + 1) if i in hits]
    if not real:
        return None
    start, end = real[0], real[-1]

    # SHAPE EXTENSION at the edges. Metadata locates the region; shape finds its true edge. Only
    # ~30-90% of a paper's references match (some are books, preprints, or absent from the cached
    # record), so the last matched entry is routinely NOT the last entry -- adjudication found one
    # region ending at entry 24 of a list that visibly continued through entry 25 and beyond.
    # Extension is bounded and stops at the first chunk that does not look bibliographic.
    from tools.evidence_hygiene.features import _biblio_score

    def looks_bibliographic(pos: int) -> bool:
        return _biblio_score(idx.ordered[pos].text or "") >= 1.5

    def short_fragment(pos: int) -> bool:
        return len(dense_key(idx.ordered[pos].text or "")) < 40

    budget = 40
    while end + 1 < n and budget:
        if looks_bibliographic(end + 1):
            end += 1
        # A short fragment is crossed only when a real entry follows within two positions, so the
        # walk cannot run away through page furniture into the next section.
        elif short_fragment(end + 1) and any(
            end + k < n and looks_bibliographic(end + k) for k in (2, 3)
        ):
            end += 1
        else:
            break
        budget -= 1

    # NO start retraction. It was tried and adjudication rejected it: on a paper whose start was
    # exactly right -- the first numbered entry, immediately after a literal "References" heading --
    # walking backwards over short chunks moved the boundary four positions earlier onto a
    # conference announcement. The classifier's prose veto is the right place to correct a start
    # that bleeds into Discussion, because it decides per chunk rather than moving a boundary.
    return start, end
