"""Run 0.6 deterministic, provenance-owned source-unit segmentation (cue-gated list splitting).

Extends Run 0.5's `datasets.segment_source_units` (which splits only on '?') WITHOUT editing it, so the
completed Run 0.5 harness is untouched. The rule (steering #1 — conservative):

1. Primary split on '?' — EXACTLY Run 0.5. A '?'-terminated span is the user's own request delimiter and is
   kept whole. This preserves the frozen AIB 6-unit representation byte-identically (AIB's stray '.' after
   "which kinds of attitudes." sits INSIDE u2 and must not become a boundary; a '?'-only primary split keeps
   it there). `segment_source_units_v2(BENCHMARK_QUESTION)` therefore equals `segment_source_units(...)`.
2. Only the DECLARATIVE TAIL (a trailing span with no '?', i.e. the whole of q_depr / q_builtenv) is
   sentence-split on '.'/'!', and each declarative sentence is comma-split into per-item units ONLY when it
   is a clearly enumerative construction introduced by a fixed conservative cue set. A declarative sentence
   with NO cue is never split, so compound qualifiers whose meaning depends on staying together remain one
   unit (e.g. "mixed, null, or uncertain findings").

Every unit's text is an exact substring of the question (modulo whitespace strip). Qwen never sees this code;
it can neither create nor delete a canonical unit. There is deliberately NO general natural-language list
parser: the whole rule is the fixed cue set + comma-split of a cued sentence.
"""

from __future__ import annotations

# Fixed, conservative enumeration cues. A declarative sentence is comma-split into list items only if it
# contains one of these; longer phrases are listed before their own substrings for clarity (position, not
# list order, decides which cue fires — see `_has_cue`).
LIST_CUES = (
    "particularly interested in",
    "interested in",
    "including",
    "such as",
    "specifically",
)
_SENTENCE_TERMINATORS = ".!"


def _question_spans(question: str) -> tuple[list[str], str]:
    """Run 0.5's '?'-split: return ('?'-terminated stripped spans, declarative tail).

    Mirrors `datasets.segment_source_units` exactly for the '?'-terminated spans; the trailing declarative
    remainder (if any) is returned separately for cue-gated sentence splitting.
    """
    spans: list[str] = []
    buf = ""
    for ch in question:
        buf += ch
        if ch == "?":
            text = buf.strip()
            if text:
                spans.append(text)
            buf = ""
    return spans, buf.strip()


def _sentences(text: str) -> list[str]:
    """Split a declarative span into sentences on '.'/'!', keeping each terminator with its sentence."""
    out: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in _SENTENCE_TERMINATORS:
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def _has_cue(sentence_lower: str) -> bool:
    return any(cue in sentence_lower for cue in LIST_CUES)


def _cue_split(sentence: str) -> list[str]:
    """A declarative sentence -> one unit, unless a cue makes it enumerative -> per-comma-item units.

    Comma-splitting is applied to the whole cued sentence (the cues in this frozen dataset sit at sentence
    start, so the first item carries the preamble+cue, e.g. "I am particularly interested in serotonergic
    function"). A leading "and"/"or" on an item is kept as part of its exact text (preserves provenance and
    keeps user-authorized open-endedness — "and other relevant ... findings", "and more" — visible).
    """
    if not _has_cue(sentence.lower()):
        return [sentence]
    parts = [part.strip() for part in sentence.split(",")]
    parts = [part for part in parts if part]
    return parts if len(parts) >= 2 else [sentence]


def _split_declarative(tail: str) -> list[str]:
    units: list[str] = []
    for sentence in _sentences(tail):
        units.extend(_cue_split(sentence))
    return units


def segment_source_units_v2(question: str) -> list[dict]:
    """Deterministic ordered source units with code-owned ids. See module docstring for the rule."""
    q = question.strip()
    texts: list[str] = []
    question_spans, tail = _question_spans(q)
    texts.extend(question_spans)  # '?'-terminated request clauses, kept whole (AIB parity)
    if tail:
        texts.extend(_split_declarative(tail))
    return [{"source_unit_id": f"u{i}", "text": text} for i, text in enumerate(texts, start=1)]
