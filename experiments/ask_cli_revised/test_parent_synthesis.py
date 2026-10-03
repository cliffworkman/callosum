"""Phase 27: the bounded parent realization (one S2 call over the Phase-26 claim ledger), offline only.

Scripted S2 clients, a recording NLI fake, and a real stages.Supervisor -- no Ollama, no network. Letters
cross-reference the Phase-27 brief's required test matrix (Sections 32-36, 47).
"""

from __future__ import annotations

import inspect
import unittest

from experiments.ask_cli_revised import parent_synthesis as ps
from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_render as psr
from experiments.ask_cli_revised import parent_synthesis_test_support as pst
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import topology as topo


def _claim(claims, kind, *, role=None):
    matches = [c for c in claims if c["claim_kind"] == kind and (role is None or c["role"] == role)]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {kind} claim (role={role}), found {len(matches)}")
    return matches[0]


def _two_unrelated_claims():
    """Two unrelated role-value claims from different children, each with its own passage."""
    sealed = pst.sealed_with(
        ("p1", 1, "the amygdala responded to scarring", ["a"]),
        ("p2", 2, "participants avoided the scarred faces", ["b"]),
    )
    specs_a = {"region": pst.spec("region", "a named brain region")}
    specs_b = {"behavior": pst.spec("behavior", "an observed behavior")}
    req_a = pst.requirement(
        "a#req",
        specs_a,
        se.new_role_completion(required_roles=["region"]),
        "exists",
        [pst.instance({"region": pst.filled("region", "p1", "the amygdala responded to scarring")})],
    )
    req_b = pst.requirement(
        "b#req",
        specs_b,
        se.new_role_completion(required_roles=["behavior"]),
        "exists",
        [pst.instance({"behavior": pst.filled("behavior", "p2", "participants avoided the scarred faces")})],
    )
    smf = {**pst.map_with("a", req_a), **pst.map_with("b", req_b)}
    return sealed, smf, psl.build_claim_ledger(smf, sealed)


def _single_claim():
    sealed = pst.sealed_with(("p1", 1, "the amygdala responded to scarring", ["x"]))
    specs = {"region": pst.spec("region", "a named brain region")}
    req = pst.requirement(
        "x#req",
        specs,
        se.new_role_completion(required_roles=["region"]),
        "exists",
        [pst.instance({"region": pst.filled("region", "p1", "the amygdala responded to scarring")})],
    )
    return sealed, psl.build_claim_ledger(pst.map_with("x", req), sealed)


def _three_claims():
    """Three independent role-value claims: valid, unsupported, omitted-by-the-model."""
    sealed = pst.sealed_with(
        ("p1", 1, "the amygdala responded to scarring", ["a"]),
        ("p2", 2, "the insula responded to scarring", ["b"]),
        ("p3", 3, "the cingulate responded to scarring", ["c"]),
    )
    maps = {}
    for child, pid, text, cat in (
        ("a", "p1", "the amygdala responded to scarring", "a named brain region"),
        ("b", "p2", "the insula responded to scarring", "a named insular region"),
        ("c", "p3", "the cingulate responded to scarring", "a named cingulate region"),
    ):
        specs = {"region": pst.spec("region", cat)}
        req = pst.requirement(
            f"{child}#req",
            specs,
            se.new_role_completion(required_roles=["region"]),
            "exists",
            [pst.instance({"region": pst.filled("region", pid, text)})],
        )
        maps.update(pst.map_with(child, req))
    return sealed, psl.build_claim_ledger(maps, sealed)


def _default_statement(claim):
    """A faithful restatement: the authorized values themselves, verbatim (never a paraphrase)."""
    if claim["claim_kind"] in ("role_value", "category_list"):
        return ". ".join(v["exact_text"] for v in claim["values"]) + "."
    return "The reported finding is stated above."


