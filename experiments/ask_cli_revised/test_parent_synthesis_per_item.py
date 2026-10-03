"""Phase 27a: per-item realization recovery, the structural whole-answer boundary, and surface-only dedup. Offline only:
scripted S2 clients, a recording NLI fake, and a real stages.Supervisor -- no Ollama, no network. Letters cross-reference
the Phase-27a brief's required matrix (sections 12 A-O). The Phase-26 ledger is never touched by any of these tests.
"""

from __future__ import annotations

import copy
import unittest

from experiments.ask_cli_revised import parent_synthesis as ps
from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_render as psr
from experiments.ask_cli_revised import parent_synthesis_test_support as pst
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised.test_parent_synthesis import (
    _c12_claims,
    _claim,
    _grounded_items,
    _heterogeneous_claims,
    _run,
    _three_claims,
)


def _n_claims(n: int):
    """``n`` independent role-value claims, each with its own distinct content word (so no claim imports another's
    value) and its own passage. The claim ledger is built by the real Phase-26 code."""
    specs, maps = [], {}
    for i in range(n):
        specs.append((f"p{i}", i + 1, f"the nucleus{i:02d} responded to scarring", [f"c{i}"]))
    sealed = pst.sealed_with(*specs)
    for i in range(n):
        req = pst.requirement(
            f"c{i}#req",
            {"region": pst.spec("region", f"a named region {i}")},
            se.new_role_completion(required_roles=["region"]),
            "exists",
            [pst.instance({"region": pst.filled("region", f"p{i}", f"the nucleus{i:02d} responded to scarring")})],
        )
        maps.update(pst.map_with(f"c{i}", req))
    return sealed, psl.build_claim_ledger(maps, sealed)


def _faithful_for(claims, *, overrides=None):
    """One item per claim, each restating its own authorized value, with ``overrides`` replacing chosen statements."""
    overrides = overrides or {}
    return [
        {"claim_id": c["claim_id"], "statement": overrides.get(c["claim_id"], f"{c['values'][0]['exact_text']}.")}
        for c in claims
    ]


def _statuses(result):
    return {s["claim_id"]: s["status"] for s in result["segments"]}


class ThreeClaimRecoveryTests(unittest.TestCase):
    """A. 3 claims: valid + too-short + valid -> grounded / fallback / grounded."""

    def test_A_a_too_short_item_falls_back_only_its_own_claim(self):
        sealed, claims = _three_claims()
        base = _grounded_items(claims)
        base[1] = {"claim_id": claims[1]["claim_id"], "statement": "explicit"}  # 8 characters
        result, client = _run(claims, sealed, answer={"items": base})
        statuses = _statuses(result)
        self.assertEqual(statuses[claims[0]["claim_id"]], "grounded")
        self.assertEqual(statuses[claims[1]["claim_id"]], "invalid_item")
        self.assertEqual(statuses[claims[2]["claim_id"]], "grounded")
        self.assertEqual(result["state"], "mixed_model_and_fallback")
        self.assertEqual(result["whole_call_status"], "ok")
        self.assertEqual(len(client.calls), 1)  # O: exactly one call, zero retry


class TwentyFourClaimRecoveryTests(unittest.TestCase):
    """B. 24 claims, one too-short item -> exactly one fallback, not 24."""

    def test_B_one_too_short_item_among_twenty_four_is_exactly_one_fallback(self):
        sealed, claims = _n_claims(24)
        items = _faithful_for(claims, overrides={claims[7]["claim_id"]: "ok"})
        result, client = _run(claims, sealed, answer={"items": items})
        statuses = [s["status"] for s in result["segments"]]
        self.assertEqual(statuses.count("invalid_item"), 1)
        self.assertEqual(statuses.count("grounded"), 23)
        self.assertEqual(result["grounded_count"], 23)
        self.assertEqual(result["fallback_count"], 1)
        self.assertEqual(result["state"], "mixed_model_and_fallback")
        self.assertEqual(len(client.calls), 1)

    def test_editorial_length_is_not_a_schema_failure(self):
        """The corrected boundary, stated directly: the supervisor accepts the answer with a too-short statement, so
        it is judged per item rather than returned as NO ANSWER."""
        sealed, claims = _n_claims(3)
        items = _faithful_for(claims, overrides={claims[0]["claim_id"]: "no"})
        supervisor = pst.make_s2_supervisor(pst.FakeParentClient(answer={"items": items}))
        raw = supervisor.call(ps.STAGE, "p", ps.build_schema([c["claim_id"] for c in claims]))
        self.assertIsNotNone(raw.answer)  # the schema no longer returns NO ANSWER for this
        self.assertEqual(len(raw.answer["items"]), 3)


