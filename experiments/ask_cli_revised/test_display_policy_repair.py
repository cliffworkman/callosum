"""The two display corrections (answer_plan.display_corrections), on sentences taken verbatim from the October 12 sealed evidence.

Pure checks; no model and no I/O. The value-level before/after on the full sealed ledger is a recorded
counterfactual, not a test, because the ledger is a run artifact.
"""

from experiments.ask_cli_revised.answer_plan import classify as cl
from experiments.ask_cli_revised.answer_plan import display_corrections as lp

AMYGDALA = (
    "Across these levels of organization, the specific amygdala response to facial anomalies correlated with "
    "stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and "
    "less prosociality toward people with facial anomalies."
)
AMYGDALA_CLAUSE = AMYGDALA.split(", ", 1)[1]
SHARED = (
    "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a "
    "universal pathogen avoidance byproduct hypothesis."
)
WE_SUGGEST = (
    "We suggest that dehumanization is underpinned by a suite of negative attitudes (IAT and EBQ), all factors "
    "associated with the functioning of the left amygdala."
)
PREDICTION = "This hypothesis predicts that anomalous and attractive faces will implicate the dACC."
PRIOR = (
    "Recent work with functional magnetic resonance imaging has implicated certain neuroanatomic structures when "
    "viewing others with facial anomalies."
)
TRUNCATED = "However, Hadza who regularly interact with outside cultural groups were more likely to think Hadza with"


def _attempt(sentence, quote=None):
    ctx = cl.Ctx(
        props={"p": {"quote": quote or sentence, "paper_id": 1}},
        span_texts_by_paper={},
        generic_map={},
        facet_terms={},
        facet_phrases={},
        direction_semantics="sufficiency-semantics-v8",
    )
    return lp.qualified_result_not_aim(cl.evaluate_sentence(sentence, "p", ctx, []), quote or sentence)


def test_qualified_result_is_not_withheld_as_an_aim_and_stays_verbatim():
    attempt = _attempt(SHARED)
    assert attempt["ok"] and attempt["attribution"] == "this_study_result"
    assert any(c["check"] == "attribution_qualified_result" for c in attempt["checks"])
    assert "suggest" in attempt["sentence"]  # the hedge is displayed, not removed


def test_author_interpretation_prediction_and_prior_work_keep_their_classification():
    assert "attribution_aim_or_hypothesis" in _attempt(WE_SUGGEST)["reasons"]
    assert "attribution_aim_or_hypothesis" in _attempt(PREDICTION)["reasons"]
    assert "attribution_prior_work" in _attempt(PRIOR)["reasons"]


def test_results_language_does_not_rescue_a_stated_aim_or_prediction():
    assert not lp.qualified_result_not_aim(
        {"reasons": ["attribution_aim_or_hypothesis"], "checks": [], "ok": False},
        "We predicted that the results would show a difference.",
    )["ok"]


def test_truncated_passage_stays_restricted():
    assert "passage_complete" in _attempt(TRUNCATED)["reasons"]


def test_whole_amygdala_sentence_is_still_not_referentially_closed():
    assert _attempt(AMYGDALA)["reasons"] == ["referentially_closed"]
    assert _attempt(AMYGDALA_CLAUSE, quote=AMYGDALA)["ok"]


def test_narrowing_is_allowed_only_when_the_removed_words_condition_nothing():
    assert lp.removed_text_is_immaterial(AMYGDALA, AMYGDALA_CLAUSE) == "Across these levels of organization,"
    for sentence in (
        "Although these effects were not significant, the response correlated with beliefs.",
        "In these patients only, the response correlated with beliefs.",
        "Among these participants, the response may have differed, and the response correlated with beliefs.",
        "Because of these results, the response correlated with beliefs.",
    ):
        clause = "the response correlated with beliefs."
        assert lp.removed_text_is_immaterial(sentence, clause) is None, sentence
    assert lp.removed_text_is_immaterial(AMYGDALA, "a clause that is not in the sentence") is None


def test_a_clause_that_itself_refers_outside_stays_restricted():
    sentence = "In addition, these effects correlated with beliefs."
    assert "referentially_closed" in _attempt("these effects correlated with beliefs.", quote=sentence)["reasons"]
