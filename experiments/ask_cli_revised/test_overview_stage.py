"""The overview stage: prompt, the one model call, screening, honest states, request-part status, and the separate artifact."""

import copy
import json
import unittest

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.overview_test_support import (
    ABSENT,
    FRAGMENT,
    GIVING,
    HEDGE,
    NULL,
    PATTERN,
    S1,
    S2,
    S3,
    STUDY,
    Entail,
    OverviewClient,
    build,
    entail_raises,
    sealed_ledger,
    stmt,
    uid,
)

FAITHFUL_GIVING = "In one study the insular response to pictured scarring correlated with lower generosity toward the people pictured."
FAITHFUL_HEDGE = (
    "One paper suggests that training in perspective taking might reduce avoidance of people with visible scarring."
)
FAITHFUL_NULL = "Participants reported explicit dislike of people with scarring, but implicit dislike was small and not significant."
FABRICATED = (
    "Avoidance is reduced in people with visible scarring."  # the p4 structure: direction and population invented
)


def ledger():
    return sealed_ledger(
        [
            ("Generosity was lower toward the people pictured.", GIVING, [S1]),
            (
                "Avoidance is reduced in people with visible scarring.",
                PATTERN,
                [S1],
            ),  # adds a direction its passage lacks
            ("Avoidance is linked to visible scarring.", PATTERN, [S1]),
            ("Training might reduce avoidance.", HEDGE, [S2]),
            ("Explicit dislike was reported; implicit dislike was small.", NULL, [S1]),
            ("The aversion is culturally shared.", FRAGMENT, [S3]),  # truncated: excluded from synthesis
            ("The study examined dislike and gaze.", STUDY, [S1]),  # a description, not a finding
            ("Earlier studies did not examine cultures.", ABSENT, []),  # unattached scope statement
        ]
    )


class HonestStateTests(unittest.TestCase):
    def test_zero_eligible_evidence_makes_no_model_call_and_says_so(self):
        sealed = sealed_ledger([("c", FRAGMENT, [S3]), ("d", STUDY, [S1])])
        client = OverviewClient(s={"overview": []})
        record, _ = build(sealed, client)
        self.assertEqual(record["state"], "no_eligible_evidence")
        self.assertEqual(client.calls, [])  # no call, no invented overview
        self.assertEqual((record["items"], record["displayed"], record["partial"]), ([], [], False))

    def test_one_eligible_passage_is_enough_for_a_narrow_overview(self):
        sealed = sealed_ledger([("c", GIVING, [S1]), ("d", GIVING, [S1])])
        record, _ = build(sealed, OverviewClient(s={"overview": [stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1])]}))
        self.assertEqual(record["state"], "ok")
        self.assertTrue(record["single_passage"])
        self.assertEqual(len(record["units"]), 1)  # two claims, one passage: repetition is not corroboration

    def test_mechanical_failures_are_no_answer_never_a_conclusion(self):
        sealed = ledger()
        for label, script, reason in (
            ("capped", None, "capped_at_allowance"),
            ("unparseable", "not json at all", "unparseable"),
            ("schema-invalid unit id", {"overview": [stmt(FAITHFUL_GIVING, ["U99"])]}, "schema_invalid"),
            ("wrong shape", {"nothing": []}, "schema_invalid"),
        ):
            with self.subTest(label):
                client = OverviewClient(s=script)
                record, _ = build(sealed, client)
                self.assertEqual((record["state"], record["reason_code"]), ("model_no_answer", reason))
                self.assertEqual(len(client.calls), 1)  # one call, no retry, no fallback
                self.assertEqual((record["items"], record["proposals"]), ([], []))

    def test_a_prompt_that_cannot_fit_is_refused_not_sent(self):
        client = OverviewClient(s={"overview": []})
        record, _ = build(ledger(), client, options={**topo.OVERVIEW_S_OPTIONS, "num_ctx": 2000})
        self.assertEqual((record["state"], record["reason_code"]), ("model_no_answer", "prompt_too_large"))
        self.assertEqual(client.calls, [])

    def test_a_valid_empty_answer_is_distinct_from_no_answer(self):
        record, _ = build(ledger(), OverviewClient(s={"overview": []}))
        self.assertEqual(record["state"], "model_returned_empty")

    def test_every_statement_withheld_is_its_own_state(self):
        record, _ = build(ledger(), OverviewClient(s={"overview": [stmt(FABRICATED, [uid(ledger(), PATTERN)])]}))
        self.assertEqual(record["state"], "no_grounded_sentences")
        self.assertEqual(record["displayed"], [])
        self.assertEqual(record["proposals"][0]["status"], "withheld")


