"""Synthetic, question-agnostic tests for each Phase-30 Step-2 rule. No q_aib vocabulary, no preserved artifact.

Vocabulary: "alpha", "beta", "gamma", "IAT"/"DG" stand in for any domain. Builders are reused from test_answer_plan.
"""

from __future__ import annotations

from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import test_answer_plan as fx
from experiments.ask_cli_revised.answer_plan import classify as cl
from experiments.ask_cli_revised.answer_plan import plan as pl
from experiments.ask_cli_revised.answer_plan import relations as rel
from experiments.ask_cli_revised.answer_plan import render as rd
from experiments.ask_cli_revised.answer_plan import source_metadata as sm
from experiments.ask_cli_revised.answer_plan import step2 as st
from experiments.ask_cli_revised.answer_plan import text as tx


def _units(smap, sealed):
    return rel.relation_units(smap, sealed, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION)


def _attach(mapped, sealed):
    rw.attach_relation_witnesses(mapped, sealed, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION)


def _witness(requirement, instance, proposition_by_id):
    return rw.witness_instance(
        requirement, instance, proposition_by_id, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
    )


def _run(props, spans, smap, nodes, facet_ids, role_ids, labels=None):
    srcs = fx.sealed(props, spans)
    over = fx.overlay_for(nodes, facet_ids, role_ids)
    plan = pl.build_plan(
        srcs,
        smap,
        over,
        scoped_final={},
        inputs={"test": True},
        containment_semantics=se.SUFFICIENCY_SEMANTICS_VERSION,
        direction_semantics=se.SUFFICIENCY_SEMANTICS_VERSION,
        labels=labels,
    )
    props_by_id = {row["proposition_id"]: row for row in props}
    return plan, props_by_id


def _single(quote, *, spans_text=None, labels=None, rid="r::one", extra_reqs=None, paper=1):
    props = [fx.prop("p1", paper, quote)]
    spans = [{"paper_id": paper, "span_id": "s1", "text": spans_text or quote, "chunk_id": 1}]
    req = fx.requirement(rid, ["rv"], [fx.instance("k1", {"rv": fx.binding("p1", quote, supporting=["p1"])})])
    smap = {"c1": {"child_id": "c1", "requirements": [req] + (extra_reqs or [])}}
    return _run(props, spans, smap, fx.one_node("c1"), [rid] + [r["id"] for r in (extra_reqs or [])], ["rv"], labels)


def _layer1(plan, props):
    return rd.render_layer1(plan, props, set())


def _check(plan, layer1, props, name):
    return next(c for c in rd.invariant_report(plan, layer1, props) if c["check"] == name)


# ---------------------------------------------------------------- A. disclosure consolidation


def test_facets_sharing_a_state_are_worded_in_one_sentence_and_every_state_is_kept():
    req_a = fx.requirement("r::a", ["rv"], [])
    req_b = fx.requirement("r::b", ["rv"], [])
    smap = {"c1": {"child_id": "c1", "requirements": [req_a, req_b]}}
    plan, _ = _run([], [], smap, fx.one_node("c1"), ["r::a", "r::b"], ["rv"])
    node = plan["nodes"][0]
    sentences = [d for d in node["disclosures"] if "does not establish" in d]
    assert sentences == [
        "The retrieved evidence does not establish any of the following: phrase of r::a; phrase of r::b."
    ]
    # Layer 3 keeps each facet's own state and its own raw item: consolidation never merges the states.
    assert [f["state"] for f in node["facets"]] == ["not_established", "not_established"]
    assert [i["facet_id"] for i in node["layer3"]["disclosure_items"] if i["kind"] == "not_established"] == [
        "r::a",
        "r::b",
    ]


def test_a_single_unmet_facet_is_worded_alone_not_as_a_list():
    req_a = fx.requirement("r::a", ["rv"], [])
    smap = {"c1": {"child_id": "c1", "requirements": [req_a]}}
    plan, _ = _run([], [], smap, fx.one_node("c1"), ["r::a"], ["rv"])
    assert "The retrieved evidence does not establish phrase of r::a." in plan["nodes"][0]["disclosures"]


