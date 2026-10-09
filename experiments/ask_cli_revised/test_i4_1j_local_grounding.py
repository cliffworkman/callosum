"""PHASE 34 / I4-1j -- pure local assertion grounding primitives.

Three pure additions under test, none consumed by any production path:

1. `assertion_authority.locate_containing_assertion` -- the deterministic achieved_outcome_span -> assertion
   boundary join (section 4/5/17 of the directive).
2. `target_relevance.match_target_to_assertions`/`local_assertion_relevance` -- the instance-local
   target-relevance matcher (sections 7-12/20).
3. `target_relevance.verify_shared_local_assertion` -- the pure, correctly-scoped `same_local_assertion`
   verifier PRIMITIVE, deliberately NOT registered into `sufficiency_engine._VERIFIER_FUNCS` (section 13/14).

Real propositions (p41/p40/p11/p35/p46/p47/p29/p53/p21) are the exact, already-committed-elsewhere sealed
quotes I4-1b/I4-1d/I4-1f already quote verbatim in their own results reports -- embedded directly here,
following that exact precedent, so this file needs no gitignored external corpus to run.
"""

from __future__ import annotations

import ast
from pathlib import Path

from experiments.ask_cli_revised import achieved_outcome_span as aos
from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import sufficiency_authoring as sa
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import target_relevance as tr
from experiments.ask_cli_revised.contract_directed import attribution as attr

HERE = Path(__file__).parent

# ---- real sealed quotes, verbatim (same disclosure precedent as I4-1b/d/f's own committed reports) ----

P41 = (
    "Results: Across the ratings for all faces, Spearman correlations revealed greater proportionality was "
    "associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193, "
    "P < 0.001), while lesser proportionality was associated with impressions of anger (ρ = 0.132, "
    "P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001)."
)
P11 = (
    "Across these levels of organization, the specific amygdala response to facial anomalies correlated with "
    "stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, "
    "and less prosociality toward people with facial anomalies."
)
P40 = (
    "Recent work with functional magnetic resonance imaging has implicated certain neuroanatomic structures "
    "when viewing others with facial anomalies.6 Laypersons with high levels of implicit bias toward those "
    "with facial anomalies demonstrated increased amygdala reactiv- ity.6 Although previous studies have used "
    "eye-tracking to characterize visual attention toward patients with craniofacial anomalies, visual "
    "at- tention has not been analyzed alongside assessments of biases and other social dispositions."
)
P35 = (
    "The contrast of decisions that were incongruent with behavioral bias (share with bad partner and keep "
    "with good partner versus the alternative choices) yielded several regions deﬁned by strength of "
    "effect (P o 0.001) and size (10 or more voxels)."
)
P46 = (
    "In addition, when comparing share decisions between partners (good versus bad), participants made more "
    "share decisions overall when playing with the good partner than with the bad (t11 \xbc 3.26, P o 0.01) "
    "or neutral (t11 \xbc 2.0, P \xbc 0.07) partners."
)
P47 = (
    "Finally, using reaction time data acquired during the experimental session, we observed that participants "
    "were faster to share when playing with the good partner compared to the bad (t11 \xbc –3.73, "
    "P o 0.005) and neutral partners (t11 \xbc –1.89, P \xbc 0.08)."
)
P29 = (
    "However, Hadza who regularly interact with outside cultural groups were more likely to think Hadza with "
    "facial scarring were less moral and were better"
)
P21 = (
    "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a "
    "universal pathogen avoidance byproduct hypothesis."
)

# Real sibling exact_text values, read directly from the recovered v4 map (`17_sufficiency_map.json`).
C8_TRAIT_TARGETS = {
    "attractiveness": (43, 200),
    "trustworthiness": (43, 200),
    "anger": (208, 372),
    "dominance": (208, 372),
    "threateningness": (208, 372),
}
C4_P11_TARGET = "the specific amygdala response"
C4_P40_TARGET = "increased amygdala reactiv- ity"
C2_TARGETS = {
    "p35": "decisions that were incongruent with behavioral bias (share with bad partner and keep with good "
    "partner versus the alternative choices)",
    "p46": "share decisions between partners (good versus bad)",
    "p47": "faster to share when playing with the good partner compared to the bad",
}