def _grounded_items(claims, text_for=None):
    text_for = text_for or {}
    return [
        {"claim_id": c["claim_id"], "statement": text_for.get(c["claim_id"], _default_statement(c))} for c in claims
    ]


def _run(claims, sealed, *, answer, entail=None, supervisor=None, question="Which regions respond to scarring?"):
    client = pst.FakeParentClient(answer=answer)
    sup = supervisor or pst.make_s2_supervisor(client)
    result = ps.realize(claims, sealed, supervisor=sup, entail=entail or pst.FakeEntail(), question=question)
    return result, client


class PromptAndSchemaTests(unittest.TestCase):
    def test_prompt_carries_only_authorized_envelopes_and_the_question(self):
        sealed, claims = _single_claim()
        sealed["verified_propositions"][0]["quote"] += " A sentence that is only in the passage, not any claim."
        prompt = ps.build_prompt(claims, "Which regions respond to scarring?")
        self.assertIn(claims[0]["claim_id"], prompt)
        self.assertIn("the amygdala responded to scarring", prompt)
        self.assertNotIn("only in the passage", prompt)  # the passage itself never enters the prompt
        self.assertNotIn("proposition_id", prompt)
        self.assertNotIn("p1", prompt.split("\n"))

    def test_schema_is_closed_and_structural_only(self):
        """Phase 27a: the whole-answer schema carries structure and runaway caps only. The claim-id enum and the
        editorial minimum are gone; an unknown id or a short statement is decided per item, not as a whole-answer NO
        ANSWER."""
        _sealed, claims = _three_claims()
        ids = [c["claim_id"] for c in claims]
        schema = ps.build_schema(ids)
        items = schema["properties"]["items"]
        self.assertEqual(items["maxItems"], ps.SCHEMA_ITEMS_PER_CLAIM * len(ids))
        props = items["items"]["properties"]
        self.assertEqual(set(props), {"claim_id", "statement"})  # no citation/proposition field can exist
        self.assertNotIn("enum", props["claim_id"])
        self.assertEqual(props["claim_id"]["maxLength"], ps.SCHEMA_CLAIM_ID_MAX_CHARS)
        self.assertNotIn("minLength", props["statement"])  # the editorial floor is per item, never whole-answer
        self.assertEqual(props["statement"]["maxLength"], ps.SCHEMA_STATEMENT_MAX_CHARS)
        self.assertFalse(items["items"]["additionalProperties"])
        self.assertEqual(schema["required"], ["items"])

    def test_contract_hash_is_stable(self):
        self.assertEqual(ps.contract_sha256(), ps.contract_sha256())

    def test_legitimate_output_fits_the_budget_for_the_real_scale(self):
        _sealed, claims = _three_claims()
        budget = topo.PARENT_SYNTHESIS_S_OPTIONS["num_predict"] * 3
        self.assertLessEqual(ps.legitimate_output_chars([c["claim_id"] for c in claims]), budget)


class EnvelopeTests(unittest.TestCase):
    def test_role_value_envelope_names_the_category_and_the_exact_text(self):
        _sealed, claims = _single_claim()
        text = ps.authorized_claim_text(claims[0])
        self.assertIn("a named brain region", text)
        self.assertIn("the amygdala responded to scarring", text)

    def test_category_list_envelope_lists_every_member(self):
        sealed = pst.sealed_with(("p1", 1, "bilateral fusiform", ["x"]), ("p2", 2, "right hippocampus", ["x"]))
        specs = {"region": pst.spec("region", "a named region")}
        req = pst.requirement(
            "x#req",
            specs,
            se.new_role_completion(required_roles=["region"]),
            "for_each_discovered_instance",
            [
                pst.instance({"region": pst.filled("region", "p1", "bilateral fusiform")}, instance_key="i1"),
                pst.instance({"region": pst.filled("region", "p2", "right hippocampus")}, instance_key="i2"),
            ],
        )
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        text = ps.authorized_claim_text(_claim(claims, "category_list"))
        self.assertIn("bilateral fusiform", text)
        self.assertIn("right hippocampus", text)

    def test_relational_envelope_is_one_joint_relation(self):
        sealed, smf, claims = _c12_claims()
        text = ps.authorized_claim_text(_claim(claims, "relational"))
        self.assertIn("One already-established joint relation", text)
        self.assertIn(pst.C12_WRONG_TARGET_MANIFESTATION_TEXT, text)

    def test_direction_envelope_uses_words_not_internal_keys(self):
        sealed, smf, claims = _heterogeneous_claims()
        text = ps.authorized_claim_text(_claim(claims, "direction_or_effectiveness"))
        self.assertIn("not supported", text)
        self.assertNotIn("not_supported", text)
        self.assertNotIn("i::", text)
        self.assertIn("heterogeneous across instances: yes", text)


