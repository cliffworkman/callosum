"""Verified-claim responsiveness classification (inc 582) — presentation only.

A broad Ask synthesis can *correctly* verify a claim that is scientifically thin: a restatement of a
paper title, a table caption, or a "topic was studied" sentence. These clear the unchanged verifier
(exact quote + NLI support), but they answer the question poorly. This module labels an
already-verified claim as ``finding`` / ``descriptive`` / ``unknown`` so the UI can lead with
substantive findings and group descriptive/study-context material after it.

It is a **presentation label, never a verification signal**: it changes no status, hides nothing, and
promotes nothing. It runs on claims that already passed verification. ``descriptive`` means "verified,
but lower answer-value" — NOT lower confidence.

Design (deliberately simple + high-precision; the ship priority is *false descriptive demotions ≈ 0*,
false negatives are acceptable):

1. Classify the **main assertion**, not stray vocabulary. A research-activity frame ("Research
   investigated the relationship between X and Y", "This study examined Z") is ``descriptive`` even
   though result words ("relationship", "association") appear as the *object* of the activity verb.
2. A reporting/result verb (found / showed / observed / demonstrated …) means the sentence *reports a
   result*, so it overrides the descriptive frame ("This study **found** greater X" → ``finding``).
3. Only when the claim is neither a pure research-activity frame nor a stated result → ``unknown``
   (fail open). ``unknown`` is treated as a finding for grouping — never demoted.

Claim semantics are primary. ``cited_chunk_types`` / ``cited_evidence_roles`` are accepted for a future
conservative refinement (they may only push an *uncertain* claim toward ``unknown``, never *manufacture*
a ``finding``); v1 does not use them, because descriptive framing occurs in scientific body prose too.
Validated read-only against 80 real persisted verified claims (3 disjoint artifacts): 0 false
descriptive demotions.
"""

from __future__ import annotations

import re
from typing import Literal, Sequence

Responsiveness = Literal["finding", "descriptive", "unknown"]

# A reporting/result verb: its presence means the sentence REPORTS a result, so it is never a pure
# research-activity frame (this is what flips "This study found greater X" back to `finding`).
_REPORT = re.compile(
    r"\b(found|finds|show(?:s|ed|n)?|demonstrat\w+|reveal\w+|report(?:s|ed)?|observ\w+|identif\w+"
    r"|establish\w+|conclud\w+|exhibit\w+|displa\w+|confirm\w+)\b",
    re.I,
)

# Activity verbs (NOT reporting verbs) that govern a research-activity frame.
_ACT = (
    r"(?:investigat\w+|examin\w+|analy[sz]\w+|assess(?:es|ed|ing)?|evaluat\w+|explor\w+"
    r"|stud(?:y|ies|ied|ying)|compar\w+|review\w+|describ\w+|present(?:s|ed|ing)?|measur\w+"
    r"|characteri[sz]\w+|quantif\w+|address(?:es|ed|ing)?|test(?:s|ed|ing)?|focus\w+|aim\w+"
    r"|sought|seeks?|look(?:s|ed)?\s+at|set\s+out|utiliz\w+|employ\w+|us(?:e|es|ed|ing))"
)
_SUBJ = (
    r"(?:this|the|our|the\s+present|the\s+current|a|an|recent|prior|previous|several|numerous"
    r"|many|various|these|one|its)?\s*(?:stud(?:y|ies)|research|paper|article|works?|investigation"
    r"|analys[ei]s|report|literature|authors?|researchers?|experiments?|trials?)"
)
# D1: "This study examined …", "Research has investigated …", "Studies utilizing MRS have investigated …"
_D1 = re.compile(rf"^\W*{_SUBJ}\b.{{0,80}}?\b{_ACT}\b", re.I)
# D1b: "We examined …", "The authors analyzed …"
_D1b = re.compile(rf"^\W*(?:we|the\s+authors?)\b.{{0,40}}?\b{_ACT}\b", re.I)
# D2: a nominalized analysis as subject — "Correlations … were analyzed", "Comparisons … have been made"
_D2 = re.compile(
    r"^\W*(?:correlations?|comparisons?|analys[ei]s|regressions?|associations?|relationships?"
    r"|measurements?|assessments?|examinations?|investigations?|models?|tests?|evaluations?)\b"
    r".{0,120}?\b(?:were|was|have\s+been|has\s+been|been|is|are)\b"
    r".{0,40}?\b(?:analy[sz]ed|examined|made|performed|conducted|comput\w+|calculat\w+|assessed"
    r"|investigated|explored|compared|done|carried\s+out|undertaken|evaluated|run|fit\w*|estimat\w+"
    r"|used|applied)\b",
    re.I,
)
# D3: a nominal study title — "Structural imaging study of …", "Longitudinal study of …"
_D3 = re.compile(
    r"^\W*(?:longitudinal|cross[-\s]?sectional|structural|functional|molecular|imaging|neuroimaging"
    r"|pet|mri|fmri|meta[-\s]?anal\w*|systematic)\s+(?:stud(?:y|ies)|analys[ei]s|imaging|investigation"
    r"|review)\s+of\b",
    re.I,
)
# D4: "Research on X was published / conducted / performed …"
_D4 = re.compile(
    r"^\W*research\b.{0,80}?\b(?:was|were|has\s+been|have\s+been|is|are)\s+"
    r"(?:publish\w+|conduct\w+|perform\w+|carried\s+out|undertak\w+)\b",
    re.I,
)

