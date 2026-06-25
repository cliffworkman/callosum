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

_DOI = re.compile(r"\b10\.\d{4,9}/\S+", re.IGNORECASE)
# A journal volume:page run like "38:3391-3401" (hyphen or en/em dash).
_VOLUME = re.compile(r"\b\d{1,4}\s?[:;]\s?\d+\s?[-–—]\s?\d+")
# Author/affiliation superscripts: ",1*", ",2" — repeated across an author list.
_AFFIL_SUPERSCRIPT = re.compile(r",\s?\d\*?")
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
    "the", "a", "an", "of", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "as", "is",
    "are", "was", "were", "be", "been", "that", "this", "these", "those", "it", "its", "from", "we", "our",
    "they", "their", "than", "which", "into",
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
    if len(_AFFIL_SUPERSCRIPT.findall(t)) >= 2:
        return True  # an author/affiliation line ("Barrett ,1* Workman,1 Sair,2")
    words = _word_tokens(t)
    n = len(words)
    if n < 12:  # short lines only — long prose is left as content
        if _VOLUME.search(t):
            return True  # "r Human Brain Mapping 38:3391-3401 (2017) r"
        # A title/masthead line has almost no function words AND no sentence-ending punctuation; a real short
        # sentence ("Paper B chunk 1 discusses cortex.") ends in . ? ! and is kept.
        if t[-1] not in ".?!" and n > 0:
            stop = sum(1 for w in words if w.lower() in _STOPWORDS)
            if stop / n < 0.10:
                return True
    return False