class DuplicateUnknownMissingTests(unittest.TestCase):
    """C, D, E: duplicate, unknown and missing identifiers never collapse their valid siblings."""

    def test_C_a_duplicate_claim_id_falls_back_that_claim_once_and_siblings_survive(self):
        sealed, claims = _three_claims()
        base = _grounded_items(claims)
        items = [base[0], base[0], base[1], base[2]]
        result, client = _run(claims, sealed, answer={"items": items})
        statuses = _statuses(result)
        self.assertEqual(statuses[claims[0]["claim_id"]], "duplicate")
        self.assertEqual(statuses[claims[1]["claim_id"]], "grounded")
        self.assertEqual(statuses[claims[2]["claim_id"]], "grounded")
        self.assertEqual(sum(1 for s in result["segments"] if s["claim_id"] == claims[0]["claim_id"]), 1)
        self.assertEqual(len(client.calls), 1)

    def test_D_an_unknown_claim_id_is_rejected_and_known_siblings_survive(self):
        sealed, claims = _three_claims()
        base = _grounded_items(claims)
        items = [base[0], {"claim_id": "ghost::0000", "statement": "A ghost claim is stated."}, base[1], base[2]]
        result, client = _run(claims, sealed, answer={"items": items})
        self.assertEqual(result["unknown_claim_ids"], ["ghost::0000"])
        self.assertNotIn("ghost::0000", [s["claim_id"] for s in result["segments"]])
        self.assertEqual(result["grounded_count"], 3)
        self.assertEqual(len(client.calls), 1)

    def test_E_a_missing_claim_falls_back_only_that_claim(self):
        sealed, claims = _three_claims()
        result, client = _run(claims, sealed, answer={"items": _grounded_items(claims)[:2]})
        statuses = _statuses(result)
        self.assertEqual(statuses[claims[2]["claim_id"]], "missing")
        self.assertEqual(statuses[claims[0]["claim_id"]], "grounded")
        self.assertEqual(statuses[claims[1]["claim_id"]], "grounded")
        self.assertEqual(len(client.calls), 1)