def _candidate_assertions_for(passage: str, proposition_id: str) -> list:
    """Test-side-only composition of the real future I4-2a seam: achieved_outcome_span's own raw
    predicate/content-span hits, joined to assertion identity via `locate_containing_assertion`, deduplicated
    by assertion span (three raw hits can and do resolve to the same two assertions for real p41 -- see the
    real join test below). This function lives in a TEST file and is never imported by production; it is the
    exact kind of cross-module composition I4-1d's own report (section 8) already established is safe only in
    a test file, never inside either pure module itself."""
    out = []
    seen_spans = set()
    for match in aos.find_achieved_outcome_matches(passage).matches:
        joined = aa.locate_containing_assertion(passage, match.content_span[0], match.content_span[1])
        if not joined["resolved"]:
            continue
        span = tuple(joined["assertion"]["span"])
        if span in seen_spans:
            continue
        seen_spans.add(span)
        out.append({"proposition_id": proposition_id, "text": joined["assertion"]["assertion"]["text"], "span": span})
    return out


# =================================================================================================
# Section 4/6: the deterministic achieved_outcome_span -> assertion_authority join
# =================================================================================================


def test_locate_containing_assertion_resolves_a_single_governing_assertion():
    result = aa.locate_containing_assertion(P11, 99, 264)  # p11's own content span
    assert result["resolved"] is True
    assert result["target_scope"] in ("within_assertion", "partial_assertion")
    assert result["assertion"]["span"] == [37, 264]


def test_locate_containing_assertion_fails_closed_on_no_governing_assertion():
    text = "An unrelated sentence with nothing matching this span."
    result = aa.locate_containing_assertion(text, 0, 3)  # "An " -- outside any predicate's scope
    assert result["resolved"] is False
    assert result["reason"] == "no_governing_assertion"
    assert result["assertion"] is None
    assert result["diagnostic"]["target_scope"] == "no_governing_assertion"


def test_locate_containing_assertion_fails_closed_on_multi_assertion():
    text = "We found that scores increased. We also found that revenue decreased."
    # a target spanning both sentences intersects two independent assertions
    result = aa.locate_containing_assertion(text, 0, len(text))
    assert result["resolved"] is False
    assert result["reason"] == "multi_assertion"
    assert result["assertion"] is None


def test_real_p41_join_frozen_spans_and_expected_assertion_identities():
    """Section 6, frozen before any battery widening: the real raw achieved_outcome_span hits for p41, their
    EXACT spans, and which of p41's two real assertions each one must resolve to. All three resolve; none is
    `multi_assertion`/`no_governing_assertion`; the first two collapse onto the SAME assertion (assertion 1);
    the third resolves to the other (assertion 2) -- the join is structurally incapable of reproducing
    `achieved_outcome_span`'s own, separate `ambiguous_with` flag between hits 1 and 2."""
    matches = aos.find_achieved_outcome_matches(P41).matches
    assert len(matches) == 3
    assert matches[0].content_span == (65, 200)
    assert matches[1].content_span == (102, 200)
    assert matches[2].content_span == (235, 373)
    # the real module's own narrower boundary grammar flags hits 0/1 as mutually ambiguous -- confirmed
    # present (not reinterpreted), then shown irrelevant to the join below.
    assert matches[0].ambiguous_with == (matches[1].predicate_span,)
    assert matches[1].ambiguous_with == (matches[0].predicate_span,)
    assert matches[2].ambiguous_with is None

    expected_assertion_span = [(43, 200), (43, 200), (208, 372)]
    for match, expected in zip(matches, expected_assertion_span, strict=True):
        joined = aa.locate_containing_assertion(P41, match.content_span[0], match.content_span[1])
        assert joined["resolved"] is True, f"expected a resolved join for {match.content_span}"
        assert tuple(joined["assertion"]["span"]) == expected

    deduped = _candidate_assertions_for(P41, "p41")
    assert len(deduped) == 2  # three raw hits collapse onto exactly two distinct assertions
    assert {tuple(c["span"]) for c in deduped} == {(43, 200), (208, 372)}


# =================================================================================================
# Section 7-12/20: the pure target-relevance matcher
# =================================================================================================


def test_local_assertion_relevance_literal_and_dehyphenated():
    assert tr.local_assertion_relevance("trustworthiness", "associated with trustworthiness") is True
    assert tr.local_assertion_relevance("attractiveness", "associated with attrac- tiveness") is True
    assert tr.local_assertion_relevance("anger", "associated with trustworthiness") is False
    assert tr.local_assertion_relevance("", "anything") is False
    assert tr.local_assertion_relevance("x", "") is False


