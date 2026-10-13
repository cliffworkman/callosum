"""Two corrections to how the display checks are applied to an authorized quotation. Pure: no model, no I/O.

Applied by ``layerc_presentation.finalize_display`` on the fresh route only. They can restore a display the
unchanged checks in ``classify`` and ``text`` withheld; they never add a source, a proposition or a value.
"""

import re

from experiments.ask_cli_revised import overview_evidence as oe
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
