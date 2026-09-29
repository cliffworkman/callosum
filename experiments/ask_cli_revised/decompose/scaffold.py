"""Deterministic scaffolds: a grammatical standalone request built from the fragment's own source words, the approved joining word and the
parent's recorded relationship, so the writer is handed a sentence instead of being asked to compose one.

Two small templates, each keyed on recorded STRUCTURE (pairs, the approved link, the parent's obligation kinds and parsed slots), never on a child
id or a request. A template that does not fit stays silent; a template that fits but cannot be completed safely reports exactly why, and the
fragment then goes to the writer with its carried context and needs the researcher's approval.

* ``which_noun_approved_verb_carried_relative``: a fragment "<prep/gerund> which <plural noun>?" continuing a parsed relationship
  "<subject> <relation> <target>" (subject = the approved antecedent), with an approved joining verb ->
  "which <plural noun> <verb> the <subject> that <relation> <target>?".
* ``in_which_population_evidence_manner_each``: a fragment "which <plural noun> and how <was/were> <subject> <verb>?" continuing an existence
  question "is there [any] [modifier] evidence for <Y>" ->
  "in which <plural noun> is there evidence for <Y>, and how <was/were> <subject> <participle> in each?".

Every piece records where its words came from: ``source`` (a source span), ``approved_joining_word`` (the researcher's, no source span),
``reference_resolution`` (an approved clarification), ``inflection`` (a rule on a source word), or ``rule`` (a grammatical word supplied by a
named rule, no source span). Anything the engine had to infer (rather than take from a source span or an approved clarification) is listed under
``pending`` and needs the researcher's confirmation. Nothing here calls a model, reads a file or knows a request.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose import prepare

_WORD_H = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")  # a hyphenated compound ("cross-cultural") is one word
T1 = "which_noun_approved_verb_carried_relative"
T2 = "in_which_population_evidence_manner_each"
_MANNER_AUX = ("was", "were")
_EXISTENCE_HEAD = ("is", "are")
_EVIDENCE_NOUNS = ("evidence",)


def _overlap(a, b) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def _source(q: str, lo: int, hi: int) -> dict:
    return {"text": q[lo:hi], "origin": "source", "span": [lo, hi]}


def _source_stripped(q: str, lo: int, hi: int) -> dict | None:
    seg = q[lo:hi]
    text = seg.strip()
    if not text:
        return None
    off = lo + (len(seg) - len(seg.lstrip()))
    return _source(q, off, off + len(text))


def _rule(text: str, rule: str, *, attach: bool = False) -> dict:
    return {"text": text, "origin": "rule", "rule": rule, "span": None, **({"attach": True} if attach else {})}


def _join_text(pieces: list[dict]) -> str:
    out = ""
    for p in pieces:
        out += p["text"] if (not out or p.get("attach")) else " " + p["text"]
    return out


def _span_pieces(q: str, parent: dict, lo: int, hi: int) -> tuple[list[dict], list[dict]]:
    """Source words in [lo, hi) with each approved reference replaced by its antecedent (one piece per replacement)."""
    ops, unsafe = prepare._ops_for_references(q, parent, [(lo, hi)])
    pieces, at = [], lo
    for a, b, rep, edit in sorted(ops, key=lambda o: o[0]):
        head = _source_stripped(q, at, a)
        if head:
            pieces.append(head)
        pieces.append(
            {
                "text": rep,
                "origin": "reference_resolution",
                "clarification": edit["clarification"],
                "replaces": edit["replaces"],
                "from_source": edit["from_source"],
                "supplied": edit["supplied"],
                "span": None,
            }
        )
        at = b
    tail = _source_stripped(q, at, hi)
    if tail:
        pieces.append(tail)
    return pieces, unsafe


def _dropped(q: str, entries: list[dict], keep: list[list[int]]) -> list[dict]:
    """Source words of the fragment's own extract that the scaffold does not use (recorded, never silent)."""
    out = []
    for e in entries:
        for a, b in e.get("spans") or [e["span"]]:
            for m in _WORD_H.finditer(q[a:b]):
                lo, hi = m.start() + a, m.end() + a
                if not any(k[0] <= lo and hi <= k[1] for k in keep):
                    out.append({"text": m.group(0), "span": [lo, hi]})
    return out