def test_match_target_to_assertions_unique_multiple_unmatched():
    candidates = [{"proposition_id": "a", "text": "X increased"}, {"proposition_id": "a", "text": "Y decreased"}]
    assert tr.match_target_to_assertions(target_text="X", candidate_assertions=candidates)["relevance"] == "unique"
    assert tr.match_target_to_assertions(target_text="Z", candidate_assertions=candidates)["relevance"] == "unmatched"
    both = [{"proposition_id": "a", "text": "X increased"}, {"proposition_id": "a", "text": "X also decreased"}]
    result = tr.match_target_to_assertions(target_text="X", candidate_assertions=both)
    assert result["relevance"] == "multiple"
    assert len(result["matches"]) == 2  # preserved, never collapsed to one


def test_match_target_to_assertions_scope_filters_before_lexical_matching():
    """The real c4 contrast (section 9, 17): a free search over the whole pool over-matches a generic
    anatomical noun; scoping to the sibling's own source proposition resolves it -- without the lexical
    matcher itself becoming any smarter."""
    candidates = [
        {"proposition_id": "p11", "text": "the specific amygdala response correlated with just-world beliefs"},
        {"proposition_id": "p40", "text": "demonstrated increased amygdala reactivity"},
    ]
    unscoped = tr.match_target_to_assertions(target_text="amygdala", candidate_assertions=candidates)
    assert unscoped["relevance"] == "multiple"
    scoped_to_p40 = tr.match_target_to_assertions(
        target_text="amygdala", candidate_assertions=candidates, allowed_proposition_ids=["p40"]
    )
    assert scoped_to_p40["relevance"] == "unique"
    assert scoped_to_p40["matches"][0]["proposition_id"] == "p40"


_GENERIC_TWINS = [
    # (label, target, candidates, allowed_proposition_ids, expected_relevance, expected_count)
    (
        "clinical_unique",
        "depression",
        [
            {"proposition_id": "c1", "text": "Depression subscale scores decreased significantly (p<.01)."},
            {"proposition_id": "c1", "text": "Anxiety subscale scores showed no significant change."},
        ],
        ["c1"],
        "unique",
        1,
    ),
    (
        "neuroscience_multiple",
        "amygdala",
        [
            {"proposition_id": "n1", "text": "Amygdala activation predicted threat sensitivity in session one."},
            {"proposition_id": "n1", "text": "Amygdala activation also predicted avoidance in session two."},
        ],
        ["n1"],
        "multiple",
        2,
    ),
    (
        "built_environment_no_match",
        "floor area",
        [{"proposition_id": "b1", "text": "Ceiling height remained unchanged across all three renovation phases."}],
        ["b1"],
        "unmatched",
        0,
    ),
    (
        "language_learning_same_lexical_target_scoped_out",
        "vocabulary",
        [
            {"proposition_id": "l1", "text": "Vocabulary gains were significant (d=0.6)."},
            {"proposition_id": "l2", "text": "Vocabulary gains were not replicated in the follow-up sample."},
        ],
        ["l1"],  # l2 lexically matches too, but is out of the relationship-derived scope
        "unique",
        1,
    ),
    (
        "clinical_hyphenated_line_wrap",
        "rehabilitation",
        [{"proposition_id": "c2", "text": "Patients completed a structured rehabili- tation programme."}],
        ["c2"],
        "unique",
        1,
    ),
    (
        "neuroscience_target_only_in_a_neighboring_unoffered_assertion",
        "hippocampus",
        # the hippocampus-bearing sentence was never resolved/offered as a candidate at all here --
        # the matcher must not reach for text it was never given.
        [{"proposition_id": "n2", "text": "Amygdala activation predicted threat sensitivity."}],
        ["n2"],
        "unmatched",
        0,
    ),
    (
        "built_environment_relevant_but_hedged",
        "floor area",
        [
            {
                "proposition_id": "b2",
                "text": "Floor area per occupant may have increased slightly, though the analysis was "
                "preliminary and not conclusive.",
            }
        ],
        ["b2"],
        "unique",  # relevance is found regardless of hedged language -- the matcher reads no guard/policy field
        1,
    ),
]


