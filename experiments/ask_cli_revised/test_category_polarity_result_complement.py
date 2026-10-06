"""Phase 33 / I2-1b: result-complement authority for the pure, unwired polarity classifier.

Review decision (recorded in the results artifact): `found that <C>` and `found to <C>` are RESULT-COMPLEMENT INTRODUCERS.
They are not finding predicates themselves. The complement must independently establish its classification:
an authoritative finding predicate inside the complement -> positive; the existing local-null rule -> null; otherwise
unknown (a result is reported, but its implication cannot be determined). The result-noun structure (P2) applies only
when `found` does not begin a complement.

Expectations in this file were written BEFORE the I2-1b classifier change and frozen. Explicit review revisions to two
I2-1a holdout expectations (H05, H17) are recorded in REVIEW_REVISIONS, not as classifier bugs.
"""

from __future__ import annotations

import pytest

from experiments.ask_cli_revised import category_polarity as cp

POS, NUL, MEN, UNK = cp.POSITIVE, cp.NULL, cp.MENTIONED, cp.UNKNOWN

# Explicit post-I2-1a review decisions. The I2-1a frozen expectation is superseded; it is kept in
# test_category_polarity_hardening.py for audit. These are NOT classifier bugs found after implementation.
REVIEW_REVISIONS = {
    "H05": ("The effect of stress was found to be small.", "stress", "positive (I2-1a) -> unknown (I2-1b review)"),
    "H17": ("Stress was found to be unrelated to recall.", "stress", "positive (I2-1a) -> unknown (I2-1b review)"),
}

FOUND_THAT = [
    ("T-A-predicted", "We found that stress predicted recall.", "stress", (), POS),
    ("T-B-associated", "We found that stress was associated with recall.", "stress", (), POS),
    ("T-C-in-database", "We found that stress was in the database.", "stress", (), UNK),
    ("T-D-measured", "We found that stress was measured.", "stress", (), UNK),
    ("T-E-negative", "We found that stress was negative.", "stress", (), UNK),
    ("T-F-not-significant", "We found that stress was not significant.", "stress", (), NUL),
    (
        "T-G-no-significant-association",
        "We found that no significant association with stress was observed.",
        "stress",
        (),
        NUL,
    ),
]

FOUND_TO = [
    ("O-A-predict", "Stress was found to predict recall.", "stress", (), POS),
    ("O-B-associated", "Stress was found to be associated with recall.", "stress", (), POS),
    ("O-C-increase", "Stress was found to increase recall.", "stress", (), POS),
    ("O-D-unrelated", "Stress was found to be unrelated to recall.", "stress", (), UNK),
    ("O-E-effect-small", "The effect of stress was found to be small.", "stress", (), UNK),
    ("O-F-negative", "Stress was found to be negative.", "stress", (), UNK),
    ("O-G-measured", "Stress was found to be measured.", "stress", (), UNK),
    ("O-H-not-significantly-affect", "Stress was found to not significantly affect recall.", "stress", (), NUL),
]

PRECEDENCE_P1_P2 = [
    # P2 (result-noun head, no complement) keeps its authority where `found` begins no complement.
    ("P2-evidence-of", "Evidence of stress was found.", "stress", (), POS),
    ("P2-association-with", "An association with stress was found.", "stress", (), POS),
    ("P2-significant-effect-of", "A significant effect of stress was found.", "stress", (), POS),
    ("P2-large-effect-of", "A large effect of stress was found.", "stress", (), POS),
    # P2 locative exclusion.
    ("P2-locative-archive", "Evidence of stress was found in the archive.", "stress", (), MEN),
    # Null precedence over P2.
    ("P2-null-no-association", "No association with stress was found.", "stress", (), NUL),
    # P1 precedence: a result-noun head does not rescue a found-to complement.
    ("P1-over-P2-effect-small", "The effect of stress was found to be small.", "stress", (), UNK),
]

