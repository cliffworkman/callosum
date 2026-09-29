"""Deterministic preparation of a child's source extract: approved referents, clarification-added cues, an approved lead-in, indispensable
fragment context and terminal punctuation, each prepared BEFORE the writer sees the child and each recorded as its own edit.

Principle: prepare what the source and the researcher's approved clarifications already settle; expose what cannot be prepared safely instead of
guessing; keep the writer's remaining job narrow (make the prepared wording independently runnable with the smallest edits). Nothing here calls a
model, reads a file, or knows any request: every rule is keyed on clarification records, source spans, obligation spans and the recorded pairings.

Traceability rules:

* A deterministic edit is recorded APART from the model's later wording (``child["preparation"]`` beside ``child["question"]``); the natural-language
  view always shows exactly what the model returned.
* Words that were in the source cite their source span. Words a clarification supplies (an added cue, an approved lead-in) cite that clarification and
  carry NO source span. A grammatical suffix supplied by a rule cites the rule. No source span is ever invented for words that were not in the source.
* A rule that is not clearly safe is not applied: the referent or context is supplied to the writer explicitly (``not_applied``) with the precise reason.

Every check that follows a written child is unchanged; preparation only decides what the writer is given.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose import requirements as req
from experiments.ask_cli_revised.decompose.ledger import FORM_WORDS, OPERATORS, POLAR_START, WH_WORDS, _applicable
from experiments.ask_cli_revised.request_contract import _sentence_spans

POSSESSIVES = frozenset({"its", "their"})
PRONOUNS = frozenset({"they", "them", "it", "this", "these", "those"})
LEADING_STRIP = (
    WH_WORDS
    | POLAR_START
    | FORM_WORDS
    | {"how", "whether", "if", "kind", "kinds", "type", "types", "sort", "sorts", "of", "there", "please"}
)
CARRY_MAX_CHARS = 300
_WORD = re.compile(r"[A-Za-z0-9]+")
_PASSIVE_AUX = frozenset({"was", "were", "been", "being"})
_OPERATION_STEMS = frozenset(lx.stem(w) for w in FORM_WORDS)


def _article_before(q: str, lo: int) -> tuple[int, int] | None:
    """The source article (the/a/an) directly before ``lo``, as a span, or None."""
    m = re.search(r"(?i)\b(the|a|an)\s+$", q[max(0, lo - 12) : lo])
    if not m:
        return None
    start = max(0, lo - 12) + m.start()
    return (start, start + len(m.group(1)))


def _local(entry: dict, lo: int, hi: int) -> tuple[int, int] | None:
    """The [lo, hi) of an absolute source range inside an extract entry's text (entries may join two source spans)."""
    off = 0
    for a, b in entry.get("spans") or [entry["span"]]:
        if a <= lo and hi <= b:
            return off + (lo - a), off + (hi - a)
        off += b - a
    return None


def _simple_singular_phrase(text: str) -> str | None:
    """None when ``text`` is safe to make possessive with 's; otherwise the reason it is not (a rigid rule would guess)."""
    words = [m.group(0) for m in _WORD.finditer(text)]
    if not words:
        return "the referent has no words"
    if re.search(r"[,;:]", text) or any(w.lower() in ("and", "or", "but") for w in words):
        return "the referent is coordinated or punctuated, so where the 's belongs is unclear"
    last = words[-1]
    if last.lower().endswith("s") and lx.stem(last) != last.lower():
        return "the referent ends in what looks like a plural, so 's versus ' is unclear"
    return None


def _referent_words(q: str, clar: dict) -> tuple[str, list[dict]]:
    """The exact source words a reference points at, with the source article directly before them when there is one."""
    lo, hi = clar["refers_to"]["span"]
    art = _article_before(q, lo)
    start = art[0] if art else lo
    parts = ([{"span": [art[0], art[1]], "text": q[art[0] : art[1]]}] if art else []) + [
        {"span": [lo, hi], "text": q[lo:hi]}
    ]
    return q[start:hi], parts