def test_generic_explanation_is_stated_once_per_answer_but_kept_in_every_items_layer_three_record():
    items = [{"kind": "reason", "text": pl.REASON_TEXT["attribution_prior_work"], "facet_id": "f", "code": "x"}]
    generic_shown: set = set()
    first = st._consolidate({"disclosure_items": items}, generic_shown, pointer=False)
    second = st._consolidate({"disclosure_items": items}, generic_shown, pointer=False)
    assert first == [pl.REASON_TEXT["attribution_prior_work"]]
    assert second == []
    assert items[0]["text"] == pl.REASON_TEXT["attribution_prior_work"]  # still recorded for Layer 2/3


# ---------------------------------------------------------------- B. paper-level qualification recall

QUOTE = "The alpha response correlated with beta outcomes."


def test_same_paper_limitation_is_attached_to_the_node_without_sharing_any_words():
    limit = "Our sample may not generalize beyond undergraduate students."
    plan, props = _single(QUOTE, spans_text=f"{QUOTE} {limit}")
    node = plan["nodes"][0]
    attached = node["layer2"]["limitations"]
    assert [e["text"] for e in attached] == [limit]
    assert attached[0]["shared_content_words"] == []  # attachment does not depend on shared words
    assert attached[0]["promoted"] is False
    assert any("generic limitation or scope cue" in why for why in attached[0]["why_attached"])
    assert limit not in _layer1(plan, props)


def test_limitation_from_another_paper_is_never_attached_to_this_nodes_evidence():
    limit = "Our sample may not generalize beyond undergraduate students."
    props = [fx.prop("p1", 1, QUOTE)]
    spans = [
        {"paper_id": 1, "span_id": "s1", "text": QUOTE, "chunk_id": 1},
        {"paper_id": 2, "span_id": "s9", "text": limit, "chunk_id": 9},
    ]
    req = fx.requirement("r::one", ["rv"], [fx.instance("k1", {"rv": fx.binding("p1", QUOTE, supporting=["p1"])})])
    plan, _ = _run(
        props, spans, {"c1": {"child_id": "c1", "requirements": [req]}}, fx.one_node("c1"), ["r::one"], ["rv"]
    )
    assert plan["nodes"][0]["layer2"]["limitations"] == []


def test_background_limitation_is_recorded_in_layer_three_and_never_attached():
    prior = "Previous studies reported limitations of the alpha response with beta outcomes."
    plan, _ = _single(QUOTE, spans_text=f"{QUOTE} {prior}")
    node = plan["nodes"][0]
    assert node["layer2"]["limitations"] == []
    decisions = node["layer3"]["limitation_decisions"]
    assert any(str(d["excluded"]).startswith("background") for d in decisions)


# ---------------------------------------------------------------- B2. promotion versus Layer-2-only


def test_standalone_limitation_that_directly_interprets_the_finding_is_promoted_to_layer_one():
    limit = "The alpha response correlated with beta outcomes may not generalize beyond undergraduate samples."
    plan, props = _single(QUOTE, spans_text=f"{QUOTE} {limit}")
    text_out = _layer1(plan, props)
    assert "may not generalize beyond undergraduate samples" in text_out
    promoted = [s for s in plan["nodes"][0]["statements"] if s["kind"] == "qualification_sentence"]
    assert promoted and promoted[0]["prop_ids"] == []
    assert _check(plan, text_out, props, "verbatim_from_passage:" + promoted[0]["claim_id"])["passed"]


def test_truncated_limitation_is_attached_for_the_reader_but_never_promoted():
    cut = "The alpha response correlated with beta outcomes may not generalize beyond"
    plan, props = _single(QUOTE, spans_text=f"{QUOTE} {cut}")
    entry = plan["nodes"][0]["layer2"]["limitations"][0]
    assert entry["promoted"] is False
    assert entry["not_promoted_reason"] == "not closed and complete on its own"
    assert "may not generalize beyond" not in _layer1(plan, props)


