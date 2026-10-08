"""PHASE 34 I4-1c assertion-source / assertion-kind classifier. UNWIRED: no production caller may import this module.

It answers, for the assertion that BEARS ON A SUPPLIED TARGET SPAN:

* ``assertion_source``: whose evidentiary assertion is it (``this_study`` / ``prior_work`` / ``unknown``)?
* ``assertion_kind``: what kind of assertion is it (``result`` / ``method_or_description`` /
  ``aim_or_hypothesis`` / ``interpretation`` / ``unknown``)?
* ``is_caption``: a structural input, never a source.
* ``source_resolution``: which rule fixed the source (``parsed`` / ``structural_results_label`` /
  ``owner_signal_context`` / ``unresolved``).
* ``authority_veto``: a reason (``negated_result_predicate`` / ``absence_of_evidence``) that keeps a this-study result
  from being authoritative even though source and kind alone would say so. ``None`` when nothing vetoes it.
* audit flags: ``framing_source``, ``citation_marked``, ``hedged``, ``negated``, ``negated_replication``.

I4-1b added three repairs: (A) a leading run-in label such as ``Results:`` is isolated before ownership parsing, so the
label cannot block a real prior or current owner; (B) that label is recognised only as a bounded, colon-delimited,
predicate-free prefix at the start of the input, and it grants no ownership by itself; (C) an assertion's region
includes its own subject, so an assertion can cover its whole content, and :func:`classify_target_assertions` returns
every intersecting assertion without collapsing them. One narrow resolver turns an otherwise-unknown result into
``this_study`` only when the label is exactly ``results`` and every veto is clear.

I4-1c adds one authority-only gate on top of that: a this-study result predicate that is itself negated (``We did not
find that X increased``), or whose predicate's own embedded clause is negated (``We found that X did not increase``),
or whose object is governed by an absence-of-evidence construction (``We found no evidence that X increased``), still
reports ``assertion_source = this_study`` and ``assertion_kind = result`` -- the authors are still reporting a result
of this study -- but ``finding_authority`` is held at ``candidate``, because the governing predicate does not
authoritatively establish the embedded positive target proposition. The veto is per-assertion and never leaks across a
clause boundary to an unvetoed sibling. It does not change provenance (who/what), only authority (does this establish
the target), and it never collapses ``interpretation`` / ``method_or_description`` / ``aim_or_hypothesis`` / caption
candidates, which were already candidate before this gate existed.

``finding_authority`` is derived by ONE central function (:func:`finding_authority`). Nothing here decides observation
polarity, role completion, recovery, relation witnessing, direction, or AnswerPlan placement.

I4-1f (I4-1e revision 2, R1-R3, R12) adds two further pure, orthogonal, STILL UNWIRED descriptors, per-assertion:

* :func:`assertion_relation`: a pure 1:1 rename-view of ``assertion_source`` (``this_study`` -> ``current_document``,
  ``prior_work`` -> ``attributed_external``, ``unknown`` -> ``unresolved``). No new inference. ``synthesis`` is never a
  value of either field -- R1's lock.
* ``aggregation`` (``literature_synthesis`` / ``non_synthetic_or_unspecified``): does this ONE local assertion
  explicitly aggregate or synthesize evidence across a literature/study set? Computed from three small, closed,
  high-precision cue families -- a fronted literature/study-set framing phrase anywhere in the assertion's own
  pre-predicate clause span; the assertion's own governing SUBJECT being a review/meta-analysis/literature-synthesis
  noun phrase (independent of how that subject's ownership itself resolved); or, for a RESULT-kind assertion only, an
  explicit synthesis-context word/phrase in its own content (never a bare pooled/combined/aggregate word alone). It
  never answers who owns the assertion, never admissibility, never document genre, and never feeds back into
  ``assertion_source``/``assertion_kind``/``finding_authority``/``authority_veto``. :func:`support_label` is a pure,
  DISPLAY-ONLY convenience derived from (``assertion_relation``, ``aggregation``, ``assertion_kind``); nothing in this
  module reads its own output back.

One narrow, disclosed lexicon addition supports both of the above: a review/meta-analysis/literature-synthesis
governing-source noun phrase (``A recent review found that X``, ``The literature suggests X``) is now recognised by
the existing owner-phrase architecture, guarded so that a trailing noun it does NOT govern (``the review variable``)
is never mistaken for ownership.

Pure: no I/O, no model, no network, no current-version lookup. Deterministic. Output is JSON-safe. Ownership is fail-closed:
a source the sealed text does not establish is ``unknown``. Lexical cues are a closed set of verbs, determiners,
prior-source nouns, and first-person or study-noun owner forms. No participant or population noun list is used.
"""

from __future__ import annotations

import hashlib
import re
from collections import namedtuple

CLASSIFIER_ID = "i4-1-assertion-authority"
RULESET_VERSION = "i4-1f.0"

THIS_STUDY = "this_study"
PRIOR_WORK = "prior_work"
UNKNOWN_SOURCE = "unknown"
RESULT = "result"
METHOD = "method_or_description"
AIM = "aim_or_hypothesis"
INTERPRETATION = "interpretation"
UNKNOWN_KIND = "unknown"
AUTHORITATIVE = "authoritative"
CANDIDATE = "candidate"
PARSED = "parsed"
STRUCTURAL_RESULTS = "structural_results_label"
OWNER_CONTEXT = "owner_signal_context"
UNRESOLVED = "unresolved"
SOURCES = (THIS_STUDY, PRIOR_WORK, UNKNOWN_SOURCE)
KINDS = (RESULT, METHOD, AIM, INTERPRETATION, UNKNOWN_KIND)
OWNER_SIGNALS = (THIS_STUDY, PRIOR_WORK)
RESULTS_LABEL = "results"
LABEL_MAX_WORDS = 8
LABEL_MAX_CHARS = 80
TARGET_SCOPES = ("within_assertion", "partial_assertion", "multi_assertion", "no_governing_assertion")
AUTHORITY_VETO_NEGATED = "negated_result_predicate"
AUTHORITY_VETO_ABSENCE = "absence_of_evidence"
AUTHORITY_VETOES = (AUTHORITY_VETO_NEGATED, AUTHORITY_VETO_ABSENCE)


def finding_authority(assertion_source, assertion_kind, is_caption=False, authority_veto=None):
    """The one central authority function. Semantic only: no polarity, no completion, no confidence.

    ``authority_veto`` (I4-1c), when set, means the governing result predicate is negated, or its target is embedded
    under an absence-of-evidence construction. It never promotes a candidate; it can only prevent AUTHORITATIVE.
    """
    if assertion_source not in SOURCES:
        raise ValueError(f"unknown assertion_source: {assertion_source!r}")
    if assertion_kind not in KINDS:
        raise ValueError(f"unknown assertion_kind: {assertion_kind!r}")
    if authority_veto is not None and authority_veto not in AUTHORITY_VETOES:
        raise ValueError(f"unknown authority_veto: {authority_veto!r}")
    if assertion_source == THIS_STUDY and assertion_kind == RESULT and not is_caption and authority_veto is None:
        return AUTHORITATIVE
    return CANDIDATE


