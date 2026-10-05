"""Synthetic, question-agnostic fixtures for each Phase-30 Step-1 rule. No q_aib vocabulary, no preserved artifact.

Vocabulary: "alpha", "beta", "gamma" stand in for any domain. Each test states the rule it exercises.
"""

from __future__ import annotations

from experiments.ask_cli_revised.answer_plan import overlay as ov
from experiments.ask_cli_revised.answer_plan import plan as pl
from experiments.ask_cli_revised.answer_plan import render as rd
from experiments.ask_cli_revised.answer_plan import text as tx

# ---------------------------------------------------------------- builders


def prop(pid, paper, quote, span="s1", page=1):
    return {
        "proposition_id": pid,
        "paper_id": paper,
        "quote": quote,
        "proposition_text": quote,
        "evidence_span_id": span,
        "evidence_anchor_chunk_id": 1,
        "verification": {"status": "verified", "page_start": page},
    }


def binding(pid, text, *, source="model_mapping", supporting=None, state="filled"):
    provenance = {"candidate_source": source}
    if supporting:
        provenance["supporting_proposition_ids"] = list(supporting)
    return {"state": state, "proposition_id": pid, "exact_text": text, "provenance": provenance, "reason": None}


def instance(key, bindings, *, complete=True, direction=None):
    return {
        "instance_key": key,
        "complete": complete,
        "state": "filled" if complete else "partially_filled",
        "role_bindings": bindings,
        "direction_observations": direction or [],
        "effectiveness_observations": [],
    }


def requirement(
    rid,
    required,
    instances,
    *,
    quant="exists",
    kind="atomic",
    role_strategy="model_nomination_only",
    direction_summary=None,
    direction=None,
):
    return {
        "id": rid,
        "kind": kind,
        "instance_quantifier": quant,
        "quantifier_n": None,
        "multi_instance": len(instances) > 1,
        "role_completion": {"required_roles": list(required), "alternative_role_groups": [], "optional_roles": []},
        "role_specs": {
            r: {"category_description": f"category of {r}", "mapping_strategy": role_strategy} for r in required
        },
        "relationship_verifiers": ["same_proposition"],
        "parent_context_roles": [],
        "direction": direction,
        "effectiveness": None,
        "direction_summary": direction_summary,
        "instances": instances,
        "state": "partially_filled",
        "reason": None,
        "source_wording_span": "",
        "empty_result_semantically_allowed": False,
    }


def sealed(props, spans):
    return {"sealed_hash": "test", "verified_propositions": props, "evidence_spans": spans}


def overlay_for(nodes, facet_ids, role_ids):
    return {
        "status": ov.OVERLAY_STATUS,
        "postdates_phase28_attempt2_live_run": True,
        "confirmed_by": "test",
        "phase28_run_id": "test",
        "scope_statement": "synthetic test overlay",
        "nodes": nodes,
        "folded_child_ids": {},
        "facet_phrases": {fid: f"phrase of {fid}" for fid in facet_ids},
        "role_phrases": {rid: f"the {rid.replace('_', ' ')}" for rid in role_ids},
        "category_phrases": {},
        "requested_construct_terms": ["alpha"],
        "obligation_phrases": {"RC-9#scope:measures-of-behavior": "the choice of measures"},
    }


def one_node(child, label="1", literal="A synthetic question?", obligations=()):
    return [
        {
            "label": label,
            "parent": None,
            "nesting": "top_level",
            "literal_text": literal,
            "owning_child_ids": [child],
            "human_review_obligations": list(obligations),
        }
    ]


def build(props, spans, smap, nodes, facet_ids, role_ids, scoped=None):
    srcs = sealed(props, spans)
    over = overlay_for(nodes, facet_ids, role_ids)
    return pl.build_plan(srcs, smap, over, scoped_final=scoped or {}, inputs={"test": True}), srcs, over


def claims_by_role(plan):
    return {r["claim_id"]: r for r in plan["claim_roles"]}


def node_text(plan, label):
    node = next(n for n in plan["nodes"] if n["label"] == label)
    return " ".join(s["text"] for s in node["statements"]) + " " + " ".join(node["disclosures"])


# ---------------------------------------------------------------- text rules


