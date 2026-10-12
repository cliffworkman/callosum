"""PHASE 34 single-vocabulary experiment. UNWIRED AND TEST-ONLY: not a sufficiency semantics version.

``achieved_outcome_predicate`` forms candidates with ``attribution._RESULT_PREDICATE`` (mostly past-tense forms),
then asks the assertion classifier to join and classify them. The classifier recognises results with its own, wider
verb sets, so a sentence such as "We demonstrate X" never reaches it. This file holds the smallest experimental
variant in which candidate formation uses the classifier's own result and replication verb sets instead, with the
join, owner rules, support policy and projection left exactly as v8 has them.

Why it lives in a test module. The mapper, engine, span matcher and attribution module are byte-pinned by the
producer code manifest, and two static guards forbid any non-test module from naming the classifier or the span
matcher. A registered version would have to edit those pinned files. Nothing here does: the variant substitutes the
span matcher on the mapper module for the duration of one call, restores it afterwards, and is reachable from no
route. Its identity is deliberately not a supported semantics version, so nothing it produces can be consumed.

The controls record behaviour, including behaviour that blocks promotion (see the over-admission controls).
"""

import contextlib
import re
import types

import pytest

from experiments.ask_cli_revised import achieved_outcome_span as aos
from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import test_i4_2a_local_grounding as old
from experiments.ask_cli_revised.contract_directed import attribution as attr

EXPERIMENT_ID = "phase34-single-vocabulary-x1"
CLASSIFIER_RESULT_WORDS = tuple(sorted(aa._RESULT_VERBS | aa._REPLICATION_VERBS, key=lambda w: (-len(w), w)))
_PATTERN = re.compile(r"\b(?:" + "|".join(CLASSIFIER_RESULT_WORDS) + r")\b", re.IGNORECASE)


def find_matches(text):
    """``aos.find_achieved_outcome_matches`` with the classifier's verbs as the anchor set; segmentation unchanged."""
    out = []
    for ss, s_end in aos._sentence_spans(text):
        for cs, ce in aos._clause_spans(text, ss, s_end):
            raw = list(_PATTERN.finditer(text, cs, ce))
            if raw:
                out.extend(aos._segment_clause(text, cs, ce, raw, (ss, s_end)))
    return aos.AchievedOutcomeMatchSet(bool(out), tuple(out), any(m.ambiguous_with for m in out))


_SHIM = types.SimpleNamespace(find_achieved_outcome_matches=find_matches)


@contextlib.contextmanager
def experimental_vocabulary():
    """Offline only. Not re-entrant, not thread-safe: the mapper's matcher is swapped process-wide while open."""
    real = sm.aos
    sm.aos = _SHIM
    try:
        yield
    finally:
        sm.aos = real


def bind_current(units, diagnostics=None):
    return sm._bind_achieved_outcome_v7(
        old.SPEC, units, sibling_bindings={}, role_completion=old.FREE, diagnostics=diagnostics
    )


def bind_experimental(units, diagnostics=None):
    with experimental_vocabulary():
        return bind_current(units, diagnostics)


def decision(text, experimental=True):
    """(state, [(relation, kind, admissible, reasons)]) for one passage; ``no_candidate`` when nothing forms."""
    bindings = (bind_experimental if experimental else bind_current)([old.unit(text)])
    if not bindings:
        return "no_candidate", []
    return bindings[0]["state"], [
        (
            c["assertion_relation"],
            c["assertion_kind"],
            c["admissible"],
            tuple(c["support_policy_evaluation"]["reasons"]),
        )
        for c in bindings[0]["candidate_supports"]
    ]


OWNED_RESULT = ("filled", [("current_document", "result", True, ())])
UNOWNED_RESULT = ("missing", [("unresolved", "result", False, ("unresolved_non_synthetic",))])
PRIOR_RESULT = ("filled", [("attributed_external", "result", True, ())])
NO_CANDIDATE = ("no_candidate", [])


# ---- identity and containment ----


def test_experiment_is_not_a_semantics_version_and_current_is_unchanged():
    assert EXPERIMENT_ID not in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS
    assert se.SUFFICIENCY_SEMANTICS_VERSION == "sufficiency-semantics-v7"
    with pytest.raises(ValueError):
        se.require_supported_semantics_version(EXPERIMENT_ID)


def test_substitution_is_scoped_and_leaves_pinned_modules_untouched():
    pattern = attr._RESULT_PREDICATE
    with pytest.raises(RuntimeError), experimental_vocabulary():
        assert sm.aos is _SHIM
        raise RuntimeError
    assert sm.aos is aos and attr._RESULT_PREDICATE is pattern
    assert decision("We demonstrate the efficacy of the method.", experimental=False) == NO_CANDIDATE


def test_vocabulary_is_exactly_the_classifiers_own_sets():
    assert set(CLASSIFIER_RESULT_WORDS) == aa._RESULT_VERBS | aa._REPLICATION_VERBS
    assert set(CLASSIFIER_RESULT_WORDS) <= aa._PREDICATES


# ---- tense twins: the variant on a present-tense sentence must decide as v8 does on its past-tense twin ----