def _reference_edit(q: str, clar: dict, ref_lo: int, ref_hi: int) -> tuple[dict | None, dict | None]:
    """(edit, not_applied) for ONE clarified reference word at its anchored source span. Exactly one of the two is set."""
    word = q[ref_lo:ref_hi]
    base = {
        "word": word,
        "source_span": [ref_lo, ref_hi],
        "clarification": clar["id"],
        "referent": clar["refers_to"]["text"],
    }
    text, from_source = _referent_words(q, clar)
    lower = word.lower()
    if lower in POSSESSIVES:
        why = _simple_singular_phrase(clar["refers_to"]["text"])
        if why:
            return None, {
                **base,
                "reason": f"possessive '{word}' would need a grammatical adjustment and it is not clearly safe: {why}",
            }
        return (
            {
                "op": "reference_resolved",
                "rule": "possessive_singular_noun_phrase",
                "clarification": clar["id"],
                "replaces": {"text": word, "source_span": [ref_lo, ref_hi]},
                "from_source": from_source,
                "supplied": [
                    {
                        "text": "'s",
                        "by": "rule:possessive_singular_noun_phrase (a grammatical suffix, not source wording)",
                    }
                ],
                "result": text + "'s",
            },
            None,
        )
    if lower.startswith("the ") and len(lower.split()) <= 4:
        return (
            {
                "op": "reference_resolved",
                "rule": "definite_description_replaced_by_approved_referent",
                "clarification": clar["id"],
                "replaces": {"text": word, "source_span": [ref_lo, ref_hi]},
                "from_source": from_source,
                "supplied": [],
                "result": text,
            },
            None,
        )
    if lower in PRONOUNS:
        return (
            {
                "op": "reference_resolved",
                "rule": "pronoun_replaced_by_antecedent",
                "clarification": clar["id"],
                "replaces": {"text": word, "source_span": [ref_lo, ref_hi]},
                "from_source": from_source,
                "supplied": [],
                "result": text,
            },
            None,
        )
    return None, {**base, "reason": f"'{word}' is not a reference shape the preparation handles safely"}


def _ops_for_references(
    q: str, parent: dict, ranges: list[tuple[int, int]]
) -> tuple[list[tuple[int, int, str, dict]], list[dict]]:
    """Reference replacements for every approved reference clarification whose target word lies inside one of ``ranges``."""
    ops, unsafe = [], []
    for c in parent.get("clarifications", []):
        if c["kind"] != "reference" or not c.get("refers_to"):
            continue
        a, b = c["target_span"]
        if not any(lo <= a and b <= hi for lo, hi in ranges) or q[a:b].lower() != c["target_text"].lower():
            continue
        edit, not_applied = _reference_edit(q, c, a, b)
        if edit:
            ops.append((a, b, edit["result"], edit))
        else:
            unsafe.append(not_applied)
    return ops, unsafe


def _apply(text_ops: list[tuple[int, int, str]], text: str) -> str:
    """Apply (lo, hi, replacement) operations to ``text`` from the right; at one position a replacement is applied before an insertion."""
    for lo, hi, rep in sorted(text_ops, key=lambda o: (-o[0], 0 if o[1] > o[0] else 1)):
        text = text[:lo] + rep + text[hi:]
    return text