def test_sentence_split_and_closure_rules():
    assert tx.split_sentences("One fact. Two fact! Three?") == ["One fact.", "Two fact!", "Three?"]
    assert "scope_phrase_refers_outside" in tx.closure_failures("Across these levels of organization, a thing held.")
    assert "pronoun_after_discourse_marker" in tx.closure_failures(
        "Accordingly, they should be interpreted cautiously."
    )
    assert tx.closure_failures("The alpha response correlated with beta outcomes.") == []


def test_self_reference_is_replaced_by_source_label_and_recorded():
    out, edit = tx.substitute_source_label("This research confirmed alpha reports.", "Paper 9")
    assert out == "Paper 9 confirmed alpha reports."
    assert edit["kind"] == "self_reference_to_source_label" and edit["from"] == "This research"


def test_run_in_heading_is_removed_and_recorded():
    rest, edit = tx.strip_run_in_heading("Specificity and generalization of effects We also observed alpha change.")
    assert rest == "We also observed alpha change."
    assert edit["kind"] == "run_in_heading_removed"


def test_caption_passage_is_detected_from_sealed_span_wording():
    spans = ["Table S1 | The alpha response correlated with beta outcomes."]
    assert tx.is_caption_passage("The alpha response correlated with beta outcomes.", spans)
    assert not tx.is_caption_passage("The alpha response correlated with beta outcomes.", ["unrelated text here."])


def test_display_joins_only_verified_hyphen_breaks_and_never_changes_meaning():
    corpus = {"attractiveness"}
    assert tx.display_text("the attrac- tiveness rating", corpus) == "the attractiveness rating"
    assert tx.display_text("anomalous-is- bad stereotype", corpus) == "anomalous-is-bad stereotype"


def test_acronym_definition_requires_an_explicit_definitional_pattern():
    spans = [{"paper_id": 1, "span_id": "s1", "text": "We used the Implicit Association Test (IAT) for alpha."}]
    hits = tx.definition_hits("IAT", spans)
    assert [h["long_form"] for h in hits] == ["Implicit Association Test"]
    assert tx.definition_hits("DG", spans) == []  # no definition: never expanded


def test_attribution_cues_are_lexical_and_never_guessed():
    assert tx.attribution_kind("We suggest that alpha is underpinned by beta.", False) == "aim_or_hypothesis"
    assert tx.attribution_kind("Previous studies reported alpha with beta.", False) == "prior_work"
    assert tx.attribution_kind("Alpha was found to exceed beta.", False) == "this_study_result"
    assert tx.attribution_kind("Alpha and beta appear together.", False) == "unknown"


# ---------------------------------------------------------------- relations and direction


def test_relation_witnessed_by_one_passage_is_primary_verbatim():
    props = [prop("p1", 1, "The alpha response correlated with beta outcomes.")]
    spans = [{"paper_id": 1, "span_id": "s1", "text": props[0]["quote"], "chunk_id": 1}]
    req = requirement(
        "r::rel",
        ["ra", "rb"],
        [
            instance(
                "k1",
                {
                    "ra": binding("p1", "alpha response", supporting=["p1"]),
                    "rb": binding("p1", "beta outcomes", supporting=["p1"]),
                },
            )
        ],
        kind="relational",
    )
    plan, _, _ = build(
        props, spans, {"c1": {"child_id": "c1", "requirements": [req]}}, one_node("c1"), ["r::rel"], ["ra", "rb"]
    )
    assert plan["nodes"][0]["facets"][0]["relation_status"] == "witnessed"
    assert "The alpha response correlated with beta outcomes." in node_text(plan, "1")
    assert plan["disagreements"] == []


def test_inherited_operand_without_joint_witness_is_not_claimable_and_is_recorded():
    props = [prop("p1", 1, "The alpha response was measured."), prop("p2", 1, "Beta outcomes were reported.")]
    spans = [{"paper_id": 1, "span_id": "s1", "text": " ".join(p["quote"] for p in props), "chunk_id": 1}]
    req = requirement(
        "r::rel",
        ["ra", "rb"],
        [
            instance(
                "k1",
                {
                    "ra": binding("p1", "alpha response", source="parent_context", supporting=["p1"]),
                    "rb": binding("p2", "Beta outcomes", supporting=["p2"]),
                },
            )
        ],
        kind="relational",
    )
    plan, _, _ = build(
        props, spans, {"c1": {"child_id": "c1", "requirements": [req]}}, one_node("c1"), ["r::rel"], ["ra", "rb"]
    )
    facet = plan["nodes"][0]["facets"][0]
    assert facet["relation_status"] == "unwitnessed_complete"
    assert "does not establish how" in " ".join(facet["disclosures"])
    assert plan["disagreements"] and plan["disagreements"][0]["answerplan_relation_witnessed"] is False