TWINS = [
    ("this_study", "We demonstrate the efficacy of the method.", "We demonstrated the efficacy of the method."),
    (
        "this_study",
        "We show that active design halves the samples.",
        "We showed that active design halved the samples.",
    ),
    (
        "unowned",
        "The simulation results show that error is lower.",
        "The simulation results showed that error was lower.",
    ),
    (
        "hypothesis",
        "We hypothesize that active design improves estimation.",
        "We hypothesized that design increased it.",
    ),
    ("proposed", "We propose a method that improves accuracy.", "We proposed a method that increased accuracy."),
    ("negated", "We do not find that active design improves it.", "We did not find that active design increased it."),
    (
        "prior_work",
        "Previous studies show that design improves it.",
        "Previous studies showed that design increased it.",
    ),
]


@pytest.mark.parametrize("category,present,past", TWINS)
def test_present_tense_decides_as_v8_decides_the_past_tense_twin(category, present, past):
    assert decision(present, experimental=False) == NO_CANDIDATE  # the vocabulary veto under audit
    assert decision(present) == decision(past, experimental=False)
    assert decision(past) == decision(past, experimental=False)  # already-recognised wording is unchanged


# ---- positive controls ----


@pytest.mark.parametrize(
    "text",
    [
        "We demonstrate the efficacy of the method.",
        "Our results show a two-fold reduction in estimation error.",
        "Here we show that active design improves estimation.",
        "The present study shows that active design improves estimation.",
        "We found that error was lower under active design.",
    ],
)
def test_owned_findings_are_admitted(text):
    assert decision(text) == OWNED_RESULT


# ---- negative controls ----


@pytest.mark.parametrize(
    "text,kind",
    [
        ("We hypothesize that active design improves estimation.", "aim_or_hypothesis"),
        ("We aim to show that active design improves estimation.", "aim_or_hypothesis"),
        ("We aimed to demonstrate a reduction in error.", "aim_or_hypothesis"),
        ("We propose a method that improves estimation accuracy.", "interpretation"),
    ],
)
def test_aims_hypotheses_and_proposals_are_not_findings(text, kind):
    state, candidates = decision(text)
    assert state == "missing" and [c[1:] for c in candidates] == [(kind, False, ("non_result_kind",))]


@pytest.mark.parametrize(
    "text",
    [
        "Active design may improve estimation accuracy.",
        "Active design could reduce the number of samples.",
        "If inputs are designed actively, estimation accuracy would improve.",
        "Future work will show whether the gain persists.",
    ],
)
def test_conditional_and_modal_statements_are_not_findings(text):
    state, candidates = decision(text)
    assert state == "missing" and all(not c[2] and "non_result_kind" in c[3] for c in candidates)


@pytest.mark.parametrize(
    "text",
    [
        "The results show a two-fold reduction in estimation error.",
        "The simulation results show that estimation error is lower.",
        "Optogenetics provides precise control of neural activity.",
        "Theory predicts that informative inputs reduce estimation error.",
        "Figure 3 shows the estimation error for each method.",
    ],
)
def test_a_recognised_verb_never_supplies_an_owner(text):
    """Background, theory, figure pointers and unowned result language stay excluded by the unchanged owner rule."""
    assert decision(text) == UNOWNED_RESULT


@pytest.mark.parametrize(
    "text",
    [
        "Previous studies show that active design improves estimation.",
        "Smith et al. (2020) demonstrate that active design reduces error.",
    ],
)
def test_prior_work_is_never_relabelled_as_this_study(text):
    """v8's default policy admits an attributed external result; the relation stays external, as for the past tense."""
    assert decision(text) == PRIOR_RESULT


def test_a_negated_result_keeps_its_negation_and_its_veto_marker():
    """Inherited from v8: a null result is a result. The verbatim text and the veto marker carry the negation."""
    candidate = bind_experimental([old.unit("We do not find that active design improves estimation.")])[0][
        "candidate_supports"
    ][0]
    assert candidate["exact_text"].startswith("We do not find")
    assert candidate["authority_veto"] == "negated_result_predicate"


# ---- documented limits: unchanged by this experiment ----


@pytest.mark.parametrize(
    "text",
    [
        "Active design: 2x fewer samples than random stimulation.",  # no verb
        "Estimation error was halved with active design.",  # verb in neither list
        "Our method yields a 1.5-2x reduction in required samples.",  # the classifier lists yield/yielded, not yields
        "We report a two-fold reduction in estimation error.",  # the classifier lists reported only
    ],
)
def test_results_without_a_listed_verb_form_remain_unsupported(text):
    assert decision(text) == NO_CANDIDATE


@pytest.mark.parametrize(
    "text",
    [
        "Estimation error was lower under active design.",
        "We identified three clusters of neurons.",
        "Neurons responded strongly in our recordings.",
        "We expected that error would fall.",
    ],
)
def test_old_only_forms_never_reached_admission_and_still_do_not(text):
    """Forms only the old pattern lists form a raw hit under v8 that the classifier cannot join. Nothing is lost."""
    assert decision(text, experimental=False) == NO_CANDIDATE and decision(text) == NO_CANDIDATE


# ---- over-admission: recorded as observed. These block promotion; they are not accepted behaviour. ----


@pytest.mark.parametrize(
    "text",
    [
        "We describe a new algorithm for input design.",
        "We provide open-source code for the method.",
        "We produce synthetic data from a linear model.",
        "Our model describes the dynamics of the population.",
        "We show the estimation error for each method in Figure 3.",
    ],
)
def test_known_defect_owned_method_statements_are_admitted_as_findings(text):
    """The classifier treats describe/provide/produce/show as result verbs whatever their object. The old pattern
    happened to exclude most of these; removing it exposes them. v8 forms no candidate for any of them."""
    assert decision(text, experimental=False) == NO_CANDIDATE
    assert decision(text) == OWNED_RESULT