def _cue_edits(parent: dict, plan: dict, applicable: list[dict], q: str) -> tuple[list, list[dict]]:
    """Clarification-added obligations (``adds``), placed from the relationship contract. Returns ([(abs_pos, text, edit)], not_applied).

    A cue the source already states is never added. The added words are the researcher's (cited to the clarification), never source words."""
    rc = plan.get("relation")
    found, unsafe = [], []
    for c in applicable:
        for cue in c.get("adds", []):
            word = "how" if cue == "manner" else "whether"
            info = {"cue": word, "clarification": c["id"]}
            if not rc or rc.get("parse_status") != "parsed":
                unsafe.append(
                    {
                        **info,
                        "reason": f"the relationship this added '{word}' belongs to is not parsed, so where it goes is not known",
                    }
                )
                continue
            key = "manner" if cue == "manner" else "polarity"
            if rc[key]["spans"] or rc[key].get("basis") != "clarification":
                continue  # the source already says it (or this clarification does not supply it here)
            pol, man = rc["polarity"], rc["manner"]
            subject_lo = rc["subject"]["spans"][0][0]
            plain_whether = bool(pol["spans"]) and (pol.get("text") or "").lower() in ("whether", "if")
            if cue == "manner" and plain_whether:
                pos, text, anchor = (
                    pol["spans"][0][1],
                    " and how",
                    {"inserted_after_source_span": list(pol["spans"][0])},
                )
            elif cue == "manner" and not pol["requested"]:
                pos, text, anchor = subject_lo, "how ", {"inserted_before_source_span": list(rc["subject"]["spans"][0])}
            elif cue == "polarity" and man["spans"]:
                pos, text, anchor = (
                    man["spans"][0][0],
                    "whether and ",
                    {"inserted_before_source_span": list(man["spans"][0])},
                )
            elif cue == "polarity" and not man["requested"]:
                pos, text, anchor = (
                    subject_lo,
                    "whether ",
                    {"inserted_before_source_span": list(rc["subject"]["spans"][0])},
                )
            else:
                unsafe.append(
                    {
                        **info,
                        "reason": f"where the added '{word}' joins the source's own polarity/manner words is not clearly safe",
                    }
                )
                continue
            found.append(
                (
                    pos,
                    text,
                    {
                        "op": "cue_added",
                        "rule": f"clarification_adds_{cue}",
                        "clarification": c["id"],
                        "replaces": None,
                        "at_source_pos": pos,
                        **anchor,
                        "anchor_text": q[next(iter(anchor.values()))[0] : next(iter(anchor.values()))[1]],
                        "from_source": [],
                        "supplied": [
                            {"text": text.strip(), "by": f"{c['id']} adds {cue} (approved; not in the source words)"}
                        ],
                        "result": text,
                    },
                )
            )
    return found, unsafe


