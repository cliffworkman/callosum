"""Classify a chunk as paper front-matter / non-content (title-page mastheads, DOIs, journal headers,
author/affiliation lines) vs body content, so synthesis retrieval can prefer real content over a title page.

Conservative by design: it errs toward "content". A false "content" just isn't deprioritized; a false
"front-matter" only deprioritizes a chunk (front matter is used as fallback, never dropped — see
summarization/pipeline.py::_select_no_query), so a paper with only front matter still contributes. Titles are
deliberately NOT caught (they read like topical prose; catching them risks dropping real content) — only the
masthead/DOI/journal-header/author-line garbage is flagged.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol

from app.backend.summarization.generators import SourceChunk

_DOI = re.compile(r"\b10\.\d{4,9}/\S+", re.IGNORECASE)
# A journal volume:page run like "38:3391-3401" (hyphen or en/em dash).
_VOLUME = re.compile(r"\b\d{1,4}\s?[:;]\s?\d+\s?[-–—]\s?\d+")
# Author/affiliation superscripts: ",1*", ",2" — repeated across an author list.
_AFFIL_SUPERSCRIPT = re.compile(r",\s?\d\*?")
# Author superscript attached to a name: "Alves1", "Workman2" (a single 1-9 not part of a larger number).
_AUTHOR_SUPERSCRIPT = re.compile(r"[A-Za-z][1-9](?![0-9])")
# Affiliation lines prefixed with a superscript digit: "1Department", "2Department".
_AFFIL_DIGIT_PREFIX = re.compile(r"(?:^|\s)\d[A-Z][a-z]")
# A grant / award id like "AG038893" or "R03 DA042336" (in funding/acknowledgment lines).
_GRANT_ID = re.compile(r"\b[A-Z]{1,3}\s?\d{4,}")
# Publisher / copyright / access boilerplate (substring match, lowercased).
_PUBLISHER_BOILER = (
    "article reuse guidelines",
    "sagepub",
    "journals.",
    "doi.org",
    "downloaded from",
    "contents lists available",
    "sciencedirect",
    "the author(s)",
    "©",
    "(c) ",
    "rights reserved",
    "creativecommons",
)
_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "by",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "from",
    "we",
    "our",
    "they",
    "their",
    "than",
    "which",
    "into",
}


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text)


def is_front_matter_chunk(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True  # empty/whitespace contributes nothing to a synthesis
    low = t.lower()
    if _DOI.search(t) or any(s in low for s in _PUBLISHER_BOILER):
        return True  # DOI / publisher / copyright / access boilerplate
    # Author / affiliation lines: comma-superscripts ("Barrett ,1* Workman,1"), name-attached superscripts
    # ("Alves1 ... Uğurlar2 ... Unkelbach3"), or digit-prefixed affiliations ("1Department ... 2Department").
    if (
        len(_AFFIL_SUPERSCRIPT.findall(t)) >= 2
        or len(_AUTHOR_SUPERSCRIPT.findall(t)) >= 2
        or len(_AFFIL_DIGIT_PREFIX.findall(t)) >= 2
    ):
        return True
    # Funding / acknowledgment lines ("Contract grant sponsor … AG038893 …").
    if ("grant" in low or "funding" in low) and _GRANT_ID.search(t):
        return True
    words = _word_tokens(t)
    n = len(words)
    if n == 0:
        return True
    if n < 12 and _VOLUME.search(t):
        return True  # "r Human Brain Mapping 38:3391-3401 (2017) r"
    # The strongest single signal for a title / journal header / heading vs body prose: it does NOT end in a
    # sentence terminator, and it is dominated by capitalized words. Body prose is mostly lowercase function
    # words, so its capitalized fraction is low even when a chunk is truncated mid-sentence — so this is safe
    # for real content. A real short sentence ("Paper B chunk 1 discusses cortex.") ends in . ? ! and is kept.
    if t[-1] not in ".?!":
        caps = sum(1 for w in words if w[:1].isupper())
        if n >= 2 and caps / n >= 0.6:
            return True  # title / journal running-header / Title-Case heading
        if n < 12:
            stop = sum(1 for w in words if w.lower() in _STOPWORDS)
            if stop / n < 0.10:
                return True  # short masthead/label line with almost no function words
    return False


class BoilerplateRow(Protocol):
    """The minimal row shape repetition detection needs. `SourceChunk` satisfies it structurally,
    and so does a narrow SELECT of (paper_id, page_start, text)."""

    paper_id: int
    page_start: int
    text: str


REPEATED_BOILERPLATE_MAX_WORDS = 25
REPEATED_BOILERPLATE_MIN_PAGE_COUNT = 3
_TRAILING_NUMBER = re.compile(r"\s*\d+\s*$")


def _normalize_space(text: str) -> str:
    return " ".join((text or "").split())


def _repetition_key(text: str) -> str:
    """Running headers/footers often embed a page or section-relative counter directly in the text (e.g. a
    Supplementary Materials header reading "...STEREOTYPE (SOM) 14" on one page and "...STEREOTYPE (SOM) 9" on
    another) -- confirmed live: this made every occurrence's normalized text unique and defeated exact-match
    repetition detection entirely. Strip one trailing numeric token before comparing; real body prose
    essentially never repeats its own non-numeric prefix verbatim across several of a paper's own pages."""
    return _TRAILING_NUMBER.sub("", _normalize_space(text))


