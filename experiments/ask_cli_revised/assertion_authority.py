"""PHASE 34 I4-1 pure assertion-source / assertion-kind classifier. UNWIRED: no production caller may import this module.

It answers, for the assertion that BEARS ON A SUPPLIED TARGET SPAN:

* ``assertion_source``: whose evidentiary assertion is it (``this_study`` / ``prior_work`` / ``unknown``)?
* ``assertion_kind``: what kind of assertion is it (``result`` / ``method_or_description`` /
  ``aim_or_hypothesis`` / ``interpretation`` / ``unknown``)?
* ``is_caption``: a structural input, never a source.
* audit flags: ``framing_source``, ``citation_marked``, ``hedged``, ``negated``, ``negated_replication``.

``finding_authority`` is derived by ONE central function (:func:`finding_authority`). Nothing here decides observation
polarity, role completion, recovery, relation witnessing, direction, or AnswerPlan placement.

Pure: no I/O, no model, no network, no current-version lookup. Deterministic. Output is JSON-safe. Ownership is fail-closed:
a source the sealed text does not establish is ``unknown``. Lexical cues are a closed set of verbs, determiners,
prior-source nouns, and first-person or study-noun owner forms. No participant or population noun list is used.
"""

from __future__ import annotations

import hashlib
import re
from collections import namedtuple

CLASSIFIER_ID = "i4-1-assertion-authority"
RULESET_VERSION = "i4-1.0"

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
SOURCES = (THIS_STUDY, PRIOR_WORK, UNKNOWN_SOURCE)
KINDS = (RESULT, METHOD, AIM, INTERPRETATION, UNKNOWN_KIND)
OWNER_SIGNALS = (THIS_STUDY, PRIOR_WORK)


def finding_authority(assertion_source, assertion_kind, is_caption=False):
    """The one central authority function. Semantic only: no polarity, no completion, no confidence."""
    if assertion_source not in SOURCES:
        raise ValueError(f"unknown assertion_source: {assertion_source!r}")
    if assertion_kind not in KINDS:
        raise ValueError(f"unknown assertion_kind: {assertion_kind!r}")
    if assertion_source == THIS_STUDY and assertion_kind == RESULT and not is_caption:
        return AUTHORITATIVE
    return CANDIDATE


# ---- closed lexicons (lowercase). Verbs and nouns only; no population or participant nouns. ----

_RESULT_VERBS = frozenset(
    "found find finds detected detect detects observed observe observes showed show shows shown revealed reveal reveals "
    "demonstrated demonstrate demonstrates correlated correlate correlates predicted predict predicts associated associate "
    "differed differ increased increase decreased decrease reduced reduce reduces expressed express described describe "
    "describes reported yielded yield produced produce produces emerged emerge indicated indicate indicates influence "
    "influences influenced implicated implicate implicates improved improve improves affected affect affects".split()
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


# ---- prior-source constructions ----


def _year_group(toks, j, hi):
    if j + 2 < hi and _is_punct(toks[j], "(") and toks[j + 1].kind == "num" and _is_punct(toks[j + 2], ")"):
        return j + 3
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
        return None
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


def _analyze_clause_assertions(toks, cs, ce):
    asserts = _clause_assertions(toks, cs, ce)
    out = []
    for k, a in enumerate(asserts):
        next_boundary = asserts[k + 1]["boundary"] if k + 1 < len(asserts) else None
        obj_start, obj_end = _object_bounds(toks, a, next_boundary, ce)
        out.append(_build(toks, a, obj_start, obj_end))
    return out


def _build(toks, a, obj_start, obj_end):
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
        "rules": rules,
        "framing_prior": (a["framing"] is not None and a["framing"]["source"] == PRIOR_WORK)
        or obj["prior"] is not None
        or obj["comparison"] is not None,
    }


# ---- target attachment ----


def _region(toks, rec):
    start = toks[rec["head"]].start
    obj_start, obj_end = rec["obj"]
    end = toks[obj_end - 1].end if obj_end > obj_start else toks[rec["pred"]].end
    return start, end


def _cite_spans(toks, lo, hi):
    return [[toks[i].start, toks[i].end] for i in range(lo, hi) if toks[i].kind == "cite"]


def _all_assertions(text):
    """(sentence span, token list, assertion records) for every sentence, in text order."""
    out = []
    for s, e in _sentence_spans(text):
        toks = _tokenize(text, s, e)
        recs = []
        clauses = []
        start = 0
        for i, t in enumerate(toks):
            if _is_punct(t, ";"):
                clauses.append((start, i))
                start = i + 1
            elif _is_punct(t, ",") and i + 1 < len(toks) and _is_word(toks[i + 1], *_CONTRAST):
                clauses.append((start, i))
                start = i + 2
        clauses.append((start, len(toks)))
        for cs, ce in clauses:
            if ce > cs:
                recs.extend(_analyze_clause_assertions(toks, cs, ce))
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


