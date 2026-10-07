"""PHASE 34 I4-1d achieved-outcome span matcher. UNWIRED: no production caller may consume this module's output.

``sufficiency_mapping._match_achieved_outcome`` reuses ``attribution.has_result_predicate`` to answer only WHETHER a
passage contains a result predicate, then returns the WHOLE PASSAGE as the binding's ``exact_text`` regardless of
internal structure. That is insufficient once a passage contains more than one local assertion -- for example
"Previous studies found X. We found Y." -- because a role binding must not inherit its span from whichever assertion
elsewhere in the passage happens to look strongest.

This module answers WHERE, not WHETHER and not WHO: :func:`find_achieved_outcome_matches` returns one
:class:`AchievedOutcomeMatch` per local assertion that anchors a result-predicate match, each carrying the exact
predicate span and a deterministic local assertion span, without ever consulting or reporting on which source
authority governs it.

This increment is about ATTACHMENT, not authority or admissibility. It is deliberately neutral about whether an
attached assertion is direct this-study evidence, prior-work/indirect evidence, review/synthetic evidence,
descriptive evidence, or ``candidate``/``authoritative`` under the Phase-34 I4-1 pure classifier's own rules -- none
of that is decided here. ``candidate`` does not mean unsatisfying; ``prior_work`` does not mean unusable. Those are
deferred to a future evidence-directness/requirement-admissibility increment. That classifier is used only for
VALIDATION, in this module's own test file -- never imported here, so that this module stays exactly as unwired as
that one (see the static guard in ``test_achieved_outcome_span.py``).

Pure: no I/O, no model, no network, no current-version lookup. Deterministic. Reuses
``contract_directed.attribution.has_result_predicate``/``_RESULT_PREDICATE`` UNMODIFIED -- not duplicated -- for
exact boolean parity with the existing mapper. The sentence/clause boundary logic below IS duplicated (not
imported) from that same I4-1 classifier's own boundary rules, by design: importing it would trip its own unwired
static guard, which forbids any non-test reference to it by name.
"""

from __future__ import annotations

import re
from collections import namedtuple

from experiments.ask_cli_revised.contract_directed import attribution as attr

MATCHER_ID = "i4-1d-achieved-outcome-span"
SCHEMA_VERSION = "i4-1d.0"  # a local matcher/schema version only -- never a sufficiency or plan identity

RULE_SINGLE_OR_LAST = "single_or_last_in_clause"
RULE_MERGED = "merged_embedded_content"
RULE_SPLIT = "split_at_coordination"
RULE_AMBIGUOUS = "ambiguous_boundary"
RULES = (RULE_SINGLE_OR_LAST, RULE_MERGED, RULE_SPLIT, RULE_AMBIGUOUS)

AchievedOutcomeMatch = namedtuple(
    "AchievedOutcomeMatch",
    [
        "predicate_span",  # (start, end) of THIS match's own anchoring result-predicate word
        "predicate_surface",  # text[predicate_span]
        "secondary_predicate_spans",  # tuple of (start, end): other result-predicate hits merged in as embedded content
        "sentence_span",  # (start, end) of the enclosing sentence
        "clause_span",  # (start, end) of the enclosing clause, after ';' / ', <contrast word>' splitting
        "assertion_span",  # (start, end): clause_span, narrowed on its left/right edge when split from a neighbour
        "content_span",  # (start, end): (predicate_start, assertion_span end) -- the tightest predicate-anchored view
        "matched_text",  # text[content_span]
        "rule",  # one of RULES
        "ambiguous_with",  # None, or a tuple of the neighbouring predicate_span(s) this one could not be deterministically bounded against
    ],
)

AchievedOutcomeMatchSet = namedtuple("AchievedOutcomeMatchSet", ["old_match_is_not_none", "matches", "has_ambiguity"])

# ---- sentence/clause boundaries (duplicated from the I4-1 classifier module by design; see module docstring) ----

_ABBREV = frozenset("al e i fig figs eq vs cf approx ca dr mr ms ref refs".split())
_SENT_TAIL_CITE = re.compile(r"\d{1,3}(?:[,–\-]\d{1,3})*")
_WS = re.compile(r"\s+")
_LAST_WORD = re.compile(r"([A-Za-z]+)$")
_CONTRAST = frozenset("but although whereas while however yet though".split())
_CLAUSE_BOUNDARY = re.compile(r";|,\s*(?:but|although|whereas|while|however|yet|though)\b", re.IGNORECASE)
_GAP_BOUNDARY = re.compile(r"\b(that|and|or|but)\b", re.IGNORECASE)


def _sentence_spans(text):
    """Sentence boundaries. A terminator counts when a citation marker and whitespace precede a capital, an opening
    quote, or an opening parenthesis. Abbreviations ('al.', 'e.g.', 'i.e.', 'Fig.') never end a sentence. Identical
    algorithm to the I4-1 classifier's own ``_sentence_spans``, duplicated (not imported) by design."""
    spans, start, n = [], 0, len(text)
    for m in re.finditer(r"[.!?]", text):
        p = m.start()
        j = p + 1
        c = _SENT_TAIL_CITE.match(text, j)
        if c:
            j = c.end()
        w = _WS.match(text, j)
        if not w:
            continue
        k = w.end()
        if k >= n or not (text[k].isupper() or text[k] in '"“('):
            continue
        last = _LAST_WORD.search(text[start:p])
        if last and last.group(1).lower() in _ABBREV:
            continue
        spans.append((start, j))
        start = k
    spans.append((start, n))
    out = []
    for a, b in spans:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if b > a:
            out.append((a, b))
    return out