def _terminal(q: str, entries: list[dict], edits: list[dict]) -> dict | None:
    last = max(entries, key=lambda e: (e.get("spans") or [e["span"]])[-1][1])
    end = (last.get("spans") or [last["span"]])[-1][1]
    if q[end - 1] in ".?!":
        return {**_source(q, end - 1, end), "attach": True}
    for e in edits:
        if e["op"] == "terminal_punctuation":
            s = e["from_source"][0]
            return {**_source(q, s["span"][0], s["span"][1]), "attach": True}
    return None


def _result(template: str, pieces: list[dict], dropped: list[dict], pending: list[dict], limits: list[str]) -> dict:
    return {
        "built": True,
        "template": template,
        "text": _join_text(pieces),
        "pieces": pieces,
        "dropped_source_words": dropped,
        "pending": pending,
        "limits": limits,
    }


# ---- template 1 --------------------------------------------------------------------------------------------------------------------------------
def _t1(parent, plans, clar, ant, state, own_stems):
    q = parent["original_question"]
    pairs = clar.get("pairs") or []
    if len(pairs) != 2:
        return None, []
    a_member = next((m for m in pairs if _overlap(m["span"], ant["span"])), None)
    b_member = next((m for m in pairs if m is not a_member), None)
    if a_member is None or b_member is None:
        return None, []
    b_tokens = lx.tokens(b_member["text"])
    if (
        len(b_tokens) < 2
        or b_tokens[0] not in ("which", "what")
        or lx.missing_stems(lx.content_stems(b_member["text"]), own_stems)
    ):
        return None, []  # not this template's shape: stay silent

    def no(reason):
        return None, [{"template": T1, "reason": reason}]

    join = state["join"]
    if not join:
        return no(
            "no researcher-approved joining word is recorded for this fragment, so the verb linking the scales to the carried words is not approved"
        )
    if not b_tokens[-1].endswith("s"):
        return no(
            f"the asked noun {b_member['text']!r} does not look plural, so agreement with the approved joining word {join['text']!r} cannot be derived"
        )
    rc = next(
        (
            p["relation"]
            for p in plans
            if p.get("relation")
            and p["relation"].get("parse_status") == "parsed"
            and [list(s) for s in p["relation"]["subject"]["spans"]] == [list(ant["span"])]
        ),
        None,
    )
    if rc is None:
        return no(
            "the parent's relationship whose subject is the approved antecedent is not parsed, so the carried relation is not derivable (the writer would have to compose it)"
        )
    if rc["polarity"]["requested"] or rc["manner"]["requested"]:
        return no("the parent's relationship itself asks whether/how, which cannot be carried as a relative clause")
    rel, tgt = rc["relation"]["spans"], rc["target"]["spans"]
    if len(rel) != 1 or len(tgt) != 1 or q[ant["span"][1] : rel[0][0]].strip():
        return no(
            "the parent's subject, relation and target are not contiguous single spans, so no relative clause can be derived from them"
        )
    frame = f"{b_member['text']} {join['text']} the".lower()
    the_verbatim = frame in (clar.get("means") or "").lower()
    target_pieces, unsafe = _span_pieces(q, parent, tgt[0][0], tgt[0][1])
    if unsafe:
        return no(
            "a reference inside the carried target could not be resolved safely: "
            + "; ".join(u["reason"] for u in unsafe)
        )
    pieces = [
        _source(q, *b_member["span"]),
        {
            "text": join["text"],
            "origin": "approved_joining_word",
            "clarification": join["clarification"],
            "decision": join.get("decision"),
            "approved_by": join.get("approved_by"),
            "span": None,
        },
        {
            **_rule("the", "definite_article_for_the_carried_referent"),
            "basis": "verbatim in the approved meaning" if the_verbatim else "a grammatical article",
        },
        _source(q, *ant["span"]),
        _rule("that", "relative_pronoun_joining_the_carried_relation"),
        _source(q, rel[0][0], rel[0][1]),
        *target_pieces,
    ]
    term = _terminal(q, state["entries"], state["edits"])
    if term:
        pieces.append(term)
    keep = [b_member["span"]] + ([[term["span"][0], term["span"][1]]] if term else [])
    dropped = [
        {**d, "why": "replaced by the approved joining word and the carried relationship"}
        for d in _dropped(q, state["entries"], keep)
    ]
    limits = [
        "the verb agreement (plural noun + the approved base-form word) is taken from the researcher's own approved wording, not derived",
        "the article 'the' and the relative 'that' are grammatical words supplied by rule; they are not source words",
    ]
    pending = [
        {
            "kind": "fragment_rewritten_as_question",
            "reason": f"the fragment {q[state['entries'][0]['span'][0] : state['entries'][-1]['span'][1]]!r} becomes a full question: its leading words are replaced by the approved joining word and the carried relationship",
        }
    ]
    return _result(T1, pieces, dropped, pending, limits), []