def _carry(
    parent: dict, plan: dict, plans: list[dict], by_id: dict, ctx: dict, own_text: str, applicable: list[dict]
) -> tuple[dict | None, list[dict], dict | None]:
    """The indispensable parent context for a fragment, prepared WITHOUT requiring the owner's relationship to have parsed.

    A fragment needs its context carried only when a recorded pairing member that IS the clarified antecedent is missing from its own words. The
    context is the source words of the owner's obligations that contain that antecedent, minus the leading question words, with the owner's approved
    references resolved. Returns (carry, not_prepared, join)."""
    q = parent["original_question"]
    frag = plan.get("clarified_fragment")
    if not (frag and ctx["inherited_extracts"]):
        return None, [], None
    clar = next((c for c in parent["clarifications"] if c["id"] == frag), None)
    ant = (clar or {}).get("refers_to")
    if not (clar and ant):
        return (
            None,
            [{"kind": "fragment_context", "reason": "the clarification of this fragment names no antecedent"}],
            None,
        )
    join = None
    link = clar.get("context_link")
    if link and link.get("authority") == req.APPROVED:
        join = {
            "text": link["text"],
            "clarification": clar["id"],
            "decision": link.get("decision"),
            "approved_by": link.get("approved_by"),
        }
    own_stems = lx.content_stems(own_text)
    absent = [
        m["text"]
        for m in clar.get("pairs") or []
        if max(m["span"][0], ant["span"][0]) < min(m["span"][1], ant["span"][1])
        and lx.missing_stems(lx.content_stems(m["text"]), own_stems)
    ]
    if not absent:
        return (
            None,
            [],
            join,
        )  # every recorded pair member is in the fragment's own words: the owner's words stay context only
    owner = ctx["inherited_extracts"][0]
    owner_plan = next((p for p in plans if p["child_id"] == owner["from_node"]), None)
    if owner_plan is None:
        return (
            None,
            [{"kind": "fragment_context", "reason": f"the continued question {owner['from_node']} is not in the plan"}],
            join,
        )
    # the source words of EVERY parent obligation that overlaps the approved antecedent, in the antecedent's own sentence; nothing here needs a
    # parsed relationship (an unparsed one is still an obligation with exact source spans)
    kinds = ("requested_item", "relationship", "existence", "qualifier")
    a_lo, a_hi = ant["span"]
    sentence = _sentence_of(q, a_lo)
    hit = [
        tuple(s)
        for r in by_id.values()
        if r["kind"] in kinds and not r.get("superseded") and r.get("origin") != "source_unit_floor"
        for s in r["spans"]
        if max(s[0], a_lo) < min(s[1], a_hi) and _sentence_of(q, s[0]) == sentence == _sentence_of(q, s[1] - 1)
    ]
    if not hit:
        return (
            None,
            [
                {
                    "kind": "fragment_context",
                    "reason": f"the approved antecedent {ant['text']!r} is inside no recorded obligation of its sentence",
                }
            ],
            join,
        )
    hull = [min(s[0] for s in hit), max(s[1] for s in hit)]
    hull = [min(hull[0], ant["span"][0]), max(hull[1], ant["span"][1])]
    toks = [(m.group(0).lower(), m.start() + hull[0], m.end() + hull[0]) for m in _WORD.finditer(q[hull[0] : hull[1]])]
    while toks and toks[0][0] in LEADING_STRIP:
        toks = toks[1:]
    if not toks:
        return (
            None,
            [
                {
                    "kind": "fragment_context",
                    "reason": "nothing remains of the owner's obligation after its question words are removed",
                }
            ],
            join,
        )
    lo, hi = toks[0][1], hull[1]
    if hi - lo > CARRY_MAX_CHARS or _sentence_of(q, lo) != _sentence_of(q, hi - 1):
        return (
            None,
            [
                {
                    "kind": "fragment_context",
                    "reason": "the owner's context is too long or crosses a sentence, so it is not prepared",
                }
            ],
            join,
        )
    ops, unsafe = _ops_for_references(q, parent, [(lo, hi)])
    text = _apply([(a - lo, b - lo, rep) for a, b, rep, _ in ops], q[lo:hi])
    edits = [e for *_, e in ops]
    covered = [
        pl["relation"]
        for pl in plans
        if pl.get("relation") and any(max(x[0], lo) < min(x[1], hi) for x in pl["relation"].get("source_spans", []))
    ]
    return (
        {
            "text": text,
            "source_spans": [[lo, hi]],
            "from_node": owner["from_node"],
            "clarification": clar["id"],
            "why": f"the recorded pairing needs {', '.join(repr(m) for m in absent)}, which the fragment's own words lack",
            "relationship_parsed": bool(covered) and all(r.get("parse_status") == "parsed" for r in covered),
            "subject_words": covered[0]["subject"]["text"]
            if len(covered) == 1 and covered[0].get("parse_status") == "parsed"
            else None,
            "relation_words": covered[0]["relation"]["text"]
            if len(covered) == 1 and covered[0].get("parse_status") == "parsed"
            else None,
            "relationship_note": "the carried words are the exact source words of the recorded obligations; a relationship parser is not needed to carry them",
            "edits": edits,
            "not_applied_references": unsafe,
            "note": "context only: carried so the request runs on its own; it is NOT a question to ask again",
        },
        [],
        join,
    )


_WH_LEAD = WH_WORDS | {"how"}
_BASE_VERBS = frozenset(w for w in FORM_WORDS if not w.endswith(("ed", "s")))
_PLURAL_DETERMINERS = frozenset(
    "the a an these those its their our some many several all other various different both two three".split()
)


def _participle(word: str) -> str | None:
    """The regular past participle of a source word that is a third-person -s form of a known operation verb, else None."""
    low = word.lower()
    if not low.endswith("s") or low.endswith(("ss", "us", "is", "as", "os")):
        return None
    base = low[:-3] + "y" if low.endswith("ies") else low[:-1]
    if base not in _BASE_VERBS:
        return None
    if base.endswith("y") and len(base) > 1 and base[-2] not in "aeiou":
        return base[:-1] + "ied"
    return base + ("d" if base.endswith("e") else "ed")


