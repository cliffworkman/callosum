"""Deterministic text checks and display transforms for the Phase-30 AnswerPlan. Pure: no model, no I/O.

Verbatim quotes are the semantic authority (Phase-30 D5). Everything here either tests a candidate sentence against its
own source passage, or transforms the display text in a way that is recorded as an edit. Nothing rewrites meaning.
"""

from __future__ import annotations

import re

from app.backend.pdf_processing.extraction import canonical_text_contains, canonicalize_quote_text
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised.contract_directed import attribution as attr

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“(\[])")
_TERMINAL = re.compile(r"[.!?)\"”’\]]\s*$")
_CAPTION_LABEL = r"(?:Table|Fig(?:ure)?\.?)\s*S?\d+\s*\|"
_CAPTION_START = re.compile(r"^\s*" + _CAPTION_LABEL, re.IGNORECASE)
# A run-in heading: three or more words with no punctuation, immediately followed by a sentence-initial pronoun.
_RUN_IN_HEADING = re.compile(r"^((?:[A-Za-z][A-Za-z\-]*\s+){3,}?)(?=(?:We|Our|This|These|The|Here)\s)")
_SELF_REFERENCE = re.compile(r"^(This|The present)\s+(research|study|work|paper|article)\b")
_SELF_STUDY = re.compile(
    r"\b(?:this|the present|our)\s+(?:research|study|paper|work|article|data|results|findings|experiments?)\b",
    re.IGNORECASE,
)
_AIM = re.compile(
    r"\b(?:aims?|aimed|hypothes[ie]s|hypothesi[sz]ed|we tested|tested whether|we examined whether|we predicted)\b",
    re.IGNORECASE,
)
_RESULT_EXTRA = re.compile(
    r"\b(?:significant\w*|greater|less|higher|lower|more|fewer|increas\w*|decreas\w*|reduc\w*|consistent with|"
    r"differ\w*|correlat\w*|associat\w*|predict\w*|slight\w*)\b",
    re.IGNORECASE,
)
_RATING = re.compile(r"\b(?:rated|ratings?|rating|impressions?)\b", re.IGNORECASE)
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
_LINEBREAK_HYPHEN = re.compile(r"([A-Za-z]+)-\s+([a-z]+)")

# (check name, pattern). A failing pattern means the sentence cannot stand on its own without context.
_CLOSURE = (
    ("scope_phrase_refers_outside", re.compile(r"^(?:Across|Within|Among|In|For|Throughout)\s+(?:these|this|those)\b")),
    ("pronoun_or_anaphor_opener", re.compile(r"^(?:These|Those|Such|It|They|Its|Their|He|She|His|Her)\b")),
    ("pronoun_or_anaphor_opener", re.compile(r"^The\s+(?:specific|same|above|latter|former)\b")),
    (
        "pronoun_after_discourse_marker",
        re.compile(r"^[A-Z][a-z]+(?:\s+[a-z]+)?,\s+(?:they|these|those|it|its|their|such)\b", re.IGNORECASE),
    ),
    (
        "anaphor_in_sentence",
        re.compile(
            r"\b(?:this|these)\s+(?:research|study|work|paper|findings|levels|results|effects?)\b", re.IGNORECASE
        ),
    ),
)


def split_sentences(text: str) -> list[str]:
    """Deterministic sentence split on terminal punctuation followed by a capital, quote or parenthesis."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return [part for part in _SENTENCE_BREAK.split(collapsed) if part.strip()]


def is_truncated(quote: str) -> bool:
    return not _TERMINAL.search(quote.strip())


def closure_failures(sentence: str) -> list[str]:
    found: list[str] = []
    for name, pattern in _CLOSURE:
        if pattern.search(sentence) and name not in found:
            found.append(name)
    return found


def strip_run_in_heading(sentence: str) -> tuple[str, dict | None]:
    """Remove a section heading fused to the front of a sentence (a PDF extraction artifact). Recorded as an edit."""
    match = _RUN_IN_HEADING.match(sentence)
    if not match:
        return sentence, None
    removed = match.group(1).strip()
    return sentence[match.end() :], {"kind": "run_in_heading_removed", "removed": removed}


def substitute_source_label(sentence: str, label: str) -> tuple[str, dict | None]:
    """Replace a sentence-initial self-reference ("This research") with the paper's source label. Recorded as an edit.
    Only the referring noun phrase changes; the rest of the verbatim sentence, including every hedge, is untouched."""
    match = _SELF_REFERENCE.match(sentence)
    if not match:
        return sentence, None
    return label + sentence[match.end() :], {
        "kind": "self_reference_to_source_label",
        "from": match.group(0),
        "to": label,
    }


def is_caption_passage(quote: str, paper_span_texts: list[str]) -> bool:
    """A table/figure caption label at the start of the passage, or the passage's wording appearing right after such a
    label in the same paper's sealed spans (structural evidence, not a judgment about the science)."""
    if _CAPTION_START.match(quote):
        return True
    head = re.sub(r"\s+", " ", quote.strip())[:20]
    if len(head) < 12:
        return False
    pattern = re.compile(_CAPTION_LABEL + r"\s*" + re.escape(head), re.IGNORECASE)
    return any(pattern.search(text) for text in paper_span_texts)