class ScreeningTests(unittest.TestCase):
    def test_the_p4_structure_is_never_promoted_and_stays_inspectable(self):
        sealed = ledger()
        client = OverviewClient(
            s={
                "overview": [
                    stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1]),
                    stmt(FABRICATED, [uid(sealed, PATTERN)], [S1]),
                ]
            }
        )
        record, _ = build(sealed, client)
        self.assertEqual([p["status"] for p in record["proposals"]], ["grounded", "withheld"])
        self.assertIn("direction_word_not_in_passage:reduced", record["proposals"][1]["reasons"])
        self.assertEqual(record["displayed"], [0])
        self.assertTrue(record["partial"])  # a withheld proposal makes the overview visibly partial
        self.assertNotIn(FABRICATED, [item["text"] for item in record["items"]])
        # the fabricated claim's added term was shown to S as not in its passage
        self.assertIn("(not in passage: reduced)", client.calls[0]["prompt"])

    def test_one_model_call_and_one_batched_nli_call_in_positional_order(self):
        sealed = ledger()
        entail = Entail()
        client = OverviewClient(
            s={
                "overview": [
                    stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)]),
                    stmt(FAITHFUL_HEDGE, [uid(sealed, HEDGE)]),
                    stmt(FAITHFUL_NULL, [uid(sealed, NULL)]),
                ]
            }
        )
        record, _ = build(sealed, client, entail)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(len(entail.calls), 1)
        self.assertEqual(
            [premise for premise, _ in entail.calls[0]], [GIVING[3], HEDGE[3], NULL[3]]
        )  # passage first, in order
        self.assertEqual(record["state"], "ok")
        self.assertFalse(record["partial"])

    def test_nli_failure_or_fallback_withholds_and_never_approves(self):
        sealed = ledger()
        answer = {"overview": [stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)])]}
        for label, entail, code in (
            ("scorer raises", entail_raises, "nli_unavailable"),
            ("embedding fallback (no contradiction score)", Entail((0.95, None)), "nli_unavailable"),
            ("low support", Entail((0.2, 0.1)), "nli_low_support:0.20"),
            ("contradicted", Entail((0.1, 0.9)), "nli_contradicted:0.90"),
        ):
            with self.subTest(label):
                record, _ = build(sealed, OverviewClient(s=answer), entail)
                self.assertEqual(record["proposals"][0]["status"], "withheld")
                self.assertIn(code, record["proposals"][0]["reasons"])
                self.assertEqual(record["state"], "no_grounded_sentences")

    def test_a_scorer_returning_the_wrong_number_of_scores_approves_nothing(self):
        sealed = ledger()
        answer = {"overview": [stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)]), stmt(FAITHFUL_NULL, [uid(sealed, NULL)])]}
        record, _ = build(sealed, OverviewClient(s=answer), lambda pairs: [(0.9, 0.05)])
        self.assertEqual({p["status"] for p in record["proposals"]}, {"withheld"})

    def test_an_intervention_idea_never_becomes_an_effectiveness_claim(self):
        sealed = ledger()
        claim = "Perspective taking training is an effective intervention against avoidance."
        record, _ = build(sealed, OverviewClient(s={"overview": [stmt(claim, [uid(sealed, HEDGE)], [S2])]}))
        self.assertEqual(record["state"], "no_grounded_sentences")
        self.assertIn("hedge_dropped", record["proposals"][0]["reasons"])


