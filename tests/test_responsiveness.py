"""Unit tests for the inc-582 verified-claim responsiveness classifier (pure, no DB/model/provider).

The ship priority is *false descriptive demotions ≈ 0* (never label a genuine finding "descriptive").
False negatives (a descriptive claim landing as finding/unknown) are acceptable. These fixtures are the
real regression cases surfaced by today's broad Ask runs plus the protected examples the classifier must
never demote.
"""

from __future__ import annotations

import pytest

from app.backend.summarization.responsiveness import classify_responsiveness

# ---- required case matrix (plan §Tests 1-7) ------------------------------------------------------

DESCRIPTIVE = [
    # 1. thin title / research-activity paraphrase
    "Research has investigated cerebral glucose metabolism in late-life depression through longitudinal studies.",
    # 2. "were analyzed" table-caption framing (nominalized analysis subject)
    "Correlations between fasting serum glucose and cerebral glucose metabolism have been analyzed.",
    "Comparisons of cerebral glucose metabolism relative to baseline have also been made between patients and controls.",
    # 3. "this study investigates/examines" framing
    "This study investigates structural imaging in late-life depression.",
    "This study examined amygdala responses to anomalous faces.",
    # research-activity frame with result vocabulary only as the OBJECT of the activity verb
    "Research has investigated the relationship between facial proportionality and perceived character traits.",
    "Research on the anomalous-is-bad stereotype was published in a peer-reviewed journal.",
    "Research has explored the association between hippocampal volume, memory, and cortisol status in depression.",
    "Studies examining late-life depression and cognitive function have employed magnetic resonance imaging.",
]

FINDING = [
    # 4. genuine directional caption finding (must NOT be demoted just for being a caption)
    "Higher amyloid burden was observed in late-life depressed patients.",
    "Greater beta-amyloid deposition has been observed in late-life depressed patients compared to healthy controls.",
    "There is a relationship between gray matter volumes and total CVLT scores.",
    # 5. substantive body-prose finding
    "Proportionality in facial features influences the attribution of negative personality traits.",
    # 6. epidemiological finding
    "One meta-analysis suggested that depression doubles the risk of developing Alzheimer's disease later in life.",
    "Late-life depression is associated with a higher rate of relapse compared to younger depressed individuals.",
    # a "this study" sentence that actually REPORTS a result -> finding (reporting verb overrides the frame)
    "This study found greater amygdala responses to anomalous faces.",
]

UNKNOWN = [
    # 7. uncertain wording, neither a research-activity frame nor a stated result -> fail open
    "The serotonin system is a logical focus for neurobiological studies in late-life depression.",
    "",
    "   ",
]


@pytest.mark.parametrize("claim", DESCRIPTIVE)
def test_descriptive_framing_is_descriptive(claim: str) -> None:
    assert classify_responsiveness(claim) == "descriptive"


@pytest.mark.parametrize("claim", FINDING)
def test_substantive_findings_are_never_demoted(claim: str) -> None:
    # the fatal error is a finding -> descriptive demotion; assert it never happens for these.
    assert classify_responsiveness(claim) == "finding"


@pytest.mark.parametrize("claim", UNKNOWN)
def test_uncertain_fails_open_to_unknown(claim: str) -> None:
    assert classify_responsiveness(claim) == "unknown"


def test_evidence_metadata_never_manufactures_a_finding() -> None:
    # A descriptive claim stays descriptive even when its cited evidence is body_prose + scientific
    # (correction #2: claim semantics are primary; evidence must not force a finding).
    claim = "This study examined amygdala responses to anomalous faces."
    assert classify_responsiveness(claim, ["body_prose"], ["scientific"]) == "descriptive"
    assert classify_responsiveness(claim, ["caption"], ["scientific"]) == "descriptive"


def test_reporting_verb_overrides_research_activity_frame() -> None:
    # "This study examined X" (activity) vs "This study found X" (reports a result).
    assert classify_responsiveness("This study examined the effect of citalopram.") == "descriptive"
    assert classify_responsiveness("This study found that citalopram reduced symptoms.") == "finding"


def test_result_vocabulary_inside_the_object_does_not_flip_to_finding() -> None:
    # "relationship between" is a result word, but here it is the OBJECT of "investigated" -> descriptive.
    assert classify_responsiveness("Research investigated the relationship between X and Y.") == "descriptive"
    # whereas asserting the relationship directly is a finding
    assert classify_responsiveness("There is a relationship between X and Y.") == "finding"