def test_limitation_referring_back_to_these_findings_is_promoted_only_when_closed():
    text = "These findings may not generalize beyond undergraduate samples."
    entry = {
        "text": text,
        "norm": tx.normalized_key(text),
        "paper_id": 1,
        "span_id": "s1",
        "span_text": text,
        "edits": [],
    }
    st._promotion(entry, [], {}, set())
    if not tx.closure_failures(text):
        assert entry["promoted"] is True
        assert "refers back to the paper's own findings" in entry["promotion_basis"]
    else:
        assert entry["promoted"] is False
        assert entry["not_promoted_reason"] == "not closed and complete on its own"


# ---------------------------------------------------------------- C. grounded acronym expansion


def test_first_layer_one_use_of_a_defined_acronym_is_expanded_from_its_same_paper_definition_only_once():
    spans = [
        {
            "paper_id": 1,
            "span_id": "s1",
            "text": "We used the Implicit Association Test (IAT) for alpha.",
            "chunk_id": 1,
        },
    ]
    ctx = cl.Ctx(
        props={},
        span_texts_by_paper={},
        generic_map={},
        facet_terms={},
        facet_phrases={},
        direction_semantics=se.SUFFICIENCY_SEMANTICS_VERSION,
    )
    ctx.span_rows = spans
    node = {
        "statements": [
            {"text": "IAT scores rose for alpha.", "paper_id": 1, "prop_ids": [], "edits": [], "claim_id": "a"},
            {"text": "IAT scores fell for beta.", "paper_id": 1, "prop_ids": [], "edits": [], "claim_id": "b"},
        ]
    }
    introduced, grounded = {}, set()
    st._ground_node(node, ctx, introduced, grounded)
    assert node["statements"][0]["text"] == "Implicit Association Test (IAT) scores rose for alpha."
    assert node["statements"][0]["edits"][0]["kind"] == "acronym_expansion_introduced"
    assert node["statements"][0]["edits"][0]["span_id"] == "s1"
    assert node["statements"][1]["text"] == "IAT scores fell for beta."  # later uses stay bare
    assert grounded == {"IAT"}


def test_an_acronym_with_no_explicit_definition_is_never_expanded():
    ctx = cl.Ctx(
        props={},
        span_texts_by_paper={},
        generic_map={},
        facet_terms={},
        facet_phrases={},
        direction_semantics=se.SUFFICIENCY_SEMANTICS_VERSION,
    )
    ctx.span_rows = [{"paper_id": 1, "span_id": "s1", "text": "DG scores rose for alpha.", "chunk_id": 1}]
    node = {"statements": [{"text": "DG scores rose for alpha.", "paper_id": 1, "prop_ids": [], "edits": []}]}
    grounded: set = set()
    st._ground_node(node, ctx, {}, grounded)
    assert node["statements"][0]["text"] == "DG scores rose for alpha."
    assert "DG" not in grounded


def test_a_definition_that_exists_only_in_another_papers_text_is_reported_but_not_applied():
    ctx = cl.Ctx(
        props={},
        span_texts_by_paper={},
        generic_map={},
        facet_terms={},
        facet_phrases={},
        direction_semantics=se.SUFFICIENCY_SEMANTICS_VERSION,
    )
    ctx.span_rows = [
        {"paper_id": 2, "span_id": "s9", "text": "We used the Implicit Association Test (IAT).", "chunk_id": 9},
    ]
    node = {"statements": [{"text": "IAT scores rose for alpha.", "paper_id": 1, "prop_ids": [], "edits": []}]}
    st._ground_node(node, ctx, {}, set())
    assert node["statements"][0]["text"] == "IAT scores rose for alpha."
    record = st._definition_record("IAT", {1}, ctx)
    assert record["long_form"] is None
    assert record["other_paper_span_ids"] == ["s9"]
    assert "another paper" in record["why"]