# I4-1f (I4-1e revision 2, R1/R3): assertion_relation is a pure, lossless, 1:1 RENAME-VIEW of assertion_source --
# never a new classification. The production-facing names avoid the real naming-collision risk the revision-2
# audit identified in finding_authority's own "candidate" value, and read naturally beside the orthogonal
# aggregation axis below. "synthesis" is never accepted here or anywhere in this module (R1's lock).
CURRENT_DOCUMENT = "current_document"
ATTRIBUTED_EXTERNAL = "attributed_external"
RELATION_UNRESOLVED = "unresolved"
ASSERTION_RELATIONS = (CURRENT_DOCUMENT, ATTRIBUTED_EXTERNAL, RELATION_UNRESOLVED)
_ASSERTION_RELATION_BY_SOURCE = {
    THIS_STUDY: CURRENT_DOCUMENT,
    PRIOR_WORK: ATTRIBUTED_EXTERNAL,
    UNKNOWN_SOURCE: RELATION_UNRESOLVED,
}


def assertion_relation(assertion_source):
    """Pure 1:1 rename-view of ``assertion_source``. Performs NO new inference over the exact closed vocabulary
    ``assertion_source`` already uses; fails explicitly (never invents a fourth relation) for anything outside it,
    including ``"synthesis"`` and any of this function's own output values."""
    try:
        return _ASSERTION_RELATION_BY_SOURCE[assertion_source]
    except (KeyError, TypeError):
        raise ValueError(f"unknown assertion_source: {assertion_source!r}") from None


# ---- closed lexicons (lowercase). Verbs and nouns only; no population or participant nouns. ----

_RESULT_VERBS = frozenset(
    "found find finds detected detect detects observed observe observes showed show shows shown revealed reveal reveals "
    "demonstrated demonstrate demonstrates correlated correlate correlates predicted predict predicts associated associate "
    "differed differ increased increase decreased decrease reduced reduce reduces expressed express described describe "
    "describes reported yielded yield produced produce produces emerged emerge indicated indicate indicates influence "
    "influences influenced implicated implicate implicates improved improve improves affected affect affects provided "
    "provide provides".split()
)
_REPLICATION_VERBS = frozenset(
    "confirmed confirm confirms replicated replicate replicates replicating reproduced reproduce corroborated "
    "corroborate".split()
)
_METHOD_VERBS = frozenset(
    "measured measure measures used use uses administered administer completed complete completes recruited recruit "
    "assessed assess assesses collected collect conducted conduct performed perform ran employed employ selected asked ask "
    "presented scored rated".split()
)
_AIM_VERBS = frozenset("hypothesized hypothesised hypothesize hypothesise aimed aim aims sought seek".split())
_TEST_VERBS = frozenset("tested test tests examined examine investigated investigate explored explore".split())
_INTERP_VERBS = frozenset(
    "suggest suggests suggested suggesting propose proposes proposed argue argues argued speculate speculated believe "
    "believes believed posit conjecture contend imply implies implied".split()
)
_PREDICATES = _RESULT_VERBS | _REPLICATION_VERBS | _METHOD_VERBS | _AIM_VERBS | _TEST_VERBS | _INTERP_VERBS

_NEG = frozenset("not never no failed fail fails".split())
_MODALS = frozenset("can could may might must shall should will would".split())
_HEAD_SKIP = (
    _NEG
    | _MODALS
    | frozenset("to did do does have has had been be is are was were also further still help helped helps".split())
)
_DISCOURSE = frozenset(
    "nevertheless however moreover furthermore additionally finally thus therefore also further indeed overall together "
    "here notably interestingly importantly similarly likewise although though even still then subsequently later next "
    "first consistently in addition".split()
)
_DISCOURSE_SHORT = frozenset("then also further subsequently later next".split())
_CONTRAST = frozenset("but although whereas while however yet though".split())
_DET = frozenset("the these those such its their his her some several".split())
_PRIOR_ADJ = frozenset("previous prior earlier recent past existing other original initial preceding".split())
_SOURCE_NOUN = frozenset(
    "study studies work works report reports research finding findings literature evidence investigation investigations "
    "paper papers experiment experiments".split()
)
_STUDY_NOUN = frozenset(
    "study studies research paper work article manuscript experiment experiments analysis investigation review".split()
)
_OWNER_DET = frozenset("this the present current".split())
_OWNER_PRONOUN = frozenset({"we"})
_COMPARISON = (
    ("consistent", "with"),
    ("in", "line", "with"),
    ("in", "agreement", "with"),
    ("contrary", "to"),
    ("unlike",),
    ("as", "in"),
    ("as", "did"),
    ("similar", "to"),
    ("replicating",),
    ("extending",),
    ("like",),
)
_HEDGE = frozenset(
    "may might could can would will should possibly perhaps potentially possibility likely probably seem seems appear "
    "appears suggest suggests suggested suggesting possible".split()
)
_ABBREV = frozenset("al e i fig figs eq vs cf approx ca dr mr ms ref refs".split())
# I4-1c: the closed head-noun set for the absence-of-evidence authority veto. 'no' + one of these, as either the
# governing subject ('No evidence showed...') or the start of the object content ('...found no evidence that...').
_ABSENCE_HEAD = frozenset("evidence support indication proof".split())
# A run-in label may never contain a predicate, modal, negation, hedge, contrast, copula, or 'that'.
_LABEL_BLOCK = (
    _PREDICATES | _NEG | _MODALS | _HEDGE | _CONTRAST | frozenset("that is are was were be been being".split())
)
_TERMINAL_TRIM = ".;!?"
_YEAR_PAREN = re.compile(r"\([^()]*\b(?:18|19|20)\d{2}\b[^()]*\)")
# A leading label: 1..LABEL_MAX_WORDS words, then ':' then whitespace then more text. Digits and punctuation are excluded.
_LABEL_RE = re.compile(
    r"[ \t]*(?P<label>[A-Za-z][A-Za-z'\-]*(?:[ \t]+[A-Za-z][A-Za-z'\-]*){0,%d})[ \t]*:[ \t]+(?=\S)"
    % (LABEL_MAX_WORDS - 1)
)

# ---- tokenization ----

_TOKEN_RE = re.compile(
    r"(?P<cite>(?:(?<=[A-Za-z]{3})|(?<=[A-Za-z]{2}[.,)])|(?<=[A-Za-z]\.))\d{1,3}(?:[,–\-]\d{1,3})*(?!\d))"
    r"|(?P<word>[A-Za-z][A-Za-z'\-]*)"
    r"|(?P<num>\d+(?:[.,]\d+)*%?)"
    r"|(?P<punct>[,;:()\[\]=<>.!?\"“”])"
)
_SENT_TAIL_CITE = re.compile(r"\d{1,3}(?:[,–\-]\d{1,3})*")
_WS = re.compile(r"\s+")
_LAST_WORD = re.compile(r"([A-Za-z]+)$")
_Tok = namedtuple("_Tok", "kind low raw start end")


def _tokenize(text, s, e):
    toks = []
    for m in _TOKEN_RE.finditer(text, s, e):
        raw = m.group(0)
        toks.append(_Tok(m.lastgroup, raw.lower(), raw, m.start(), m.end()))
    return toks


def _is_word(t, *lows):
    return t.kind == "word" and (not lows or t.low in lows)


def _is_punct(t, *lows):
    return t.kind == "punct" and (not lows or t.low in lows)


def _is_name(t):
    return t.kind == "word" and t.raw[:1].isupper() and t.low not in _DET and t.low not in _PRIOR_ADJ


def _sentence_spans(text):
    """Sentence boundaries. A terminator counts when a citation marker and whitespace precede a capital, an opening quote,
    or an opening parenthesis. Abbreviations ('al.', 'e.g.', 'i.e.', 'Fig.') never end a sentence."""
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