def _inflection_edits(q: str, entries: list[dict]) -> list[dict]:
    """A wh-passive question whose LAST word is a present-tense -s form of a known operation verb ("how was <subject> measures?") has a clear
    inflection error: the past participle is the only sensible reading. Corrected as a recorded edit of that one source word, never a new word.
    Deliberately narrow: a wh-word directly before the passive auxiliary, at least one subject word between it and the verb, the verb ends the
    source span, and the word before it is not a plural determiner (so 'how were these measures?' is left alone)."""
    out = []
    for e in entries:
        for a, b in e.get("spans") or [e["span"]]:
            toks = [(m.group(0), m.start() + a, m.end() + a) for m in _WORD.finditer(q[a:b])]
            for i, (w, _lo, _hi) in enumerate(toks):
                if w.lower() not in _PASSIVE_AUX or i == 0 or toks[i - 1][0].lower() not in _WH_LEAD:
                    continue
                j = len(toks) - 1
                if j < i + 2 or toks[j - 1][0].lower() in _PLURAL_DETERMINERS:
                    continue
                word, lo, hi = toks[j]
                new = _participle(word)
                if new is None:
                    continue
                out.append(
                    {
                        "op": "inflection_corrected",
                        "rule": "past_participle_after_wh_passive_auxiliary",
                        "clarification": None,
                        "replaces": {"text": word, "source_span": [lo, hi]},
                        "from_source": [],
                        "supplied": [
                            {
                                "text": new,
                                "by": "rule:past_participle_after_wh_passive_auxiliary (an inflection of the source word, no new word)",
                            }
                        ],
                        "inflection_of": {"text": word, "source_span": [lo, hi]},
                        "result": new,
                    }
                )
    return out


def _grammar_notes(text: str) -> list[dict]:
    """A present-tense -s form of an operation verb shortly after a passive auxiliary ("how was <subject> measures") is probably an
    inflection typo for the past participle. Only the note is prepared: the writer may correct THAT word's inflection, nothing else."""
    words = [m.group(0) for m in _WORD.finditer(text)]
    out = []
    for i, w in enumerate(words):
        if w.lower() not in _PASSIVE_AUX:
            continue
        for t in words[i + 1 : i + 6]:
            if (
                t.lower().endswith("s")
                and not t.lower().endswith(("ss", "us", "is", "as", "os"))
                and lx.stem(t) in _OPERATION_STEMS
            ):
                out.append(
                    {
                        "word": t,
                        "after": w,
                        "note": f"'{t}' after '{w}' may be a typo for a past participle; the only permitted correction is that one word's inflection, and only if the request cannot run without it",
                    }
                )
                break
    return out


def _sentence_of(q: str, pos: int) -> int:
    return next((i for i, (a, b) in enumerate(_sentence_spans(q)) if a <= pos < b), -1)