def test_direction_is_not_attached_to_a_witnessed_relation_when_the_sign_modifies_an_operand_object():
    props = [prop("p1", 1, "Explicit negative attitudes toward alpha were found with the beta questionnaire.")]
    spans = [{"paper_id": 1, "span_id": "s1", "text": props[0]["quote"], "chunk_id": 1}]
    key = "k1"
    summary = {
        "observed_values": ["negative"],
        "consensus_value": "negative",
        "has_within_instance_conflict": False,
        "has_across_instance_heterogeneity": False,
        "complete_instance_keys": [key],
        "instance_keys_with_observations": [key],
        "instance_keys_missing_observations": [],
        "conflicted_instance_keys": [],
    }
    req = requirement(
        "r::dir",
        ["ra", "rb"],
        [
            instance(
                key,
                {
                    "ra": binding("p0", "alpha", source="parent_context", supporting=["p0"]),
                    "rb": binding("p1", "beta questionnaire", supporting=["p1"]),
                },
                direction=[{"reported": True, "sign": "negative", "proposition_id": "p1", "exact_text": "negative"}],
            )
        ],
        kind="relational",
        direction={"reported": True},
        direction_summary=summary,
    )
    plan, _, _ = build(
        props, spans, {"c1": {"child_id": "c1", "requirements": [req]}}, one_node("c1"), ["r::dir"], ["ra", "rb"]
    )
    text_out = node_text(plan, "1")
    assert "A direction finding" not in text_out and "reported relationship" not in text_out
    # The section-7 witness realises the inherited referent "alpha", so the relation is witnessed. But the sign's grammatical
    # object is "attitudes", not the relation and not a named operand. I1b fails closed: no relation attachment and no
    # operand valence. The I1a over-attachment is closed here.
    assert not [r for r in plan["claim_roles"] if r.get("role") == "attached_to_relation"]
    assert not [s for s in plan["nodes"][0]["statements"] if s["kind"] == "value_level_valence"]
    directions = [r for r in plan["claim_roles"] if r.get("claim_kind") == "direction_or_effectiveness"]
    assert directions and directions[0]["role"] == "suppressed"
    assert directions[0]["direction_target"] == "unknown"
    assert directions[0]["reasons"] == ["direction_target_unresolved"]


def test_direction_is_value_level_when_the_inherited_referent_is_not_realised_in_the_witness_passage():
    # Same structure, but the child's own passage no longer realises the inherited referent. The relation is not
    # witnessed, so the direction falls back to a value-level statement that names its own subject.
    props = [prop("p1", 1, "Explicit negative attitudes were found with the beta questionnaire.")]
    # The requested-construct term ("alpha") must still be present in the paper, but in a different sealed span, so the
    # candidate passage itself does not realise the inherited referent.
    spans = [
        {"paper_id": 1, "span_id": "s1", "text": props[0]["quote"], "chunk_id": 1},
        {"paper_id": 1, "span_id": "s2", "text": "The alpha site was described in the methods.", "chunk_id": 2},
    ]
    summary = {
        "observed_values": ["negative"],
        "consensus_value": "negative",
        "has_within_instance_conflict": False,
        "has_across_instance_heterogeneity": False,
        "complete_instance_keys": ["k1"],
        "instance_keys_with_observations": ["k1"],
        "instance_keys_missing_observations": [],
        "conflicted_instance_keys": [],
    }
    req = requirement(
        "r::dir",
        ["ra", "rb"],
        [
            instance(
                "k1",
                {
                    "ra": binding("p0", "alpha", source="parent_context", supporting=["p0"]),
                    "rb": binding("p1", "beta questionnaire", supporting=["p1"]),
                },
                direction=[{"reported": True, "sign": "negative", "proposition_id": "p1", "exact_text": "negative"}],
            )
        ],
        kind="relational",
        direction={"reported": True},
        direction_summary=summary,
    )
    plan, _, _ = build(
        props, spans, {"c1": {"child_id": "c1", "requirements": [req]}}, one_node("c1"), ["r::dir"], ["ra", "rb"]
    )
    valence = [s for s in plan["nodes"][0]["statements"] if s["kind"] == "value_level_valence"]
    assert valence and valence[0]["subject"] == "beta questionnaire"
    assert not [r for r in plan["claim_roles"] if r.get("role") == "attached_to_relation"]