# ---- run-in label (I4-1b repair A/B) ----


def _detect_run_in_label(text):
    """A leading run-in label at the start of the classifier input, or None. Structural only: a label grants no owner.
    Rejected when it contains a predicate/modal/negation/hedge/contrast/copula/'that', contains digits or citations, is
    itself a prior-source phrase (its ownership would be lost), or is an owner phrase."""
    m = _LABEL_RE.match(text)
    if m is None:
        return None
    surface = m.group("label")
    if len(surface) > LABEL_MAX_CHARS:
        return None
    toks = _tokenize(surface, 0, len(surface))
    if not toks or any(t.kind != "word" or t.low in _LABEL_BLOCK for t in toks):
        return None
    if _match_prior_np(toks, 0, len(toks)) is not None or _owner_full(toks, 0, len(toks)):
        return None
    return {
        "surface": surface,
        "normalized": " ".join(surface.split()).lower(),
        "span": [m.start("label"), m.end("label")],
        "remainder_start": m.end(),
    }


# ---- prior-source constructions ----


def _year_group(toks, j, hi):
    if j + 2 < hi and _is_punct(toks[j], "(") and toks[j + 1].kind == "num" and _is_punct(toks[j + 2], ")"):
        return j + 3
    return j


# I4-1f (I4-1e revision 2, section 3): a review/meta-analysis/literature-synthesis governing-source noun phrase.
# Kept fully SELF-CONTAINED (its own determiner handling, its own trailing-noun guard) rather than folded into the
# three branches above, so adding it can change ONLY cases whose governing source owner falls inside this new class
# -- the pre-existing _DET/_PRIOR_ADJ/_SOURCE_NOUN branches, and every caller's behaviour for text that does not
# contain this vocabulary, are byte-unchanged.
_REVIEW_GENRE_ADJ = frozenset("systematic meta-analytic".split())
_REVIEW_HEAD = frozenset("review reviews meta-analysis meta-analyses literature".split())
_REVIEW_DET = _DET | frozenset({"a", "an"})  # local only: "a"/"an" are not in the shared _DET (see module notes)
_REVIEW_MODIFIER_REQUIRED_HEAD = frozenset({"evidence"})  # too generic a noun to recognise bare


def _match_review_source_np(toks, i, hi):
    """End index (exclusive) of a review/meta-analysis/literature-synthesis governing-source noun phrase starting
    at ``i``, or None. An optional determiner (including "a"/"an"), then an optional single temporal-priority
    (``_PRIOR_ADJ``, e.g. "recent") or genre (``_REVIEW_GENRE_ADJ``, e.g. "systematic"/"meta-analytic") modifier,
    then the head noun. "evidence" is recognised ONLY directly after the genre modifier (too generic a noun to
    recognise bare, unlike "review"/"meta-analysis"/"literature"). GUARDS against the head noun modifying a
    FOLLOWING noun it does not govern (e.g. "the review variable") by requiring nothing but a citation marker or
    end-of-range may follow it within ``[i, hi)`` -- the exact property that makes this a GOVERNING source owner,
    not merely a word that happens to occur."""
    j = i
    if j < hi and _is_word(toks[j], *_REVIEW_DET):
        j += 1
    genre_modifier = j < hi and _is_word(toks[j], *_REVIEW_GENRE_ADJ)
    if j < hi and _is_word(toks[j], *_PRIOR_ADJ, *_REVIEW_GENRE_ADJ):
        j += 1
    if j < hi and _is_word(toks[j], *_REVIEW_HEAD):
        j += 1
    elif genre_modifier and j < hi and _is_word(toks[j], *_REVIEW_MODIFIER_REQUIRED_HEAD):
        j += 1
    else:
        return None
    while j < hi and toks[j].kind == "cite":
        j += 1
    if j < hi and toks[j].kind == "word":
        return None
    return j


def _match_prior_np(toks, i, hi):
    """End index (exclusive) of an external-source noun phrase starting at ``i``, or None. Determiners are skipped."""
    j = i
    if j < hi and _is_word(toks[j], *_DET):
        j += 1
    if j + 1 < hi and _is_word(toks[j], *_PRIOR_ADJ) and _is_word(toks[j + 1], *_SOURCE_NOUN):
        j += 2
    elif j + 2 < hi and _is_name(toks[j]) and _is_word(toks[j + 1], "et") and _is_word(toks[j + 2], "al"):
        j += 3
        if j < hi and _is_punct(toks[j], "."):
            j += 1
        j = _year_group(toks, j, hi)
        if j < hi and _is_word(toks[j], *_SOURCE_NOUN):
            j += 1
    elif j + 3 < hi and _is_name(toks[j]) and _year_group(toks, j + 1, hi) == j + 4:
        j += 4
    else:
        return _match_review_source_np(toks, i, hi)
    while j < hi and toks[j].kind == "cite":
        j += 1
    return j


def _comparison_len(toks, c, hi):
    for phrase in _COMPARISON:
        n = len(phrase)
        if c + n <= hi and all(_is_word(toks[c + k], phrase[k]) for k in range(n)):
            return n
    return 0


# ---- owner / prior subjects ----


def _owner_full(toks, a, b):
    """True only when [a, b) is exactly an owner noun phrase (no verb, no punctuation)."""
    if a >= b or any(toks[i].kind == "punct" for i in range(a, b)):
        return False
    if any(toks[i].kind in ("cite", "num") for i in range(a, b)):
        return False
    lows = [toks[i].low for i in range(a, b)]
    if not lows:
        return False
    if lows == ["we"]:
        return True
    if lows[0] == "our" and len(lows) <= 3 and not any(x in _PREDICATES or x in _HEAD_SKIP for x in lows):
        return True
    return (
        len(lows) <= 3
        and lows[0] in _OWNER_DET
        and lows[-1] in _STUDY_NOUN
        and all(x in _OWNER_DET or x in _STUDY_NOUN for x in lows)
    )


def _prior_prefix(toks, a, b):
    return a < b and _match_prior_np(toks, a, b) is not None


def _skip_discourse(toks, a, b):
    while a < b and (toks[a].kind == "punct" or _is_word(toks[a], *_DISCOURSE)):
        a += 1
    return a


# ---- predicates, subjects, assertions ----


def _head_start(toks, idx, cs):
    h = idx
    while h - 1 >= cs and idx - h < 4 and _is_word(toks[h - 1], *_HEAD_SKIP):
        h -= 1
    return h


def _last_boundary(toks, cs, head):
    for j in range(head - 1, cs - 1, -1):
        t = toks[j]
        if _is_punct(t, ",") or _is_word(t, "and", "or", "but", "that"):
            return j
    return None


def _subject_record(toks, a, b, inherited=False):
    """Owner or prior subject for [a, b). Owner is exact; prior is a leading external-source noun phrase."""
    if a is None or b is None or a >= b:
        return {"start": None, "end": None, "source": UNKNOWN_SOURCE, "rule": "subject.absent", "inherited": inherited}
    a = _skip_discourse(toks, a, b)
    if a >= b:
        return {"start": None, "end": None, "source": UNKNOWN_SOURCE, "rule": "subject.absent", "inherited": inherited}
    if _owner_full(toks, a, b):
        return {"start": a, "end": b, "source": THIS_STUDY, "rule": "subject.owner", "inherited": inherited}
    if _prior_prefix(toks, a, b):
        return {"start": a, "end": b, "source": PRIOR_WORK, "rule": "subject.prior_source", "inherited": inherited}
    return {"start": a, "end": b, "source": UNKNOWN_SOURCE, "rule": "subject.unowned", "inherited": inherited}