def prepare_child(parent: dict, plan: dict, plans: list[dict], by_id: dict, ctx: dict) -> dict:
    """Everything deterministic that can be done for one child before it is written. ``active`` is False when nothing applies (the child is then
    rendered exactly as before)."""
    q = parent["original_question"]
    applicable = _applicable(parent, plan, by_id)
    entries = [dict(e) for e in ctx["extract"]]
    original_lines_text = " ".join(e["text"] for e in entries)
    text_ops: dict[int, list[tuple[int, int, str]]] = {}
    edits: list[dict] = []
    not_applied: list[dict] = []

    def add_op(abs_lo: int, abs_hi: int, replacement: str, edit: dict) -> bool:
        for i, e in enumerate(entries):
            loc = _local(e, abs_lo, abs_hi)
            if loc:
                text_ops.setdefault(i, []).append((loc[0], loc[1], replacement))
                edits.append(edit)
                return True
        return False

    ranges = [tuple(s) for e in entries for s in (e.get("spans") or [e["span"]])]
    ref_ops, unsafe = _ops_for_references(q, parent, ranges)
    not_applied += unsafe
    for a, b, rep, edit in ref_ops:
        if not add_op(a, b, rep, edit):
            not_applied.append(
                {
                    "word": q[a:b],
                    "source_span": [a, b],
                    "clarification": edit["clarification"],
                    "reason": "the word is not inside the extract",
                }
            )
    cue_ops, cue_unsafe = _cue_edits(parent, plan, applicable, q)
    not_applied += cue_unsafe
    for pos, text, edit in cue_ops:
        if not add_op(pos, pos, text, edit):
            not_applied.append(
                {
                    "cue": edit["supplied"][0]["text"],
                    "clarification": edit["clarification"],
                    "reason": "its position is not inside the extract",
                }
            )
    for edit in _inflection_edits(q, entries):
        lo, hi = edit["replaces"]["source_span"]
        if not add_op(lo, hi, edit["result"], edit):
            not_applied.append(
                {
                    "word": edit["replaces"]["text"],
                    "source_span": [lo, hi],
                    "reason": "the word is not inside the extract",
                }
            )
    # terminal punctuation: kept only when the extract ends exactly where its source sentence ends
    last = max(entries, key=lambda e: (e.get("spans") or [e["span"]])[-1][1])
    end = (last.get("spans") or [last["span"]])[-1][1]
    sent = next(((a, b) for a, b in _sentence_spans(q) if a <= end - 1 < b), None)
    if sent and q[end : sent[1]].strip() in ("?", ".", "!") and not last["text"].rstrip().endswith(("?", ".", "!")):
        mark = q[end : sent[1]].strip()
        idx = entries.index(last)
        text_ops.setdefault(idx, []).append((len(last["text"]), len(last["text"]), mark))
        edits.append(
            {
                "op": "terminal_punctuation",
                "rule": "extract_ends_at_its_source_sentence",
                "clarification": None,
                "replaces": None,
                "from_source": [{"span": [q.index(mark, end), q.index(mark, end) + 1], "text": mark}],
                "supplied": [],
                "result": mark,
            }
        )
    for i, ops in text_ops.items():
        entries[i]["text"] = _apply(ops, entries[i]["text"])
        entries[i]["prepared"] = True
    prepared_text = " ".join(e["text"] for e in entries)
    # the approved lead-in (a non-fragment child whose subject the extract does not state)
    prefix = None
    subject = ctx["subject"][0] if ctx["subject"] else None
    link = ctx.get("link")
    if (
        subject
        and not plan.get("clarified_fragment")
        and not ctx["inherited_extracts"]
        and link
        and link.get("authority") == req.APPROVED
        and lx.coverage_fraction(lx.content_stems(subject["text"]), lx.content_stems(prepared_text)) < 0.6
    ):
        s_lo, s_hi = subject["spans"][0]
        art = _article_before(q, s_lo)
        subject_words = q[art[0] : s_hi] if art else q[s_lo:s_hi]
        prefix = {
            "op": "context_prefix",
            "rule": "approved_context_link_then_the_request_subject",
            "clarification": link["clarification"],
            "decision": link.get("decision"),
            "replaces": None,
            "from_source": ([{"span": [art[0], art[1]], "text": q[art[0] : art[1]]}] if art else [])
            + [{"span": [s_lo, s_hi], "text": q[s_lo:s_hi]}],
            "supplied": [
                {
                    "text": link["text"],
                    "by": f"{link['clarification']} context_link (researcher-approved joining words, no source span)",
                },
                {"text": ",", "by": "punctuation"},
            ],
            "result": f"{link['text']} {subject_words},",
        }
        edits.append(prefix)
    elif (
        subject
        and not plan.get("clarified_fragment")
        and link
        and link.get("authority") != req.APPROVED
        and lx.coverage_fraction(lx.content_stems(subject["text"]), lx.content_stems(prepared_text)) < 0.6
    ):
        not_applied.append(
            {
                "kind": "context_prefix",
                "reason": f"the joining words {link['text']!r} are not researcher-approved, so they are not used",
            }
        )
    carry, carry_missing, join = _carry(parent, plan, plans, by_id, ctx, prepared_text, applicable)
    fixed = {e["replaces"]["text"] for e in edits if e["op"] == "inflection_corrected"}
    grammar = [g for g in _grammar_notes(original_lines_text) if g["word"] not in fixed]
    scope = [
        {
            "id": r["id"],
            "kind": r["kind"],
            "text": r["text"],
            "clarification": c["id"],
            "decision": (r.get("provenance") or {}).get("decision"),
        }
        for c in applicable
        for r in c.get("requirements", [])
        if r["kind"] in req.DECIDED_KINDS
    ]
    edits.sort(key=_edit_key)
    from experiments.ask_cli_revised.decompose import (
        scaffold as scaffold_mod,
    )  # late: the scaffold builds on this module's helpers

    scaffold = scaffold_mod.build(
        parent, plan, plans, by_id, ctx, {"entries": entries, "edits": edits, "join": join, "own_text": prepared_text}
    )
    all_edits = edits + (carry["edits"] if carry else [])
    resolved = {e["replaces"]["text"].lower() for e in all_edits if e["op"] == "reference_resolved"}
    requirements = _requirements(
        applicable, prepared_text, carry, edits, resolved, bool(scaffold and scaffold["built"])
    )
    scaffold_relevant = bool(scaffold and (scaffold["built"] or any(r["template"] for r in scaffold["not_built"])))
    active = bool(edits or not_applied or carry or carry_missing or grammar or join or scaffold_relevant)
    return {
        "active": active,
        "extract_entries": entries,
        "prefix": prefix["result"] if prefix else None,
        "edits": edits,
        "not_applied": not_applied,
        "not_prepared": carry_missing,
        "carry": carry,
        "join": join,
        "requirements": requirements,
        "scope_review": scope,
        "grammar_notes": grammar,
        "scaffold": scaffold,
        "original_extract_text": original_lines_text,
    }