def test_generic_cross_domain_twins():
    for label, target, candidates, scope, expected_relevance, expected_count in _GENERIC_TWINS:
        result = tr.match_target_to_assertions(
            target_text=target, candidate_assertions=candidates, allowed_proposition_ids=scope
        )
        assert result["relevance"] == expected_relevance, label
        assert len(result["matches"]) == expected_count, label


def test_no_domain_vocabulary_in_executable_target_relevance_logic():
    """The twins above carry domain words only as TEST DATA. `target_relevance.py` itself contains none of
    them."""
    source = (HERE / "target_relevance.py").read_text(encoding="utf-8")
    for word in ("depression", "amygdala", "hippocampus", "floor area", "vocabulary", "rehabilitation"):
        assert word not in source.lower()


# =================================================================================================
# Real c8/c4/c2 batteries (sections 16-18), composed through the real pipeline end to end
# =================================================================================================


def test_real_c8_battery_all_five_trait_targets_split_correctly():
    candidates = _candidate_assertions_for(P41, "p41")
    assert len(candidates) == 2
    for term, expected_span in C8_TRAIT_TARGETS.items():
        result = tr.match_target_to_assertions(
            target_text=term, candidate_assertions=candidates, allowed_proposition_ids=["p41"]
        )
        assert result["relevance"] == "unique", f"{term} did not uniquely resolve"
        assert tuple(result["matches"][0]["span"]) == expected_span, term
    # explicit disclosure: "attractiveness" succeeds only through the existing dehyphenation fallback --
    # not special-cased, not re-spelled.
    assert tr.local_assertion_relevance("attractiveness", candidates[0]["text"]) is True
    assert "attractiveness" not in candidates[0]["text"]  # the sealed text literally has the line-wrap hyphen


def test_real_c4_battery_both_instances_and_the_unscoped_over_match():
    p11_candidates = _candidate_assertions_for(P11, "p11")
    p40_candidates = _candidate_assertions_for(P40, "p40")
    assert len(p11_candidates) == 1
    assert len(p40_candidates) == 1
    pool = p11_candidates + p40_candidates

    instance_1 = tr.match_target_to_assertions(
        target_text=C4_P11_TARGET, candidate_assertions=pool, allowed_proposition_ids=["p11"]
    )
    instance_2 = tr.match_target_to_assertions(
        target_text=C4_P40_TARGET, candidate_assertions=pool, allowed_proposition_ids=["p40"]
    )
    assert instance_1["relevance"] == "unique"
    assert instance_1["matches"][0]["proposition_id"] == "p11"
    assert instance_2["relevance"] == "unique"
    assert instance_2["matches"][0]["proposition_id"] == "p40"

    # the load-bearing demonstration (section 17's own closing instruction): remove the scope and the
    # bare, generic target over-matches both propositions.
    unscoped = tr.match_target_to_assertions(target_text="amygdala", candidate_assertions=pool)
    assert unscoped["relevance"] == "multiple"
    assert {m["proposition_id"] for m in unscoped["matches"]} == {"p11", "p40"}
    scoped = tr.match_target_to_assertions(
        target_text="amygdala", candidate_assertions=pool, allowed_proposition_ids=["p40"]
    )
    assert scoped["relevance"] == "unique"


def test_real_c2_battery_one_positive_two_honest_no_matches():
    p35_candidates = _candidate_assertions_for(P35, "p35")
    p46_candidates = _candidate_assertions_for(P46, "p46")
    p47_candidates = _candidate_assertions_for(P47, "p47")
    # p35/p46's own source sentences never pass the existing, narrower result-predicate lexicon at all
    # (confirmed directly, not assumed) -- there is nothing to even offer as a candidate.
    assert p35_candidates == []
    assert p46_candidates == []
    assert attr.has_result_predicate(P35) is False
    assert attr.has_result_predicate(P46) is False
    assert len(p47_candidates) == 1
    assert attr.has_result_predicate(P47) is True

    r47 = tr.match_target_to_assertions(
        target_text=C2_TARGETS["p47"], candidate_assertions=p47_candidates, allowed_proposition_ids=["p47"]
    )
    r35 = tr.match_target_to_assertions(
        target_text=C2_TARGETS["p35"], candidate_assertions=p35_candidates, allowed_proposition_ids=["p35"]
    )
    r46 = tr.match_target_to_assertions(
        target_text=C2_TARGETS["p46"], candidate_assertions=p46_candidates, allowed_proposition_ids=["p46"]
    )
    assert r47["relevance"] == "unique"
    assert r35["relevance"] == "unmatched"  # never a fallback to a generic shared passage
    assert r46["relevance"] == "unmatched"