def _first_assertion(toks, cs, ce, head, idx):
    comma = None
    for j in range(head - 1, cs - 1, -1):
        if _is_punct(toks[j], ","):
            comma = j
            break
    framing = None
    subj_start = cs
    if comma is not None:
        subj_start = comma + 1
        framing = (cs, comma)
    that_j = None
    for j in range(subj_start, head):
        if _is_word(toks[j], "that"):
            that_j = j
    if that_j is not None:
        subj_start = that_j + 1
    subj = _subject_record(toks, subj_start, head)
    framing_rec = None
    if framing is not None:
        for i in range(framing[0], framing[1]):
            e = _match_prior_np(toks, i, framing[1])
            if e is not None:
                framing_rec = {"start": i, "end": e, "source": PRIOR_WORK, "rule": "framing.prior_source"}
                break
        if framing_rec is None and subj["source"] == UNKNOWN_SOURCE:
            for i in range(framing[0], framing[1] - 1):
                if _is_word(toks[i], "according") and _is_word(toks[i + 1], "to"):
                    subj = {**subj, "source": PRIOR_WORK, "rule": "subject.according_to_source"}
                    framing_rec = {"start": i, "end": framing[1], "source": PRIOR_WORK, "rule": "framing.according_to"}
                    break
    return {"head": head, "pred": idx, "subj": subj, "framing": framing_rec, "boundary": None}


def _new_assertion(toks, head, idx, boundary, subj):
    return {"head": head, "pred": idx, "subj": subj, "framing": None, "boundary": boundary}


def _clause_assertions(toks, cs, ce):
    cands = [i for i in range(cs, ce) if _is_word(toks[i], *_PREDICATES)]
    asserts = []
    for idx in cands:
        head = _head_start(toks, idx, cs)
        if not asserts:
            asserts.append(_first_assertion(toks, cs, ce, head, idx))
            continue
        j = head - 1
        while j >= cs and _is_word(toks[j], *_DISCOURSE_SHORT):
            j -= 1
        if j >= cs and (_is_punct(toks[j], ",") or _is_word(toks[j], "and", "or")):
            prev = asserts[-1]["subj"]
            asserts.append(_new_assertion(toks, head, idx, j, {**prev, "inherited": True}))
            continue
        b = _last_boundary(toks, cs, head)
        if b is None:
            continue
        seg = _subject_record(toks, b + 1, head)
        if seg["source"] == UNKNOWN_SOURCE:
            continue
        asserts.append(_new_assertion(toks, head, idx, b, {**seg, "rule": seg["rule"] + ".new_subject"}))
    return asserts


def _object_bounds(toks, a, next_boundary, ce):
    obj_start = a["pred"] + 1
    obj_end = next_boundary if next_boundary is not None else ce
    if obj_end < obj_start:
        obj_end = obj_start
    while obj_end > obj_start and (
        _is_punct(toks[obj_end - 1], ",", ";", ":", ".", "!", "?") or _is_word(toks[obj_end - 1], "and", "or")
    ):
        obj_end -= 1
    return obj_start, obj_end


def _object_content(toks, obj_start, obj_end, comparison_ok=True):
    """Content span, prior-object framing, and the 'that'-shift. Pure over the object tokens."""
    content_start = obj_start
    if obj_start < obj_end and _is_word(toks[obj_start], "that"):
        content_start = obj_start + 1
    prior = None
    shifted = False
    for i in range(obj_start, obj_end):
        e = _match_prior_np(toks, i, obj_end)
        if e is not None:
            prior = (i, e)
            m = e
            if m < obj_end and _is_punct(toks[m], ","):
                m += 1
            if m < obj_end and _is_word(toks[m], "that"):
                content_start = m + 1
                shifted = True
            break
    content_end = obj_end
    comparison = None
    if comparison_ok:
        for c in range(content_start, obj_end):
            n = _comparison_len(toks, c, obj_end)
            if n and _match_prior_np(toks, c + n, min(obj_end, c + n + 6)) is not None:
                comparison = (c, c + n)
                if c - 1 >= content_start and _is_punct(toks[c - 1], ","):
                    content_end = c - 1
                else:
                    content_end = c
                break
    while content_end > content_start and _is_punct(toks[content_end - 1], ","):
        content_end -= 1
    return {
        "content": (content_start, content_end),
        "prior": prior,
        "shifted": shifted,
        "comparison": comparison,
    }


def _analyze_clause_assertions(toks, cs, ce, label_scope=False, label_normalized=None):
    """Assertions of one clause. ``label_scope`` is True only for the first clause of a sentence whose input starts with a
    run-in label; within it, the scope is the first assertion plus any assertion coordinated on its inherited subject."""
    asserts = _clause_assertions(toks, cs, ce)
    out = []
    in_scope = label_scope
    for k, a in enumerate(asserts):
        next_boundary = asserts[k + 1]["boundary"] if k + 1 < len(asserts) else None
        obj_start, obj_end = _object_bounds(toks, a, next_boundary, ce)
        rec = _build(toks, a, obj_start, obj_end, cs)
        if label_scope:
            in_scope = k == 0 or (in_scope and bool(a["subj"]["inherited"]))
        rec["label_scope"] = bool(in_scope)
        rec["label_normalized"] = label_normalized if in_scope else None
        out.append(rec)
    return out


# ---- authority veto detection (I4-1c): negated result predicate, absence of evidence ----


def _content_negated(toks, cs, ce):
    """True when the object CONTENT itself reads as a clause whose own result/replication predicate is negated
    ('X did not increase'), distinct from the governing predicate's own head-to-pred negation ('did not find')."""
    for i in range(cs, ce):
        if _is_word(toks[i], *_RESULT_VERBS) or _is_word(toks[i], *_REPLICATION_VERBS):
            h = _head_start(toks, i, cs)
            if any(_is_word(toks[j], *_NEG) for j in range(h, i)):
                return True
    return False


def _absence_of_evidence(toks, subj, content_start, content_end):
    """True when the governing subject, or the start of the object content, is exactly 'no' + a closed absence-head
    noun ('no evidence', 'no support', 'no indication', 'no proof'). Deliberately narrow: not a null-result ontology."""
    s, e = subj["start"], subj["end"]
    if s is not None and e - s == 2 and _is_word(toks[s], "no") and _is_word(toks[s + 1], *_ABSENCE_HEAD):
        return True
    return (
        content_end - content_start >= 2
        and _is_word(toks[content_start], "no")
        and _is_word(toks[content_start + 1], *_ABSENCE_HEAD)
    )


# ---- aggregation detection (I4-1f): literature/study-set synthesis, orthogonal to source/kind/authority ----