def classify_assertion_authority(
    text,
    *,
    target_start,
    target_end,
    is_caption=False,
    structural_context=None,
    locator=None,
):
    """Classify the assertion bearing on the explicit target span ``text[target_start:target_end]``.

    ``structural_context`` may carry ``{"owner_signal": "this_study" | "prior_work"}`` supplied by a caller that has
    ALREADY verified contextual ownership. It is applied only to an unowned governing assertion and is recorded.
    ``locator`` may carry ``{"paper_id", "evidence_anchor_chunk_id"}``; the quote hash is added here.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if not (isinstance(target_start, int) and isinstance(target_end, int)):
        raise TypeError("target_start and target_end must be int")
    if not (0 <= target_start < target_end <= len(text)):
        raise ValueError("target span must satisfy 0 <= start < end <= len(text)")
    if not isinstance(is_caption, bool):
        raise TypeError("is_caption must be bool")
    owner_signal = _resolve_owner_signal(structural_context)
    ts, te = target_start, target_end
    surface = text[ts:te]
    sentences = _all_assertions(text)
    target_sentence = None
    all_recs = []
    for (s, e), toks, recs in sentences:
        if s <= ts and te <= e:
            target_sentence = (s, e)
        for rec in recs:
            all_recs.append((toks, rec))

    result = {
        "classifier": {"id": CLASSIFIER_ID, "ruleset": RULESET_VERSION, "pure": True, "unwired": True},
        "input": {
            "text_length": len(text),
            "text_sha256": _sha256(text),
            "target": {"start": ts, "end": te, "surface": surface},
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
        },
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
    signatures = {(rec["source"], rec["kind"]) for _, rec in covering}
    if len(signatures) > 1:
        result.update(
            assertion_source=UNKNOWN_SOURCE,
            assertion_kind=UNKNOWN_KIND,
            finding_authority=finding_authority(UNKNOWN_SOURCE, UNKNOWN_KIND, is_caption),
            ambiguity="multiple_assertions_disagree",
            rule="multiple_assertions_disagree",
        )
        result["fail_closed_reasons"].append("multiple_assertions_disagree")
        result["rules_applied"] = sorted({r for _, rec in covering for r in rec["rules"]})
        return result

    toks, rec = covering[0]
    source, kind = rec["source"], rec["kind"]
    rules = list(rec["rules"])
    consumed = None
    if source == UNKNOWN_SOURCE and owner_signal is not None and rec["subj"]["source"] == UNKNOWN_SOURCE:
        source = owner_signal
        rules.append("context.owner_supplied")
        consumed = {"owner_signal": owner_signal, "applied_to": _region(toks, rec)}
    authority = finding_authority(source, kind, is_caption)
    region = _region(toks, rec)
    cite = _cite_spans(toks, rec["subj"]["start"] if rec["subj"]["start"] is not None else rec["head"], rec["obj"][1])
    hedged = any(_is_word(toks[i], *_HEDGE) for i in range(rec["head"], rec["obj"][1]))
    framing_source = PRIOR_WORK if rec["framing_prior"] else None
    framing_public = None
    if rec["framing"] is not None:
        framing_public = {"span": [toks[rec["framing"]["start"]].start, toks[rec["framing"]["end"] - 1].end]}
    elif rec["prior_object"] is not None:
        a, b = rec["prior_object"]
        framing_public = {"span": [toks[a].start, toks[b - 1].end]}
    if rec["comparison"] is not None and framing_public is None:
        c = rec["comparison"][0]
        framing_public = {"span": [toks[c].start, toks[rec["comparison"][1] - 1].end]}
    result.update(
        assertion=_assertion_public(text, toks, rec),
        assertion_source=source,
        assertion_kind=kind,
        finding_authority=authority,
        framing_source=framing_source,
        framing=framing_public,
        citation_marked=bool(cite),
        citation_spans=cite,
        hedged=hedged,
        negated=bool(rec["negated"]),
        negated_replication=bool(rec["negated_replication"]),
        structural_context_consumed=consumed,
        rule=rules[-1] if rules else "none",
        rules_applied=rules,
        ambiguity=None,
    )
    if region[0] > ts or te > region[1]:
        result["fail_closed_reasons"].append("region_mismatch")
    return result


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
