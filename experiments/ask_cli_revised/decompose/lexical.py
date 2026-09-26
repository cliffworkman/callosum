"""Deterministic lexical helpers shared by the engine's checks.

These are HEURISTICS by design: they raise flags and rank candidates; they never decide what the user meant. Every
table here is generic English question scaffolding, not tied to any particular request.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z0-9]+")

# Words that carry no requested content in a standalone question (articles, prepositions, auxiliaries, wh-words,
# quantifier scaffolding). Qualifier words such as "specific", "only", "not" are deliberately absent: they are content.
FUNCTION_WORDS = frozenset(
    """a an the of in on at to for from by with without within into onto about as and or but nor so than then that
    this these those it its itself they them their theirs there here is are was were be been being am do does did done
    have has had having can could will would shall should may might must yes if whether which what who whom whose when
    where why how also just very more much many some such both either neither each every any all i me my we us our you
    your he she his her him one ones per via using use used please give tell show list return provide kind kinds type
    types way ways form forms sort sorts particular particularly relevant""".split()
)

# Words that make a child question refer to something outside itself.
DEIXIS_WORDS = frozenset("they them their theirs it its itself themselves this these those such former latter".split())

_NO_STRIP = ("ss", "us", "is", "as", "os")
_SUFFIXES = (
    ("ational", "ate"),
    ("ations", "ate"),
    ("ation", "ate"),
    ("ities", "ity"),
    ("ings", ""),
    ("ing", ""),
    ("ies", "y"),
    ("ied", "y"),
    ("edly", ""),
    ("ed", ""),
    ("ness", ""),
    ("ments", ""),
    ("ment", ""),
    ("ly", ""),
    ("es", ""),
    ("s", ""),
)


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD.finditer(text)]


def stem(word: str) -> str:
    w = word.lower()
    if len(w) <= 3:
        return w
    for suffix, replacement in _SUFFIXES:
        if suffix == "s" and w.endswith(_NO_STRIP):
            continue
        if w.endswith(suffix) and len(w) - len(suffix) + len(replacement) >= 3:
            return w[: len(w) - len(suffix)] + replacement
    return w


FUNCTION_STEMS = frozenset(stem(w) for w in FUNCTION_WORDS)


def stems_match(a: str, b: str) -> bool:
    """Equal stems, or one a prefix of the other (both at least 5 characters): manifest ~ manifestation."""
    if a == b:
        return True
    return min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a))


def is_content_token(tok: str) -> bool:
    """A function word, or an inflection of one ("returned" ~ "return"), is not content."""
    return len(tok) > 2 and tok not in FUNCTION_WORDS and stem(tok) not in FUNCTION_STEMS


def content_stems(text: str) -> list[str]:
    """Distinct content-word stems in order of first appearance (function words and 1-2 letter tokens removed)."""
    seen: dict[str, None] = {}
    for tok in tokens(text):
        if is_content_token(tok):
            seen.setdefault(stem(tok), None)
    return list(seen)


def has_stem(stems: list[str], candidate: str) -> bool:
    return any(stems_match(candidate, s) for s in stems)


def missing_stems(required: list[str], available: list[str]) -> list[str]:
    return [r for r in required if not has_stem(available, r)]


def coverage_fraction(required: list[str], available: list[str]) -> float:
    if not required:
        return 1.0
    return 1.0 - len(missing_stems(required, available)) / len(required)


def deixis_in(text: str) -> list[str]:
    return sorted({tok for tok in tokens(text) if tok in DEIXIS_WORDS})