_EDIT_ORDER = {
    "context_prefix": 0,
    "reference_resolved": 1,
    "cue_added": 1,
    "inflection_corrected": 1,
    "terminal_punctuation": 2,
}


def _edit_key(e: dict) -> tuple:
    """Display order: the lead-in, then the in-extract edits by source position, then the closing punctuation."""
    span = (e.get("replaces") or {}).get("source_span") or [e.get("at_source_pos", 0)]
    return (_EDIT_ORDER[e["op"]], span[0])


QUESTION_WORDS = WH_WORDS | {"how", "whether", "if"}


def _requirements(
    applicable: list[dict],
    prepared_text: str,
    carry: dict | None,
    edits: list[dict],
    resolved: set,
    scaffolded: bool = False,
) -> list[dict]:
    """What the finished wording will be held to, in the vocabulary the ledger and requirement checks already use. Nothing here is a new check;
    it only tells the writer, in advance, what the existing checks look for."""
    toks = set(lx.tokens(prepared_text))
    asked = sorted(toks & QUESTION_WORDS)
    quals = sorted(toks & (OPERATORS - QUESTION_WORDS))
    out: list[dict] = []
    if asked:
        out.append(
            {
                "id": "own_operations",
                "text": f"keeps every question word it already asks ({', '.join(asked)}); a compound operation such as 'whether and how' or 'which ... and how' stays whole",
                "check": "operator_dropped",
            }
        )
    if quals:
        out.append(
            {"id": "qualifiers", "text": f"keeps its qualifiers ({', '.join(quals)})", "check": "operator_dropped"}
        )
    out.append(
        {
            "id": "no_new_ask",
            "text": "adds no NEW question or operation, and does not ask again what the question it continues asks",
            "check": "operator_added",
        }
    )
    for e in edits:
        if e["op"] == "cue_added":
            word = e["supplied"][0]["text"].replace("and ", "").strip()
            out.append(
                {
                    "id": f"cue:{e['clarification']}",
                    "text": f"still asks '{word}' (added by {e['clarification']}; it is already in the prepared request)",
                    "check": "the added-cue requirement and the relationship check",
                }
            )
    if resolved or any(c["kind"] == "reference" for c in applicable):
        done = f" (already replaced by code: {', '.join(sorted(resolved))})" if resolved else ""
        out.append(
            {
                "id": "references",
                "text": f"leaves no approved reference word unresolved{done}",
                "check": "clarified_reference_unresolved",
            }
        )
    if carry and not scaffolded:
        out.append(
            {
                "id": "carry",
                "text": f"states the carried context ({carry['text']!r}) as what is being asked about, not as a question",
                "check": "referent_relationship_incomplete / pair_member_missing",
            }
        )
    for c in applicable:
        if c.get("pairs") and len(c["pairs"]) >= 2:
            out.append(
                {
                    "id": f"pair:{c['id']}",
                    "text": f"keeps {' and '.join(repr(m['text']) for m in c['pairs'])} together in this one request",
                    "check": "pair_member_missing",
                }
            )
    if scaffolded:
        out.append(
            {
                "id": "scaffold",
                "text": "is the prepared request exactly as built by code; any other wording is held for the researcher's approval and is never presented as the code's",
                "check": "departs_from_prepared_request",
            }
        )
    out.append(
        {
            "id": "form",
            "text": "keeps the researcher's request form (an imperative stays an imperative, a question a question)",
            "check": "request_form_changed",
        }
    )
    return out
