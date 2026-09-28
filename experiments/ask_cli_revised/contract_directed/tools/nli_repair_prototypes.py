"""PROTOTYPE module for `NLI_REPAIR_DESIGN.md` (2026-09-28) -- NOT wired into production. Nothing here is
imported by `overview.py`, `overview_guards.py`, `app/backend/summarization/verification.py`, or
`partial_answer_renderer.py`; nothing here makes a network, model, or NLI call. This module exists to make the
design's two proposed mechanisms concrete and testable, not to implement them.

Wiring either function into production is a separate, explicitly-authorized implementation pass -- see the
design doc's "Recommended implementation order."

---

## 1. Citation-metadata boundary (design doc Section 2)

`strip_redundant_unit_markers` separates an inline unit-citation marker (e.g. " (U1)", " (U2, U3)") from the
text an NLI scorer is given, WITHOUT ever modifying the raw text a researcher sees. It strips a marker ONLY
when it is unambiguous: a trailing parenthetical containing exactly the proposal's own structured `unit_ids`
(as a set, no foreign or missing ids, no duplicates) and nothing else. Every other shape -- embedded mid-
sentence, a subset/superset of `unit_ids`, containing prose, referencing an id not in `unit_ids` -- is left
completely untouched; this function never guesses.

Motivating minimal pair (`nli-boundary-diagnostic-001`, pairs A/B): the SAME source-faithful c9 statement
scored support=0.8109 without a trailing marker and support=0.2352 with " (U1)" appended -- see the module-level
test for the exact acceptance fixture, checked with zero inference.

## 2. A premise-reliability disposition (design doc Section 3)

`disposition` adds a third possible proposal status, `INDETERMINATE`, alongside today's `GROUNDED`/`WITHHELD`
(the exact strings `overview.py`'s `screen_proposals` already uses -- see the compatibility test). It is
triggered ONLY by a separate self-entailment reliability probe on the PREMISE (never by the candidate's own
support/contradiction score), mirroring `nli-boundary-diagnostic-002`'s finding: c9's premise self-entails at
~0.99; c11's fails at 0.007/0.981. `SELF_ENTAILMENT_SUPPORT_FLOOR` below is an explicit PLACEHOLDER, not a
calibrated production value -- see the design doc for why calibrating it needs a separately authorized,
larger, labeled evaluation this prototype does not attempt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------------------------------------------
# 1. Citation-metadata boundary
# ---------------------------------------------------------------------------------------------------------------

# A trailing parenthetical containing ONLY comma-separated "U<digits>" tokens, immediately before at most one
# closing punctuation mark, at the very end of the string. Deliberately narrow: does not match a parenthetical
# containing prose (e.g. " (see above)"), one not at the end of the text, or one mixing a unit token with other
# content (e.g. " (U1, p. 4)").
_TRAILING_MARKER = re.compile(r"\s*\((U\d+(?:,\s*U\d+)*)\)([.!?]?)\s*$")

MARKER_NONE = "none"
MARKER_STRIPPED = "stripped_matches_unit_ids"
MARKER_AMBIGUOUS = "ambiguous_left_untouched"


@dataclass(frozen=True)
class MarkerStripResult:
    nli_hypothesis_text: str  # what a scorer should be given -- == raw_text whenever nothing was stripped
    raw_text: str  # ALWAYS the untouched input; never modified; this is what a researcher/audit sees
    stripped_marker: str | None  # the exact substring removed (e.g. " (U1)"), or None
    marker_outcome: str  # one of MARKER_NONE / MARKER_STRIPPED / MARKER_AMBIGUOUS


def strip_redundant_unit_markers(text: str, unit_ids: list[str]) -> MarkerStripResult:
    match = _TRAILING_MARKER.search(text)
    if match is None:
        return MarkerStripResult(text, text, None, MARKER_NONE)
    marker_ids = [tok.strip() for tok in match.group(1).split(",")]
    if len(marker_ids) != len(set(marker_ids)) or set(marker_ids) != set(unit_ids):
        # Duplicate token, or the marker's ids don't exactly match unit_ids (subset, superset, or a foreign
        # id) -- ambiguous. Do not guess; leave the text exactly as the model wrote it.
        return MarkerStripResult(text, text, None, MARKER_AMBIGUOUS)
    trailing_punct = match.group(2) or ""
    stripped_span = match.group(0)
    stripped_text = text[: match.start()] + trailing_punct
    removed = stripped_span[: len(stripped_span) - len(trailing_punct)] if trailing_punct else stripped_span
    return MarkerStripResult(stripped_text, text, removed, MARKER_STRIPPED)


# ---------------------------------------------------------------------------------------------------------------
# 2. Premise-reliability disposition
# ---------------------------------------------------------------------------------------------------------------

# The exact strings `overview.py`'s screen_proposals already assigns (`record["status"] = "withheld" if
# record["reasons"] else "grounded"`) -- reused verbatim, never renamed, so wiring this in only ADDS a third
# value rather than changing what either existing one means.
GROUNDED = "grounded"
WITHHELD = "withheld"
INDETERMINATE = "indeterminate"

# PLACEHOLDER. Not a calibrated production threshold -- see NLI_REPAIR_DESIGN.md Section 3.
SELF_ENTAILMENT_SUPPORT_FLOOR = 0.5


@dataclass(frozen=True)
class ReliabilityProbe:
    """One premise's self-entailment score: (premise, premise) through the SAME scorer/pair-shape production
    uses for the real (premise, candidate) pair -- never the candidate's own score."""

    self_support: float
    self_contradiction: float | None


def probe_is_reliable(probe: ReliabilityProbe, *, floor: float = SELF_ENTAILMENT_SUPPORT_FLOOR) -> bool:
    return probe.self_support >= floor


def disposition(
    *,
    candidate_support: float,
    candidate_contradiction: float,
    probe: ReliabilityProbe,
    support_threshold: float,
    contradiction_threshold: float,
) -> tuple[str, list[str]]:
    """``(status, reasons)``. Reliability is checked FIRST, using only the probe -- the candidate's own score is
    never consulted until the premise has already passed the reliability floor. Once past that gate, the
    decision order (contradiction-before-support) exactly mirrors `overview_guards.nli_reasons` -- see the
    compatibility test asserting this reproduces its real output for every historical score pair with a
    reliable premise."""
    if not probe_is_reliable(probe):
        return INDETERMINATE, [f"nli_unreliable_premise:self_support={probe.self_support:.2f}"]
    if candidate_contradiction >= contradiction_threshold and candidate_contradiction > candidate_support:
        return WITHHELD, [f"nli_contradicted:{candidate_contradiction:.2f}"]
    if candidate_support < support_threshold:
        return WITHHELD, [f"nli_low_support:{candidate_support:.2f}"]
    return GROUNDED, []