def _clause_spans(text, s, e):
    """Split [s, e) at ';' and at ', <contrast word>' -- the same boundary set the I4-1 classifier's own clause
    splitter uses, reimplemented directly over characters rather than tokens."""
    spans, start = [], s
    for m in _CLAUSE_BOUNDARY.finditer(text, s, e):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, e))
    return [(a, b) for a, b in spans if b > a]


def _last_boundary_in_gap(text, gap_start, gap_end):
    """The LAST occurrence of 'that'/'and'/'or'/'but' in [gap_start, gap_end), or None. Mirrors the nearest-backward
    scan the I4-1 classifier's own ``_last_boundary`` performs when looking for what separates two predicates."""
    last = None
    for m in _GAP_BOUNDARY.finditer(text, gap_start, gap_end):
        last = m
    if last is None:
        return None
    return last.group(0).lower(), (last.start(), last.end())


def _build(text, m, secondary, sentence_span, clause_span, seg_start, seg_end, rule, ambiguous_with):
    content_start = m.start()
    content_end = seg_end
    return AchievedOutcomeMatch(
        predicate_span=(m.start(), m.end()),
        predicate_surface=text[m.start() : m.end()],
        secondary_predicate_spans=secondary,
        sentence_span=sentence_span,
        clause_span=clause_span,
        assertion_span=(seg_start, seg_end),
        content_span=(content_start, content_end),
        matched_text=text[content_start:content_end],
        rule=rule,
        ambiguous_with=ambiguous_with,
    )


def _segment_clause(text, cs, ce, raw_matches, sentence_span):
    """Walk the result-predicate matches of one clause left to right, deciding for each consecutive pair whether the
    second is embedded content of the first ('that' is the last boundary word between them), a coordinated sibling
    assertion ('and'/'or'/'but' is the last boundary word), or genuinely undecidable (no boundary word at all).

    An undecidable boundary is reported as ambiguous on BOTH sides -- the match just closed carries the next raw
    match's span in ``ambiguous_with``, and the next match (once closed) carries this one's span back -- never
    silently merged, split, or reported as ambiguous on only one side of the pair."""
    out = []
    n = len(raw_matches)
    i = 0
    anchor_idx = 0
    seg_start = cs
    secondary: list[tuple[int, int]] = []
    left_ambiguous_span = None  # set when THIS anchor's own left boundary (against the previous anchor) was undecidable
    clause_span = (cs, ce)
    while i < n:
        at_last = i == n - 1
        boundary = None if at_last else _last_boundary_in_gap(text, raw_matches[i].end(), raw_matches[i + 1].start())
        word, span = boundary if boundary else (None, None)
        if not at_last and word == "that":
            secondary.append(raw_matches[i + 1].span())
            i += 1
            continue
        # Closing the current anchor now: either it is the clause's last match, it is split from the next one by a
        # coordinating word, or the boundary against the next one is undecidable.
        if at_last:
            seg_end = ce
            right_ambiguous_span = None
        elif word in ("and", "or", "but"):
            seg_end = span[0]
            right_ambiguous_span = None
        else:
            seg_end = ce
            right_ambiguous_span = raw_matches[i + 1].span()
        ambiguous_with = tuple(s for s in (left_ambiguous_span, right_ambiguous_span) if s) or None
        if ambiguous_with:
            rule = RULE_AMBIGUOUS
        elif secondary:
            rule = RULE_MERGED
        elif at_last:
            rule = RULE_SINGLE_OR_LAST
        else:
            rule = RULE_SPLIT
        out.append(
            _build(
                text,
                raw_matches[anchor_idx],
                tuple(secondary),
                sentence_span,
                clause_span,
                seg_start,
                seg_end,
                rule,
                ambiguous_with,
            )
        )
        if at_last:
            break
        seg_start = span[1] if word in ("and", "or", "but") else raw_matches[i + 1].start()
        anchor_idx = i + 1
        secondary = []
        left_ambiguous_span = raw_matches[i].span() if right_ambiguous_span else None
        i += 1
    return out


def find_achieved_outcome_matches(text):
    """Every local assertion in ``text`` that anchors a result-predicate match, deterministically. Never collapses a
    multi-assertion passage to one match, never ranks candidates by source authority, never uses
    the I4-1 classifier module. ``old_match_is_not_none`` is the exact historical ``_match_achieved_outcome`` boolean,
    carried alongside for self-contained parity verification: it is always true iff ``matches`` is non-empty."""
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    all_matches: list[AchievedOutcomeMatch] = []
    for ss, se in _sentence_spans(text):
        for cs, ce in _clause_spans(text, ss, se):
            raw = list(attr._RESULT_PREDICATE.finditer(text, cs, ce))
            if not raw:
                continue
            all_matches.extend(_segment_clause(text, cs, ce, raw, (ss, se)))
    return AchievedOutcomeMatchSet(
        old_match_is_not_none=attr.has_result_predicate(text),
        matches=tuple(all_matches),
        has_ambiguity=any(mm.ambiguous_with for mm in all_matches),
    )
