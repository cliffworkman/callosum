"""Relational obligations as STRUCTURE, and a conformance check of any wording against that structure.

A relationship obligation is parsed, from the request's own exact words, into: subject, relation, target, requested
polarity ("whether"), requested manner ("how"), the answer form (yes/no or wh-question), qualifications, and the
referents that are unresolved (or clarified by a user). Every slot carries exact source spans. The child writer is given
this structure, and any candidate wording or repair is parsed the same way and compared with it.

The parse uses a small closed list of relation verbs and clause rules, disclosed here; when it cannot parse, the
relationship is ``unparsed`` and every wording of it is left for semantic review. Conformance is a DETERMINISTIC
diagnostic: it can prove a wording CHANGED the subject, target, direction, relation or requested operation, but a
wording that passes it is still only a candidate. Nothing here certifies semantic fidelity.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.decompose import clarifications as clar
from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.request_contract import _sentence_spans

LEXICAL = 0.6
_VERBS = frozenset(
    """relate relates related relating relation relationship relationships correlate correlates correlated correlation
    associate associates associated association link links linked affect affects affected influence influences
    influenced predict predicts predicted impact impacts cause causes caused differ differs differed""".split()
)
_FAMILIES = {
    "association": ("relat", "correl", "associat", "link"),
    "effect": ("affect", "influenc", "impact", "caus", "predict", "differ"),
}
_PREPS = frozenset({"to", "with", "between", "of"})
_LEAD = frozenset(
    "whether and or how if so do does did is are can could will would should please which what that then".split()
)
_WH = frozenset({"what", "which", "who", "whom", "whose", "how"})
_KIND = frozenset("kind kinds type types sort sorts form forms variety".split())
_POLAR_START = frozenset("do does did is are can could was were has have will would should".split())
_COPULA = frozenset({"is", "are", "was", "were"})
_MANNER = frozenset({"how", "way", "ways", "manner", "mechanism", "mechanisms", "means", "method", "process"})

Token = tuple[str, int, int]


def _tokens(text: str, lo: int, hi: int) -> list[Token]:
    return [(m.group(0).lower(), lo + m.start(), lo + m.end()) for m in re.finditer(r"[A-Za-z0-9]+", text[lo:hi])]


def _union(spans: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for lo, hi in sorted((s[0], s[1]) for s in spans):
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def _family(word: str) -> str | None:
    return next((f for f, prefixes in _FAMILIES.items() if any(word.startswith(p) for p in prefixes)), None)


def _strip_lead(toks: list[Token], *, keep_wh: bool = False) -> list[Token]:
    """Drop leading auxiliaries and polarity/manner words; with keep_wh, stop at a leading wh-word (it is parsed separately)."""
    i = 0
    while i < len(toks) and toks[i][0] in _LEAD and not (keep_wh and toks[i][0] in _WH):
        i += 1
    return toks[i:]


def _wh_marker(toks: list[Token]) -> int:
    """Length of a leading wh-marker ("what kind of", "which", "how")."""
    if not toks or toks[0][0] not in _WH:
        return 0
    j = 1
    while j < len(toks) and (toks[j][0] in _KIND or toks[j][0] == "of"):
        j += 1
    return j


def _noun_relation(toks: list[Token], vi: int) -> tuple[list[Token], list[Token]] | None:
    """ "the relation of X to Y" / "the relation between X and Y": the subject and target are AFTER the noun."""
    if not toks[vi][0].startswith(("relation", "correlation", "association")) or vi + 1 >= len(toks):
        return None
    prep, rest = toks[vi + 1][0], toks[vi + 2 :]
    joiners = {"between": {"and"}, "of": {"to", "with", "and"}}.get(prep)
    if not joiners:
        return None
    j = next((i for i, t in enumerate(rest) if t[0] in joiners), None)
    return (rest[:j], rest[j + 1 :]) if j is not None else None


def _slot(question: str, toks: list[Token]) -> dict | None:
    if not toks:
        return None
    lo, hi = toks[0][1], toks[-1][2]
    return {"text": question[lo:hi], "spans": [[lo, hi]]}


def candidate_antecedents(parent: dict, ref: dict) -> list[dict]:
    """CANDIDATE referents for a reference word: the subject (for singular words) and the nearest requested items that
    precede it in its sentence, else the previous sentence. Candidates only: none is ever approved."""
    q = parent["original_question"]
    lo = ref["spans"][0][0]
    out: list[dict] = []
    if ref["text"].lower() not in {"they", "them", "their", "theirs", "these", "those"}:
        out += [{"id": s["id"], "text": s["text"], "role": "subject"} for s in parent.get("referents", [])]
    sents = _sentence_spans(q)
    idx = next((i for i, (a, b) in enumerate(sents) if a <= lo < b), None)
    pool = [
        r
        for r in parent["requirements"]
        if r["kind"] == "requested_item"
        and not r.get("superseded")
        and r["origin"] != "source_unit_floor"
        and r["spans"]
    ]
    for si in (idx, idx - 1 if idx else None):
        if si is None or si < 0:
            continue
        a, b = sents[si]
        found = sorted(
            (r for r in pool if a <= r["spans"][0][0] and r["spans"][-1][1] <= b and r["spans"][-1][1] <= lo),
            key=lambda r: -r["spans"][-1][1],
        )
        if found:
            out += [{"id": r["id"], "text": r["text"], "role": "preceding requested item"} for r in found[:2]]
            break
    return out


def _references(parent: dict, slot: dict | None, name: str) -> list[dict]:
    if not slot:
        return []
    lo, hi = slot["spans"][0]
    out = []
    for a in parent["ambiguities"]:
        if a["origin"] != "deterministic_cue" or not a["spans"]:
            continue
        s = a["spans"][0]
        if lo <= s[0] and s[1] <= hi:
            c = clar.covering(parent, s)
            out.append(
                {
                    "id": a["id"],
                    "word": a["text"],
                    "span": s,
                    "slot": name,
                    "status": "clarified_by_user" if c else "unresolved",
                    "clarification": c["id"] if c else None,
                    "means": c["means"] if c else None,
                    "antecedent": c["refers_to"] if c else None,  # the exact request words the user says it points at
                    "candidates": [] if c else candidate_antecedents(parent, a),
                }
            )
    return out


def build_contract(parent: dict, rel: dict) -> dict:
    """The structure of one relationship obligation, parsed from its exact source words."""
    q = parent["original_question"]
    base = {"obligation_id": rel["id"], "source_spans": rel["spans"], "direction": "subject_to_target"}
    ranges = _union(rel["spans"])
    groups = [_tokens(q, lo, hi) for lo, hi in ranges]
    gi = next((i for i, g in enumerate(groups) if any(t[0] in _VERBS for t in g)), None)
    if gi is None:
        return {
            **base,
            "parse_status": "unparsed",
            "reason": "no relation verb from the closed list in the obligation's words",
        }
    toks = groups[gi]  # subject, relation and target are read from the range that holds the relation verb
    context_spans = [
        r for i, r in enumerate(ranges) if i != gi
    ]  # other ranges are linked cross-unit context, not slots
    vi = next(i for i, t in enumerate(toks) if t[0] in _VERBS)
    verb_end = vi + (1 if vi + 1 < len(toks) and toks[vi + 1][0] in _PREPS else 0)
    noun = _noun_relation(toks, vi)
    if noun:
        subject_toks, target_toks = noun
    else:
        subject_toks, target_toks = _strip_lead(toks[:vi]), toks[verb_end + 1 :]
        if not subject_toks and gi > 0:
            subject_toks = groups[gi - 1]
        if not target_toks and gi + 1 < len(groups):
            target_toks = groups[gi + 1]
    wh = None
    if subject_toks and not noun:
        sents = _sentence_spans(q)
        a = next((a for a, b in sents if a <= subject_toks[0][1] < b), None)
        pre = _tokens(q, a, subject_toks[0][1]) if a is not None else []
        if pre and pre[0][0] == "and":
            pre = pre[1:]
        m = _wh_marker(pre)
        if m and len(pre[m:]) <= 3 and not any(t in _VERBS for t, _, _ in pre[m:]):
            wh, subject_toks = (
                pre[:m],
                pre[m:] + subject_toks,
            )  # the wh-phrase belongs to the clause; its modifiers belong to the subject
    if not subject_toks or not target_toks:
        return {**base, "parse_status": "unparsed", "reason": "no subject or no target found around the relation verb"}
    dependents = [r for r in parent["requirements"] if r.get("part_of") == rel["id"]]
    pol = next((r for r in dependents if r["kind"] == "polarity"), None)
    man = next((r for r in dependents if r["kind"] == "manner"), None)
    added: dict[
        str, str
    ] = {}  # what a MEANING clarification over this relationship says it also asks (not in the source words)
    for c in parent.get("clarifications", []):
        if c["kind"] == "meaning" and any(
            max(c["target_span"][0], s[0]) < min(c["target_span"][1], s[1]) for s in rel["spans"]
        ):
            for what in c.get("adds", []):
                added.setdefault(what, c["id"])
    subject, target = _slot(q, subject_toks), _slot(q, target_toks)
    refs_s, refs_t = _references(parent, subject, "subject"), _references(parent, target, "target")
    subject["is_reference"] = len(subject_toks) == 1 and subject_toks[0][0] in lx.DEIXIS_WORDS
    subject["reference"] = refs_s[0] if subject["is_reference"] and refs_s else None
    clarified = bool(subject["reference"] and subject["reference"]["status"] == "clarified_by_user")
    # a wording is compared with the exact request words the user pointed at when there are any, else with what they said it means
    subject["resolved_text"] = (
        ((subject["reference"]["antecedent"] or {}).get("text") or subject["reference"]["means"]) if clarified else None
    )
    if wh:
        form = {"form": "wh", "marker": q[wh[0][1] : wh[-1][2]], "spans": [[wh[0][1], wh[-1][2]]]}
    elif pol:
        form = {"form": "polar", "marker": pol["text"], "spans": pol["spans"]}
    else:
        form = {"form": "unspecified", "marker": None, "spans": []}
    return {
        **base,
        "parse_status": "parsed",
        "subject": subject,
        "relation": {
            **_slot(q, toks[vi : verb_end + 1 if verb_end > vi else vi + 1]),
            "family": _family(toks[vi][0]),
            "verb": toks[vi][0],
        },
        "target": {**target, "references": refs_t},
        "polarity": {
            "requested": bool(pol) or "polarity" in added,
            "text": pol["text"] if pol else None,
            "spans": pol["spans"] if pol else [],
            "basis": "source" if pol else ("clarification" if "polarity" in added else None),
            "clarification": None if pol else added.get("polarity"),
        },
        "manner": {
            "requested": bool(man) or "manner" in added,
            "text": man["text"] if man else None,
            "spans": man["spans"] if man else [],
            "basis": "source" if man else ("clarification" if "manner" in added else None),
            "clarification": None if man else added.get("manner"),
        },
        "answer_form": form,
        "context_spans": context_spans,
        "qualifications": [
            {"id": r["id"], "kind": r["kind"], "text": r["text"], "spans": r["spans"]}
            for r in dependents
            if r["kind"] in ("kinds", "qualifier", "population")
        ],
        "clarified_meanings": [
            {"id": c["id"], "means": c["means"], "adds": c.get("adds", []), "basis": "clarification"}
            for c in parent.get("clarifications", [])
            if c["kind"] == "meaning"
            and any(max(c["target_span"][0], s[0]) < min(c["target_span"][1], s[1]) for s in rel["spans"])
        ],
        "unresolved_referents": [r for r in refs_s + refs_t if r["status"] == "unresolved"],
        "clarified_referents": [r for r in refs_s + refs_t if r["status"] == "clarified_by_user"],
    }


def render(contract: dict) -> str:
    """The structure as the child writer sees it."""
    if contract["parse_status"] != "parsed":
        return "Relationship (its structure could not be parsed automatically; ask it in the request's own words, and do not change what relates to what)."
    s, r, t = contract["subject"], contract["relation"], contract["target"]
    lines = [
        "Relationship to ask about, parsed from the request's own words. Keep the subject, the relation, the target and the direction exactly:"
    ]
    if s.get("resolved_text"):
        ref = s["reference"]
        lines.append(
            f'- subject: "{s["text"]}" (chars {s["spans"][0][0]}-{s["spans"][0][1]}), which the user has clarified means: "{ref["means"]}" ({ref["clarification"]}). '
            + (
                f'It points at the request words "{ref["antecedent"]["text"]}" (chars {ref["antecedent"]["span"][0]}-{ref["antecedent"]["span"][1]}), asked as a separate question; use that meaning.'
                if ref.get("antecedent")
                else "Use that."
            )
        )
    elif s["is_reference"]:
        lines.append(
            f'- subject: "{s["text"]}" (chars {s["spans"][0][0]}-{s["spans"][0][1]}), an unresolved reference (see Unresolved wording).'
        )
    else:
        lines.append(f'- subject: "{s["text"]}" (chars {s["spans"][0][0]}-{s["spans"][0][1]})')
    lines.append(f'- relation: "{r["text"]}" (chars {r["spans"][0][0]}-{r["spans"][0][1]})')
    lines.append(f'- target: "{t["text"]}" (chars {t["spans"][0][0]}-{t["spans"][0][1]})')
    for ref in t["references"]:
        if ref["status"] == "clarified_by_user":
            lines.append(
                f'  - in the target, "{ref["word"]}" (chars {ref["span"][0]}-{ref["span"][1]}) is clarified by the user to mean: "{ref["means"]}"'
                + (f' (the request words "{ref["antecedent"]["text"]}")' if ref.get("antecedent") else "")
            )

    def ask(word: str, key: str) -> list[str]:
        part = contract[key]
        if not part["requested"]:
            return []
        return [
            word
            + (
                f" [added by the user's clarification {part['clarification']}; not in the source words]"
                if part["basis"] == "clarification"
                else ""
            )
        ]

    asks = ask("whether (yes/no)", "polarity") + ask("how", "manner")
    form = contract["answer_form"]
    lines.append(
        f"- what is asked about it: {' AND '.join(asks) if asks else 'nothing beyond the relationship itself'}; answer form: {form['form']}"
        + (f' ("{form["marker"]}")' if form["marker"] else "")
    )
    if contract["qualifications"]:
        lines.append(
            "- qualifications: " + "; ".join(f'{q_["kind"]}: "{q_["text"]}"' for q_ in contract["qualifications"])
        )
    lines.append("Do not swap the subject and the target, do not replace either, and do not change the answer form.")
    return "\n".join(lines)


# ---- conformance of a wording against the structure ------------------------------------------------------------------------


def _form_of(clause: str) -> str:
    lead = [t for t, _, _ in _tokens(clause, 0, len(clause))]
    while lead[:1] and lead[0] in ("and", "but", "then", "also"):
        lead = lead[1:]
    if lead and (lead[0] in _POLAR_START or lead[0] == "whether" or "if" in lead or "whether" in lead):
        return "polar"
    return "wh" if lead and lead[0] in _WH else "unspecified"


def parse_question(text: str) -> dict:
    """Subject, relation, target and question form of a wording. A leading context clause ("In the context of X, whether
    ...") does not hide the form or the subject: both are read from the clause that holds the relation verb."""
    toks = _tokens(text, 0, len(text))
    form = _form_of(text.split(",")[0])
    vi = next((i for i, t in enumerate(toks) if t[0] in _VERBS), None)
    if vi is None:
        return {"has_relation": False, "form": form}
    start = text.rfind(",", 0, toks[vi][1]) + 1  # the clause that holds the verb
    end = text.find(",", toks[vi][2])
    if form == "unspecified":
        form = _form_of(text[start : end if end != -1 else len(text)])
    first = next((i for i, t in enumerate(toks) if t[1] >= start), 0)
    verb_end = vi + (1 if vi + 1 < len(toks) and toks[vi + 1][0] in _PREPS else 0)
    cut = end
    noun = _noun_relation(toks, vi)
    if noun:
        pre, tail = noun
        tail = [t for t in tail if cut == -1 or t[1] < cut]
    else:
        pre = _strip_lead(toks[first:vi], keep_wh=True)
        pre = _strip_lead(pre[_wh_marker(pre) :]) if pre and pre[0][0] in _WH else pre
        tail = [t for t in toks[verb_end + 1 :] if cut == -1 or t[1] < cut]
    return {
        "has_relation": True,
        "form": form,
        "verb": toks[vi][0],
        "family": _family(toks[vi][0]),
        "subject": [t[0] for t in pre],
        "target": [t[0] for t in tail],
        "subject_text": " ".join(t[0] for t in pre),
        "target_text": " ".join(t[0] for t in tail),
    }


def _cover(want: list[str], have_words: list[str]) -> float:
    stems = lx.content_stems(" ".join(want))
    return lx.coverage_fraction(stems, lx.content_stems(" ".join(have_words))) if stems else 1.0


def conformance(contract: dict, question: str) -> dict:
    """DIAGNOSTIC: does this wording keep the relationship's subject, target, direction, relation and answer form?"""
    if contract["parse_status"] != "parsed":
        return {
            "status": "not_verifiable",
            "violations": [],
            "review": [{"kind": "relationship_structure_not_parsed", "note": contract.get("reason")}],
            "child_parse": None,
        }
    child = parse_question(question)
    violations: list[dict] = []
    review: list[dict] = []
    want_form = contract["answer_form"]["form"]
    if want_form in ("polar", "wh") and child["form"] != want_form:
        violations.append(
            {
                "kind": "operation_changed",
                "note": f"the request asks a {want_form} question about this relationship; the wording is {child['form']}",
            }
        )
    if want_form == "unspecified" and child["form"] == "polar" and not contract["polarity"]["requested"]:
        violations.append(
            {
                "kind": "operation_changed",
                "note": "the wording turns the relationship into a yes/no question the request did not ask",
            }
        )
    toks = set(lx.tokens(question))
    for key, cues in (("manner", _MANNER), ("polarity", {"whether", "if"})):
        part = contract[key]
        if part["basis"] == "clarification" and not (cues & toks or (key == "polarity" and child["form"] == "polar")):
            violations.append(
                {
                    "kind": "operation_changed",
                    "note": f"the user's clarification {part['clarification']} says this relationship also asks {'how' if key == 'manner' else 'whether'}; the wording does not",
                }
            )
    if not child["has_relation"]:
        violations.append({"kind": "relation_changed", "note": "the wording no longer states the relation"})
        return {"status": "violations", "violations": violations, "review": review, "child_parse": child}
    if child["family"] != contract["relation"]["family"]:
        violations.append(
            {"kind": "relation_changed", "note": f"relation '{contract['relation']['verb']}' became '{child['verb']}'"}
        )
    subj, tgt = contract["subject"], contract["target"]
    csubj, ctgt = child["subject"], child["target"]
    only_pronoun = len(csubj) == 1 and csubj[0] in lx.DEIXIS_WORDS
    if subj.get("resolved_text"):
        if _cover([subj["resolved_text"]], csubj) < LEXICAL and not (only_pronoun and csubj[0] == subj["text"].lower()):
            violations.append(
                {
                    "kind": "subject_changed",
                    "note": f'the user clarified the subject as "{subj["resolved_text"]}"; the wording\'s subject is "{child["subject_text"]}"',
                }
            )
    elif subj["is_reference"]:
        if not only_pronoun:
            cands = (subj["reference"] or {}).get("candidates", [])
            if any(_cover([c["text"]], csubj) >= LEXICAL for c in cands):
                review.append(
                    {
                        "kind": "subject_reading_adopted",
                        "note": f'the subject "{subj["text"]}" is unresolved; the wording adopted "{child["subject_text"]}" (a candidate, not approved)',
                    }
                )
            else:
                violations.append(
                    {
                        "kind": "subject_changed",
                        "note": f'the subject "{subj["text"]}" is unresolved and "{child["subject_text"]}" is not even a candidate reading',
                    }
                )
    elif _cover([subj["text"]], csubj) < LEXICAL:
        violations.append(
            {"kind": "subject_changed", "note": f'subject "{subj["text"]}" became "{child["subject_text"]}"'}
        )
    plain_target = re.sub(r"\b(" + "|".join(lx.DEIXIS_WORDS) + r")\b", " ", tgt["text"], flags=re.I)
    if lx.content_stems(plain_target) and _cover([plain_target], ctgt) < LEXICAL:
        violations.append({"kind": "target_changed", "note": f'target "{tgt["text"]}" became "{child["target_text"]}"'})
    subject_words = subj.get("resolved_text") or (None if subj["is_reference"] else subj["text"])
    if subject_words and _cover([plain_target], csubj) >= LEXICAL and _cover([subject_words], ctgt) >= LEXICAL:
        violations.append({"kind": "direction_changed", "note": "the subject and the target are swapped"})
    child_refs = [w for w in ctgt if w in lx.DEIXIS_WORDS]
    for ref in tgt["references"]:
        if ref["status"] == "clarified_by_user":
            meant = (ref.get("antecedent") or {}).get("text") or ref["means"]
            if not (ref["word"].lower() in ctgt or _cover([meant], ctgt) >= LEXICAL):
                violations.append(
                    {
                        "kind": "referent_changed",
                        "note": f'"{ref["word"]}" was clarified to mean "{ref["means"]}"; the wording\'s target does not carry it',
                    }
                )
        elif child_refs and ref["word"].lower() not in child_refs:
            violations.append(
                {
                    "kind": "referent_changed",
                    "note": f'the reference word "{ref["word"]}" became "{child_refs[0]}", which points at something else',
                }
            )
        elif not child_refs:
            review.append(
                {
                    "kind": "referent_resolved_by_wording",
                    "note": f'"{ref["word"]}" in the target was replaced by explicit wording; the reading is not approved',
                }
            )
    return {
        "status": "violations" if violations else ("review_required" if review else "conforms"),
        "violations": violations,
        "review": review,
        "child_parse": child,
    }


def introduced_relation(question: str, owned_text: str) -> dict | None:
    """A child that owns no relationship must not state one. A relation word (from the closed list) in its wording that
    none of the request words it owns contain is a relationship the request never attached to this item."""
    parsed = parse_question(question)
    if not parsed["has_relation"]:
        return None
    if any(_family(t) == parsed["family"] for t, _, _ in _tokens(owned_text, 0, len(owned_text))):
        return None
    return {
        "verb": parsed["verb"],
        "family": parsed["family"],
        "subject": parsed["subject_text"],
        "target": parsed["target_text"],
    }


def copular_identity(question: str, referent_text: str) -> bool:
    """A bare copula tying an item to the subject ("traits ARE <subject>") asserts an identity the request never states."""
    toks = [t for t, _, _ in _tokens(question, 0, len(question))]
    ref = [t for t, _, _ in _tokens(referent_text, 0, len(referent_text))]
    for k in range(2, len(toks) - len(ref) + 1):
        if toks[k : k + len(ref)] == ref and toks[k - 1] in _COPULA and toks[k - 2] not in {"there", "here"}:
            return True
    return False
