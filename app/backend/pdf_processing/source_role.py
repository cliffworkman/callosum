"""Deterministic substantive-prose assessment shared by both reference guards (inc 611).

Two independent guards decide that a chunk "is bibliography": the pre-retrieval heading filter
(``chunks.section == 'references'``) and the derived ``chunk_structure`` label that inc 607 demotes. Both
trusted a signal that is evidence about source ROLE, not proof of it -- an extraction section label, or
membership in an inferred reference region -- and both removed genuine Discussion prose (development cases
in ``EVIDENCE_FALSE_EXCLUSION_ROOT_CAUSES.md``). This module answers the narrower question they were missing:
**does the text itself read as substantive prose rather than a reference entry?**

The discriminator is structural, never topical. A reference entry and a Discussion sentence can share every
scientific word (an article title can state a finding), so vocabulary is deliberately unused. What differs
is form:

* **In-text citations are stripped before scoring.** ``biblio_score`` counts "et al." and years, so a
  Discussion paragraph citing three studies scored like a reference list (measured 1.8 against a 1.5 veto
  cap). Parenthetical author-year groups, numeric brackets and superscript-style numerals are removed, so
  what remains is the author's own prose. Entry-defining structure -- author-initial lists, volume(issue),
  DOIs, page ranges, numbered entries -- is NOT inside parentheses and survives the strip, which is what
  keeps a real reference entry recognisable.
* **A finite-clause marker is required** (auxiliary, copula, modal or first person). Reference titles are
  overwhelmingly noun phrases; that, not a verb list, is the guard against promoting a title.

Outcomes are a closed vocabulary. ``fragment`` and ``mixed`` are explicit ambiguity: callers must not turn
them into a confident scientific label. Pure: no connection, file, model or network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SUBSTANTIVE = "substantive_prose"
MIXED = "mixed_prose_and_entries"
FRAGMENT = "prose_fragment"
NOT_PROSE = "not_prose"
OUTCOMES = (SUBSTANTIVE, MIXED, FRAGMENT, NOT_PROSE)

_STOPWORDS = frozenset(
    "the of and in to a is was were for with that as on by at from this these we our are be been "
    "not but or an it its than which their there have has had".split()
)
# Finite-clause markers. Closed and grammatical by design: content verbs ("predicts", "improves") occur
# in article titles, auxiliaries and first person almost never do.
_FINITE = frozenset(
    "is are was were be been being has have had do does did may might could would should can will must "
    "shall we our us i".split()
)
_YEAR = r"(?:19|20)\d{2}[a-z]?"
# A parenthetical holding a year: (Smith et al., 2004; Jones, 2010), (e.g. Burns et al., 2014), (2019).
_PAREN_CITATION = re.compile(r"\([^()]{0,300}?\b" + _YEAR + r"\b[^()]{0,300}?\)")
# A citation tail cut off by chunking: the chunk opens mid-parenthesis ("al., 2004; Tucker et al., 2006).").
_LEADING_ORPHAN = re.compile(r"^[^()]{0,300}?\b" + _YEAR + r"\b[^()]{0,40}?\)[.,;:]?\s*")
# ...or closes before its parenthesis does.
_TRAILING_ORPHAN = re.compile(r"\([^()]{0,300}$")
_NUMERIC_BRACKET = re.compile(r"\[\s*\d{1,3}(?:\s*[,–-]\s*\d{1,3})*\s*\]")
# Superscript-style reference numbers flattened into text: "images,31 and", "full-color images.47-49 Given".
_SUPERSCRIPT_NUM = re.compile(r"(?<=[a-z][,.;)])\s?\d{1,3}(?:\s?[,–\-�]\s?\d{1,3})*(?=\s|$)")

_INITIALS = re.compile(r"\b[A-Z][a-z]+,\s*[A-Z]\.(?:\s*[A-Z]\.)?")
_INITIALS_VANCOUVER = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z]{1,3}\b(?=[,;.])")
_VOLUME_ISSUE = re.compile(r"\b\d+\s*\(\d+(?:\s*[/–-]\s*\d+)?\)\s*[,:]")
_VOLUME_PAGES = re.compile(r"\b\d{1,4}\s*[,:]\s*\d+\s*[-–‐]\s*\d+\b")
_DOI = re.compile(r"\b10\.\d{4,9}/\S+|doi\.org|doi:", re.I)
_NUMBERED_ENTRY = re.compile(r"^\s*\d{1,3}[.)]\s+[A-Z]")
# An entry START -- "Surname, I. (2006)." / "Surname AC (2006)." / "C. A. (2008)." -- is destroyed by the
# citation strip (the year parenthetical goes), so it is detected on the RAW text. In running prose an author
# is cited as "Surname (2006)" or "Surname et al. (2006)", never with initials before the year.
_ENTRY_START = re.compile(
    r"(?:\b[A-Z][a-z]+,\s*(?:[A-Z]\.\s*){1,3}|\b[A-Z][a-z]{2,}\s+[A-Z]{1,3}|(?:\b[A-Z]\.\s*){2,})"
    r"(?:,?\s*&\s*[A-Z][a-z]+,\s*(?:[A-Z]\.\s*){1,3})?\s*\(" + _YEAR + r"\)"
)
_BARE_YEAR = re.compile(r"\b" + _YEAR + r"\b")
# Split after a word of >= 2 lowercase letters, so author initials ("J. A.") do not end a sentence.
_SENTENCE_END = re.compile(r"(?<=[a-z]{2}[.?!])\s+(?=[A-Z(\"'])")

MIN_SUBSTANTIVE_WORDS = 20
MIN_MIXED_LEAD_SENTENCES = 2  # a single leading "sentence" is usually a reference title's tail
MIN_FRAGMENT_WORDS = 8
MIN_STOP_RATIO = 0.22
MIN_FRAGMENT_STOP_RATIO = 0.25
MAX_CAPS_RATIO = 0.30
MAX_FRAGMENT_CAPS_RATIO = 0.20


@dataclass(frozen=True)
class ProseAssessment:
    outcome: str
    reason: str
    residual_words: int


def strip_citations(text: str) -> str:
    """The author's own prose: in-text citation apparatus removed, everything else untouched in order."""
    t = " ".join((text or "").split())
    t = _LEADING_ORPHAN.sub("", t, count=1)
    previous = None
    while previous != t:  # nested or adjacent groups
        previous = t
        t = _PAREN_CITATION.sub("", t)
    t = _TRAILING_ORPHAN.sub("", t)
    t = _NUMERIC_BRACKET.sub("", t)
    t = _SUPERSCRIPT_NUM.sub("", t)
    return " ".join(t.split())