# NEW FROZEN HOLDOUT (complement-specific). Frozen before the I2-1b classifier change; reported once after it.
HOLDOUT_COMPLEMENT = [
    ("CH01-found-that-reduced", "We found that stress reduced recall.", "stress", (), POS),
    ("CH02-found-that-assessed", "We found that stress was assessed in the sample.", "stress", (), UNK),
    ("CH03-found-that-large", "We found that stress was large.", "stress", (), UNK),
    ("CH04-found-to-correlate", "Stress was found to correlate with recall.", "stress", (), POS),
    ("CH05-found-to-be-correlated", "Stress was found to be correlated with recall.", "stress", (), POS),
    ("CH06-found-to-be-weak", "Stress was found to be weak.", "stress", (), UNK),
    ("CH07-found-to-be-independent", "Stress was found to be independent of recall.", "stress", (), UNK),
    ("CH08-p2-large-effect", "A large effect of stress was found.", "stress", (), POS),
    ("CH09-p2-locative", "Evidence of stress was found in the archive.", "stress", (), MEN),
    ("CH10-null-inside-found-that", "We found that no significant effect of stress was observed.", "stress", (), NUL),
    ("CH11-found-that-reduced-by", "We found that recall was reduced by stress.", "stress", (), POS),
    ("CH12-found-to-be-recorded", "Stress was found to be recorded in the database.", "stress", (), UNK),
    (
        "CH13-predicate-before-introducer",
        "Stress predicted sleep, and we found that recall was high.",
        "stress",
        (),
        UNK,
    ),
    ("CH14-found-to-increase", "Stress was found to increase recall.", "stress", (), POS),
    (
        "CH15-found-that-then-clause-null",
        "We found that stress was in the sample, and that the effect was not significant.",
        "stress",
        (),
        UNK,
    ),
    (
        "CH16-found-that-positive-then-contrast-negation",
        "We found that stress predicted recall, but the effect was not significant.",
        "stress",
        (),
        UNK,
    ),
]


@pytest.mark.parametrize("case", FOUND_THAT, ids=[c[0] for c in FOUND_THAT])
def test_found_that_is_an_introducer_not_authority(case):
    cid, text, term, competing, expected = case
    result = cp.classify_category_observation(text, term, competing_terms=competing)
    assert result["observation_polarity"] == expected, (cid, result["rule"], result["ambiguity"])


@pytest.mark.parametrize("case", FOUND_TO, ids=[c[0] for c in FOUND_TO])
def test_found_to_is_an_introducer_not_authority(case):
    cid, text, term, competing, expected = case
    result = cp.classify_category_observation(text, term, competing_terms=competing)
    assert result["observation_polarity"] == expected, (cid, result["rule"], result["ambiguity"])


@pytest.mark.parametrize("case", PRECEDENCE_P1_P2, ids=[c[0] for c in PRECEDENCE_P1_P2])
def test_p1_precedence_and_p2_narrowness(case):
    cid, text, term, competing, expected = case
    result = cp.classify_category_observation(text, term, competing_terms=competing)
    assert result["observation_polarity"] == expected, (cid, result["rule"], result["ambiguity"])


def test_review_revisions_are_documented_and_superseded_expectations_are_kept():
    from experiments.ask_cli_revised import test_category_polarity_hardening as hardening

    holdout = {row[0]: row for row in hardening.HOLDOUT}
    assert holdout["H05-found-to-be-small"][4] == POS  # original I2-1a frozen expectation kept for audit
    assert holdout["H17-found-to-be-unrelated"][4] == POS
    assert set(REVIEW_REVISIONS) == {"H05", "H17"}


def test_found_to_be_adjective_is_never_positive_without_a_finding_predicate():
    for text, term in (
        ("Stress was found to be unrelated to recall.", "stress"),
        ("The effect of stress was found to be small.", "stress"),
    ):
        assert cp.classify_category_observation(text, term)["observation_polarity"] == UNK, text


def test_result_introducer_is_recorded_in_the_audit_output():
    result = cp.classify_category_observation("We found that stress predicted recall.", "stress")
    # The audit text keeps the sentence-final period, as every other clause field does (format, not polarity).
    assert result["result_complement"] == "that stress predicted recall."
    result = cp.classify_category_observation("Evidence of stress was found.", "stress")
    assert result["result_complement"] is None