def speculative_or_aim(quote: str) -> bool:
    cues = attr.detect_cues(quote)
    return bool(cues["own_interpretation"]) or bool(_AIM.search(quote))


def attribution_kind(quote: str, caption: bool) -> str:
    """Lexical attribution of a verbatim passage. Structural section metadata is not in the replay fixture, so this is
    the defensible lexical evidence only (Phase-30 D4). Anything without a clear cue is `unknown`, never a guess."""
    if caption:
        return "caption"
    if speculative_or_aim(quote):
        return "aim_or_hypothesis"
    if attr.detect_cues(quote)["prior"]:
        return "prior_work"
    if has_result_language(quote):
        return "this_study_result"
    return "unknown"


def has_result_language(text: str) -> bool:
    return bool(attr.has_result_predicate(text) or _RESULT_EXTRA.search(text) or attr.has_statistics(text))


def has_statistics(text: str) -> bool:
    return bool(attr.has_statistics(text))


def has_own_cue(text: str) -> bool:
    return bool(attr.detect_cues(text)["own"]) or bool(_SELF_STUDY.search(text))


def stimulus_rating_cue(text: str) -> bool:
    return bool(_RATING.search(text))


def construct_direct(quote: str, paper_span_texts: list[str], terms: list[str]) -> bool:
    """Requested-construct identity (Phase-30 D7). Direct when the passage or its own paper's sealed text names one of the
    facet's requested-construct terms. Without configured terms the test cannot run and reports direct (no evidence
    either way); the replay overlay always configures terms."""
    if not terms:
        return True
    haystacks = [quote.lower()] + [text.lower() for text in paper_span_texts]
    return any(term.lower() in haystack for term in terms for haystack in haystacks)


def display_text(text: str, corpus_words: set[str]) -> str:
    """Display-only linebreak-hyphen normalization (Phase-30 U15). A joined word is used only when that exact word occurs
    in the sealed corpus; otherwise the hyphen is kept. Verification always uses canonical source text."""

    def repair(match: re.Match) -> str:
        left, right = match.group(1), match.group(2)
        joined = (left + right).lower()
        return left + right if joined in corpus_words else f"{left}-{right}"

    return _LINEBREAK_HYPHEN.sub(repair, text)


def corpus_word_set(texts: list[str]) -> set[str]:
    words: set[str] = set()
    for text in texts:
        words.update(token.lower() for token in re.findall(r"[A-Za-z]+", text))
    return words


def acronyms(text: str) -> list[str]:
    return sorted(set(_ACRONYM.findall(text)))


def definition_hits(term: str, spans: list[dict]) -> list[dict]:
    """Every explicit definitional construction for an acronym in sealed text (Phase-30 U11, Step-2 item C).

    Two constructions are accepted and nothing else: "Long Form (ABBR)" (optionally quoted) and "ABBR (Long Form)". The
    long form is the capitalized phrase that directly precedes the parenthesized acronym, so a sentence such as "We used the
    Implicit Association Test (IAT)" yields "Implicit Association Test", not the whole sentence. Hits are returned in sealed
    span order, so the result is deterministic."""
    capitalized_phrase = r"((?:[A-Z][\w\-]*)(?:\s+(?:[A-Z][\w\-]*|of|and|for|with|in|on|the|to|a))*)"
    long_then_abbr = re.compile(capitalized_phrase + r"[\"“”']?\s*\(\s*" + re.escape(term) + r"\s*\)")
    abbr_then_long = re.compile(re.escape(term) + r"\s*\(\s*([^()]{4,120}?)\s*\)")
    hits: list[dict] = []
    for span in sorted(spans, key=lambda row: (row["paper_id"], str(row["span_id"]))):
        text_value = re.sub(r"\s+", " ", span["text"])
        for pattern_name, pattern in (
            ("long_form_then_acronym", long_then_abbr),
            ("acronym_then_long_form", abbr_then_long),
        ):
            for match in pattern.finditer(text_value):
                hits.append(
                    {
                        "term": term,
                        "long_form": match.group(1).strip(),
                        "paper_id": span["paper_id"],
                        "span_id": span["span_id"],
                        "pattern": pattern_name,
                        "matched": match.group(0),
                    }
                )
    return hits


def same_text(a: str, b: str) -> bool:
    return canonicalize_quote_text(a) == canonicalize_quote_text(b)


def contains(needle: str, haystack: str) -> bool:
    return bool(needle) and canonical_text_contains(needle=needle, haystack=haystack)


def normalized_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def negation_or_hedge(text: str) -> bool:
    return bool(oe.has_negation(text)) or bool(oe.has_hedge(text))
