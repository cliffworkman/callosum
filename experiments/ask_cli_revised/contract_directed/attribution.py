"""Who does a passage attribute a statement to? (own finding / another study / speculation / unresolved)

Section labels are provenance CLUES, not judgments: an Introduction can preview the present study's findings and a Discussion
can report them, while a Discussion or Introduction can equally recount another study. So attribution is derived from what the
sentence itself says, by explicit deterministic cues; the model's provenance label may only *downgrade* (never upgrade) the
result, and uncertainty is a first-class state that is preserved, never resolved by guessing.

States: own_established | other_study | speculation | mixed | unresolved.
A unit closes a first-hand-finding obligation only when its state is `own_established`.

Own-study bases (any one): an explicit first-person/this-study cue; reported test statistics; or a result statement that also
appears in the paper's OWN abstract (an authors' summary of their own work) and reports a result with no contrary cue.
"""

from __future__ import annotations

import re

from app.backend.pdf_processing.extraction import canonical_text_contains

_FLAGS = re.IGNORECASE

_OWN_VERBS = (
    r"found|observed|show(?:ed|n)?|report(?:ed)?|test(?:ed)?|examined|measured|assess(?:ed)?|recruit(?:ed)?|present(?:ed)?|"
    r"ask(?:ed)?|conduct(?:ed)?|replicat(?:ed)?|identif(?:ied)?|demonstrat(?:ed)?|detect(?:ed)?|used|administer(?:ed)?|"
    r"collect(?:ed)?|compar(?:ed)?|analy[sz](?:ed)?|pool(?:ed)?|obtain(?:ed)?|record(?:ed)?|manipulat(?:ed)?|expos(?:ed)?|"
    r"describ(?:ed)?|confirm(?:ed)?|ran|performed|extend(?:ed)?|investigat(?:ed)?"
)
_OWN = [
    re.compile(rf"\bwe\s+(?:also\s+|further\s+|then\s+|first\s+|next\s+|thus\s+|now\s+)?(?:{_OWN_VERBS})\b", _FLAGS),
    re.compile(
        r"\b(?:this|the present|the current|present|current|our)\s+"
        r"(?:study|studies|research|paper|work|experiment|experiments|analysis|investigation|article|manuscript|"
        r"meta-analysis|review|sample|data|findings|results|participants)\b",
        _FLAGS,
    ),
    re.compile(
        r"\b(?:these|the)\s+(?:results|findings|data)\s+(?:suggest|show|indicate|demonstrate|reveal|confirm|provide)\b",
        _FLAGS,
    ),
    re.compile(r"\bparticipants\s+(?:\w+ed|were|had|did|made|chose|saw|rated|took|gave|held)\b", _FLAGS),
]
_INTERPRETATION = [
    re.compile(r"\bwe\s+(?:suggest|propose|speculate|hypothesi[sz]e|argue|believe|posit|conjecture|contend)\b", _FLAGS)
]
_PRIOR = [
    re.compile(
        r"\b(?:previous|prior|earlier|past|recent|existing|other)\s+"
        r"(?:studies|study|research|work|reports?|findings|literature|evidence|investigations?|papers|experiments)\b",
        _FLAGS,
    ),
    re.compile(
        r"\b(?:has|have)\s+(?:been\s+)?(?:shown|found|reported|demonstrated|suggested|documented|established)\b", _FLAGS
    ),
    re.compile(r"\b[A-Z][A-Za-z\-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z\-]+|\s+et\s+al\.?),?\s*\(?\d{4}[a-z]?\)?"),
    re.compile(r"\baccording to\b", _FLAGS),
    re.compile(r"\b(?:was|were)\s+(?:reported|shown|found|demonstrated)\s+(?:by|in)\b", _FLAGS),
]
_HEDGE = re.compile(
    r"\b(?:might|may|could|would|possibly|perhaps|potentially|should|hypothesi[sz]ed|theori[sz]ed|proposed|speculat\w*)\b",
    _FLAGS,
)
_STATISTICS = re.compile(
    r"(?:\b[pP]\s*[<=>≤≥]\s*\.?\d|\bβ\s*=|\b[tFrzZ]\s*(?:\(\d+(?:,\s*\d+)?\))?\s*=\s*[−\-–]?\d|\bSE\s*=\s*\d|"
    r"\bN\s*=\s*\d|\bn\s*=\s*\d|\bd\s*=\s*[−\-–]?\d|\bOR\s*=\s*\d|\bR2\s*=|\b\d+(?:\.\d+)?\s*%|\bCI\b)"
)
_RESULT_PREDICATE = re.compile(
    r"\b(?:correlated|demonstrated|showed|found|revealed|identified|replicated|chose|rated|expected|predicted|differed|"
    r"responded|exhibited|reported|detected|observed|increased|decreased|associated|were\s+(?:more|less|subjected)|"
    r"was\s+(?:greater|lower|higher|stronger|weaker|sensitive))\b",
    _FLAGS,
)