class WholeCallBoundaryTests(unittest.TestCase):
    """F, G: whole-call failure is reserved for an answer that cannot be safely recovered as an item list."""

    def test_F_completely_malformed_top_level_responses_fall_back_the_whole_call(self):
        sealed, claims = _three_claims()
        for answer in ("not json at all", ["a", "list", "at", "top"], {"items": "not a list"}, {"items": [5]}):
            with self.subTest(answer=answer):
                result, client = _run(claims, sealed, answer=answer)
                self.assertEqual(result["state"], "deterministic_fallback")
                self.assertEqual(result["grounded_count"], 0)
                self.assertEqual(len(client.calls), 1)

    def test_F_an_item_that_breaks_the_closed_shape_is_a_whole_call_failure(self):
        """A closed {claim_id, statement} object is the structural contract. An extra key is not an identifiable item."""
        sealed, claims = _three_claims()
        items = _grounded_items(claims)
        items[0]["citation"] = "p1"
        result, _client = _run(claims, sealed, answer={"items": items})
        self.assertEqual(result["state"], "deterministic_fallback")
        self.assertEqual(result["grounded_count"], 0)

    def test_G_a_model_exception_falls_back_the_whole_call(self):
        sealed, claims = _three_claims()

        def boom(prompt, schema):
            raise RuntimeError("transport down")

        result, client = _run(claims, sealed, answer=boom)
        self.assertEqual(result["state"], "deterministic_fallback")
        self.assertIn("exception", result["whole_call_status"])
        self.assertEqual(len(client.calls), 1)

    def test_a_runaway_statement_beyond_the_structural_cap_is_a_whole_answer_failure(self):
        """The one structural exception, stated precisely: beyond the runaway cap a statement is a whole-answer failure.
        Between the editorial maximum and that cap it is per item (next test)."""
        sealed, claims = _three_claims()
        items = _grounded_items(claims)
        items[0]["statement"] = "x" * (ps.SCHEMA_STATEMENT_MAX_CHARS + 1)
        result, _client = _run(claims, sealed, answer={"items": items})
        self.assertEqual(result["state"], "deterministic_fallback")

    def test_a_statement_over_the_editorial_maximum_is_per_item_invalid(self):
        sealed, claims = _three_claims()
        items = _grounded_items(claims)
        items[1]["statement"] = "x" * (ps.MAX_STATEMENT_CHARS + 1) + " amygdala responded."
        result, client = _run(claims, sealed, answer={"items": items})
        statuses = _statuses(result)
        self.assertEqual(statuses[claims[1]["claim_id"]], "invalid_item")
        self.assertIn("statement_too_long", result["segments"][1]["item_reasons"])
        self.assertEqual(result["grounded_count"], 2)
        self.assertEqual(len(client.calls), 1)

    def test_an_all_invalid_answer_is_a_deterministic_fallback_with_a_completed_call(self):
        sealed, claims = _three_claims()
        items = [{"claim_id": c["claim_id"], "statement": "ok"} for c in claims]
        result, client = _run(claims, sealed, answer={"items": items})
        self.assertEqual(result["state"], "deterministic_fallback")
        self.assertEqual(result["whole_call_status"], "ok")
        self.assertTrue(all(s["status"] == "invalid_item" for s in result["segments"]))
        self.assertEqual(len(client.calls), 1)


class PerClaimScreenTests(unittest.TestCase):
    """H, I, J: each fidelity layer still fails only the claim it judged."""

    def test_H_claim_value_fidelity_failure_is_per_claim(self):
        sealed, claims = _n_claims(3)
        wrong = claims[1]
        items = _faithful_for(claims, overrides={wrong["claim_id"]: "the nucleus02 responded to scarring."})
        result, _client = _run(claims, sealed, answer={"items": items})
        by_id = {s["claim_id"]: s for s in result["segments"]}
        self.assertEqual(by_id[wrong["claim_id"]]["status"], "withheld")
        self.assertTrue(by_id[wrong["claim_id"]]["claim_screen_reasons"])
        self.assertEqual(by_id[claims[0]["claim_id"]]["status"], "grounded")
        self.assertEqual(by_id[claims[2]["claim_id"]]["status"], "grounded")

    def test_I_source_passage_failure_is_per_claim(self):
        sealed, claims = _n_claims(3)
        bad_statement = "the nucleus01 responded to scarring."
        bad = claims[1]

        def score(premise, hypothesis):
            # The claim-envelope layer is supported; only the source passage contradicts this one statement.
            if hypothesis == bad_statement and "Category:" not in premise:
                return (0.05, 0.9)
            return (0.9, 0.05)

        items = _faithful_for(claims, overrides={bad["claim_id"]: bad_statement})
        result, _client = _run(claims, sealed, answer={"items": items}, entail=pst.FakeEntail(score=score))
        by_id = {s["claim_id"]: s for s in result["segments"]}
        self.assertEqual(by_id[bad["claim_id"]]["status"], "withheld")
        self.assertEqual(by_id[bad["claim_id"]]["claim_screen_reasons"], [])  # the claim layer passed
        self.assertTrue(by_id[bad["claim_id"]]["nli_reasons"])
        self.assertEqual(by_id[claims[0]["claim_id"]]["status"], "grounded")
        self.assertEqual(by_id[claims[2]["claim_id"]]["status"], "grounded")

    def test_J_heterogeneity_collapse_is_per_claim(self):
        sealed, _smf, claims = _heterogeneous_claims()
        direction = _claim(claims, "direction_or_effectiveness")
        items = [{"claim_id": direction["claim_id"], "statement": "Overall, the intervention reduced bias."}]
        result, client = _run(claims, sealed, answer={"items": items})
        seg = next(s for s in result["segments"] if s["claim_id"] == direction["claim_id"])
        self.assertEqual(seg["status"], "withheld")
        self.assertTrue(seg["heterogeneity_reasons"])
        self.assertEqual(len(client.calls), 1)