def repeated_boilerplate_keys(rows: Iterable[BoilerplateRow]) -> dict[int, set[str]]:
    """Per paper, the repetition keys that qualify as running header/footer noise.

    Split out (inc 577) so DETECTION can run over a paper's whole chunk set while FILTERING stays
    scoped to the caller's candidate list. Previously the two were fused, so the answer depended on
    which section-filtered list happened to be handed in: measured on the testing library, a
    ``sections=['methods']`` synthesis kept 112 running-head chunks that whole-paper scope removes,
    because a header appearing on five pages survived into too few of the selected-section chunks to
    reach the page-count floor.

    Takes only the three fields the rule needs -- ``paper_id``, ``page_start``, ``text`` -- so the
    caller can satisfy it with a narrow SELECT rather than a second full chunk materialization.
    """
    pages_by_text: dict[int, dict[str, set[int]]] = {}
    for row in rows:
        by_text = pages_by_text.setdefault(row.paper_id, {})
        by_text.setdefault(_repetition_key(row.text), set()).add(row.page_start)
    return {
        paper_id: {
            key
            for key, pages in by_text.items()
            if len(key.split()) <= REPEATED_BOILERPLATE_MAX_WORDS and len(pages) >= REPEATED_BOILERPLATE_MIN_PAGE_COUNT
        }
        for paper_id, by_text in pages_by_text.items()
    }


def exclude_repeated_boilerplate_chunks(
    chunks: list[SourceChunk], *, keys: dict[int, set[str]] | None = None
) -> list[SourceChunk]:
    """Drop chunks whose text is short and recurs verbatim (modulo a trailing page number) across several of
    the SAME paper's own pages -- a running header/footer, not real content (complementary to
    is_front_matter_chunk above, which is purely content-pattern-based and doesn't catch a plain title-case
    running header with no DOI/superscript/volume fingerprint). Never a cross-paper comparison, and never drops
    a paper's ENTIRE candidate set (falls back to the unfiltered chunks for that paper if every one of its
    chunks would otherwise qualify) -- mirrors this codebase's existing "front matter is never dropped
    outright" philosophy (_select_no_query's own docstring) at the paper level, while still excluding real
    noise at the chunk level for the common case.

    ``keys`` supplies a precomputed, paper-global key set (inc 577). Omitted, the keys are derived from
    ``chunks`` itself, which is exactly the previous behavior -- and is correct whenever the caller's list
    already IS the paper's whole chunk set.
    """
    by_paper: dict[int, list[SourceChunk]] = {}
    for chunk in chunks:
        by_paper.setdefault(chunk.paper_id, []).append(chunk)
    derived = keys if keys is not None else repeated_boilerplate_keys(chunks)
    kept_ids: set[int] = set()
    for paper_id, paper_chunks in by_paper.items():
        boilerplate_keys = derived.get(paper_id, set())
        survivors = [c for c in paper_chunks if _repetition_key(c.text) not in boilerplate_keys]
        kept_ids.update((c.chunk_id for c in (survivors if survivors else paper_chunks)))
    return [c for c in chunks if c.chunk_id in kept_ids]