def _c12_claims():
    sealed, smf = pst.real_c12_fixture()
    return sealed, smf, psl.build_claim_ledger(smf, sealed)


def _heterogeneous_claims():
    sealed = pst.sealed_with(
        ("p1", 1, "Intervention X showed decreased bias scores in the treatment group.", ["x"]),
        ("p2", 2, "No significant effect of Intervention X on bias scores was observed.", ["x"]),
    )
    specs = {"a": pst.spec("a", "category a")}
    inst1 = pst.instance({"a": pst.filled("a", "p1", "decreased bias scores")}, instance_key="i1")
    inst2 = pst.instance({"a": pst.filled("a", "p2", "no significant effect")}, instance_key="i2")
    req = pst.requirement(
        "x#req",
        specs,
        se.new_role_completion(required_roles=["a"]),
        "for_each_discovered_instance",
        [inst1, inst2],
        multi_instance=True,
        effectiveness=se.new_effectiveness_assessment(),
    )
    smf = pst.map_with("x", req)
    sd.compute_direction_and_effectiveness(sealed, smf)
    return sealed, smf, psl.build_claim_ledger(smf, sealed)


class ParseTests(unittest.TestCase):
    def test_non_dict_answer_is_malformed(self):
        with self.assertRaises(ps.MalformedParentOutput):
            ps.parse_items(["not", "a", "dict"])

    def test_items_must_be_a_list(self):
        with self.assertRaises(ps.MalformedParentOutput):
            ps.parse_items({"items": "text"})

    def test_an_item_missing_its_statement_is_malformed(self):
        with self.assertRaises(ps.MalformedParentOutput):
            ps.parse_items({"items": [{"claim_id": "x::1"}]})

    def test_well_formed_items_parse_to_claim_id_and_statement_only(self):
        items = ps.parse_items({"items": [{"claim_id": "x::1", "statement": "A statement."}]})
        self.assertEqual(items, [{"claim_id": "x::1", "statement": "A statement."}])