# Cue family A (section 6A): a closed, literal, literature/study-set FRAMING phrase, scanned over the assertion's
# own pre-predicate clause span -- not the subject, since a comma-separated list inside the subject (a pre-existing,
# unrelated parsing property; see the module notes on _first_assertion/_clause_assertions) can otherwise swallow a
# fronted adverbial like "Across multiple studies," before subject detection ever sees it. "across trials" sits here
# too, alongside "across studies": the directive's own conservative rule (section 7) already authorises it as an
# explicit synthesis-context phrase, and a fronted "Across trials," is the same signal in adverbial position.
_AGGREGATION_FRAMING_PHRASES = (
    ("across", "multiple", "studies"),
    ("across", "prior", "studies"),
    ("across", "studies"),
    ("across", "trials"),
)
# Cue family C (section 7): explicit synthesis-context words/phrases, checked only within a RESULT-kind assertion's
# own content span. Deliberately NOT "pooled"/"combined"/"aggregate"/"effect" -- those describe ordinary
# within-study statistical combination (pooled across participants/sites/conditions/time points; combined across
# measures) and are never, by themselves, sufficient (the conservative rule this increment exists to hold).
_SYNTHESIS_CONTEXT_WORDS = frozenset("meta-analytic meta-analysis meta-analyses".split())
_SYNTHESIS_CONTEXT_PHRASES = (
    ("across", "studies"),
    ("across", "trials"),
    ("literature-wide",),
)
LITERATURE_SYNTHESIS = "literature_synthesis"
NON_SYNTHETIC = "non_synthetic_or_unspecified"
AGGREGATIONS = (LITERATURE_SYNTHESIS, NON_SYNTHETIC)

_SUPPORT_LABEL_BY_RELATION_AGGREGATION = {
    (CURRENT_DOCUMENT, NON_SYNTHETIC): "direct_empirical",
    (CURRENT_DOCUMENT, LITERATURE_SYNTHESIS): "direct_synthetic",
    (ATTRIBUTED_EXTERNAL, NON_SYNTHETIC): "attributed_indirect",
    (ATTRIBUTED_EXTERNAL, LITERATURE_SYNTHESIS): "attributed_synthetic",
    (RELATION_UNRESOLVED, NON_SYNTHETIC): "unresolved",
    (RELATION_UNRESOLVED, LITERATURE_SYNTHESIS): "unresolved_synthetic",
}


def support_label(relation, aggregation, kind):
    """Pure, DISPLAY-ONLY convenience derived from (``assertion_relation``, ``aggregation``, ``assertion_kind``).
    Never the semantic representation, and never consumed by any admissibility/classification function in this
    module -- ``method_or_description``/``interpretation`` collapse to a single label regardless of relation or
    aggregation; ``aim_or_hypothesis``/``unknown`` kinds have no label at all (a stated intention, or no assertion,
    is not itself offered as evidence)."""
    if relation not in ASSERTION_RELATIONS:
        raise ValueError(f"unknown assertion_relation: {relation!r}")
    if aggregation not in AGGREGATIONS:
        raise ValueError(f"unknown aggregation: {aggregation!r}")
    if kind not in KINDS:
        raise ValueError(f"unknown assertion_kind: {kind!r}")
    if kind == METHOD:
        return "descriptive"
    if kind == INTERPRETATION:
        return "interpretive"
    if kind in (AIM, UNKNOWN_KIND):
        return None
    return _SUPPORT_LABEL_BY_RELATION_AGGREGATION[(relation, aggregation)]


def _phrase_at(toks, lo, hi, phrase):
    """True when the exact word sequence ``phrase`` occurs contiguously anywhere in token range [lo, hi)."""
    n = len(phrase)
    return any(all(_is_word(toks[k + off], phrase[off]) for off in range(n)) for k in range(lo, max(lo, hi - n + 1)))


def _compute_aggregation(toks, cs, head, subj, content_start, content_end, kind):
    """Cue A (framing, clause-scoped) OR cue B (the governing subject is itself a review/meta-analysis/literature
    noun phrase, independent of how its ownership resolved) OR cue C (RESULT-kind content only, an explicit
    synthesis-context word/phrase, never a bare pooled/combined/aggregate word alone) -> LITERATURE_SYNTHESIS.
    Never reads finding_authority, authority_veto, observation_polarity, or any requirement/RoleSpec state."""
    if any(_phrase_at(toks, cs, head, phrase) for phrase in _AGGREGATION_FRAMING_PHRASES):
        return LITERATURE_SYNTHESIS
    if subj["start"] is not None and _match_review_source_np(toks, subj["start"], subj["end"]) == subj["end"]:
        return LITERATURE_SYNTHESIS
    if kind == RESULT and (
        any(_is_word(toks[k], *_SYNTHESIS_CONTEXT_WORDS) for k in range(content_start, content_end))
        or any(_phrase_at(toks, content_start, content_end, phrase) for phrase in _SYNTHESIS_CONTEXT_PHRASES)
    ):
        return LITERATURE_SYNTHESIS
    return NON_SYNTHETIC


def _build(toks, a, obj_start, obj_end, cs):
    head, pred = a["head"], a["pred"]
    pt = toks[pred]
    obj = _object_content(toks, obj_start, obj_end)
    neg = any(_is_word(toks[i], *_NEG) for i in range(head, pred))
    modal_head = any(_is_word(toks[i], *_MODALS) for i in range(head, pred))
    replication = pt.low in _REPLICATION_VERBS
    rules = [f"predicate.{pt.low}"]
    prior_in_object = obj["prior"] is not None or obj["comparison"] is not None
    subj = a["subj"]
    subj_source = subj["source"]
    rules.append(subj["rule"])

    if replication:
        kind = RESULT
        rules.append("predicate.replication")
        if prior_in_object and neg:
            source = PRIOR_WORK
            rules.append("replication.negated_prior_content")
        elif prior_in_object and subj_source == THIS_STUDY:
            source = THIS_STUDY
            rules.append("replication.confirmed_prior_content_owned_by_subject")
        elif prior_in_object:
            source = subj_source if subj_source != THIS_STUDY else UNKNOWN_SOURCE
            rules.append("replication.prior_content_unowned_subject")
        else:
            source = UNKNOWN_SOURCE
            rules.append("replication.unmarked_content")
    else:
        source = subj_source
        if pt.low in _AIM_VERBS:
            kind = AIM
            rules.append("kind.aim_verb")
        elif pt.low in _TEST_VERBS:
            after = toks[pred + 1] if pred + 1 < len(toks) else None
            if after is not None and _is_word(after, "whether", "if"):
                kind = AIM
                rules.append("kind.test_whether_aim_scope")
            else:
                kind = METHOD
                rules.append("kind.test_method")
        elif pt.low in _METHOD_VERBS:
            kind = METHOD
            rules.append("kind.method_verb")
        elif pt.low in _INTERP_VERBS:
            kind = INTERPRETATION
            rules.append("kind.interpretation_verb")
        else:
            kind = RESULT
            rules.append("kind.result_verb")
            if modal_head:
                kind = INTERPRETATION
                rules.append("kind.modal_scope_interpretation")
            elif pt.low in ("predicted", "expected") and obj_start < obj_end and _is_word(toks[obj_start], "that"):
                window = toks[obj_start : min(obj_end, obj_start + 6)]
                if any(_is_word(t, "would", "will") for t in window):
                    kind = AIM
                    rules.append("kind.hypothesis_scope_modal")
        if neg and kind == METHOD:
            kind = UNKNOWN_KIND
            rules.append("negated_method_unknown")
        elif neg and kind == UNKNOWN_KIND:
            rules.append("negated_unknown")
    if source == UNKNOWN_SOURCE and not replication and a["framing"] is None:
        rules.append("source.unowned")
    # I4-1c: the authority veto is a property of the assertion's own structure, independent of source/label resolution.
    # It only ever applies to a result kind -- method/aim/interpretation/caption are already candidate and untouched.
    authority_veto = None
    if kind == RESULT:
        content_start, content_end = obj["content"]
        if neg or _content_negated(toks, content_start, content_end):
            authority_veto = AUTHORITY_VETO_NEGATED
            rules.append(f"veto.{AUTHORITY_VETO_NEGATED}")
        elif _absence_of_evidence(toks, subj, content_start, content_end):
            authority_veto = AUTHORITY_VETO_ABSENCE
            rules.append(f"veto.{AUTHORITY_VETO_ABSENCE}")
    # I4-1f: computed from this assertion's own clause/subject/content alone -- never from source, kind, or the
    # authority veto above, and never from a neighbouring assertion's own clause/subject/content (section 5).
    content_start, content_end = obj["content"]
    aggregation = _compute_aggregation(toks, cs, head, subj, content_start, content_end, kind)
    return {
        "head": head,
        "pred": pred,
        "obj": (obj_start, obj_end),
        "content": obj["content"],
        "prior_object": obj["prior"],
        "comparison": obj["comparison"],
        "subj": subj,
        "framing": a["framing"],
        "source": source,
        "kind": kind,
        "negated": neg,
        "negated_replication": bool(replication and neg),
        "replication": replication,
        "modal_head": modal_head,
        "authority_veto": authority_veto,
        "aggregation": aggregation,
        "rules": rules,
        "framing_prior": (a["framing"] is not None and a["framing"]["source"] == PRIOR_WORK)
        or obj["prior"] is not None
        or obj["comparison"] is not None,
    }


