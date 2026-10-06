"""Phase 33 / I2-1: pure observation-polarity classifier (unwired).

The expectations below were written from the approved Phase-33 audit BEFORE the classifier was implemented or run.
Three tiers:

- APPROVED: the audit matrix (rows A-P), the adversarial minimal pairs, and the cross-domain twins. These encode the
  written semantic contract and are asserted as hard requirements.
- INVARIANTS: determinism, JSON serialisability, case handling, sentence scope, valence/measurement/hedge isolation,
  repeated-term behaviour, and the unwired static guards.
- RESIDUAL: a generated battery whose expectations are the intuitive reading. These are NOT asserted. The results
  report records every mismatch with the lexical item responsible; they are not tuned away.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from experiments.ask_cli_revised import category_polarity as cp

HERE = Path(__file__).resolve().parent

POS, NUL, MEN, UNK = cp.POSITIVE, cp.NULL, cp.MENTIONED, cp.UNKNOWN

# (id, text, term, competing_terms, expected polarity)
APPROVED_MATRIX = [
    ("A-null", "Treatment reduced pain, but not significantly.", "pain", (), NUL),
    ("A-pos", "Treatment significantly reduced pain.", "pain", (), POS),
    ("B-null", "Building type was measured, but no association with wellbeing was found.", "building type", (), UNK),
    ("B-pos", "Building type predicted wellbeing.", "building type", (), POS),
    ("C-null", "Word category was tested but did not significantly affect recall.", "word category", (), UNK),
    ("C-pos", "Word category significantly affected recall.", "word category", (), POS),
    ("D-val", "Participants expressed negative evaluations of the buildings.", "negative evaluations", (), POS),
    ("D-val-term", "Participants expressed negative evaluations of the buildings.", "negative", (), POS),
    ("D-val2", "The buildings were negative.", "negative", (), MEN),
    ("E-proc", "Participants did not complete the second questionnaire.", "questionnaire", (), MEN),
    (
        "F-p36-explicit",
        "Participants expressed explicit biases against people with facial anomalies, but their implicit biases were "
        "slight and not significant.",
        "explicit",
        ("implicit",),
        POS,
    ),
    (
        "F-p36-implicit",
        "Participants expressed explicit biases against people with facial anomalies, but their implicit biases were "
        "slight and not significant.",
        "implicit",
        ("explicit",),
        NUL,
    ),
    ("G", "The treatment did not increase the outcome.", "treatment", (), UNK),
    ("H", "The treatment may not have significantly reduced pain.", "pain", (), NUL),
    ("I", "Treatment reduced pain. Participants did not respond to the second survey.", "pain", (), POS),
    ("J-null", "No significant association between stress and sleep was found.", "stress", (), NUL),
    ("J-pos", "Stress predicted sleep.", "stress", (), POS),
    ("K", "The treatment was not without effect.", "treatment", (), UNK),
    ("L", "The treatment not only increased the outcome but also improved sleep.", "treatment", (), UNK),
    ("M", "No studies have examined the outcome.", "outcome", (), MEN),
    ("N-measured", "Word category was measured.", "word category", (), MEN),
    ("N-assessed", "Word category was assessed.", "word category", (), MEN),
    ("N-included", "Word category was included in the analysis.", "word category", (), MEN),
    ("O", "The treatment reduced pain, but the effect on nausea was not significant.", "pain", (), UNK),
    ("P", "Participants showed no significant difference in recall.", "recall", (), NUL),
]

ADVERSARIAL_PAIRS = [
    ("pair-A-assoc", "Stress was associated with sleep.", "stress", (), POS),
    ("pair-A-null-assoc", "No association between stress and sleep was found.", "stress", (), NUL),
    ("pair-B-observed", "Negative evaluations were observed.", "evaluations", (), POS),
    ("pair-B-valence-only", "Evaluations were negative.", "evaluations", (), MEN),
    ("pair-C-measured", "Sleep was measured.", "sleep", (), MEN),
    ("pair-C-found-to-predict", "Word category was found to predict recall.", "word category", (), POS),
    ("pair-D-did-not-predict", "Building type did not predict wellbeing.", "building type", (), UNK),
    (
        "pair-D-no-predictive-effect",
        "No predictive effect of building type on wellbeing was found.",
        "building type",
        (),
        NUL,
    ),
    ("pair-E-hedged-pos", "Stress may predict sleep.", "stress", (), POS),
    ("pair-E-hedged-null", "Stress may not significantly predict sleep.", "stress", (), NUL),
    ("pair-F-not-only", "Building type was not only significant but large.", "building type", (), UNK),
    (
        "pair-G-no-leak",
        "Stress predicted sleep. The effect on recall was not significant.",
        "stress",
        (),
        POS,
    ),
]

CROSS_DOMAIN = [
    ("xd-agri-pos", "Fertilizer increased crop yield.", "crop yield", (), POS),
    ("xd-agri-null", "Fertilizer did not significantly increase crop yield.", "crop yield", (), NUL),
    ("xd-agri-unknown", "Fertilizer did not increase crop yield.", "crop yield", (), UNK),
    (
        "xd-edu-contrast-attached",
        "Tutoring improved algebra scores, whereas homework showed no significant effect.",
        "algebra scores",
        ("homework",),
        POS,
    ),
    (
        "xd-edu-contrast-unattached",
        "Tutoring improved algebra scores, whereas homework showed no significant effect.",
        "algebra scores",
        (),
        UNK,
    ),
    (
        "xd-materials-null",
        "Tensile strength was measured, and the coating was not significantly different.",
        "coating",
        (),
        NUL,
    ),
    ("xd-materials-unknown", "The coating did not change tensile strength.", "coating", (), UNK),
    ("xd-lang-pos", "Recall differed by word category.", "word category", (), POS),
    (
        "xd-clin-unknown-carry",
        "Drug X reduced anxiety scores, but the effect on sleep was not significant.",
        "anxiety",
        (),
        UNK,
    ),
]

# Residual battery: expectations are the intuitive reading, NOT asserted. Mismatches are reported.
RESIDUAL_BATTERY = [
    ("R1-lowered", "Drug X lowered anxiety scores.", "anxiety", (), POS),
    ("R2-did-not-lower", "Drug X did not lower anxiety scores.", "anxiety", (), UNK),
    ("R3-not-associated", "Drug X was not associated with anxiety scores.", "anxiety", (), NUL),
    ("R4-significant-alone", "Stress was significant.", "stress", (), POS),
    ("R5-found-in-database", "The sample was found in the database.", "sample", (), MEN),
    ("R6-and-clause-null", "Anxiety predicts sleep and stress was not significant.", "stress", (), NUL),
    ("R7-not-reduced-by", "Anxiety was not reduced by sleep.", "anxiety", (), UNK),
    ("R8-did-not-find", "Participants did not find stress.", "stress", (), UNK),
    ("R9-two-negations", "Stress was not measured and was not significant.", "stress", (), UNK),
    ("R10-not-spurious", "The effect was significant and not spurious.", "effect", (), POS),
    ("R11-linked-procedural", "Stress was low and not reliably linked to sleep.", "stress", (), UNK),
    ("R12-but-not-nausea", "Sleep was affected, but not stress.", "sleep", (), POS),
    ("R13-raised-then-contrast", "Fertilizer raised yields, whereas irrigation did not.", "fertilizer", (), POS),
    ("R14-was-significant-only", "Building type was significant.", "building type", (), POS),
    ("R15-to-predict-procedural", "The model was used to predict sleep.", "model", (), MEN),
]

ALL_HARD = APPROVED_MATRIX + ADVERSARIAL_PAIRS + CROSS_DOMAIN


def _classify(text, term, competing=()):
    return cp.classify_category_observation(text, term, competing_terms=competing)


@pytest.mark.parametrize("case", ALL_HARD, ids=[c[0] for c in ALL_HARD])
def test_approved_matrix_pairs_and_cross_domain_expectations(case):
    cid, text, term, competing, expected = case
    result = _classify(text, term, competing)
    assert result["observation_polarity"] == expected, (cid, result["rule"], result["ambiguity"])


def test_contrary_finding_is_reserved_and_never_emitted():
    emitted = {_classify(text, term, comp)["observation_polarity"] for _, text, term, comp, _ in ALL_HARD}
    emitted |= {_classify(text, term)["observation_polarity"] for _, text, term, _, _ in RESIDUAL_BATTERY}
    assert cp.CONTRARY_RESERVED not in emitted
    assert emitted <= {POS, NUL, MEN, UNK}


def test_output_is_deterministic_json_serialisable_and_score_free():
    for _, text, term, comp, _ in ALL_HARD:
        first = _classify(text, term, comp)
        second = _classify(text, term, comp)
        assert first == second
        encoded = json.dumps(first, sort_keys=True)
        assert json.loads(encoded) == first
        assert not any(isinstance(v, float) for v in first.values())
        keys = set(first)
        assert not keys & {"confidence", "score", "probability"}


def test_letter_case_alone_does_not_change_polarity():
    for _, text, term, comp, _ in ALL_HARD[:12]:
        base = _classify(text, term, comp)["observation_polarity"]
        assert _classify(text.upper(), term.upper(), comp)["observation_polarity"] == base
        assert _classify(text.lower(), term.lower(), comp)["observation_polarity"] == base


def test_unrelated_sentence_negation_does_not_change_a_term_result():
    positive = "Stress predicted sleep."
    assert _classify(positive, "stress")["observation_polarity"] == POS
    with_negated_neighbour = positive + " Participants did not respond to the survey."
    assert _classify(with_negated_neighbour, "stress")["observation_polarity"] == POS
    neighbour_first = "Participants did not respond to the survey. " + positive
    assert _classify(neighbour_first, "stress")["observation_polarity"] == POS


def test_adding_a_valence_word_alone_cannot_make_mentioned_positive():
    base = "Stress was measured."
    assert _classify(base, "stress")["observation_polarity"] == MEN
    for valence in ("negative", "positive", "higher", "lower", "more", "less"):
        assert _classify(f"{base[:-1]} as {valence}.", "stress")["observation_polarity"] == MEN, valence


def test_adding_a_measurement_verb_alone_cannot_make_mentioned_positive():
    for measure in ("measured", "assessed", "included", "recruited", "administered", "collected", "tested", "used"):
        text = f"Stress was {measure}."
        assert _classify(text, "stress")["observation_polarity"] == MEN, measure


def test_adding_a_local_finding_predicate_can_make_positive():
    assert _classify("Stress was measured.", "stress")["observation_polarity"] == MEN
    assert _classify("Stress was measured and predicted sleep.", "stress")["observation_polarity"] == POS


def test_procedural_negation_cannot_become_null_merely_because_of_not():
    cases = [
        ("Participants did not complete the second questionnaire.", "questionnaire"),
        ("Participants did not attend the session.", "session"),
        ("Stress was not recorded in the first wave.", "stress"),
    ]
    for text, term in cases:
        result = _classify(text, term)
        assert result["observation_polarity"] != NUL, text


def test_hedge_toggle_alone_does_not_change_polarity():
    plain = _classify("Stress predicted sleep.", "stress")
    hedged = _classify("Stress may have predicted sleep.", "stress")
    assert plain["observation_polarity"] == hedged["observation_polarity"] == POS
    assert plain["hedge"] is False and hedged["hedge"] is True
    null_plain = _classify("Stress had no significant effect on sleep.", "stress")
    null_hedged = _classify("Stress may have had no significant effect on sleep.", "stress")
    assert null_plain["observation_polarity"] == null_hedged["observation_polarity"] == NUL


def test_absence_statement_is_scope_not_null():
    result = _classify("No studies have examined the outcome.", "outcome")
    assert result["observation_polarity"] == MEN
    assert result["absence_statement"] is True


def test_repeated_term_occurrences_are_reported_not_selected():
    text = "Anxiety was measured. Anxiety predicted sleep."
    result = _classify(text, "anxiety")
    assert result["observation_polarity"] == UNK
    assert result["rule"] == "repeated_term_occurrence"
    assert result["term_occurrences"] == 2
    assert [o["observation_polarity"] for o in result["occurrence_results"]] == [MEN, POS]


def test_absent_term_is_unknown_with_an_explicit_reason():
    result = _classify("Stress predicted sleep.", "wellbeing")
    assert result["observation_polarity"] == UNK
    assert result["rule"] == "term_absent"
    assert result["term_occurrences"] == 0


def test_empty_term_is_refused():
    with pytest.raises(ValueError):
        _classify("Stress predicted sleep.", "   ")


def test_module_is_pure_and_has_no_version_or_domain_authority():
    source = (HERE / "category_polarity.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        for alias in (node.names if isinstance(node, (ast.Import, ast.ImportFrom)) else [])
    }
    assert "experiments.ask_cli_revised.sufficiency_engine" not in imported
    assert not re.search(r"SUFFICIENCY_SEMANTICS|PLAN_VERSION", source)
    assert not re.search(r"\bopen\(|requests|httpx|urllib|socket|subprocess", source)
    lowered = source.lower()
    for domain_word in (
        "amygdala",
        "facial",
        "anomal",
        "stereotype",
        "bias",
        "attitude",
        "prosocial",
        "wellbeing",
        "recall",
    ):
        assert domain_word not in lowered, domain_word


def test_module_is_not_imported_by_any_production_path():
    base = HERE
    offenders = []
    for path in base.rglob("*.py"):
        if "__pycache__" in path.parts or path.name in {"category_polarity.py", "test_category_polarity.py"}:
            continue
        if "category_polarity" in path.read_text(encoding="utf-8"):
            offenders.append(path.name)
    assert offenders == [], offenders
