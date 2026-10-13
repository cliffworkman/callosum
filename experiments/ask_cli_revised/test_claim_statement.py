"""The verified claim as the answer's statement, on claim/quotation pairs taken verbatim from the October 12 sealed run.

Pure checks; no model and no I/O.
"""

from experiments.ask_cli_revised import layerc_presentation as lp
from experiments.ask_cli_revised.answer_plan import classify as cl
from experiments.ask_cli_revised.answer_plan import disclosure_v5 as dv5
from experiments.ask_cli_revised.answer_plan import display_corrections as dc
from experiments.ask_cli_revised.answer_plan import render_v5

AMYGDALA_Q = (
    "Across these levels of organization, the specific amygdala response to facial anomalies correlated with "
    "stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and "
    "less prosociality toward people with facial anomalies."
)
AMYGDALA_C = (
    "The specific amygdala response to facial anomalies correlates with stronger just-world beliefs, less "
    "dispositional empathic concern, and less prosociality toward people with facial anomalies."
)
DEHUMANIZATION_Q = (
    "We suggest that dehumanization is underpinned by a suite of negative attitudes (IAT and EBQ), social cognitive "
    "biases (just-world beliefs), emotional dispositions (affective empathy), and undesirable behaviors (less "
    "generosity in the DG)."
)
DEHUMANIZATION_C = (
    "The 'anomalous-is-bad' stereotype is underpinned by negative attitudes measured via IAT and EBQ, social "
    "cognitive biases involving just-world beliefs, emotional dispositions regarding affective empathy, and "
    "undesirable behaviors characterized by less generosity in the DG."
)
HEDGED_Q = (
    "These findings suggest that exposure-based storytelling can alter automatic evaluations of individuals with "
    "facial anomalies and may offer a promising, scalable approach to reducing stigma."
)
HEDGED_C = "Exposure-based storytelling alters automatic evaluations of individuals with facial anomalies."
PROSOCIAL_Q = (
    "This research confirmed earlier reports that people with anomalous faces are imbued with negative personality "
    "characteristics, detected explicit biases against people with facial anomalies, and described a behavioral "
    "manifestation of the anomalous-is-bad stereotype affecting prosociality."
)
PROSOCIAL_C = "The 'anomalous-is-bad' stereotype manifests behaviorally as reduced prosociality."
HADZA_Q = (
    "However, Hadza who regularly interact with outside cultural groups were more likely to think Hadza with facial "
    "scarring were less moral and were better"
)
HADZA_C = (
    "Hadza individuals who regularly interact with outside cultural groups are more likely to perceive Hadza people "
    "with facial scarring as less moral."
)
PRIOR_Q = "Laypersons with high levels of implicit bias toward those with facial anomalies demonstrated increased amygdala reactivity.6"
PRIOR_C = "Laypersons with high levels of implicit bias toward those with facial anomalies demonstrated increased amygdala reactivity."


def test_faithful_claim_may_stand_for_its_sentence_and_unfaithful_ones_may_not():
    assert dc.claim_statement_reasons(AMYGDALA_C, AMYGDALA_Q) == []
    assert dc.claim_statement_reasons(HADZA_C, HADZA_Q) == []
    assert "hedge_dropped" in dc.claim_statement_reasons(DEHUMANIZATION_C, DEHUMANIZATION_Q)  # and a changed referent
    assert "hedge_dropped" in dc.claim_statement_reasons(HEDGED_C, HEDGED_Q)
    assert any(r.startswith("direction_word") for r in dc.claim_statement_reasons(PROSOCIAL_C, PROSOCIAL_Q))
    assert dc.claim_statement_reasons(None, AMYGDALA_Q) == ["no_claim_text"]


def test_a_citation_marker_is_not_truncation():
    assert dc.ends_at_citation_marker(PRIOR_Q) and dc.ends_at_citation_marker("particularly the amygdala.6,34")
    assert not dc.ends_at_citation_marker(HADZA_Q) and not dc.ends_at_citation_marker("was observed in 2006")


def _records(kind="result", relation="current_document", *, own=True, diagnostic=False):
    payload = {
        "assertion_kind": kind,
        "assertion_relation": relation,
        "aggregation": "non_synthetic_or_unspecified",
        "supporting_proposition_ids": ["p"],
    }
    meta = {"placement": {"child_id": "c", "requirement_id": "r"}, "payload": payload, "diagnostic_only": diagnostic}
    return {
        "support_views": {"v": {"support_ref": "s"}},
        "candidate_metadata_by_support": {"s": "m"} if own else {},
        "candidate_metadata": {"m": meta},
    }


PATH = {"establishment_refs": [{"ref": "v"}], "placement": {"child_id": "c", "requirement_id": "r", "role": "x"}}


def _attempt(sentence, quote):
    ctx = cl.Ctx(
        props={"p": {"quote": quote, "paper_id": 1}},
        span_texts_by_paper={},
        generic_map={},
        facet_terms={},
        facet_phrases={},
        direction_semantics="sufficiency-semantics-v8",
    )
    return cl.evaluate_sentence(sentence, "p", ctx, [])