class SurfaceDedupTests(unittest.TestCase):
    """K, L, M: identical surface values display once; evidence and the ledger are untouched."""

    @staticmethod
    def _category_list(values, props):
        return {
            "claim_id": "category_list::hadza0000",
            "claim_kind": "category_list",
            "category_description": "a named culture",
            "role": "culture",
            "values": [
                {"exact_text": v, "proposition_id": p, "role": "culture"} for v, p in zip(values, props, strict=True)
            ],
            "admissible_proposition_ids": list(props),
        }

    def test_K_hadza_backed_by_two_propositions_displays_once_and_keeps_both_supports(self):
        claim = self._category_list(["Hadza", "Hadza"], ["p1", "p2"])
        self.assertEqual(psr.literal_statement(claim), "a named culture: Hadza.")
        self.assertEqual(len(claim["values"]), 2)  # both corroborating values remain in the ledger
        self.assertEqual(claim["admissible_proposition_ids"], ["p1", "p2"])  # both supports remain
        self.assertIn("p1", psr.format_citations(claim))
        self.assertIn("p2", psr.format_citations(claim))
        self.assertEqual(ps.authorized_claim_text(claim).count("- Hadza"), 1)

    def test_L_near_but_not_identical_values_both_display(self):
        self.assertEqual(
            psr.distinct_surface(["right amygdala", "bilateral amygdala"]), ["right amygdala", "bilateral amygdala"]
        )
        self.assertEqual(psr.distinct_surface(["implicit bias", "explicit bias"]), ["implicit bias", "explicit bias"])
        claim = self._category_list(["right amygdala", "bilateral amygdala"], ["p1", "p2"])
        self.assertEqual(psr.literal_statement(claim), "a named culture: right amygdala; bilateral amygdala.")

    def test_whitespace_only_difference_is_the_same_surface_value(self):
        self.assertEqual(psr.distinct_surface(["Hadza", "Hadza  ", " Hadza"]), ["Hadza"])

    def test_M_rendering_never_mutates_the_ledger(self):
        claim = self._category_list(["Hadza", "Hadza"], ["p1", "p2"])
        before = copy.deepcopy(claim)
        psr.literal_statement(claim)
        ps.authorized_claim_text(claim)
        ps.build_prompt([claim], "q")
        self.assertEqual(claim, before)


class ClaimValueAndCitationInvariantTests(unittest.TestCase):
    """N, O: the c12 adversarial correction is still withheld, and the answer keeps the ledger's own citations."""

    def test_N_c12_adversarial_correction_is_still_withheld(self):
        sealed, smf, claims = _c12_claims()
        relational = _claim(claims, "relational")
        corrected = "The intervention targeted bias against people with anomalous faces."
        items = _grounded_items(claims, {relational["claim_id"]: corrected})
        result, client = _run(claims, sealed, answer={"items": items})
        seg = next(s for s in result["segments"] if s["claim_id"] == relational["claim_id"])
        self.assertEqual(seg["status"], "withheld")
        self.assertIn(pst.C12_WRONG_TARGET_MANIFESTATION_TEXT, seg["final_text"])
        self.assertEqual(len(client.calls), 1)

    def test_grounded_citations_are_exactly_the_claims_admissible_ids_after_per_item_recovery(self):
        sealed, claims = _three_claims()
        base = _grounded_items(claims)
        base[1] = {"claim_id": claims[1]["claim_id"], "statement": "ok"}
        result, _client = _run(claims, sealed, answer={"items": base})
        for seg, claim in zip(result["segments"], claims, strict=True):
            self.assertEqual(seg["cited_proposition_ids"], claim["admissible_proposition_ids"])


if __name__ == "__main__":
    unittest.main()