def test_real_c10_check_remains_guard_excluded_not_a_target_relevance_question():
    """Section 19: confirmed unchanged. p29/p53's own result-predicate-bearing sentence is excluded by the
    PRE-EXISTING `hedged` guard (the word "likely"), and p21 fails the PRE-EXISTING result-predicate lexicon
    gate entirely ("suggest" is not a result verb) -- neither outcome has anything to do with target
    relevance, and I4-1j changes neither."""
    from experiments.ask_cli_revised import overview_evidence as oe

    assert attr.has_result_predicate(P29) is True
    assert oe.has_hedge(P29) is True  # "more likely" -- this is what excludes it today, unrelated to I4-1j
    assert attr.has_result_predicate(P21) is False  # "suggest" is outside the result-predicate lexicon


# =================================================================================================
# Section 13/14: same_local_assertion -- the pure primitive, deliberately NOT registered
# =================================================================================================


def test_verify_shared_local_assertion_is_correct_against_a_genuinely_narrowed_local_assertion():
    """Once a caller supplies the EVIDENCE role's own already-resolved local-assertion text (never a whole
    passage), the primitive discriminates correctly -- this is what registration will mean once I4-2a's span
    narrowing exists."""
    assertion_1_text = "greater proportionality was associated with attrac- tiveness and trustworthiness"
    assertion_2_text = "lesser proportionality was associated with impressions of anger, dominance"
    assert tr.verify_shared_local_assertion(
        sibling_target_text="attractiveness", evidence_assertion_text=assertion_1_text
    )
    assert not tr.verify_shared_local_assertion(sibling_target_text="anger", evidence_assertion_text=assertion_1_text)
    assert tr.verify_shared_local_assertion(sibling_target_text="dominance", evidence_assertion_text=assertion_2_text)


def test_verify_shared_local_assertion_is_vacuous_against_todays_real_whole_passage_binding():
    """The exact, empirically-demonstrated reason registration must wait (section 13): fed TODAY's real
    `achieved_outcome_predicate` binding shape (the whole passage, not a narrowed span), this primitive
    returns True for every one of c8's five real trait terms -- a non-discriminating, actively misleading
    result if it were ever consulted as a safety check. This is not a defect in the function; it is proof
    that the CALLER'S input (a whole passage) is the wrong shape for this question, which is exactly why
    `_VERIFIER_FUNCS` registration does not happen in this increment."""
    for term in C8_TRAIT_TARGETS:
        assert tr.verify_shared_local_assertion(sibling_target_text=term, evidence_assertion_text=P41) is True


def test_same_local_assertion_is_not_registered_in_verifier_funcs():
    assert "same_local_assertion" not in se._VERIFIER_FUNCS


def test_no_real_q_aib_requirement_authors_same_local_assertion():
    children = {
        cid: {"wording": f"stub wording for {cid}"}
        for cid in ["c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"]
    }
    contracts = sa.build_qaib_contract(children)
    for contract in contracts.values():
        for req in contract["requirements"]:
            assert "same_local_assertion" not in req["relationship_verifiers"]
            assert req["relationship_verifiers"] == ["same_proposition"]  # unchanged from every prior phase


def test_current_same_proposition_behavior_is_byte_identical():
    """Zero collateral change to the one relationship verifier that IS wired: `same_proposition`'s own
    behavior over the real recovered c8/c2/c4 shapes, reproduced here without any gitignored external file."""
    p41_binding = {"proposition_id": "p41"}
    p20_binding = {"proposition_id": "p20"}
    p11_binding = {"proposition_id": "p11"}
    p40_binding = {"proposition_id": "p40"}
    assert se._verify_same_proposition({"a": p41_binding, "b": p41_binding}, ["a", "b"]) is True
    assert se._verify_same_proposition({"a": p20_binding, "b": p41_binding}, ["a", "b"]) is False
    assert se._verify_same_proposition({"a": p11_binding, "b": p40_binding}, ["a", "b"]) is False


# =================================================================================================
# Section 21: candidate_support schema parity (full coverage lives in test_sufficiency_support_schema.py;
# this is a cross-check that the corrected schema composes with this increment's own primitives)
# =================================================================================================


