"""Phase 33 / I2-1a: precision hardening of the pure, unwired polarity classifier.

Expectations in this file were written from the I2-1 review decisions BEFORE any I2-1a classifier change was made or run:

- R10 (negation governs its null complement): hard requirements below.
- R5 (bare `found` is not positive authority): hard requirements below, including the narrow structural patterns.
- HOLDOUT: a new adversarial battery stressing procedural finding verbs, negation/complement order, coordination, and
  object-location versus result uses of `found`. Expectations are frozen here. It is REPORTED, not asserted, so the
  repaired classifier is not tuned against it.

Kept unchanged by the review (not asserted here, asserted in test_category_polarity.py): bare significance is
mentioned_only; `linked` is not a finding cue; contrast-unknown behaviour; no general `and` boundary.
"""

from __future__ import annotations

import re

import pytest

from experiments.ask_cli_revised import category_polarity as cp

POS, NUL, MEN, UNK = cp.POSITIVE, cp.NULL, cp.MENTIONED, cp.UNKNOWN

# R10: negation must govern the null complement.
R10_PAIRS = [
    ("R10-A-not-significant", "The effect was not significant.", "effect", (), NUL),
    # Prefer positive if the finding-predicate contract were met; the sentence has none, so mentioned is expected.
    ("R10-B-significant-and-not", "The effect was significant and not spurious.", "effect", (), MEN),
    ("R10-C-slight-and-not", "Implicit bias was slight and not significant.", "implicit bias", (), NUL),
    ("R10-D-no-difference", "Participants showed no significant difference in recall.", "recall", (), NUL),
    ("R10-E-no-association", "There was no association between stress and sleep.", "stress", (), NUL),
    # `not` must not pair with the earlier `significant`; the later `not robust` has no complement, so unknown.
    ("R10-F-significant-but-not", "The effect was significant but not robust.", "effect", (), UNK),
    # Two negation cues: the existing multiple-negation fail-closed rule.
    ("R10-G-two-negations", "The effect was not significant and not robust.", "effect", (), UNK),
]

# R5: bare `found` is not positive authority. Narrow structural result patterns are the only exception.
FOUND_PAIRS = [
    ("F1-location", "The sample was found in the database.", "sample", (), MEN),
    ("F2-archive", "The document was found in the archive.", "document", (), MEN),
    ("F3-we-found-that", "We found that stress predicted recall.", "stress", (), POS),
    ("F4-found-to-predict", "Stress was found to predict recall.", "stress", (), POS),
    ("F5-null-not-found-dependent", "No association with stress was found.", "stress", (), NUL),
    ("F6-evidence-of-was-found", "Evidence of stress was found.", "stress", (), POS),
    ("F7-researchers-found", "Researchers found stress.", "stress", (), MEN),
    ("F8-questionnaire-online", "The participant found the questionnaire online.", "questionnaire", (), MEN),
    ("F9-association-with-was-found", "An association with stress was found.", "stress", (), POS),
]

# HOLDOUT: frozen before the first run of the repaired classifier. Reported, not asserted.
HOLDOUT = [
    ("H01-samples-in-freezer", "Samples were found in the freezer.", "samples", (), MEN),
    ("H02-found-the-instructions", "Participants found the instructions confusing.", "instructions", (), MEN),
    ("H03-found-in-every", "Stress was found in every participant.", "stress", (), MEN),
    ("H04-found-the-data", "We found the data in the repository.", "data", (), MEN),
    ("H05-found-to-be-small", "The effect of stress was found to be small.", "stress", (), POS),
    ("H06-not-found-to-predict", "Stress was not found to predict recall.", "stress", (), UNK),
    ("H07-sample-found-period", "The database was searched and the sample was found.", "sample", (), MEN),
    ("H08-found-in-sample", "Stress and anxiety were found in the sample.", "stress", (), MEN),
    ("H09-significant-association-found", "A significant association with stress was found.", "stress", (), POS),
    ("H10-no-significant-association", "No significant association with stress was found.", "stress", (), NUL),
    ("H11-two-negations-found", "Stress was not associated and was not found to predict recall.", "stress", (), UNK),
    ("H12-and-not-spurious", "The effect was significant and not spurious.", "effect", (), MEN),
    ("H13-significant-found-in", "Stress was significant and found in the sample.", "stress", (), MEN),
    ("H14-strong-and-not-significant", "The association was strong and not significant.", "association", (), NUL),
    ("H15-not-significant-and-found", "Stress was not significant and was found to predict recall.", "stress", (), NUL),
    (
        "H16-recall-not-reduced-and-found",
        "Recall was not reduced, and stress was found to predict recall.",
        "recall",
        (),
        UNK,
    ),
    ("H17-found-to-be-unrelated", "Stress was found to be unrelated to recall.", "stress", (), POS),
    ("H18-researchers-found-that-not-sig", "Researchers found that stress was not significant.", "stress", (), NUL),
    ("H19-did-not-find", "We did not find stress in the sample.", "stress", (), UNK),
    (
        "H20-predicted-then-found-in",
        "Stress predicted recall, but the sample was found in the database.",
        "stress",
        (),
        POS,
    ),
    ("H21-findings-were-found", "The findings for stress were found in the archive.", "stress", (), MEN),
    ("H22-evidence-found-in-archive", "Evidence of stress was found in the archive.", "stress", (), MEN),
]


@pytest.mark.parametrize("case", R10_PAIRS, ids=[c[0] for c in R10_PAIRS])
def test_r10_negation_governs_its_null_complement(case):
    cid, text, term, competing, expected = case
    result = cp.classify_category_observation(text, term, competing_terms=competing)
    assert result["observation_polarity"] == expected, (cid, result["rule"], result["ambiguity"])


@pytest.mark.parametrize("case", FOUND_PAIRS, ids=[c[0] for c in FOUND_PAIRS])
def test_r5_bare_found_is_not_positive_authority(case):
    cid, text, term, competing, expected = case
    result = cp.classify_category_observation(text, term, competing_terms=competing)
    assert result["observation_polarity"] == expected, (cid, result["rule"], result["ambiguity"])


def test_r5_found_location_uses_are_never_positive():
    for cid, text, term, competing, _ in FOUND_PAIRS:
        if cid in {"F1-location", "F2-archive", "F7-researchers-found", "F8-questionnaire-online"}:
            result = cp.classify_category_observation(text, term, competing_terms=competing)
            assert result["observation_polarity"] != POS, cid


def test_holdout_battery_is_frozen_and_reported_not_asserted():
    """The holdout expectations are fixed above. This test only guarantees the battery is well-formed; the mismatch
    report is produced by the results run, with no assertion on individual rows."""
    assert len(HOLDOUT) == 22
    assert len({row[0] for row in HOLDOUT}) == len(HOLDOUT)


def test_hardening_keeps_bare_significance_mentioned_only():
    for text, term in (("Stress was significant.", "stress"), ("Building type was significant.", "building type")):
        assert cp.classify_category_observation(text, term)["observation_polarity"] == MEN, text


def test_hardening_keeps_linked_out_of_the_finding_lexicon():
    result = cp.classify_category_observation("Stress was low and not reliably linked to sleep.", "stress")
    assert result["observation_polarity"] != POS
    assert "linked" not in result["finding_cues"]


def test_hardening_adds_no_domain_vocabulary():
    source = open(cp.__file__, encoding="utf-8").read().lower()
    for word in ("amygdala", "facial", "anomal", "stereotype", "bias", "attitude", "prosocial", "wellbeing", "recall"):
        assert word not in source, word
    assert not re.search(r"SUFFICIENCY_SEMANTICS|PLAN_VERSION", source)