class PromptTests(unittest.TestCase):
    def test_passages_are_paired_with_claims_and_only_eligible_passages_are_sent(self):
        sealed = ledger()
        client = OverviewClient(s={"overview": []})
        record, _ = build(sealed, client)
        prompt = client.calls[0]["prompt"]
        self.assertIn(GIVING[3], prompt)
        self.assertIn("Candidate claims:", prompt)
        for excluded in (FRAGMENT[3], STUDY[3], ABSENT[3]):
            self.assertNotIn(excluded, prompt)
        sent = {u["unit_id"] for u in record["units"] if u["sent_to_model"]}
        self.assertEqual(sent, {uid(sealed, p) for p in (GIVING, PATTERN, HEDGE, NULL)})
        reasons = {u["passage"]: u["not_sent_reason"] for u in record["units"] if not u["sent_to_model"]}
        self.assertEqual(set(reasons.values()), {"ineligible"})  # every exclusion is recorded, none is silent

    def test_which_request_part_a_passage_was_attached_to_is_never_shown_to_the_model(self):
        client = OverviewClient(s={"overview": []})
        build(ledger(), client)
        prompt = client.calls[0]["prompt"]
        _, _, after_parts = prompt.partition("Source passages.")
        self.assertNotIn("s1-o1", after_parts)  # part ids appear only in the tagging list, never beside a passage
        self.assertIn("- s1-o1:", prompt)

    def test_the_prompt_is_capped_and_overflow_is_recorded_not_silent(self):
        specs = [
            (
                f"claim {i}",
                (100 + i, 900 + i, "e1", f"Participant group {i} reported explicit dislike of scarred faces."),
                [S1],
            )
            for i in range(15)
        ]
        sealed = sealed_ledger(specs)
        client = OverviewClient(s={"overview": []})
        record, _ = build(sealed, client)
        self.assertLessEqual(len(client.calls[0]["prompt"]), ov.MAX_PROMPT_CHARS)
        sent = [u for u in record["units"] if u["sent_to_model"]]
        omitted = [u for u in record["units"] if u["not_sent_reason"] == "omitted_by_prompt_cap"]
        self.assertEqual((len(sent), len(omitted)), (oe.MAX_UNITS, 3))

    def test_thinking_is_on_and_the_explicit_options_reach_the_model(self):
        client = OverviewClient(s={"overview": []}, thinking="reasoning text")
        build(ledger(), client)
        call = client.calls[0]
        self.assertIs(call["think"], True)
        self.assertEqual(call["model"], "qwen3.5:9b")
        self.assertEqual(call["options"], topo.OVERVIEW_S_OPTIONS)  # nothing silently changed, no fallback