def test_an_unexpanded_parenthetical_acronym_fails_the_grounding_check():
    props = {"p1": fx.prop("p1", 1, QUOTE)}
    plan, _ = _single(QUOTE)
    text_out = _layer1(plan, props) + " Stray text (DG)."
    assert _check(plan, text_out, props, "parenthetical_acronyms_are_grounded")["passed"] is False


# ---------------------------------------------------------------- D. source labels


def test_citeproc_style_labels_follow_author_count_and_fall_back_to_neutral():
    assert sm.label_for(1, {"authors": ["Workman"], "year": 2021})["narrative"] == "Workman (2021)"
    assert sm.label_for(1, {"authors": ["Workman", "Doe"], "year": 2021})["narrative"] == "Workman and Doe (2021)"
    assert sm.label_for(1, {"authors": ["Workman", "Doe"], "year": 2021})["parenthetical"] == "(Workman & Doe, 2021)"
    assert sm.label_for(1, {"authors": ["Workman", "Doe", "Roe"], "year": 2021})["narrative"] == "Workman et al. (2021)"
    neutral = sm.label_for(14, None)
    assert neutral["neutral"] is True and neutral["narrative"] == "Source 14"


def test_colliding_labels_receive_citeproc_year_suffixes_in_paper_order():
    extract = {
        "papers": {
            "2": {"authors": ["Workman", "Doe", "Roe"], "year": 2021},
            "1": {"authors": ["Workman", "Doe", "Roe"], "year": 2021},
        }
    }
    labels = sm.labels_for(extract, [2, 1])
    assert labels[1]["list"] == "Workman et al., 2021a"
    assert labels[2]["list"] == "Workman et al., 2021b"


def test_layer_one_source_list_uses_metadata_labels_and_never_paper_numbers():
    labels = sm.labels_for({"papers": {"1": {"authors": ["Workman", "Doe"], "year": 2021}}}, [1])
    plan, props = _single(QUOTE, labels=labels)
    text_out = _layer1(plan, props)
    assert "[1] Workman & Doe, 2021, page 1." in text_out
    assert "Paper 1" not in text_out
    assert _check(plan, text_out, props, "layer1_uses_source_labels_not_paper_numbers")["passed"]


# ---------------------------------------------------------------- E. Layer 1 / Layer 2 / Layer 3 separation


def test_layer_one_fixed_text_carries_no_layer_three_vocabulary_and_layer_two_explains_each_limitation():
    limit = "Our sample may not generalize beyond undergraduate students."
    plan, props = _single(QUOTE, spans_text=f"{QUOTE} {limit}")
    text_out = _layer1(plan, props)
    assert _check(plan, text_out, props, "layer1_fixed_text_has_no_layer3_vocabulary")["passed"]
    layer2 = rd.render_layer2(plan, props)
    assert "Attached because" in layer2 and "Not stated in Layer 1" in layer2
    assert "p1" not in layer2.split() and "::" not in layer2


def test_layer_three_records_plan_hash_disagreements_and_every_claim_role():
    plan, props = _single(QUOTE)
    audit = rd.render_layer3(plan, {"authorization_sha256": "x"})
    assert plan["plan_sha256"] in audit and "claim_ids" not in audit.split("\n")[0]
    assert "## Claim roles" in audit


# ---------------------------------------------------------------- F/G. determinism and the full plan


def test_step_two_plan_is_deterministic_with_labels_present():
    labels = sm.labels_for({"papers": {"1": {"authors": ["Workman", "Doe"], "year": 2021}}}, [1])
    limit = "Our sample may not generalize beyond undergraduate students."
    first, _ = _single(QUOTE, spans_text=f"{QUOTE} {limit}", labels=labels)
    second, _ = _single(QUOTE, spans_text=f"{QUOTE} {limit}", labels=labels)
    assert first["plan_sha256"] == second["plan_sha256"]
    assert first["step2"] == second["step2"]


def test_layer_one_word_count_is_measured_on_the_body_only():
    text_out = "# Answer\n\n**1. Q?**\n\n*Answered.*\n\nThe alpha beta result[1].\n\n## Sources\n\n[1] Workman, 2021.\n"
    assert rd.layer1_body_words(text_out) == 8