OWN_ESTABLISHED = "own_established"
OTHER_STUDY = "other_study"
SPECULATION = "speculation"
MIXED = "mixed"
UNRESOLVED = "unresolved"

_MODEL_NON_OWN = frozenset({"recounts_other_study", "background_generic", "hypothesis_or_speculation"})


def detect_cues(text: str) -> dict:
    """Explicit attribution cues found in `text` (each list holds the matched phrases, in order)."""
    return {
        "own": [m.group(0) for p in _OWN for m in p.finditer(text)],
        "own_interpretation": [m.group(0) for p in _INTERPRETATION for m in p.finditer(text)],
        "prior": [m.group(0) for p in _PRIOR for m in p.finditer(text)],
        "hedge": [m.group(0) for m in _HEDGE.finditer(text)],
    }


def has_statistics(text: str) -> bool:
    return bool(_STATISTICS.search(text))


def in_abstract(text: str, abstract_clean: str | None) -> bool:
    if not abstract_clean or not text.strip():
        return False
    return canonical_text_contains(needle=text.strip(), haystack=abstract_clean)


def derive_attribution(
    texts: list[str],
    *,
    abstract_clean: str | None = None,
    model_class: str | None = None,
    basis_phrase: str | None = None,
    section: str | None = None,
) -> dict:
    """Attribution of the statement carried by `texts` (the establishing units' display texts).

    `section` is recorded only as an informational flag; it never changes the state.
    """
    joined = " ".join(t.strip() for t in texts if t.strip())
    cues = detect_cues(joined)
    bases: list[str] = []
    if cues["own"]:
        bases.append("explicit_own_cue")
    if has_statistics(joined):
        bases.append("result_statistics")
    if texts and all(in_abstract(t, abstract_clean) for t in texts) and _RESULT_PREDICATE.search(joined):
        bases.append("authors_abstract_result_statement")

    prior, hedge, interpretation = cues["prior"], cues["hedge"], cues["own_interpretation"]
    if bases and prior:
        state = MIXED
    elif prior:
        state = OTHER_STUDY
    elif interpretation and "result_statistics" not in bases:
        state = SPECULATION
    elif bases:
        state = OWN_ESTABLISHED
    elif hedge:
        state = SPECULATION
    else:
        state = UNRESOLVED

    flags: list[str] = []
    if state == OWN_ESTABLISHED and hedge:
        flags.append("hedged")
    if basis_phrase and not canonical_text_contains(needle=basis_phrase, haystack=joined):
        flags.append("model_basis_phrase_not_in_text")
    if state == OWN_ESTABLISHED and model_class in _MODEL_NON_OWN:
        state = UNRESOLVED
        flags.append("model_disagrees_with_cues")
    if model_class == "this_study_reports" and state in {OTHER_STUDY, SPECULATION, MIXED, UNRESOLVED}:
        flags.append("model_upgrade_refused")
    if section == "introduction" and state == OWN_ESTABLISHED:
        flags.append("own_claim_in_introduction_preview")
    if section in {"results", "discussion"} and state == OTHER_STUDY:
        flags.append("other_study_recital_in_" + section)
    return {"state": state, "bases": bases, "cues": cues, "flags": flags, "model_class": model_class}