def test_candidate_support_composes_with_the_new_join_and_matcher():
    candidates = _candidate_assertions_for(P41, "p41")
    match = tr.match_target_to_assertions(
        target_text="attractiveness", candidate_assertions=candidates, allowed_proposition_ids=["p41"]
    )
    winner = match["matches"][0]
    record = se.new_candidate_support(
        supporting_proposition_ids=["p41"],
        span_proposition_id="p41",
        exact_text=winner["text"],
        assertion_span=list(winner["span"]),
        assertion_relation="current_document",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=True,
        support_label="direct_empirical",
    )
    assert record["supporting_proposition_ids"] == ["p41"]
    assert record["span_proposition_id"] == "p41"
    assert record["assertion_span"] == [43, 200]


# =================================================================================================
# Section 22: static, zero-production-consumption guards
# =================================================================================================

_I4_1J_NAMES = (
    "locate_containing_assertion",
    "match_target_to_assertions",
    "local_assertion_relevance",
    "verify_shared_local_assertion",
    "target_relevance",
)

_PRODUCTION_FILES = (
    "sufficiency_mapping.py",
    "sufficiency_recovery_targets.py",
    "sufficiency_diagnostic.py",
    "sufficiency_model_scope.py",
    "sufficiency_authoring.py",
    "e2e.py",
)


def test_no_production_module_consumes_the_i4_1j_primitives():
    # I4-2a authorizes only the exact mapper path, across every production subtree (including future files).
    repo = HERE.parents[1]
    allowed = {HERE / "sufficiency_mapping.py", HERE / "target_relevance.py", HERE / "assertion_authority.py"}
    offenders = {}
    for root in ("app", "integrations", "experiments", "tools", "tests", "mcp_server", "tui", "sync_server"):
        for path in (repo / root).rglob("*.py"):
            if path.name.startswith("test_") or path in allowed or "__pycache__" in path.parts:
                continue
            hit = [name for name in _I4_1J_NAMES if name in path.read_text(encoding="utf-8", errors="replace")]
            if hit:
                offenders[str(path.relative_to(repo))] = hit
    assert offenders == {}, f"Only the mapper may consume local grounding: {offenders}"


def test_answer_plan_package_does_not_consume_the_i4_1j_primitives():
    answer_plan_dir = HERE / "answer_plan"
    offenders = []
    for path in answer_plan_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}:{name}" for name in _I4_1J_NAMES if name in text]
    assert offenders == []


def test_target_relevance_module_imports_neither_classifier_family_module():
    """`target_relevance.py` stays independent of `assertion_authority`/`achieved_outcome_span` by design
    (module docstring, section's own architectural note) -- confirmed here, not merely asserted."""
    source = (HERE / "target_relevance.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.rsplit(".", 1)[-1])
    assert "assertion_authority" not in imported_names
    assert "achieved_outcome_span" not in imported_names


def test_assertion_authority_unwired_guard_is_unaffected_by_the_new_function():
    """`locate_containing_assertion` lives inside `assertion_authority.py` itself -- confirms the module's
    OWN pre-existing unwired guard (no non-test reference to the module's name anywhere outside the I4-1
    family) still passes unchanged, since adding a function to the module does not change which OTHER files
    reference it by name."""
    from experiments.ask_cli_revised import test_assertion_authority as taa

    taa.test_classifier_is_unwired_static_guard()


def test_versions_are_unchanged_for_sufficiency_and_plan():
    from experiments.ask_cli_revised.answer_plan import plan as ap

    assert se.SUFFICIENCY_SEMANTICS_VERSION == se.SUFFICIENCY_SEMANTICS_V7  # I4-2b5 support-policy integration
    assert ap.PLAN_VERSION == "answer-plan-step2-v4"


def test_ruleset_version_deliberately_unchanged():
    """I4-1j adds `locate_containing_assertion` to `assertion_authority.py` but changes the OUTPUT of no
    existing function -- unlike I4-1b/c/f (each of which changed what `classify_assertion_authority` et al.
    actually return), there is no classification-rule change here for `RULESET_VERSION` to track. Left at
    `"i4-1f.0"` on purpose, not by oversight."""
    assert aa.RULESET_VERSION == "i4-1f.0"
    assert aa.RULESET_VERSION.startswith("i4-1")  # the one invariant every prior phase's own test also checks