class ClaimValueScreenTests(unittest.TestCase):
    def test_same_passage_substitution_is_withheld_by_claim_value_fidelity(self):
        """Domain-neutral (Section 35): one passage holds phrases A and B; the claim authorizes only A."""
        sealed = pst.sealed_with(("p1", 1, "Alpha widgets increased output while beta gadgets were reported.", ["x"]))
        specs = {"subject": pst.spec("subject", "a reported subject")}
        req = pst.requirement(
            "x#req",
            specs,
            se.new_role_completion(required_roles=["subject"]),
            "exists",
            [pst.instance({"subject": pst.filled("subject", "p1", "alpha widgets")})],
        )
        claim = _claim(psl.build_claim_ledger(pst.map_with("x", req), sealed), "role_value")
        statement = "Beta gadgets were reported."
        self.assertTrue(ps.claim_value_reasons(claim, statement, [claim]))
        self.assertEqual(ps.source_passage_reasons(claim, statement, sealed), [])  # the passage DOES contain B

    def test_c12_corrected_alternate_target_is_withheld_while_source_passage_passes(self):
        """Section 34: the same p-passage carries the correct alternate phrase; claim-value fidelity fails."""
        sealed, smf, claims = _c12_claims()
        relational = _claim(claims, "relational")
        statement = "The intervention targeted bias against people with anomalous faces."
        claim_reasons = ps.claim_value_reasons(relational, statement, claims)
        self.assertTrue(any("target_manifestation" in r for r in claim_reasons), claim_reasons)
        self.assertEqual(ps.source_passage_reasons(relational, statement, sealed), [])

    def test_a_statement_importing_another_claims_value_is_withheld(self):
        sealed, _smf, claims = _two_unrelated_claims()
        a = next(c for c in claims if c["role"] == "region")
        statement = "The amygdala responded to scarring, and participants avoided the scarred faces."
        self.assertTrue(any(r.startswith("imports_other_claim") for r in ps.claim_value_reasons(a, statement, claims)))

    def test_new_relation_language_is_withheld(self):
        sealed, _smf, claims = _two_unrelated_claims()
        a = next(c for c in claims if c["role"] == "region")
        self.assertTrue(
            any(
                r.startswith("relation_language_not_in_claim")
                for r in ps.claim_value_reasons(
                    a, "The amygdala responded to scarring, which is associated with avoidance.", claims
                )
            )
        )

    def test_a_faithful_restatement_passes_the_claim_value_screen(self):
        sealed, claims = _single_claim()
        statement = "The amygdala responded to scarring."
        self.assertEqual(ps.claim_value_reasons(claims[0], statement, claims), [])

    def test_a_dropped_hedge_is_withheld(self):
        sealed = pst.sealed_with(("p1", 1, "The insula might respond to scarring.", ["x"]))
        specs = {"region": pst.spec("region", "a named region")}
        req = pst.requirement(
            "x#req",
            specs,
            se.new_role_completion(required_roles=["region"]),
            "exists",
            [pst.instance({"region": pst.filled("region", "p1", "The insula might respond to scarring.")})],
        )
        claim = _claim(psl.build_claim_ledger(pst.map_with("x", req), sealed), "role_value")
        self.assertTrue(ps.claim_value_reasons(claim, "The insula responds to scarring.", [claim]))


class HeterogeneityGuardTests(unittest.TestCase):
    def test_overall_collapse_of_a_heterogeneous_effect_is_withheld(self):
        """Section 37: 'Overall, X increases Y.' on a heterogeneous claim is withheld."""
        sealed, smf, claims = _heterogeneous_claims()
        de = _claim(claims, "direction_or_effectiveness")
        self.assertTrue(ps.heterogeneity_reasons(de, "Overall, the intervention reduced bias."))

    def test_faithful_heterogeneity_phrasing_with_observed_values_is_accepted(self):
        sealed, smf, claims = _heterogeneous_claims()
        de = _claim(claims, "direction_or_effectiveness")
        statement = "Effects differed across instances: one showed support and another found no significant effect."
        self.assertEqual(ps.heterogeneity_reasons(de, statement), [])

    def test_a_consensus_claim_is_never_subject_to_the_heterogeneity_guard(self):
        sealed, smf, claims = _c12_claims()
        de = _claim(claims, "direction_or_effectiveness")
        self.assertEqual(ps.heterogeneity_reasons(de, "Overall, the intervention was supported."), [])


