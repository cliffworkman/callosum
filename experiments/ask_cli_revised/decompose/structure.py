"""Focused structural checks on a PREPARED child's wording: reliable, closed-list, deliberately not a grammar verifier.

Two checks, both pure and both only about a child that has a preparation record:

* ``departs_from_prepared_request``: the deterministic preparation is the only wording whose construction is defended (source words, approved
  words and named rules, each with its origin). Any other wording, however many required words it contains, is the writer's own composition:
  it is held for the researcher's approval rather than allowed to run on the strength of a ``candidate`` label. Comparison ignores case,
  spacing and closing punctuation only; the words added and removed are listed.
* ``unjoined_carried_clause``: when a fragment carries a parent's relationship ("<subject> <relation> ..."), the carried subject and relation
  must not be run together straight after a verb or an approved joining word ("measure <subject> <relation> ..."): an object noun phrase
  followed by its own verb needs a relative marker. This is the exact defect the v7 check found in a wording whose every required word was
  present. It fires only on that pattern; it says nothing about any other sentence.

Neither check certifies grammar: their absence is not a certificate, and a wording that passes still passes only lexical checks.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose.ledger import FORM_WORDS

_WORDS = re.compile(r"[a-z0-9']+")


def normalize(text: str) -> str:
    """Lower-case words only: spacing, closing punctuation and case never make two wordings different."""
    return " ".join(_WORDS.findall(str(text).lower()))


def _bag_diff(after: str, before: str) -> tuple[list[str], list[str]]:
    def minus(left: list[str], right: list[str]) -> list[str]:
        pool, out = list(right), []
        for t in left:
            if t in pool:
                pool.remove(t)
            else:
                out.append(t)
        return out

    a, b = normalize(after).split(), normalize(before).split()
    return minus(a, b), minus(b, a)


def departs_from_prepared_request(child: dict) -> dict | None:
    prep = child.get("preparation")
    if not prep or not prep.get("prepared_request"):
        return None
    if normalize(child["question"]) == normalize(prep["prepared_request"]):
        return None
    added, removed = _bag_diff(child["question"], prep["prepared_request"])
    return {
        "flag": "departs_from_prepared_request",
        "words_added": added,
        "words_removed": removed,
        "note": "the writer's wording is not the deterministic prepared request; a candidate label does not authorize it, so it is held for the "
        "researcher's approval. Words added: "
        + (", ".join(added) or "none")
        + "; words removed: "
        + (", ".join(removed) or "none"),
    }


def unjoined_carried_clause(child: dict) -> dict | None:
    prep = child.get("preparation") or {}
    carry = prep.get("carry") or {}
    if not carry.get("subject_words") or not carry.get("relation_words"):
        return None
    toks = lx.tokens(child["question"])
    run = lx.tokens(carry["subject_words"]) + lx.tokens(carry["relation_words"])
    joiners = set(FORM_WORDS) | {t for t in lx.tokens((prep.get("join") or {}).get("text", ""))}
    for i in range(1, len(toks) - len(run) + 1):
        if toks[i : i + len(run)] == run and toks[i - 1] in joiners:
            return {
                "flag": "unjoined_carried_clause",
                "words": [toks[i - 1], carry["subject_words"], carry["relation_words"]],
                "note": f"the carried subject ({carry['subject_words']!r}) and its relation ({carry['relation_words']!r}) follow {toks[i - 1]!r} with "
                "no 'that/which/who' between them, so the wording reads as a run-on rather than a request; it needs the researcher's approval",
            }
    return None


def findings(child: dict) -> list[dict]:
    """Structural findings for one child (empty when it has no preparation record or nothing fires)."""
    return [f for f in (unjoined_carried_clause(child), departs_from_prepared_request(child)) if f]