# ---- target attachment ----


def _region(toks, rec):
    """Char span of an assertion: its own subject (when not inherited) through its object end."""
    subj = rec["subj"]
    start = toks[rec["head"]].start
    if subj["start"] is not None and not subj["inherited"]:
        start = min(start, toks[subj["start"]].start)
    obj_start, obj_end = rec["obj"]
    end = toks[obj_end - 1].end if obj_end > obj_start else toks[rec["pred"]].end
    return start, end


def _cite_spans(toks, lo, hi):
    return [[toks[i].start, toks[i].end] for i in range(lo, hi) if toks[i].kind == "cite"]


def _all_assertions(text):
    """(sentence span, token list, assertion records) for every sentence, in text order. A leading run-in label is removed
    from the first sentence before tokenization; only that sentence's first clause run may be label-scoped."""
    label = _detect_run_in_label(text)
    out = []
    for idx, (s, e) in enumerate(_sentence_spans(text)):
        scoped = label is not None and idx == 0
        start = label["remainder_start"] if scoped else s
        if start >= e:
            continue
        toks = _tokenize(text, start, e)
        recs = []
        clauses = []
        cstart = 0
        for i, t in enumerate(toks):
            if _is_punct(t, ";"):
                clauses.append((cstart, i))
                cstart = i + 1
            elif _is_punct(t, ",") and i + 1 < len(toks) and _is_word(toks[i + 1], *_CONTRAST):
                clauses.append((cstart, i))
                cstart = i + 2
        clauses.append((cstart, len(toks)))
        for ci, (cs, ce) in enumerate(clauses):
            if ce > cs:
                recs.extend(
                    _analyze_clause_assertions(
                        toks,
                        cs,
                        ce,
                        label_scope=scoped and ci == 0,
                        label_normalized=label["normalized"] if scoped else None,
                    )
                )
        out.append(((s, e), toks, recs))
    return out


def _span_public(text, toks, a, b):
    """Exact offsets and the verbatim text of token range [a, b)."""
    if a >= b:
        return None
    s, e = toks[a].start, toks[b - 1].end
    return {"span": [s, e], "text": text[s:e]}


def _assertion_public(text, toks, rec):
    head, pred = rec["head"], rec["pred"]
    obj_start, obj_end = rec["obj"]
    region = _region(toks, rec)
    subj = rec["subj"]
    subj_public = None
    if subj["start"] is not None:
        subj_public = {
            **_span_public(text, toks, subj["start"], subj["end"]),
            "source": subj["source"],
            "rule": subj["rule"],
            "inherited": bool(subj["inherited"]),
        }
    return {
        "span": [region[0], region[1]],
        "text": text[region[0] : region[1]],
        "predicate": {**_span_public(text, toks, pred, pred + 1), "lemma": toks[pred].low},
        "head": _span_public(text, toks, head, pred + 1),
        "subject": subj_public,
        "object": _span_public(text, toks, obj_start, obj_end),
        "content": _span_public(text, toks, rec["content"][0], rec["content"][1]),
    }


def _covers(region, ts, te):
    return region[0] <= ts and te <= region[1]


def _content_span(text, ts, te):
    """The target without leading/trailing whitespace and without terminal sentence punctuation. Coverage uses this span;
    the raw target is still reported."""
    while ts < te and text[ts].isspace():
        ts += 1
    while te > ts and (text[te - 1].isspace() or text[te - 1] in _TERMINAL_TRIM):
        te -= 1
    return ts, te


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def durable_locator(paper_id, evidence_anchor_chunk_id, quote_text):
    """The I4-0 durable source tuple composed from existing fields. Evidence IDs are never migrated or trusted alone."""
    return {
        "paper_id": paper_id,
        "evidence_anchor_chunk_id": evidence_anchor_chunk_id,
        "quote_sha256": _sha256(quote_text),
    }


def _resolve_owner_signal(structural_context):
    if structural_context is None:
        return None
    if not isinstance(structural_context, dict):
        raise ValueError("structural_context must be a dict or None")
    signal = structural_context.get("owner_signal")
    if signal is None:
        return None
    if signal not in OWNER_SIGNALS:
        raise ValueError(f"owner_signal must be one of {OWNER_SIGNALS}")
    return signal


def _validate_target(text, target_start, target_end, is_caption, structural_context):
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if not (isinstance(target_start, int) and isinstance(target_end, int)):
        raise TypeError("target_start and target_end must be int")
    if not (0 <= target_start < target_end <= len(text)):
        raise ValueError("target span must satisfy 0 <= start < end <= len(text)")
    if not isinstance(is_caption, bool):
        raise TypeError("is_caption must be bool")
    return _resolve_owner_signal(structural_context)


def _results_veto(rec, toks, text, is_caption):
    """Why the structural Results resolver must NOT apply. None when it may. Under-classification is acceptable."""
    if is_caption:
        return "caption"
    if rec.get("label_normalized") != RESULTS_LABEL:
        return "label_not_results"
    if rec["kind"] != RESULT:
        return "kind_not_result"
    if rec["framing_prior"]:
        return "prior_framing_or_object"
    if rec["replication"]:
        return "replication_act"
    if rec["negated"]:
        return "negated"
    if rec["modal_head"] or any(_is_word(toks[i], *_HEDGE) for i in range(rec["head"], rec["obj"][1])):
        return "hedged_or_modal"
    lo = rec["subj"]["start"] if rec["subj"]["start"] is not None else rec["head"]
    hi = rec["obj"][1]
    if _cite_spans(toks, lo, hi):
        return "citation_in_assertion"
    if any(_is_word(toks[i], "ref", "refs", "cf") for i in range(lo, hi)):
        return "citation_like_marker"
    if any(_is_word(toks[i], "et") and i + 1 < hi and _is_word(toks[i + 1], "al") for i in range(lo, hi)):
        return "citation_like_marker"
    s, e = _region(toks, rec)
    if _YEAR_PAREN.search(text[s:e]):
        return "citation_like_parenthetical"
    return None