def _settle(quote, claim, records, *, kind="evidence_slot", target=""):
    prop = {"proposition_id": "p", "quote": quote, "proposition_text": claim, "paper_id": 1}
    return lp._settle(_attempt(quote, quote), records, PATH, {"kind": kind}, prop, target)


def test_verified_claim_is_the_statement_and_the_sentence_stays_as_evidence():
    settled = _settle(AMYGDALA_Q, AMYGDALA_C, _records())
    assert settled["ok"] and settled["statement"] == AMYGDALA_C and settled["raw_sentence"] == AMYGDALA_Q
    assert "qualification" not in settled
    assert any(c["check"] == "referentially_closed_not_applied_to_verified_claim" for c in settled["checks"])


def test_unfaithful_claim_is_not_used_and_the_raw_sentence_rules_still_apply():
    settled = _settle(AMYGDALA_Q, "The amygdala causes reduced prosociality.", _records())
    assert "statement" not in settled and settled["claim_not_used"]
    assert settled["reasons"] == ["referentially_closed"] and not settled["ok"]


def test_a_literal_value_must_be_named_by_the_claim():
    settled = _settle(AMYGDALA_Q, AMYGDALA_C, _records(), kind="literal_value", target="just-world beliefs")
    assert settled["statement"] == AMYGDALA_C
    settled = _settle(AMYGDALA_Q, AMYGDALA_C, _records(), kind="literal_value", target="facial symmetry")
    assert "statement" not in settled and settled["claim_not_used"] == ["authorized_value_not_named"]


def test_truncated_evidence_is_shown_as_truncated():
    settled = _settle(HADZA_Q, HADZA_C, _records())
    assert settled["ok"] and settled["qualification"]["prefix"] == lp.TRUNCATED_PREFIX


def test_the_scientific_record_decides_attribution_when_it_exists():
    prior = _settle(PRIOR_Q, PRIOR_C, _records(relation="attributed_external"))
    assert prior["ok"] and prior["qualification"]["prefix"] == "The source reports prior evidence: "
    assert not _settle(PRIOR_Q, PRIOR_C, _records(kind="aim_or_hypothesis"))["ok"]
    interpretation = _settle(PRIOR_Q, PRIOR_C, _records(kind="interpretation"))
    assert interpretation["qualification"]["prefix"] == lp.INTERPRETATION_PREFIX
    # a record for the same requirement and proposition governs a sibling value that has none of its own
    sibling = _settle(PRIOR_Q, PRIOR_C, _records(relation="attributed_external", own=False))
    assert sibling["qualification"]["prefix"] == "The source reports prior evidence: "


def test_without_a_record_the_lexical_attribution_check_still_applies():
    records = _records(own=False, diagnostic=True)
    quote = "Recent work has implicated the amygdala when viewing others with facial anomalies."
    settled = _settle(quote, quote, records)
    assert "attribution_prior_work" in settled["reasons"] and not settled["ok"]


def test_prefix_function_matches_the_existing_qualifier():
    assert dv5.prefix_for("attributed_external", "x") == "The source reports prior evidence: "
    assert dv5.prefix_for("current_document", "x") == ""


def test_near_duplicate_claims_and_already_shown_sentences_are_not_printed_twice():
    full = {"text": AMYGDALA_C, "members": [{"n": 1}], "evidence": [AMYGDALA_Q]}
    subset = {
        "text": "The specific amygdala response to facial anomalies correlates with less prosociality toward people "
        "with facial anomalies.",
        "members": [{"n": 2}],
        "evidence": [AMYGDALA_Q],
    }
    raw = {"text": AMYGDALA_Q, "members": [{"n": 3}]}
    other = {"text": "Participants made more share decisions with the good partner.", "members": [{"n": 4}]}
    kept = render_v5._absorb([full, subset, raw, other])
    assert [e["text"] for e in kept] == [AMYGDALA_C, other["text"]]
    assert full["members"] == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_acronym_is_expanded_once_from_a_unique_sealed_definition():
    sealed = {
        "verified_propositions": [{"proposition_id": "p1", "paper_id": 248}, {"proposition_id": "p2", "paper_id": 20}],
        "evidence_spans": [
            {
                "paper_id": 248,
                "span_id": "e3",
                "text": "We developed the 'Normalizing Anomalies with Mobile Exposure' (NAME) intervention.",
            }
        ],
    }
    nodes = [
        {
            "statements": [
                {"text": "The NAME intervention reduced implicit bias.", "members": [{"proposition_id": "p1"}]},
                {"text": "The NAME intervention was brief.", "members": [{"proposition_id": "p1"}]},
                {"text": "PT decreased in AD patients.", "members": [{"proposition_id": "p2"}]},
            ]
        }
    ]
    lp.ground_acronyms(nodes, sealed)
    texts = [s["text"] for s in nodes[0]["statements"]]
    assert texts[0] == "The Normalizing Anomalies with Mobile Exposure (NAME) intervention reduced implicit bias."
    assert texts[1] == "The NAME intervention was brief." and texts[2] == "PT decreased in AD patients."
    assert nodes[0]["statements"][0]["edits"][0]["span_id"] == "e3"