class RealizeTests(unittest.TestCase):
    def test_A_faithful_realization_is_model_realized_with_exactly_one_call(self):
        sealed, claims = _three_claims()
        result, client = _run(claims, sealed, answer={"items": _grounded_items(claims)})
        self.assertEqual(result["state"], "model_realized")
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(result["call_attempted"])
        self.assertEqual(result["grounded_count"], 3)

    def test_B_malformed_output_falls_back_every_claim_without_retry(self):
        sealed, claims = _three_claims()
        result, client = _run(claims, sealed, answer="this is not json at all")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(result["state"], "deterministic_fallback")
        self.assertEqual(result["grounded_count"], 0)

    def test_C_a_raising_model_call_falls_back_every_claim(self):
        sealed, claims = _three_claims()

        def boom(prompt, schema):
            raise RuntimeError("transport down")

        result, client = _run(claims, sealed, answer=boom)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(result["state"], "deterministic_fallback")
        self.assertIn("exception", result["whole_call_status"])

    def test_D_a_missing_claim_gets_a_per_claim_fallback_and_is_never_dropped(self):
        sealed, claims = _three_claims()
        items = _grounded_items(claims)[:-1]
        result, _client = _run(claims, sealed, answer={"items": items})
        statuses = [s["status"] for s in result["segments"]]
        self.assertEqual(statuses.count("missing"), 1)
        self.assertEqual(len(result["segments"]), len(claims))
        self.assertEqual(result["state"], "mixed_model_and_fallback")

    def test_E_a_duplicate_claim_id_falls_back_that_claim_once_and_never_renders_twice(self):
        """Phase 27a: a duplicated id is per-item. Neither copy is trusted, that claim falls back exactly once, and
        its valid siblings stay grounded. [c0, c0, c1, c2] for three claims: c0 duplicate, c1 and c2 grounded."""
        sealed, claims = _three_claims()
        base = _grounded_items(claims)
        items = [base[0], base[0], base[1], base[2]]
        result, client = _run(claims, sealed, answer={"items": items})
        by_id = {s["claim_id"]: s for s in result["segments"]}
        self.assertEqual(by_id[claims[0]["claim_id"]]["status"], "duplicate")
        self.assertEqual(by_id[claims[1]["claim_id"]]["status"], "grounded")
        self.assertEqual(by_id[claims[2]["claim_id"]]["status"], "grounded")
        self.assertEqual(len(result["segments"]), len(claims))
        self.assertEqual(result["item_diagnostics"]["duplicate_claim_ids"], [claims[0]["claim_id"]])
        self.assertEqual(len(client.calls), 1)

    def test_F_an_unknown_claim_id_is_recorded_and_never_contaminates_known_siblings(self):
        """Phase 27a: an unknown id is no longer a whole-answer schema failure. It is recorded and discarded, and
        every known claim still appears exactly once, grounded."""
        sealed, claims = _three_claims()
        base = _grounded_items(claims)
        items = [base[0], base[1], {"claim_id": "ghost::0000", "statement": "A ghost claim is stated."}, base[2]]
        result, client = _run(claims, sealed, answer={"items": items})
        self.assertEqual(result["unknown_claim_ids"], ["ghost::0000"])
        self.assertNotIn("ghost::0000", [s["claim_id"] for s in result["segments"]])
        self.assertEqual(result["grounded_count"], 3)
        self.assertEqual(len(client.calls), 1)

    def test_G_unsupported_wording_is_withheld_per_claim_others_stay_grounded(self):
        sealed, claims = _three_claims()
        bad = claims[1]["claim_id"]
        items = _grounded_items(claims, {bad: "The insula causes a loss of attention."})
        result, _client = _run(claims, sealed, answer={"items": items})
        by_id = {s["claim_id"]: s for s in result["segments"]}
        self.assertEqual(by_id[bad]["status"], "withheld")
        self.assertEqual(result["grounded_count"], 2)

    def test_H_a_cross_claim_relation_invention_is_withheld_and_both_claims_render_separately(self):
        sealed, _smf, claims = _two_unrelated_claims()
        a = next(c for c in claims if c["role"] == "region")
        items = [
            {
                "claim_id": a["claim_id"],
                "statement": "The amygdala responded to scarring, which is associated with avoidance.",
            },
            {
                "claim_id": next(c for c in claims if c["role"] == "behavior")["claim_id"],
                "statement": "Participants avoided the scarred faces.",
            },
        ]
        result, _client = _run(claims, sealed, answer={"items": items})
        by_id = {s["claim_id"]: s for s in result["segments"]}
        self.assertEqual(by_id[a["claim_id"]]["status"], "withheld")
        self.assertIn("amygdala", by_id[a["claim_id"]]["final_text"])
        self.assertNotIn("associated", by_id[a["claim_id"]]["final_text"])

    def test_I_c12_silent_correction_is_withheld_and_fallback_keeps_the_wrong_value(self):
        """Section 34 (the strongest upstream-error proof): passage-grounded, but a different value."""
        sealed, smf, claims = _c12_claims()
        relational = _claim(claims, "relational")
        corrected = "The intervention targeted bias against people with anomalous faces."
        items = _grounded_items(claims, {relational["claim_id"]: corrected})
        result, _client = _run(claims, sealed, answer={"items": items})
        seg = next(s for s in result["segments"] if s["claim_id"] == relational["claim_id"])
        self.assertEqual(seg["status"], "withheld")
        self.assertEqual(seg["evidence_screen_reasons"], [])  # passage-grounded, so the evidence screen passes
        self.assertTrue(seg["claim_screen_reasons"])  # but claim-value fidelity fails
        # the deterministic literal fallback, exactly as the Phase-26 renderer states it -- the wrong value intact
        self.assertEqual(seg["final_text"], psr.literal_statement(relational))
        self.assertIn(pst.C12_WRONG_TARGET_MANIFESTATION_TEXT, seg["final_text"])

    def test_J_a_heterogeneity_collapse_is_withheld(self):
        sealed, smf, claims = _heterogeneous_claims()
        de = _claim(claims, "direction_or_effectiveness")
        items = [{"claim_id": de["claim_id"], "statement": "Overall, the intervention reduced bias."}]
        result, _client = _run(claims, sealed, answer={"items": items})
        seg = next(s for s in result["segments"] if s["claim_id"] == de["claim_id"])
        self.assertEqual(seg["status"], "withheld")
        self.assertTrue(seg["heterogeneity_reasons"])

    def test_K_a_valid_paraphrase_that_keeps_every_value_is_accepted(self):
        sealed, claims = _single_claim()
        items = [
            {
                "claim_id": claims[0]["claim_id"],
                "statement": "The amygdala responded to scarring, per the reported finding.",
            }
        ]
        result, _client = _run(claims, sealed, answer={"items": items})
        self.assertEqual(result["segments"][0]["status"], "grounded")

    def test_L_a_prompt_over_the_cap_skips_the_call_and_falls_back_for_every_claim(self):
        sealed, claims = _three_claims()
        client = pst.FakeParentClient(answer={"items": []})
        result = ps.realize(
            claims,
            sealed,
            supervisor=pst.make_s2_supervisor(client),
            entail=pst.FakeEntail(),
            question="q",
            prompt_char_cap=10,
        )
        self.assertEqual(client.calls, [])
        self.assertEqual(result["skip_reason"], "prompt_too_large")
        self.assertFalse(result["call_attempted"])

    def test_no_claims_means_no_call(self):
        client = pst.FakeParentClient(answer={"items": []})
        result = ps.realize(
            [], pst.sealed_with(), supervisor=pst.make_s2_supervisor(client), entail=pst.FakeEntail(), question="q"
        )
        self.assertEqual(client.calls, [])
        self.assertEqual(result["state"], "no_claims")

    def test_no_s_supervisor_means_no_call_and_deterministic_fallback(self):
        sealed, claims = _three_claims()
        result = ps.realize(claims, sealed, supervisor=None, entail=pst.FakeEntail(), question="q")
        self.assertEqual(result["skip_reason"], "no_s_supervisor")
        self.assertFalse(result["call_attempted"])
        self.assertEqual(result["state"], "deterministic_fallback")

    def test_a_binding_that_is_not_the_parent_envelope_refuses_the_call(self):
        sealed, claims = _three_claims()
        client = pst.FakeParentClient(answer={"items": _grounded_items(claims)})
        sup = pst.make_s2_supervisor(client, base_options=topo.OVERVIEW_S_OPTIONS)
        result = ps.realize(claims, sealed, supervisor=sup, entail=pst.FakeEntail(), question="q")
        self.assertEqual(client.calls, [])
        self.assertEqual(result["skip_reason"], "s_binding_not_parent_envelope")

    def test_a_thinking_on_binding_refuses_the_call(self):
        sealed, claims = _three_claims()
        client = pst.FakeParentClient(answer={"items": _grounded_items(claims)})
        sup = pst.make_s2_supervisor(client, binding=topo.OVERVIEW_PROFILES["T5O"].S)
        result = ps.realize(claims, sealed, supervisor=sup, entail=pst.FakeEntail(), question="q")
        self.assertEqual(client.calls, [])
        self.assertEqual(result["skip_reason"], "s_binding_not_parent_envelope")

    def test_NLI_failure_falls_back_conservatively_and_never_retries(self):
        sealed, claims = _three_claims()
        client = pst.FakeParentClient(answer={"items": _grounded_items(claims)})
        result = ps.realize(
            claims,
            sealed,
            supervisor=pst.make_s2_supervisor(client),
            entail=pst.FakeEntail(raises=RuntimeError("nli down")),
            question="q",
        )
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(result["grounded_count"], 0)
        self.assertEqual(result["state"], "deterministic_fallback")

    def test_one_batched_validation_call_for_all_candidates(self):
        sealed, claims = _three_claims()
        entail = pst.FakeEntail()
        _run(claims, sealed, answer={"items": _grounded_items(claims)}, entail=entail)
        self.assertEqual(len(entail.batches), 1)
        self.assertEqual(entail.batches[0], 2 * len(claims))  # a claim pair and a source pair per candidate

    def test_partial_validity_preserves_every_claim_exactly_once(self):
        """Section 38: one valid, one unsupported, one omitted."""
        sealed, claims = _three_claims()
        valid, unsupported, _omitted = claims
        items = [
            {"claim_id": valid["claim_id"], "statement": "The amygdala responded to scarring."},
            {"claim_id": unsupported["claim_id"], "statement": "The insula causes a loss of attention."},
        ]
        result, _client = _run(claims, sealed, answer={"items": items})
        statuses = {s["claim_id"]: s["status"] for s in result["segments"]}
        self.assertEqual(statuses[valid["claim_id"]], "grounded")
        self.assertEqual(statuses[unsupported["claim_id"]], "withheld")
        self.assertEqual(statuses[_omitted["claim_id"]], "missing")
        self.assertEqual(len(result["segments"]), 3)
        self.assertEqual(result["grounded_count"], 1)


class CitationControlTests(unittest.TestCase):
    def test_grounded_citations_are_exactly_the_claims_admissible_ids(self):
        sealed, claims = _three_claims()
        result, _client = _run(claims, sealed, answer={"items": _grounded_items(claims)})
        for seg, claim in zip(result["segments"], claims, strict=True):
            self.assertEqual(seg["cited_proposition_ids"], claim["admissible_proposition_ids"])

    def test_the_output_schema_offers_the_model_no_citation_field(self):
        _sealed, claims = _three_claims()
        props = ps.build_schema([c["claim_id"] for c in claims])["properties"]["items"]["items"]["properties"]
        self.assertEqual(set(props), {"claim_id", "statement"})


class IndependenceTests(unittest.TestCase):
    def test_realize_takes_no_overview_or_child_prose_input(self):
        params = list(inspect.signature(ps.realize).parameters)
        self.assertEqual(params[:2], ["claim_ledger", "sealed"])
        for forbidden in ("overview", "child_overview", "overview_record", "items", "proposals"):
            self.assertNotIn(forbidden, params)


if __name__ == "__main__":
    unittest.main()