def _effective(rec, toks, text, owner_signal, is_caption):
    """The assertion's source after ordinary parsing, the optional caller-verified owner context, and the narrow Results
    resolver. The resolver fires only on unknown source and never overrides an explicit owner."""
    source, kind = rec["source"], rec["kind"]
    rules = list(rec["rules"])
    resolution = PARSED if source != UNKNOWN_SOURCE else UNRESOLVED
    consumed = None
    if source == UNKNOWN_SOURCE and owner_signal is not None and rec["subj"]["source"] == UNKNOWN_SOURCE:
        source = owner_signal
        rules.append("context.owner_supplied")
        resolution = OWNER_CONTEXT
        consumed = {"owner_signal": owner_signal, "applied_to": _region(toks, rec)}
    elif source == UNKNOWN_SOURCE and rec["label_scope"]:
        veto = "owner_signal_supplied" if owner_signal is not None else _results_veto(rec, toks, text, is_caption)
        if veto is None:
            source = THIS_STUDY
            resolution = STRUCTURAL_RESULTS
            rules.append("resolver.structural_results_label")
        else:
            rules.append(f"resolver.vetoed.{veto}")
    return {"source": source, "kind": kind, "resolution": resolution, "rules": rules, "consumed": consumed}


def _assertion_fields(text, toks, rec, eff, is_caption):
    region = _region(toks, rec)
    lo = rec["subj"]["start"] if rec["subj"]["start"] is not None else rec["head"]
    cite = _cite_spans(toks, lo, rec["obj"][1])
    hedged = any(_is_word(toks[i], *_HEDGE) for i in range(rec["head"], rec["obj"][1]))
    framing_public = None
    if rec["framing"] is not None:
        framing_public = {"span": [toks[rec["framing"]["start"]].start, toks[rec["framing"]["end"] - 1].end]}
    elif rec["prior_object"] is not None:
        a, b = rec["prior_object"]
        framing_public = {"span": [toks[a].start, toks[b - 1].end]}
    if rec["comparison"] is not None and framing_public is None:
        c = rec["comparison"][0]
        framing_public = {"span": [toks[c].start, toks[rec["comparison"][1] - 1].end]}
    authority_veto = rec["authority_veto"]
    return {
        "assertion": _assertion_public(text, toks, rec),
        "span": [region[0], region[1]],
        "assertion_source": eff["source"],
        "assertion_kind": eff["kind"],
        "finding_authority": finding_authority(eff["source"], eff["kind"], is_caption, authority_veto),
        "authority_veto": authority_veto,
        "aggregation": rec["aggregation"],
        "source_resolution": eff["resolution"],
        "label_scope": bool(rec["label_scope"]),
        "framing_source": PRIOR_WORK if rec["framing_prior"] else None,
        "framing": framing_public,
        "citation_marked": bool(cite),
        "citation_spans": cite,
        "hedged": hedged,
        "negated": bool(rec["negated"]),
        "negated_replication": bool(rec["negated_replication"]),
        "structural_context_consumed": eff["consumed"],
        "rule": eff["rules"][-1] if eff["rules"] else "none",
        "rules_applied": eff["rules"],
    }


def _input_public(text, ts, te, cts, cte, is_caption, owner_signal, locator, label):
    return {
        "text_length": len(text),
        "text_sha256": _sha256(text),
        "target": {
            "start": ts,
            "end": te,
            "surface": text[ts:te],
            "content": [cts, cte],
            "content_surface": text[cts:cte],
        },
        "is_caption": is_caption,
        "structural_context_supplied": owner_signal is not None,
        "locator": (
            {
                "paper_id": locator["paper_id"],
                "evidence_anchor_chunk_id": locator["evidence_anchor_chunk_id"],
                "quote_sha256": _sha256(text),
            }
            if locator
            else None
        ),
        "run_in_label_surface": label["surface"] if label else None,
        "run_in_label_normalized": label["normalized"] if label else None,
        "run_in_label_span": label["span"] if label else None,
    }


def _classifier_public():
    return {"id": CLASSIFIER_ID, "ruleset": RULESET_VERSION, "pure": True, "unwired": True}


def classify_assertion_authority(
    text,
    *,
    target_start,
    target_end,
    is_caption=False,
    structural_context=None,
    locator=None,
):
    """Classify the single assertion bearing on the explicit target span. Fails closed unless ONE assertion's region covers
    the target's content (terminal punctuation ignored). Multi-assertion targets are represented by
    :func:`classify_target_assertions`, never collapsed here.

    ``structural_context`` may carry ``{"owner_signal": "this_study" | "prior_work"}`` supplied by a caller that has
    ALREADY verified contextual ownership. It is applied only to an unowned governing assertion and is recorded.
    ``locator`` may carry ``{"paper_id", "evidence_anchor_chunk_id"}``; the quote hash is added here.
    """
    owner_signal = _validate_target(text, target_start, target_end, is_caption, structural_context)
    ts, te = _content_span(text, target_start, target_end)
    if te <= ts:
        raise ValueError("target span has no content after trimming whitespace and terminal punctuation")
    label = _detect_run_in_label(text)
    target_sentence = None
    all_recs = []
    for (s, e), toks, recs in _all_assertions(text):
        if s <= ts and te <= e:
            target_sentence = (s, e)
        for rec in recs:
            all_recs.append((toks, rec))

    result = {
        "classifier": _classifier_public(),
        "input": _input_public(text, target_start, target_end, ts, te, is_caption, owner_signal, locator, label),
        "sentence": (
            {"span": [target_sentence[0], target_sentence[1]], "text": text[target_sentence[0] : target_sentence[1]]}
            if target_sentence
            else None
        ),
        "assertion": None,
        "assertions_considered": 0,
        "framing": None,
        "framing_source": None,
        "citation_marked": False,
        "citation_spans": [],
        "hedged": False,
        "negated": False,
        "negated_replication": False,
        "structural_context_consumed": None,
        "source_resolution": None,
        "label_scope": False,
        "authority_veto": None,
        "aggregation": None,
        "rules_applied": [],
        "fail_closed_reasons": [],
        "ambiguity": None,
    }

    covering = [(toks, rec) for toks, rec in all_recs if _covers(_region(toks, rec), ts, te)]
    if not covering:
        overlapping = [
            (toks, rec) for toks, rec in all_recs if _region(toks, rec)[0] < te and ts < _region(toks, rec)[1]
        ]
        if overlapping:
            reason = "target_crosses_assertion_boundary"
        elif target_sentence is not None and any(
            target_sentence[0] <= _region(toks, rec)[0] < target_sentence[1] for toks, rec in all_recs
        ):
            reason = "target_outside_predicate_scope"
        else:
            reason = "no_governing_predicate"
        result.update(
            assertion_source=UNKNOWN_SOURCE,
            assertion_kind=UNKNOWN_KIND,
            finding_authority=finding_authority(UNKNOWN_SOURCE, UNKNOWN_KIND, is_caption),
            ambiguity=reason,
            rule=reason,
        )
        result["fail_closed_reasons"].append(reason)
        return result

    result["assertions_considered"] = len(covering)
    effs = [(toks, rec, _effective(rec, toks, text, owner_signal, is_caption)) for toks, rec in covering]
    # I4-1c: two covering assertions must agree on authority_veto too, not just source/kind -- otherwise silently
    # picking the first could serve an authoritative reading when another equally-covering reading is vetoed.
    # I4-1f: extends the same soundness rule to aggregation, now that it is a property the caller can read from a
    # single-assertion result -- silently picking the first could otherwise report literature_synthesis (or not)
    # from whichever covering reading happened to be first, when another equally-covering reading disagrees.
    signatures = {(eff["source"], eff["kind"], rec["authority_veto"], rec["aggregation"]) for _, rec, eff in effs}
    if len(signatures) > 1:
        result.update(
            assertion_source=UNKNOWN_SOURCE,
            assertion_kind=UNKNOWN_KIND,
            finding_authority=finding_authority(UNKNOWN_SOURCE, UNKNOWN_KIND, is_caption),
            ambiguity="multiple_assertions_disagree",
            rule="multiple_assertions_disagree",
        )
        result["fail_closed_reasons"].append("multiple_assertions_disagree")
        result["rules_applied"] = sorted({r for _, _, eff in effs for r in eff["rules"]})
        return result

    toks, rec, eff = effs[0]
    result.update(_assertion_fields(text, toks, rec, eff, is_caption))
    result["ambiguity"] = None
    region = _region(toks, rec)
    if region[0] > ts or te > region[1]:
        result["fail_closed_reasons"].append("region_mismatch")
    return result


