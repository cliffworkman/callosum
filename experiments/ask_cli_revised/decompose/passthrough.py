"""The explicit "no decomposition needed" decision.

Decomposition exists to separate sibling obligations and to restore the context a fragment needs. When the request is already ONE
independently runnable Ask request, the honest outcome is to keep it exactly as written and send it through the normal downstream
Ask path once, without the decomposition writer. That is a statement about DECOMPOSITION only: nothing here says the question has
been answered, retrieved or synthesized, and tree closure never implies it (``ANSWER_STATE``).

Three outcomes, and only the first is a pass-through:

* ``no_decomposition_needed``: every required check passed. The inventory AND independent deterministic text checks agree.
* ``decompose``: the inventory found two or more anchor obligations. The existing path runs.
* ``uncertain``: no-split could not be established (and a split was not established either). The existing path runs, the decision is
  recorded as uncertain with the checks that failed, and the result is never presented as a pass-through. A zero-obligation inventory
  is uncertain, not evidence: "no obligations were found" says nothing about whether the request is one thread. Neither is one broad
  obligation evidence, because a model can return one obligation over a request that has several independently answerable threads.

The checks are generic English structure, not tied to any request. They are deliberately conservative: a false ``uncertain`` costs
only today's behaviour; a false pass-through would send a multi-part request downstream as if it were one.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.decompose import children as ch
from experiments.ask_cli_revised.decompose import ledger
from experiments.ask_cli_revised.decompose import lexical as lx

NO_DECOMPOSITION = "no_decomposition_needed"
DECOMPOSE = "decompose"
UNCERTAIN = "uncertain"
ANSWER_STATE = "not_executed"  # decomposition completeness is never answer completeness
DOWNSTREAM = {
    "ask_execution": "run_the_original_request_once_through_the_normal_ask_path",
    "answer_state": ANSWER_STATE,
    "note": "decomposition completeness is not answer completeness: nothing has been retrieved, answered or synthesized",
}
_INTERROGATIVE = ledger.WH_WORDS | {"how", "whether"}
_COORDINATORS = frozenset(ch._CONJUNCTIONS) | {"nor", "plus"}
_LIST_PUNCTUATION = re.compile(r"[,;:]")
DECISION_LIMITS = (
    "the checks read English structure only (question words, operation verbs, coordinating words, punctuation); they are not a semantic parser",
    "a request is passed through only when NO check failed, so an unusual but genuinely single request may stay uncertain",
    "a scripted or recorded inventory shows the decision path, never what a real inventory model would return",
)


def structure_signals(text: str) -> dict:
    """Independent text-only evidence about how many separately answerable threads a request may hold. No model, no inventory."""
    toks = lx.tokens(text)
    # an interrogative head ("what", "how", "whether") is the request head; an operation verb only counts when there is none,
    # because after an interrogative it is usually a participle or an embedded verb ("how is it measured")
    heads = [t for t in toks if t in _INTERROGATIVE] or [t for t in toks if t in ledger.FORM_WORDS]
    form = ledger.request_form(text)
    if not heads and form == "question":  # a polar question ("is there...", "does ...") is one request head
        heads = [toks[0]] if toks else []
    return {
        "form": form,
        "heads": heads,
        "coordinators": sorted({t for t in toks if t in _COORDINATORS}),
        "list_punctuation": sorted(set(_LIST_PUNCTUATION.findall(text))),
        "question_marks": text.count("?"),
    }


def _check(name: str, passed: bool, evidence) -> dict:
    return {"check": name, "passed": bool(passed), "evidence": evidence}


def decide(parent: dict, plans: list[dict], by_id: dict) -> dict:
    """The decomposition decision for a built parent contract and its plans. Pure: no model call, no write."""
    q = parent["original_question"]
    anchors = [p for p in plans if p["kind"] == "anchor" and not p.get("unit_level")]
    signals = structure_signals(q)
    checks: list[dict] = []
    if len(anchors) >= 2:
        return {
            "outcome": DECOMPOSE,
            "basis": f"the inventory found {len(anchors)} anchor obligations",
            "checks": [_check("two_or_more_anchor_obligations", True, [p["child_id"] for p in anchors])],
            "blocking": [],
            "limits": list(DECISION_LIMITS),
            "downstream": dict(DOWNSTREAM),
        }
    checks.append(
        _check("exactly_one_written_anchor", len(plans) == 1 and len(anchors) == 1, [p["kind"] for p in plans])
    )
    checks.append(_check("one_source_unit", len(parent["source_units"]) == 1, len(parent["source_units"])))
    unparsed = [p["child_id"] for p in plans if p.get("relation") and p["relation"].get("parse_status") != "parsed"]
    checks.append(
        _check(
            "relationship_structure_understood",
            not unparsed,
            {
                "unparsed": unparsed,
                "note": "a relationship the closed, English-only relation-verb list cannot parse is a limit of these checks",
            },
        )
    )
    checks.append(
        _check(
            "no_unanchored_inventory_obligation",
            not any(
                r["anchoring"] == "none"
                for r in parent["requirements"]
                if r["origin"] != "source_unit_floor" and not r.get("superseded")
            ),
            "every inventory obligation is anchored to exact words",
        )
    )
    checks.append(
        _check(
            "one_request_head",
            len(signals["heads"]) == 1,
            {"heads": signals["heads"], "note": "more than one request head can be more than one thread"},
        )
    )
    checks.append(_check("recognized_request_form", signals["form"] != "fragment", signals["form"]))
    checks.append(
        _check(
            "no_coordination_or_list_punctuation",
            not signals["coordinators"] and not signals["list_punctuation"],
            {"coordinators": signals["coordinators"], "list_punctuation": signals["list_punctuation"]},
        )
    )
    checks.append(_check("one_question_mark_at_most", signals["question_marks"] <= 1, signals["question_marks"]))
    if len(plans) == 1 and len(anchors) == 1:
        ctx = ch.child_context(parent, plans[0], by_id, plans=plans, governing_operation=True)
        extract = " ".join(e["text"] for e in ctx["extract"])
        checks.append(
            _check(
                "extract_is_the_whole_request",
                lx.tokens(extract) == lx.tokens(q),
                {
                    "extract_words": len(lx.tokens(extract)),
                    "request_words": len(lx.tokens(q)),
                    "note": "the exact word sequence, so 'returned unchanged' is literally true",
                },
            )
        )
        checks.append(
            _check(
                "no_open_reference_or_ambiguity",
                not ctx["unresolved"],
                [u["word"] for u in ctx["unresolved"]],
            )
        )
        checks.append(
            _check(
                "no_clarification_or_restored_context_applies",
                not (ctx["clarified"] or ctx["joint"] or ctx["inherited"] or ctx["inherited_extracts"])
                and not plans[0].get("clarified_fragment"),
                {
                    "clarified": len(ctx["clarified"]),
                    "paired": len(ctx["joint"]),
                    "inherited": len(ctx["inherited"]),
                },
            )
        )
        subject = ctx["subject"][0]["text"] if ctx["subject"] else None
        checks.append(
            _check(
                "no_subject_restoration_needed",
                not subject or lx.coverage_fraction(lx.content_stems(subject), lx.content_stems(extract)) >= 0.6,
                subject,
            )
        )
    blocking = [c["check"] for c in checks if not c["passed"]]
    if blocking:
        basis = "no-split could not be established: " + ", ".join(blocking)
        if not [
            r for r in parent["requirements"] if r["kind"] in ch.ANCHOR_KINDS and r["origin"] != "source_unit_floor"
        ]:
            basis = "the inventory found no obligations, which is not evidence that the request is one thread; " + basis
        outcome = UNCERTAIN
    else:
        basis = "one anchor obligation covers the whole request and every deterministic check agrees"
        outcome = NO_DECOMPOSITION
    return {
        "outcome": outcome,
        "basis": basis,
        "checks": checks,
        "blocking": blocking,
        "limits": list(DECISION_LIMITS),
        "downstream": dict(DOWNSTREAM),
    }