def _words(text: str) -> list[str]:
    return text.split()


def _ratios(words: list[str]) -> tuple[float, float]:
    n = max(len(words), 1)
    stops = sum(1 for w in words if w.lower().strip(".,;:()[]\"'") in _STOPWORDS)
    caps = sum(1 for w in words if w[:1].isupper())
    return stops / n, caps / n


def _has_finite_clause(words: list[str]) -> bool:
    return any(w.lower().strip(".,;:()[]\"'") in _FINITE for w in words)


def entry_structure(text: str) -> bool:
    """Structure that defines a reference ENTRY and survives citation stripping."""
    return bool(
        len(_INITIALS.findall(text)) >= 2
        or len(_INITIALS_VANCOUVER.findall(text)) >= 2
        or _VOLUME_ISSUE.search(text)
        or _VOLUME_PAGES.search(text)
        or _DOI.search(text)
        or _NUMBERED_ENTRY.match(text)
    )


def _sentence_has_entry_marks(sentence: str) -> bool:
    return bool(
        _INITIALS.search(sentence)
        or _INITIALS_VANCOUVER.search(sentence)
        or _VOLUME_ISSUE.search(sentence)
        or _VOLUME_PAGES.search(sentence)
        or _DOI.search(sentence)
        or _BARE_YEAR.search(sentence)
    )


def _reads_as_prose(text: str, *, min_words: int) -> bool:
    words = _words(text)
    if len(words) < min_words or not text.rstrip().endswith((".", "?", "!")):
        return False
    stops, caps = _ratios(words)
    return stops >= MIN_STOP_RATIO and caps < MAX_CAPS_RATIO and _has_finite_clause(words)


def assess_prose(text: str) -> ProseAssessment:
    """Classify the FORM of ``text``. Never reads a section label: that is the signal under suspicion."""
    residual = strip_citations(text)
    words = _words(residual)
    if not words:
        return ProseAssessment(NOT_PROSE, "empty", 0)
    raw = " ".join((text or "").split())
    # Conjunctions are ordered cheapest-first: the entry-start scan is the costliest test and most bibliography
    # fails earlier, which keeps the whole-library heading rescue off the Ask critical path (see LATENCY.md).
    if (
        _reads_as_prose(residual, min_words=MIN_SUBSTANTIVE_WORDS)
        and not entry_structure(residual)
        and not _ENTRY_START.search(raw)
    ):
        return ProseAssessment(SUBSTANTIVE, "prose.citations_stripped", len(words))

    # Prose followed (or preceded) by entries in one chunk: keep the ambiguity explicit.
    sentences = _SENTENCE_END.split(residual)
    lead: list[str] = []
    for sentence in sentences:
        if _sentence_has_entry_marks(sentence):
            break
        lead.append(sentence)
    rest = sentences[len(lead) :]
    if (
        rest
        and len(lead) >= MIN_MIXED_LEAD_SENTENCES
        and all(len(_words(sentence)) >= 6 for sentence in lead)
        and _reads_as_prose(" ".join(lead), min_words=MIN_SUBSTANTIVE_WORDS)
        and (entry_structure(" ".join(rest)) or _ENTRY_START.search(raw))
    ):
        return ProseAssessment(MIXED, "prose.leading_prose_then_entries", len(words))

    if (
        MIN_FRAGMENT_WORDS <= len(words) < MIN_SUBSTANTIVE_WORDS
        and raw == residual  # no citation apparatus of any kind
        and not _BARE_YEAR.search(raw)
        and ":" not in raw  # "Title: subtitle"
        and not entry_structure(raw)
        and raw.endswith((".", "?", "!"))
    ):
        stops, caps = _ratios(words)
        if stops >= MIN_FRAGMENT_STOP_RATIO and caps < MAX_FRAGMENT_CAPS_RATIO and _has_finite_clause(words):
            return ProseAssessment(FRAGMENT, "prose.short_finite_clause", len(words))
    return ProseAssessment(NOT_PROSE, "prose.criteria_not_met", len(words))


def contains_prose(text: str) -> bool:
    """Any of substantive, mixed or fragment: the text is not demonstrably bibliography-only."""
    return assess_prose(text).outcome != NOT_PROSE