# ---------------------------------------------------------------- claim classification


def _single_role(
    pid_text, *, quote, role_strategy="model_nomination_only", extra_reqs=None, spans_text=None, rid="r::one"
):
    props = [prop("p1", 1, quote)]
    spans = [{"paper_id": 1, "span_id": "s1", "text": spans_text or quote, "chunk_id": 1}]
    req = requirement(
        rid, ["rv"], [instance("k1", {"rv": binding("p1", pid_text, supporting=["p1"])})], role_strategy=role_strategy
    )
    smap = {"c1": {"child_id": "c1", "requirements": [req] + (extra_reqs or [])}}
    return build(props, spans, smap, one_node("c1"), [rid] + [r["id"] for r in (extra_reqs or [])], ["rv"])


def test_polarity_negation_is_kept_by_rendering_the_verbatim_sentence_never_a_bare_keyword():
    quote = "Alpha participants expressed explicit biases, but their implicit biases were slight and not significant."
    plan, _, _ = _single_role("implicit", quote=quote)
    texts = [s["text"] for n in plan["nodes"] for s in n["statements"]]
    assert texts and "not significant" in texts[0]
    assert "implicit" != texts[0].strip().rstrip(".").lower()


def test_speculative_source_is_suppressed_and_hedge_is_never_dropped_into_a_claim():
    plan, _, _ = _single_role("alpha", quote="We suggest that alpha is underpinned by beta.")
    record = next(iter(claims_by_role(plan).values()))
    assert record["role"] == "suppressed"
    assert "attribution_aim_or_hypothesis" in record["reasons"]
    assert node_text(plan, "1").find("We suggest") == -1


def test_prior_work_is_attributed_only_and_absent_from_layer_one_as_a_result():
    plan, _, _ = _single_role("alpha", quote="Previous studies reported alpha with beta outcomes.")
    record = next(iter(claims_by_role(plan).values()))
    assert record["role"] == "attributed_only" and record["layer"] == "layer2"
    assert not any(n["statements"] for n in plan["nodes"])


def test_generic_summary_bound_under_two_requirements_is_not_a_specific_finding():
    quote = "This study confirmed that alpha was found in beta."
    other = requirement(
        "r::other",
        ["rv"],
        [instance("k2", {"rv": binding("p1", quote, supporting=["p1"])})],
        role_strategy="achieved_outcome_predicate",
    )
    plan, _, _ = _single_role(quote, quote=quote, role_strategy="achieved_outcome_predicate", extra_reqs=[other])
    record = next(iter(claims_by_role(plan).values()))
    assert "passage_not_generic_summary" in record["reasons"]
    assert record["role"] == "suppressed"


def test_caption_source_and_truncated_passage_are_suppressed():
    quote = "The alpha response correlated with beta outcomes."
    plan, _, _ = _single_role(quote, quote=quote, spans_text="Table S1 | " + quote)
    assert "caption_source" in next(iter(claims_by_role(plan).values()))["reasons"]
    plan2, _, _ = _single_role("alpha response", quote="The alpha response correlated with beta outcomes and")
    assert "passage_complete" in next(iter(claims_by_role(plan2).values()))["reasons"]


def test_requested_construct_adjacency_is_never_an_answer():
    quote = "Participants shared more with good partners than with bad partners."
    plan, _, _ = _single_role("good partners", quote=quote)
    record = next(iter(claims_by_role(plan).values()))
    assert "requested_construct_direct" in record["reasons"]
    assert record["role"] == "suppressed"


def test_anaphoric_source_sentence_is_not_standalone():
    quote = "Across these levels of organization, the alpha response correlated with beta outcomes."
    plan, _, _ = _single_role("alpha response", quote=quote)
    assert "referentially_closed" in next(iter(claims_by_role(plan).values()))["reasons"]