class RequestPartTests(unittest.TestCase):
    def test_a_passage_may_bear_on_a_part_it_was_not_attached_to(self):
        # GIVING was attached to s1 only. Attachment is topical, not a limit on use: the overview may tag s2 and s3 too.
        sealed = sealed_ledger([("c", GIVING, [S1])])
        record, _ = build(
            sealed, OverviewClient(s={"overview": [stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1, S3])]})
        )
        parts = {p["child_id"]: p for p in record["parts"]}
        self.assertEqual(parts[S3]["status"], "passage_stated")
        self.assertEqual(parts[S3]["attached_unit_ids"], [])  # not attached, still stated
        self.assertEqual(parts[S2]["status"], "no_responsive_evidence")

    def test_stated_hedged_topical_and_none_are_four_different_statuses(self):
        sealed = sealed_ledger([("c", GIVING, [S1]), ("d", HEDGE, [S2]), ("e", FRAGMENT, [S3])])
        answer = {
            "overview": [
                stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1]),
                stmt(FAITHFUL_HEDGE, [uid(sealed, HEDGE)], [S2]),
            ]
        }
        record, _ = build(sealed, OverviewClient(s=answer))
        status = {p["child_id"]: p["status"] for p in record["parts"]}
        self.assertEqual(status, {S1: "passage_stated", S2: "hedged_only", S3: "topical_only"})
        s3 = next(p for p in record["parts"] if p["child_id"] == S3)
        self.assertEqual(
            list(s3["attached_not_used"].values()), [["truncated_passage"]]
        )  # why its passage was not used
        none = build(sealed_ledger([("c", GIVING, [S1])]), OverviewClient(s={"overview": []}))[0]
        self.assertEqual({p["child_id"]: p["status"] for p in none["parts"]}[S3], "no_responsive_evidence")

    def test_a_withheld_statement_never_makes_a_part_stated(self):
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        record, _ = build(sealed, OverviewClient(s={"overview": [stmt(FABRICATED, [uid(sealed, PATTERN)], [S1])]}))
        self.assertEqual(next(p for p in record["parts"] if p["child_id"] == S1)["status"], "topical_only")

    def test_no_part_carries_a_completeness_verdict(self):
        record, _ = build(ledger(), OverviewClient(s={"overview": []}))
        for part in record["parts"]:
            self.assertIn(
                part["status"],
                {"passage_stated", "hedged_only", "topical_only", "no_responsive_evidence", "not_assessed"},
            )
        self.assertNotIn("complete", json.dumps(record["parts"]).lower().replace("completeness", ""))


class SeparateArtifactTests(unittest.TestCase):
    def test_the_sealed_ledger_is_untouched_and_referenced_by_hash(self):
        sealed = ledger()
        before = copy.deepcopy(sealed)
        record, _ = build(sealed, OverviewClient(s={"overview": [stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1])]}))
        self.assertEqual(sealed, before)
        self.assertNotIn("overview", sealed)  # model-written prose never enters the sealed evidence ledger
        self.assertEqual(record["sealed_ledger_hash"], "sealed-hash")

    def test_the_artifact_is_hashed_over_its_content(self):
        sealed = ledger()
        record, _ = build(sealed, OverviewClient(s={"overview": [stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1])]}))
        self.assertEqual(record["overview_hash"], ov.canonical_hash(record))
        json.dumps(record)  # serializable as written
        tampered = copy.deepcopy(record)
        tampered["items"][0]["text"] += " (edited)"
        self.assertNotEqual(ov.canonical_hash(tampered), record["overview_hash"])

    def test_items_resolve_to_units_and_ledger_claims(self):
        sealed = ledger()
        record, _ = build(sealed, OverviewClient(s={"overview": [stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1])]}))
        (item,) = record["items"]
        self.assertEqual((item["sentence_id"], item["unit_numbers"], item["proposition_ids"]), ("o1", [1], ["p1"]))

    def test_the_reasoning_text_is_returned_and_a_loop_is_measurable(self):
        loop = "the same eight words repeat again and again here " * 200
        honest = " ".join(f"distinct-reasoning-word-{i}" for i in range(400))
        record, reasoning = build(ledger(), OverviewClient(s={"overview": []}, thinking=loop))
        self.assertEqual(reasoning, loop)
        self.assertGreater(record["call"]["repetition_ratio"], 0.9)
        self.assertLess(ov.repetition_ratio(honest), 0.05)
        self.assertEqual(ov.repetition_ratio("too short"), 0.0)
        self.assertEqual(record["call"]["prompt_tokens"], 1500)
        self.assertEqual(record["call"]["thinking_chars"], len(loop))


PATTERN_FAITHFUL = "The authors described a behavioral pattern of avoidance linked to visible scarring."