def aggregation(text, *, target_start, target_end, is_caption=False, structural_context=None):
    """Pure. Answers exactly: does the ONE local assertion governing this target span explicitly aggregate or
    synthesize evidence across a literature/study set? Never who owns the assertion (see :func:`assertion_relation`),
    never requirement admissibility, never document genre -- a review/meta-analysis need not itself be held in any
    library for this to return ``LITERATURE_SYNTHESIS``. Fails closed exactly like :func:`classify_assertion_authority`
    when no single assertion governs the target (same ``ValueError``-free ambiguity contract: this wrapper raises
    instead, since a bare string return has nowhere to carry the fail-closed reason)."""
    result = classify_assertion_authority(
        text,
        target_start=target_start,
        target_end=target_end,
        is_caption=is_caption,
        structural_context=structural_context,
    )
    if result["ambiguity"] is not None:
        raise ValueError(f"no single governing assertion for this target: {result['ambiguity']}")
    return result["aggregation"]


def classify_target_assertions(
    text,
    *,
    target_start,
    target_end,
    is_caption=False,
    structural_context=None,
    locator=None,
):
    """Represent every assertion that intersects the target span. Never collapses them to one authority.

    ``target_scope``: ``within_assertion`` (one assertion covers the target), ``partial_assertion`` (one assertion
    intersects but does not cover it), ``multi_assertion`` (two or more intersect), or ``no_governing_assertion``
    (none intersects). Each returned record carries its own classification and ``covers_target``. ``aggregate_authority``
    is always None, so no caller can read a single authority for a broad target from this result.
    """
    owner_signal = _validate_target(text, target_start, target_end, is_caption, structural_context)
    ts, te = _content_span(text, target_start, target_end)
    if te <= ts:
        raise ValueError("target span has no content after trimming whitespace and terminal punctuation")
    label = _detect_run_in_label(text)
    hits = []
    for _, toks, recs in _all_assertions(text):
        for rec in recs:
            rs, re_ = _region(toks, rec)
            if rs < te and ts < re_:
                hits.append((rs, toks, rec, _covers((rs, re_), ts, te)))
    hits.sort(key=lambda h: h[0])
    if not hits:
        scope = "no_governing_assertion"
    elif len(hits) == 1:
        scope = "within_assertion" if hits[0][3] else "partial_assertion"
    else:
        scope = "multi_assertion"
    assertions = []
    for _, toks, rec, covers in hits:
        eff = _effective(rec, toks, text, owner_signal, is_caption)
        assertions.append({**_assertion_fields(text, toks, rec, eff, is_caption), "covers_target": covers})
    return {
        "classifier": _classifier_public(),
        "input": _input_public(text, target_start, target_end, ts, te, is_caption, owner_signal, locator, label),
        "target_scope": scope,
        "assertions": assertions,
        "aggregate_authority": None,
        "ambiguity": None if hits else "no_governing_assertion",
    }


def locate_containing_assertion(
    text,
    target_start,
    target_end,
    *,
    is_caption=False,
    structural_context=None,
    locator=None,
):
    """I4-1j: the deterministic join between a localized span (e.g. one of a sibling result-predicate-
    localizing module's own predicate/content-span hits -- deliberately not named here; see the module-level
    note below) and this classifier's own assertion-level identity. A thin wrapper over
    :func:`classify_target_assertions` -- no new parsing, no new boundary logic; this function exists only to
    give the join a single, fail-closed entry point rather than requiring every caller to re-derive the same
    three-way scope check.

    Resolves iff `classify_target_assertions` reports exactly one intersecting assertion
    (`target_scope in {"within_assertion", "partial_assertion"}`) -- the span may cover that one assertion
    wholly or only partially; either way there is exactly one governing assertion to attribute it to.
    Fails closed, never guesses, on `"no_governing_assertion"` (zero intersecting assertions) and on
    `"multi_assertion"` (two or more) -- the full, unmodified `classify_target_assertions` result is always
    returned as `"diagnostic"`, so a caller that needs to understand WHY a join failed (which assertions were
    even considered) never has to re-run the classifier a second time.

    This is the one join that sibling module's own predicate hits should resolve through to acquire assertion
    identity -- never its own, independently-duplicated, narrower boundary grammar. The two modules stay
    independent (neither imports the other's name, each protected by its own unwired static guard); only a
    caller that already has both results composes them, exactly as this function's own real-sealed-quote
    join test does."""
    result = classify_target_assertions(
        text,
        target_start=target_start,
        target_end=target_end,
        is_caption=is_caption,
        structural_context=structural_context,
        locator=locator,
    )
    scope = result["target_scope"]
    resolved = scope in ("within_assertion", "partial_assertion")
    return {
        "resolved": resolved,
        "assertion": result["assertions"][0] if resolved else None,
        "target_scope": scope,
        "reason": None if resolved else scope,
        "diagnostic": result,
    }


def classify_all_occurrences(text, surface, *, is_caption=False, structural_context=None, locator=None):
    """Every exact occurrence of ``surface``, each classified separately. Never selects a preferred occurrence."""
    spans = []
    i = text.find(surface)
    while surface and i != -1:
        spans.append((i, i + len(surface)))
        i = text.find(surface, i + len(surface))
    return [
        classify_assertion_authority(
            text,
            target_start=a,
            target_end=b,
            is_caption=is_caption,
            structural_context=structural_context,
            locator=locator,
        )
        for a, b in spans
    ]


def classify_surface(text, surface, *, occurrence=None, is_caption=False, structural_context=None, locator=None):
    """Surface-level entry point. A repeated surface without an explicit 1-based ``occurrence`` is reported as ambiguous
    and is never silently resolved to one occurrence."""
    spans = []
    i = text.find(surface) if surface else -1
    while surface and i != -1:
        spans.append((i, i + len(surface)))
        i = text.find(surface, i + len(surface))
    if not spans:
        return {"ambiguity": "surface_not_found", "occurrence_count": 0, "results": None}
    if occurrence is None:
        if len(spans) > 1:
            return {
                "ambiguity": "repeated_target_occurrence",
                "occurrence_count": len(spans),
                "occurrence_spans": [list(s) for s in spans],
                "results": None,
            }
        occurrence = 1
    if not (isinstance(occurrence, int) and 1 <= occurrence <= len(spans)):
        raise ValueError("occurrence must be a 1-based index within the occurrences of the surface")
    a, b = spans[occurrence - 1]
    res = classify_assertion_authority(
        text,
        target_start=a,
        target_end=b,
        is_caption=is_caption,
        structural_context=structural_context,
        locator=locator,
    )
    return {"ambiguity": None, "occurrence_count": len(spans), "results": res}