def test_category_list_renders_as_one_verbatim_enumeration_when_every_value_is_clean():
    props = [
        prop("p1", 1, "We found alpha reports of the Explicit Bias Questionnaire."),
        prop("p2", 1, "We found alpha evidence using the Implicit Association Test."),
    ]
    spans = [{"paper_id": 1, "span_id": "s1", "text": " ".join(p["quote"] for p in props), "chunk_id": 1}]
    req = requirement(
        "r::list",
        ["measure"],
        [
            instance("a", {"measure": binding("p1", "Explicit Bias Questionnaire", supporting=["p1"])}, complete=False),
            instance("b", {"measure": binding("p2", "Implicit Association Test", supporting=["p2"])}, complete=False),
        ],
        quant="for_each_discovered_instance",
    )
    plan, _, _ = build(
        props, spans, {"c1": {"child_id": "c1", "requirements": [req]}}, one_node("c1"), ["r::list"], ["measure"]
    )
    texts = " ".join(s["text"] for s in plan["nodes"][0]["statements"])
    assert texts.strip().startswith("Phrase of r::list: Explicit Bias Questionnaire; Implicit Association Test.")


# ---------------------------------------------------------------- answerability and facets


def test_searched_empty_is_stated_as_searched_not_absent():
    facet = {
        "facet_id": "f",
        "phrase": "a finding",
        "required_roles": ["rv"],
        "relation_required": False,
        "relation_status": None,
        "cardinality": False,
        "instances": {},
    }
    state = pl._facet_state(facet, [], resolved={"f"})
    assert state["state"] == pl.SEARCHED_EMPTY
    items = pl._disclosure_items(facet, state, [], {}, {"role_phrases": {"rv": "x"}, "category_phrases": {}})
    assert items[0]["kind"] == "searched_empty"
    assert items[0]["text"].startswith("The scoped search completed without establishing")


# ---------------------------------------------------------------- overlay, determinism, rendering


def test_overlay_refuses_undeclared_human_review_obligations_and_uncovered_children():
    frozen = {"requirements": {"RC-9#scope:measures-of-behavior": {"class": "human_review_meaning"}}}
    smap = {
        "c1": {"child_id": "c1", "requirements": [requirement("r::x", ["rv"], [instance("k", {})])]},
        "c2": {"child_id": "c2", "requirements": []},
    }
    nodes = [
        {
            "label": "1",
            "parent": None,
            "nesting": "top_level",
            "literal_text": "Q?",
            "owning_child_ids": ["c1"],
            "human_review_obligations": ["RC-7#made-up"],
        }
    ]
    over = overlay_for(nodes, ["r::x"], ["rv"])
    problems = ov.validate_overlay(over, smap, frozen)
    assert any("RC-7#made-up" in p for p in problems)
    assert any("child c2" in p for p in problems)


def test_plan_is_deterministic_and_layer_one_contains_no_internal_identifiers():
    quote = "The alpha response correlated with beta outcomes."
    plan_a = _single_role("alpha response", quote=quote)[0]
    plan_b, _, _ = _single_role("alpha response", quote=quote)
    assert plan_a["plan_sha256"] == plan_b["plan_sha256"]
    props = {r["proposition_id"]: r for r in [prop("p1", 1, quote)]}
    text_out = rd.render_layer1(plan_a, props, set())
    checks = rd.invariant_report(plan_a, text_out, props)
    failing = [c["check"] for c in checks if not c["passed"]]
    assert failing == [], failing
    assert "p1" not in text_out.split() and "::" not in text_out


def test_enumeration_refuses_a_value_that_is_a_whole_passage_or_a_sentence():
    # A value that carries a full stop inside it is a passage, not a phrase: no enumeration may be built from it.
    props = [
        prop("p1", 1, "We found alpha evidence for Explicit Bias Questionnaire. Beta was also measured."),
        prop("p2", 1, "We found alpha evidence using the Implicit Association Test."),
    ]
    spans = [{"paper_id": 1, "span_id": "s1", "text": " ".join(p["quote"] for p in props), "chunk_id": 1}]
    req = requirement(
        "r::list",
        ["measure"],
        [
            instance(
                "a",
                {"measure": binding("p1", "Explicit Bias Questionnaire. Beta was also measured.", supporting=["p1"])},
                complete=False,
            ),
            instance("b", {"measure": binding("p2", "Implicit Association Test", supporting=["p2"])}, complete=False),
        ],
        quant="for_each_discovered_instance",
    )
    plan, _, _ = build(
        props, spans, {"c1": {"child_id": "c1", "requirements": [req]}}, one_node("c1"), ["r::list"], ["measure"]
    )
    kinds = [s["kind"] for n in plan["nodes"] for s in n["statements"]]
    assert "enumeration" not in kinds