class ScreenProposalsMarkerBoundaryTests(unittest.TestCase):
    """Direct tests of `overview.screen_proposals`'s citation-marker wiring (NLI_REPAIR_DESIGN.md Section 2/3),
    independent of the full `build_overview` prompt/model-call machinery. Every scorer here is the `Entail`
    fake -- no model/NLI/network call anywhere in this class."""

    def _units_and_ids(self, sealed):
        units, _ = oe.build_units(sealed)
        return {u["unit_id"]: u for u in units}

    def test_sends_the_stripped_hypothesis_to_entail_not_the_raw_text(self):
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        marked_text = PATTERN_FAITHFUL[:-1] + f" ({u1})."
        entail = Entail(score=(0.9, 0.05))
        records = ov.screen_proposals([stmt(marked_text, [u1], [S1])], by_id, {S1}, entail)
        self.assertEqual(len(entail.calls), 1)
        ((premise, hypothesis),) = entail.calls[0]
        self.assertEqual(hypothesis, PATTERN_FAITHFUL, "NLI must see the marker-stripped text, not the raw one")
        self.assertEqual(premise, PATTERN[3])
        self.assertEqual(records[0]["text"], marked_text, "the raw model text must be preserved, unmodified")

    def test_records_marker_audit_fields(self):
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        marked_text = PATTERN_FAITHFUL[:-1] + f" ({u1})."
        records = ov.screen_proposals([stmt(marked_text, [u1], [S1])], by_id, {S1}, Entail())
        record = records[0]
        self.assertEqual(record["nli_hypothesis_text"], PATTERN_FAITHFUL)
        self.assertEqual(record["marker_outcome"], "stripped_matches_unit_ids")
        self.assertEqual(record["stripped_marker"], f" ({u1})")

    def test_no_marker_present_behaves_exactly_as_before(self):
        """Backward compatibility: an ordinary unmarked proposal's NLI input is unchanged."""
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        entail = Entail(score=(0.9, 0.05))
        records = ov.screen_proposals([stmt(PATTERN_FAITHFUL, [u1], [S1])], by_id, {S1}, entail)
        ((premise, hypothesis),) = entail.calls[0]
        self.assertEqual(hypothesis, PATTERN_FAITHFUL)
        self.assertEqual(records[0]["marker_outcome"], "none")
        self.assertIsNone(records[0]["stripped_marker"])
        self.assertEqual(records[0]["status"], "grounded")

    def test_a_conflicting_marker_withholds_even_with_a_high_nli_score(self):
        """Negative control: a genuinely high NLI score must NOT rescue a proposal whose citation marker
        disagrees with its own structured unit_ids -- an attribution mismatch stays ineligible regardless."""
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        conflicting_text = PATTERN_FAITHFUL[:-1] + " (U99)."  # a unit id that isn't even u1
        entail = Entail(score=(0.99, 0.0))  # a deliberately high stub score
        records = ov.screen_proposals([stmt(conflicting_text, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertEqual(record["status"], "withheld")
        self.assertTrue(any(r.startswith("unit_marker_conflicts_with_unit_ids") for r in record["reasons"]))
        self.assertEqual(record["text"], conflicting_text, "raw text is still preserved even when withheld")

    def test_removing_a_marker_does_not_rescue_a_genuinely_unsupported_candidate(self):
        """Negative control: stripping the marker only changes what NLI sees, never the score itself -- a
        candidate that would fail on its stripped text fails exactly the same as it would have on the raw
        text (this fake scorer ignores content, but the point is the STATUS logic doesn't special-case a
        stripped proposal into passing)."""
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        marked_text = PATTERN_FAITHFUL[:-1] + f" ({u1})."
        entail = Entail(score=(0.1, 0.05))  # below threshold regardless of stripping
        records = ov.screen_proposals([stmt(marked_text, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertEqual(record["status"], "withheld")
        self.assertIn("nli_low_support:0.10", record["reasons"])
        self.assertEqual(record["marker_outcome"], "stripped_matches_unit_ids", "stripping still happened")

    # ---- end-to-end final-disposition coverage (2026-09-28 audit) -----------------------------------------
    # The tests above check either the text transformation alone, or a single (foreign-id) mismatch shape's
    # disposition. These four close the gap the audit named: every recognizable mismatch shape -- and the
    # legitimate positive case -- checked all the way through screen_proposals's FINAL status under a
    # deliberately generous stub NLI score, not inferred from a string-transformation test alone.

    # A digit ("1") legitimately present in the passage itself, distinct from PATTERN_FAITHFUL/GIVING/NULL
    # (none of which contain any digit). At the time this test was written, this fixture was a deliberate
    # WORKAROUND for a real, separate bug this same audit found (screen()'s number check reading the bare
    # digit inside "(U1)" itself as an invented number) -- named then, not fixed, per that pass's explicit
    # scope boundary. That bug is now FIXED (2026-09-28, see test_a_legitimate_marker_does_not_spuriously_
    # trigger_number_not_in_passage below, which reproduces it directly on a digit-free passage); this
    # fixture is kept as-is since it remains a valid, harmless positive control either way.
    _DIGIT_PASSAGE = (
        11,
        999,
        "e1",
        "The authors described 1 behavioral pattern of avoidance linked to visible scarring.",
    )

    def test_positive_control_a_legitimate_exact_marker_still_grounds_under_a_high_score(self):
        sealed = sealed_ledger([("c", self._DIGIT_PASSAGE, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        text = self._DIGIT_PASSAGE[3][:-1] + f" ({u1})."
        entail = Entail(score=(0.99, 0.0))
        records = ov.screen_proposals([stmt(text, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertEqual(record["status"], "grounded")
        self.assertEqual(record["marker_outcome"], "stripped_matches_unit_ids")
        self.assertEqual(record["reasons"], [])

    def test_negative_control_a_duplicated_marker_cannot_ground_under_a_high_score(self):
        """The exact case this audit was asked to check: `(U1, U1)` against `unit_ids=["U1"]` with a
        deliberately generous stub score. Confirmed already correct before this test existed -- added to close
        the coverage gap, not because a production change was needed."""
        sealed = sealed_ledger([("c", self._DIGIT_PASSAGE, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        text = self._DIGIT_PASSAGE[3][:-1] + f" ({u1}, {u1})."
        entail = Entail(score=(0.99, 0.0))
        records = ov.screen_proposals([stmt(text, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertNotEqual(record["status"], "grounded")
        self.assertEqual(record["status"], "withheld")
        self.assertTrue(any(r.startswith("unit_marker_conflicts_with_unit_ids") for r in record["reasons"]))
        self.assertEqual(record["marker_outcome"], "conflicts_with_unit_ids")

    def test_negative_control_a_subset_marker_cannot_ground_under_a_high_score(self):
        """unit_ids cites two units; the marker names only one -- a missing-id mismatch, not previously
        checked at the final-disposition level (only the foreign-id shape was)."""
        sealed = sealed_ledger([("a", self._DIGIT_PASSAGE, [S1]), ("b", GIVING, [S1])])
        by_id = self._units_and_ids(sealed)
        u1, u2 = sorted(by_id)
        text = self._DIGIT_PASSAGE[3][:-1] + f" ({u1})."  # cites only u1; unit_ids below cites both
        entail = Entail(score=(0.99, 0.0))
        records = ov.screen_proposals([stmt(text, [u1, u2], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertNotEqual(record["status"], "grounded")
        self.assertTrue(any(r.startswith("unit_marker_conflicts_with_unit_ids") for r in record["reasons"]))
        self.assertEqual(record["marker_outcome"], "conflicts_with_unit_ids")

    def test_negative_control_a_superset_marker_cannot_ground_under_a_high_score(self):
        """unit_ids cites one unit; the marker names two -- an added-id mismatch, not previously checked at
        the final-disposition level."""
        sealed = sealed_ledger([("a", self._DIGIT_PASSAGE, [S1]), ("b", GIVING, [S1])])
        by_id = self._units_and_ids(sealed)
        u1, u2 = sorted(by_id)
        text = self._DIGIT_PASSAGE[3][:-1] + f" ({u1}, {u2})."  # cites both; unit_ids below cites only u1
        entail = Entail(score=(0.99, 0.0))
        records = ov.screen_proposals([stmt(text, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertNotEqual(record["status"], "grounded")
        self.assertTrue(any(r.startswith("unit_marker_conflicts_with_unit_ids") for r in record["reasons"]))
        self.assertEqual(record["marker_outcome"], "conflicts_with_unit_ids")

    # ---- 2026-09-28: a legitimate marker's OWN digit must never register as an invented number -------------
    # PATTERN (digit-free) reproduces the bug directly, without the _DIGIT_PASSAGE workaround above.

    def test_a_legitimate_marker_does_not_spuriously_trigger_number_not_in_passage(self):
        """Reproduction: before the fix, a scientifically faithful candidate ending in a VALID `(U1)` marker
        (unit_ids=["U1"], digit-free passage) was incorrectly withheld -- screen()'s number check read the
        bare "1" inside "(U1)" as an invented number, even though the citation boundary had already correctly
        identified this exact marker as redundant, structurally-validated metadata, not claim content."""
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        text = PATTERN_FAITHFUL[:-1] + f" ({u1})."
        entail = Entail(score=(0.99, 0.0))
        records = ov.screen_proposals([stmt(text, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertFalse(
            any(r.startswith("number_not_in_passage") for r in record["reasons"]),
            f"the marker's own digit must never be read as an invented number: {record['reasons']}",
        )
        self.assertEqual(record["status"], "grounded")
        self.assertEqual(record["marker_outcome"], "stripped_matches_unit_ids")
        self.assertEqual(record["text"], text, "raw text preserved byte-for-byte")
        self.assertEqual(record["nli_hypothesis_text"], PATTERN_FAITHFUL)

    def test_a_genuinely_invented_number_is_still_caught_alongside_a_valid_marker(self):
        """Negative control: the fix must not create a loophole -- a real invented number in the SCIENTIFIC
        CLAIM (not the marker) stays caught, even though a valid, correctly-stripped marker is also present."""
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        invented = PATTERN_FAITHFUL[:-1] + f" among 50 participants ({u1})."  # "50" is nowhere in PATTERN
        entail = Entail(score=(0.99, 0.0))
        records = ov.screen_proposals([stmt(invented, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertIn("number_not_in_passage:50", record["reasons"])
        self.assertNotEqual(record["status"], "grounded")
        self.assertEqual(
            record["marker_outcome"], "stripped_matches_unit_ids", "the marker itself still strips cleanly"
        )

    def test_duplicate_marker_still_withheld_for_conflict_after_the_numeric_fix(self):
        """The numeric-guard fix must not weaken the independent marker-conflict guard: (U1, U1) stays withheld
        for its conflict, under a high stub score, exactly as commit aa818feb already proved."""
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        text = PATTERN_FAITHFUL[:-1] + f" ({u1}, {u1})."
        entail = Entail(score=(0.99, 0.0))
        records = ov.screen_proposals([stmt(text, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertNotEqual(record["status"], "grounded")
        self.assertTrue(any(r.startswith("unit_marker_conflicts_with_unit_ids") for r in record["reasons"]))

    def test_a_meaningful_scientific_parenthetical_with_an_invented_number_is_still_validated(self):
        """A parenthetical that does NOT purport to be a unit citation (fails the strict marker shape) must
        remain fully subject to ordinary numerical validation -- the fix narrows scope to structurally
        validated marker text only, never to parentheticals in general."""
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        by_id = self._units_and_ids(sealed)
        u1 = next(iter(by_id))
        text = PATTERN_FAITHFUL[:-1] + " (n = 50)."  # an ordinary parenthetical, not a unit-citation marker
        entail = Entail(score=(0.99, 0.0))
        records = ov.screen_proposals([stmt(text, [u1], [S1])], by_id, {S1}, entail)
        record = records[0]
        self.assertIn("number_not_in_passage:50", record["reasons"])
        self.assertEqual(record["marker_outcome"], "none")


if __name__ == "__main__":
    unittest.main()
