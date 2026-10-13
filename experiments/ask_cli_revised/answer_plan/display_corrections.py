"""Two corrections to how the display checks are applied to an authorized quotation. Pure: no model, no I/O.

Applied by ``layerc_presentation.finalize_display`` on the fresh route only. They can restore a display the
unchanged checks in ``classify`` and ``text`` withheld; they never add a source, a proposition or a value.
"""

import re

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import overview_guards as og
from experiments.ask_cli_revised.contract_directed import attribution as attr

CLOSURE = "referentially_closed"
AIM = "attribution_aim_or_hypothesis"
# The study's own results as grammatical subject of a reporting verb: tentative, but a result and not an aim.
_QUALIFIED_RESULT = re.compile(
    r"\b(?:results?|findings?|data|analys[ei]s)\s+(?:\w+\s+){0,2}?(?:suggests?|indicates?|shows?|demonstrates?|reveals?)\b",
    re.IGNORECASE,
)
# An aim, test or prediction stated as an act. The bare noun "hypothesis" is deliberately not here.
_AIM_ACT = re.compile(
    r"\b(?:aims?|aimed|hypothesi[sz]ed?|predict(?:s|ed|ion|ions)?|we tested|tested whether|we examined whether|"
    r"expected to|is expected|are expected|was expected|were expected)\b",
    re.IGNORECASE,
)
# Words whose removal could change what a clause claims: conditions, contrasts and exceptions.
_MATERIAL = re.compile(
    r"\b(?:if|unless|only|except|when|whereas|although|though|while|but|however|compared|versus|than|after|before|"
    r"controlling|adjusting|among|between)\b",
    re.IGNORECASE,
)


def recompute(attempt):
    attempt["reasons"] = sorted({c["check"] for c in attempt["checks"] if not c["passed"]})
    attempt["ok"] = all(c["passed"] for c in attempt["checks"])
    return attempt


def qualified_result_not_aim(attempt, quote):
    """A failed aim/hypothesis attribution becomes a passed, labelled check when the passage is a qualified result."""
    if AIM not in attempt["reasons"]:
        return attempt
    if not _QUALIFIED_RESULT.search(quote) or _AIM_ACT.search(quote) or attr.detect_cues(quote)["own_interpretation"]:
        return attempt
    attempt["checks"] = [
        {"check": "attribution_qualified_result", "passed": True, "detail": "reclassified_from:aim_or_hypothesis"}
        if c["check"] == AIM
        else c
        for c in attempt["checks"]
    ]
    attempt["attribution"] = "this_study_result"
    return recompute(attempt)


def removed_text_is_immaterial(original_sentence, clause):
    """The clause is a contiguous part of the sentence, and what was cut holds nothing that conditions the claim."""
    start = original_sentence.find(clause)
    if start < 0:
        return None
    removed = (original_sentence[:start] + " " + original_sentence[start + len(clause) :]).strip()
    material = bool(
        oe.has_negation(removed) or oe.has_hedge(removed) or oe.causal_stems(removed) or _MATERIAL.search(removed)
    )
    return None if material else removed


# Checks that exist because a raw source sentence was being printed as prose. They do not apply to a verified claim.
RAW_SENTENCE_FORM = ("referentially_closed", "passage_complete")


# A sentence that ends in its own punctuation followed by a numeric citation marker ("reactivity.6") is complete.
_CITATION_MARKER_END = re.compile(r"[.!?][\"')]?\s?\d{1,3}(?:[,;\-]\s?\d{1,3})*\s*$")


def ends_at_citation_marker(sentence):
    return bool(_CITATION_MARKER_END.search(sentence))


def claim_statement_reasons(claim, sentence):
    """Why the sealed claim may not stand as the statement for this evidence sentence; empty when it may.

    The claim was verified against its whole quotation. Here it is held to the one sentence Layer C authorized for
    display, with the project's existing rephrasing screen: no added direction, cause, number, acronym or vocabulary,
    and no dropped hedge or negation. Nothing is rewritten; a claim that fails is simply not used.
    """
    if not isinstance(claim, str) or not claim.strip():
        return ["no_claim_text"]
    unit = {"passage": sentence, "flags": oe.passage_flags(sentence)}
    return og.screen({"text": claim, "unit_ids": ["U1"], "bears_on": []}, units={"U1": unit}, part_ids=set())