# Result-assertion markers — consulted ONLY after a descriptive frame is ruled out, so a result word
# inside the object of "investigated" never forces `finding`.
_RESULT = re.compile(
    r"|".join(
        [
            r"\bassociat(?:ed|ion)\s+with\b",
            r"\bcorrelat(?:ed|es|ion)\s+with\b",
            r"\b(?:relationship|association|correlation|difference|link)\s+between\b",
            r"\bthere\s+(?:is|are|was|were)\s+(?:a|an|no)\b",
            r"\blinked\s+to\b",
            r"\bpredict\w*\b",
            r"\brisk\s+factor\b",
            r"\bprodrome\b",
            r"\binfluenc\w+\b",
            r"\baffect(?:s|ed)\b",
            r"\bcontribut\w+\b",
            r"\bleads?\s+to\b",
            r"\bimplicat\w+\b",
            r"\b(?:higher|lower|greater|reduced|increased|decreased|elevated|diminished|smaller"
            r"|larger|fewer|poorer|worse|better|stronger|weaker|impaired|more|less)\b",
            r"\bthan\b",
            r"\bcompared\s+(?:to|with)\b",
            r"\bdoubl\w+|halv\w+|twice|[-\s]fold\b",
            r"\bno\s+(?:significant\s+)?(?:difference|association|correlation|effect|change"
            r"|relationship|differences)\b",
            r"\bsignifican\w*\b",
            r"\bp\s*[<=>]\s*0?\.\d",
            r"\b\d+(?:\.\d+)?\s*%\b",
        ]
    ),
    re.I,
)


def _normalize(text: str) -> str:
    """Collapse soft hyphens + PDF line-break hyphenation + whitespace so the rules see clean prose."""
    text = (text or "").replace("­", "").replace("‐", "-")
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)  # de-hyphenate a word split across a line
    return re.sub(r"\s+", " ", text).strip()


def _descriptive_frame(text: str) -> bool:
    return bool(_D1.search(text) or _D1b.search(text) or _D2.search(text) or _D3.search(text) or _D4.search(text))


def classify_responsiveness(
    claim_text: str,
    cited_chunk_types: Sequence[str | None] | None = None,
    cited_evidence_roles: Sequence[str | None] | None = None,
) -> Responsiveness:
    """Label an already-verified claim ``finding`` / ``descriptive`` / ``unknown``. Pure; no I/O.

    ``cited_chunk_types`` / ``cited_evidence_roles`` are reserved (see module docstring) and do not
    affect the v1 label — claim semantics decide, and evidence metadata may never manufacture a
    ``finding``.
    """
    text = _normalize(claim_text)
    if not text:
        return "unknown"
    reports_result = bool(_REPORT.search(text))
    if _descriptive_frame(text) and not reports_result:
        return "descriptive"
    if reports_result or _RESULT.search(text):
        return "finding"
    return "unknown"