# ---- template 2 --------------------------------------------------------------------------------------------------------------------------------
def _existence_shape(q: str, span: list[int]) -> dict | None:
    """Tokens of "is there [any] [modifier...] evidence for <Y>" with absolute spans, or None."""
    toks = [(m.group(0), m.start() + span[0], m.end() + span[0]) for m in _WORD_H.finditer(q[span[0] : span[1]])]
    words = [t[0].lower() for t in toks]
    if len(words) < 5 or words[0] not in _EXISTENCE_HEAD or words[1] != "there":
        return None
    i = 2
    dropped = []
    if words[i] == "any":
        dropped.append(toks[i])
        i += 1
    mods = []
    while i < len(words) and words[i] not in _EVIDENCE_NOUNS and len(mods) < 3:
        mods.append(toks[i])
        i += 1
    if (
        i >= len(words)
        or words[i] not in _EVIDENCE_NOUNS
        or i + 1 >= len(words)
        or words[i + 1] != "for"
        or i + 2 >= len(words)
    ):
        return None
    return {
        "lead": (toks[0], toks[1]),
        "dropped": dropped + mods,
        "evidence": toks[i],
        "for": toks[i + 1],
        "y": (toks[i + 2][1], span[1]),
    }


def _t2(parent, plans, by_id, clar, ant, state, own_stems):
    q = parent["original_question"]
    pairs = clar.get("pairs") or []
    if len(pairs) != 2:
        return None, []
    p_member = next((m for m in pairs if lx.tokens(m["text"])[:1] == ["which"]), None)
    m_member = next((m for m in pairs if lx.tokens(m["text"])[:1] == ["how"]), None)
    if (
        p_member is None
        or m_member is None
        or lx.missing_stems(lx.content_stems(p_member["text"] + " " + m_member["text"]), own_stems)
    ):
        return None, []  # not this template's shape: stay silent

    def no(reason):
        return None, [{"template": T2, "reason": reason}]

    existence = next(
        (
            r
            for r in by_id.values()
            if r["kind"] == "existence"
            and not r.get("superseded")
            and any(_overlap(s, ant["span"]) for s in r["spans"])
        ),
        None,
    )
    if existence is None or len(existence["spans"]) != 1:
        return no(
            "the continued question is not a single existence question ('is there ... evidence for ...'), so the 'in which ... is there evidence for ...' form does not apply"
        )
    shape = _existence_shape(q, existence["spans"][0])
    if shape is None:
        return no(
            "the continued existence question does not have the form 'is there [any] [modifier] evidence for <topic>'"
        )
    m_tokens = [
        (m.group(0), m.start() + m_member["span"][0], m.end() + m_member["span"][0])
        for m in prepare._WORD.finditer(q[m_member["span"][0] : m_member["span"][1]])
    ]
    if len(m_tokens) < 4 or m_tokens[1][0].lower() not in _MANNER_AUX:
        return no(
            "the manner part is not of the form 'how was/were <subject> <verb>', so it cannot be carried as the second clause"
        )
    verb = m_tokens[-1]
    fix = next(
        (
            e
            for e in state["edits"]
            if e["op"] == "inflection_corrected" and e["replaces"]["source_span"] == [verb[1], verb[2]]
        ),
        None,
    )
    if not fix and not verb[0].lower().endswith("ed"):
        return no(
            f"the manner clause's last word {verb[0]!r} is not a past participle and no recorded correction applies"
        )
    pending = []
    # the topic Y: the continued question's own words, unless an approved reference in this fragment names the same thing
    y_lo, y_hi = shape["y"]
    y_pieces, unsafe = _span_pieces(q, parent, y_lo, y_hi)
    if unsafe:
        return no(
            "a reference inside the continued question's topic could not be resolved safely: "
            + "; ".join(u["reason"] for u in unsafe)
        )
    y_tokens = [m.group(0).lower() for m in prepare._WORD.finditer(q[y_lo:y_hi])]
    subject = [t for t in m_tokens[2:-1]]
    subj_lo, subj_hi = subject[0][1], subject[-1][2]
    subj_ref = next(
        (
            e
            for e in state["edits"]
            if e["op"] == "reference_resolved"
            and subj_lo <= e["replaces"]["source_span"][0]
            and e["replaces"]["source_span"][1] <= subj_hi
        ),
        None,
    )
    subj_pieces, _ = _span_pieces(q, parent, subj_lo, subj_hi)
    if subj_ref and not any(p["origin"] == "reference_resolution" for p in y_pieces):
        referent = subj_ref["result"]
        if (
            y_tokens
            and referent.split()
            and y_tokens[-1] == referent.split()[-1].lower()
            and referent.lower() != q[y_lo:y_hi].lower()
        ):
            y_pieces = [
                {
                    "text": referent,
                    "origin": "inferred_reference",
                    "based_on": subj_ref["clarification"],
                    "replaces": {"text": q[y_lo:y_hi], "source_span": [y_lo, y_hi]},
                    "span": None,
                }
            ]
            pending.append(
                {
                    "kind": "inferred_reference",
                    "reason": f"the continued question's {q[y_lo:y_hi]!r} is replaced by {referent!r} because it shares its head noun with the approved referent of {subj_ref['replaces']['text']!r} ({subj_ref['clarification']}); no approved clarification covers {q[y_lo:y_hi]!r} itself",
                }
            )
    pieces = [
        _rule("in", "preposition_carrying_the_asked_population_into_the_existence_clause"),
        _source(q, *p_member["span"]),
        _source(q, shape["lead"][0][1], shape["lead"][1][2]),
        _source(q, shape["evidence"][1], shape["for"][2]),
        *y_pieces,
        _rule(",", "comma_between_the_two_clauses", attach=True),
    ]
    between = _source_stripped(q, p_member["span"][1], m_member["span"][0])
    if between and lx.tokens(between["text"]) == ["and"]:
        pieces.append(between)
    else:
        return no(
            "the two paired parts are not joined by 'and' in the fragment, so the second clause cannot be attached"
        )
    pieces += [_source(q, m_tokens[0][1], m_tokens[1][2]), *subj_pieces]
    if fix:
        pieces.append(
            {
                "text": fix["result"],
                "origin": "inflection",
                "rule": fix["rule"],
                "inflection_of": fix["replaces"],
                "span": None,
            }
        )
    else:
        pieces.append(_source(q, verb[1], verb[2]))
    pieces.append(_rule("in each", "each_value_paired_with_its_counterpart"))
    term = _terminal(q, state["entries"], state["edits"])
    if term:
        pieces.append(term)
    dropped = [
        {
            "text": t[0],
            "span": [t[1], t[2]],
            "why": "the asked population ('which ...') now carries the scope this word expressed",
        }
        for t in shape["dropped"]
    ]
    own_used = [p_member["span"], between["span"], m_member["span"]] + ([term["span"]] if term else [])
    dropped += [{**d, "why": "not used by the scaffold"} for d in _dropped(q, state["entries"], own_used)]
    pending.append(
        {
            "kind": "scope_words_dropped_and_supplied",
            "reason": "the continued question's modifier(s) "
            + ", ".join(repr(t[0]) for t in shape["dropped"])
            + " are left out because 'which ...' now asks that dimension, and 'in each' is supplied to keep each value with its counterpart (the approved pairing); both need the researcher's confirmation",
        }
    )
    limits = [
        "the words 'in', ',' and 'in each' are supplied by rule, not taken from source spans",
        "the request restates the topic in both clauses instead of using a pronoun, so no reference is left for the reader to resolve",
    ]
    return _result(T2, pieces, dropped, pending, limits), []


def build(parent: dict, plan: dict, plans: list[dict], by_id: dict, ctx: dict, state: dict) -> dict | None:
    """The scaffold for a clarified fragment, or None when the child is not a fragment. ``state`` carries the preparation so far
    (``entries``, ``edits``, ``join``, ``own_text``)."""
    frag = plan.get("clarified_fragment")
    if not frag:
        return None
    clar = next((c for c in parent["clarifications"] if c["id"] == frag), None)
    ant = (clar or {}).get("refers_to")
    if not (clar and ant):
        return None
    own_stems = lx.content_stems(state["own_text"])
    reasons: list[dict] = []
    for build_one in (
        lambda: _t1(parent, plans, clar, ant, state, own_stems),
        lambda: _t2(parent, plans, by_id, clar, ant, state, own_stems),
    ):
        got, why = build_one()
        if got:
            return got
        reasons += why
    return {
        "built": False,
        "not_built": reasons
        or [
            {
                "template": None,
                "reason": "no scaffold template fits this fragment's recorded pairing shape; the writer composes the request and the wording needs the researcher's approval",
            }
        ],
    }
