"""Researcher-facing answer, detailed inspection, and the final audit that re-derives everything from the sealed ledger."""

import copy
import re
import unittest

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised import overview_audit as audit
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import overview_render as rnd
from experiments.ask_cli_revised.ledger_renderer import _literal, render_answer
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
    make_supervisor,
    sealed_ledger,
    stmt,
    uid,
)
from experiments.ask_cli_revised.supervisor_eval.scoring import corpus_absence_hits

FAITHFUL_GIVING = "In one study the insular response to pictured scarring correlated with lower generosity toward the people pictured."
FAITHFUL_HEDGE = (
    "One paper suggests that training in perspective taking might reduce avoidance of people with visible scarring."
)
FABRICATED = "Avoidance is reduced in people with visible scarring."

SPECS = [
    ("Generosity was lower toward the people pictured.", GIVING, [S1]),
    ("Avoidance is reduced in people with visible scarring.", PATTERN, [S1]),
    ("Avoidance is linked to visible scarring.", PATTERN, [S1]),
    ("Training might reduce avoidance.", HEDGE, [S2]),
    ("Explicit dislike was reported; implicit dislike was small.", NULL, [S1]),
    ("The aversion is culturally shared.", FRAGMENT, [S3]),
    ("The study examined dislike and gaze.", STUDY, [S1]),
    ("Earlier studies did not examine cultures.", ABSENT, []),
]


def make(specs=SPECS, statements=None, entail=None, client=None):
    sealed = sealed_ledger(specs)
    if statements is None:
        statements = [
            stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1]),
            stmt(FAITHFUL_HEDGE, [uid(sealed, HEDGE)], [S2]),
            stmt(FABRICATED, [uid(sealed, PATTERN)], [S1]),  # withheld: makes the overview partial
        ]
    client = client or OverviewClient(s={"overview": statements})
    record, _ = ov.build_overview(
        sealed, audit.sealed_hash_of(sealed), supervisor=make_supervisor(client), entail=entail or Entail()
    )
    answer, manifest = rnd.researcher_answer(sealed, record)
    return sealed, record, answer, manifest


class ResearcherAnswerTests(unittest.TestCase):
    def setUp(self):
        self.sealed, self.record, self.answer, self.manifest = make()

    def test_it_opens_with_the_overview_then_findings_then_unresolved_parts(self):
        self.assertTrue(self.answer.startswith("# Overview of the retrieved evidence"))
        order = [self.answer.index(h) for h in ("\n## Overview", "\n## Supporting findings", "\n## Unresolved parts")]
        self.assertEqual(order, sorted(order))
        self.assertIn("1. " + _literal(FAITHFUL_GIVING), self.answer)

    def test_every_statement_cites_a_passage_shown_exactly_beneath_it(self):
        for n in (1, 2):
            self.assertIn(f"**[{n}]** Paper", self.answer)
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", self.answer.split("## Supporting findings")[0])}
        shown = {int(n) for n in re.findall(r"\*\*\[(\d+)\]\*\*", self.answer)}
        self.assertEqual(cited, shown)
        self.assertIn("> " + _literal(GIVING[3]), self.answer)  # the exact passage, escaped only for markdown
        self.assertIn("Paper 11, chunk 101, e1, page 3", self.answer)

    def test_citation_numbers_are_contiguous_even_when_a_withheld_statement_owned_a_passage(self):
        # internally the withheld statement's passage is U2 and the hedged one is U3; the reader must see [1] and [2]
        self.assertEqual([i["unit_ids"] for i in self.record["items"]], [["U1"], ["U3"]])
        self.assertIn(_literal(FAITHFUL_HEDGE) + " [2]", self.answer)
        self.assertNotIn("[3]", self.answer)
        self.assertEqual(self.manifest["statements"][1]["citation_numbers"], [2])
        self.assertEqual(self.manifest["statements"][1]["unit_ids"], ["U3"])  # the stable id is kept in the manifest
        self.assertIn("U3 (cited as [2])", rnd.detailed_inspection(self.sealed, self.record))

    def test_supporting_findings_are_deduplicated_and_concise(self):
        self.assertEqual(len(self.record["claims"]), 8)
        blocks = re.findall(r"\*\*\[\d+\]\*\* Paper", self.answer)
        self.assertEqual(len(blocks), 2)  # 8 claims, 2 cited passages
        self.assertIn("Not used in the overview:", self.answer)
        for detail_only in ("Parent reconciliation", "Overview construction record", "Contract for this item"):
            self.assertNotIn(detail_only, self.answer)
        for paraphrase in ("Avoidance is linked to visible scarring.", "Training might reduce avoidance."):
            self.assertNotIn(paraphrase, self.answer)  # ledger claim paraphrases live in the inspection, not the answer

    def test_repeated_restatement_is_labelled_as_not_corroboration_once_not_per_passage(self):
        self.assertEqual(self.answer.count("are not independent support"), 1)
        self.assertIn(
            "Restated by ledger claim(s) p1.", self.answer
        )  # which ledger claims, without repeating the caveat each time

    def test_citation_numbers_follow_the_order_the_reader_meets_them(self):
        sealed = sealed_ledger([("a", GIVING, [S1]), ("b", HEDGE, [S2]), ("c", NULL, [S1])])
        # the model cites the LAST passage first: readers must still meet [1], [2], [3] in order
        statements = [
            stmt(FAITHFUL_HEDGE, [uid(sealed, HEDGE)], [S2]),
            stmt(FAITHFUL_GIVING, [uid(sealed, GIVING)], [S1]),
            stmt(
                "Participants reported explicit dislike of people with scarring, but implicit dislike was small and not significant.",
                [uid(sealed, NULL)],
                [S1],
            ),
        ]
        _, record, answer, manifest = make(
            specs=[("a", GIVING, [S1]), ("b", HEDGE, [S2]), ("c", NULL, [S1])], statements=statements
        )
        self.assertEqual([i["unit_ids"] for i in record["items"]], [["U2"], ["U1"], ["U3"]])
        cites = re.findall(r"\. \[(\d+)\]\n", answer.split("## Supporting findings")[0].replace("\\.", "."))
        self.assertEqual(cites, ["1", "2", "3"])
        self.assertEqual(
            [m for m in re.findall(r"\*\*\[(\d+)\]\*\*", answer)], ["1", "2", "3"]
        )  # findings listed in the same order
        self.assertEqual(manifest["statements"][0]["unit_ids"], ["U2"])  # the stable internal id is kept

    def test_a_withheld_statement_makes_the_overview_visibly_partial_and_never_appears(self):
        self.assertTrue(self.record["partial"])
        self.assertIn("**Partial overview.** 1 proposed statement(s) were withheld", self.answer)
        self.assertNotIn(_literal(FABRICATED), self.answer)

    def test_a_single_passage_overview_says_so(self):
        _, record, answer, _ = make([("c", GIVING, [S1])], [stmt(FAITHFUL_GIVING, ["U1"], [S1])])
        self.assertTrue(record["single_passage"])
        self.assertIn("rests on one retrieved passage", answer)
        self.assertNotIn("Partial overview", answer)

    def test_qualifications_are_stated_beside_the_passage(self):
        self.assertIn("Qualifications: hedged wording", self.answer)
        self.assertIn("Qualifications: reports an association", self.answer)

    def test_scope_statement_and_no_corpus_absence_phrasing(self):
        self.assertIn("makes no statement about what the library or the literature holds", self.answer)
        self.assertEqual(corpus_absence_hits(self.answer), [])
        self.assertEqual(self.manifest["mode"], "researcher-answer-v1")

    def test_it_points_to_the_inspection_artifacts(self):
        self.assertIn(rnd.DETAIL_FILE, self.answer)
        self.assertIn(rnd.RECORD_FILE, self.answer)


class UnresolvedPartsTests(unittest.TestCase):
    def setUp(self):
        _, self.record, self.answer, _ = make()
        self.section = self.answer.split("## Unresolved parts")[1]

    def test_parts_are_grouped_by_what_was_actually_established(self):
        self.assertIn("**Judged topically responsive only; no overview statement bears on these parts**", self.section)
        self.assertIn("(attached passage(s) were not used: truncated_passage)", self.section)  # the culture part
        self.assertIn("**Only hedged statements bear on these parts**", self.section)
        self.assertIn(
            "**Statements the overview makes bear on these parts (whole-part answers were not assessed)**", self.section
        )

    def test_no_completeness_verdict_only_an_explicit_not_assessed_and_an_unresolved_line(self):
        self.assertIn("did not assess whether any part is fully", self.section)
        self.assertIn("Completeness remains unresolved", self.section)
        self.assertIn("topical judgment. It does not establish that the passage answers the part", self.section)

    def test_a_part_with_nothing_is_stated_plainly_without_claiming_the_literature_lacks_it(self):
        _, _, answer, _ = make([("c", GIVING, [S1])], [stmt(FAITHFUL_GIVING, ["U1"], [S1])])
        self.assertIn("**No responsive evidence was found for these parts in this run**", answer)
        self.assertEqual(corpus_absence_hits(answer), [])


class NoOverviewStateTests(unittest.TestCase):
    def messages(self):
        out = {}
        out["no_eligible"] = make([("c", FRAGMENT, [S3])], [])[2]
        out["no_answer"] = make(client=OverviewClient(s=None))[2]
        out["empty"] = make(statements=[])[2]
        out["all_withheld"] = make(statements=[stmt(FABRICATED, ["U2"], [S1])])[2]
        return out

    def test_each_state_has_fixed_honest_text(self):
        m = self.messages()
        self.assertIn(
            "no retrieved passage was eligible for synthesis in this run (1 truncated_passage)", m["no_eligible"]
        )
        self.assertIn("(mechanical: capped_at_allowance). This is not a scientific result.", m["no_answer"])
        self.assertIn("returned no statements from the eligible passages", m["empty"])
        self.assertIn(
            "No overview statement passed screening (1 proposed statement(s) were withheld", m["all_withheld"]
        )

    def test_no_state_invents_an_overview_and_none_claims_the_literature_lacks_evidence(self):
        for name, answer in self.messages().items():
            with self.subTest(name):
                self.assertNotIn("\n1. ", answer)
                self.assertEqual(corpus_absence_hits(answer), [])
                self.assertIn("## Supporting findings", answer)  # the source-verified passages are still shown

    def test_when_there_is_no_overview_the_passages_are_still_listed_with_why_they_were_not_used(self):
        answer = self.messages()["no_eligible"]
        self.assertIn("Not used in the overview: truncated_passage.", answer)


class DetailedInspectionTests(unittest.TestCase):
    def setUp(self):
        self.sealed, self.record, _, _ = make()
        self.detail = rnd.detailed_inspection(self.sealed, self.record)

    def test_it_is_the_unchanged_ledger_rendering_followed_by_the_construction_record(self):
        base, _ = render_answer(self.sealed)
        self.assertTrue(self.detail.startswith(base.rstrip("\n") + "\n\n## Overview construction record"))

    def test_nothing_is_dropped_claims_novel_terms_exclusions_withheld_statements_and_receipts(self):
        for needle in (
            "terms the claim adds beyond its passage",
            "reduced",  # the fabricated claim's added term
            "passage_not_used:truncated_passage",
            "**WITHHELD**",
            "direction_word_not_in_passage:reduced",
            "passage_restated_in_overview",
            "Sealed evidence ledger hash (referenced, not modified)",
            "qwen3.5:9b",
            "presence_penalty",
            "Screening (lexical rules plus a local NLI model) can withhold a statement but cannot prove one correct.",
        ):
            self.assertIn(needle, self.detail)

    def test_a_claim_whose_added_terms_were_not_carried_is_labelled_so_not_as_restated(self):
        sealed = sealed_ledger(SPECS)
        good = stmt(
            "The authors described a behavioral pattern of avoidance linked to visible scarring.",
            [uid(sealed, PATTERN)],
            [S1],
        )
        _, record, _, _ = make(statements=[good])
        rows = {r["proposition_id"]: r["disposition"] for r in rnd.claim_dispositions(record)}
        self.assertEqual(rows["p2"], "passage_used_claim_wording_not_used")  # the claim that invented "reduced"
        self.assertEqual(rows["p3"], "passage_restated_in_overview")  # a claim that added nothing
        detail = rnd.detailed_inspection(sealed, record)
        self.assertIn("does not carry the terms the claim adds beyond it", detail)

    def test_statement_numbers_match_between_the_answer_the_proposals_and_the_parts_table(self):
        self.assertEqual(self.record["displayed"], [0, 1])  # proposal 2 (index 2) was withheld
        self.assertIn("**GROUNDED** (statement 1;", self.detail)
        self.assertIn("**GROUNDED** (statement 2;", self.detail)
        self.assertIn("**WITHHELD** (not shown;", self.detail)
        parts = {
            line.split("|")[1].split()[0]: line.split("|")[4].strip()
            for line in self.detail.splitlines()
            if line.startswith("| s")
        }
        self.assertEqual(
            (parts["s1-o1"], parts["s2-o1"], parts["s3-o1"]), ("1", "2", "-")
        )  # not the raw 0-based indices

    def test_the_withheld_statement_is_kept_here_and_only_here(self):
        _, _, answer, _ = make()
        self.assertIn(_literal(FABRICATED), self.detail)
        self.assertNotIn(_literal(FABRICATED), answer)


class MarkupSafetyTests(unittest.TestCase):
    """Passages are untrusted PDF text and statements are model text: neither may inject markup into the answer."""

    def test_model_text_cannot_inject_links_html_or_headings(self):
        sealed, record, _, _ = make()
        record = copy.deepcopy(record)
        record["items"][0]["text"] = "Click [here](http://evil.example) <script>x</script>\n# Injected heading"
        answer, _ = rnd.researcher_answer(sealed, record)
        self.assertNotIn("](http", answer)
        self.assertNotIn("<script>", answer)
        self.assertNotRegex(answer, r"(?m)^# Injected heading")

    def test_a_passage_cannot_inject_markup_into_the_supporting_findings(self):
        hostile = (11, 950, "e1", "Avoidance was linked to scarring. [x](http://evil.example) <img src=x>.")
        sealed, record, answer, _ = make(
            [("c", hostile, [S1])], [stmt("Avoidance was linked to scarring.", ["U1"], [S1])]
        )
        self.assertEqual(record["state"], "ok")  # the passage really is cited and rendered
        backslash = chr(92)
        self.assertIn(backslash + "<img src=x" + backslash + ">", answer)  # shown, but escaped
        self.assertNotRegex(answer, r"(?<![\\])<img")  # no unescaped tag
        self.assertNotRegex(answer, r"(?<![\\])\]\(http")  # no live link
        result = audit.audit_overview(
            sealed, audit.sealed_hash_of(sealed), record, answer, rnd.detailed_inspection(sealed, record)
        )
        self.assertTrue(result["ok"])


def rehash(record):
    record["overview_hash"] = ov.canonical_hash(record)
    return record


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.sealed, self.record, self.answer, _ = make()
        self.detail = rnd.detailed_inspection(self.sealed, self.record)
        self.h = audit.sealed_hash_of(self.sealed)

    def run_audit(self, record=None, answer=None, detail=None, sealed_hash=None):
        return audit.audit_overview(
            self.sealed, sealed_hash or self.h, record or self.record, answer or self.answer, detail or self.detail
        )

    def failed(self, result):
        return {name for name, ok in result["checks"].items() if not ok}

    def test_a_genuine_artifact_passes_and_says_it_is_screening_not_proof(self):
        result = self.run_audit()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["screening_not_proof"])
        self.assertIn("cannot prove one correct", result["note"])

    def test_editing_the_artifact_without_rehashing_is_caught(self):
        record = copy.deepcopy(self.record)
        record["items"][0]["text"] += " (edited)"
        self.assertIn("overview_hash_matches_content", self.failed(self.run_audit(record)))

    def test_replacing_a_grounded_statement_with_a_fabricated_one_and_rehashing_is_caught(self):
        record = copy.deepcopy(self.record)
        record["proposals"][0]["text"] = FABRICATED
        record["items"][0]["text"] = FABRICATED
        failed = self.failed(self.run_audit(rehash(record)))
        self.assertIn("every_proposal_rescreens_to_its_stored_status", failed)

    def test_forging_a_passage_eligibility_flag_is_caught(self):
        record = copy.deepcopy(self.record)
        next(u for u in record["units"] if "truncated_passage" in u["eligibility"]["reasons"])["eligibility"] = {
            "eligible": True,
            "reasons": [],
        }
        self.assertIn("passages_and_claims_match_the_ledger", self.failed(self.run_audit(rehash(record))))

    def test_forging_an_nli_score_to_approve_a_withheld_statement_is_caught(self):
        record = copy.deepcopy(self.record)
        withheld = record["proposals"][2]
        withheld.update(
            {"nli": {"support": 0.99, "contradiction": 0.0}, "nli_reasons": [], "reasons": [], "status": "grounded"}
        )
        self.assertIn("every_proposal_rescreens_to_its_stored_status", self.failed(self.run_audit(rehash(record))))

    def test_a_withheld_statement_smuggled_into_the_answer_is_caught(self):
        answer = self.answer + "\n" + _literal(FABRICATED) + "\n"
        failed = self.failed(self.run_audit(answer=answer))
        self.assertIn("no_withheld_statement_in_the_answer", failed)
        self.assertIn("researcher_answer_matches_render", failed)

    def test_an_edited_answer_or_inspection_is_caught(self):
        self.assertIn(
            "researcher_answer_matches_render",
            self.failed(self.run_audit(answer=self.answer.replace("Overview", "Summary"))),
        )
        self.assertIn("detailed_inspection_matches_render", self.failed(self.run_audit(detail=self.detail + "extra")))

    def test_referencing_a_different_ledger_is_caught(self):
        self.assertIn("references_the_sealed_ledger", self.failed(self.run_audit(sealed_hash="0" * 64)))

    def test_inconsistent_derived_fields_are_caught(self):
        record = copy.deepcopy(self.record)
        self.assertEqual(record["displayed"], [0, 1])  # the two grounded statements; index 2 was withheld
        record["displayed"] = [0, 2]  # would display the withheld one
        self.assertIn("derived_fields_consistent", self.failed(self.run_audit(rehash(record))))


class CoverageConstraintsTests(unittest.TestCase):
    """`coverage_constraints` is optional and additive (2026-09-27, Gate 2 diagnostic): every existing caller that
    omits it must see today's exact prompt and behavior, unchanged."""

    QUESTION, STATES, BLOCKS = "the request", [{"field_id": "c1", "note": "part one"}], ["[U1] paper 1\nPassage: x"]

    def test_no_constraints_reproduces_todays_exact_prompt(self):
        default = ov.render_prompt(self.QUESTION, self.STATES, self.BLOCKS)
        explicit_empty = ov.render_prompt(self.QUESTION, self.STATES, self.BLOCKS, coverage_constraints=())
        original = ov.PROMPT_TEMPLATE.format(
            question=self.QUESTION, parts=ov.render_part_lines(self.STATES), units="\n\n".join(self.BLOCKS)
        )
        self.assertEqual(default, original)
        self.assertEqual(explicit_empty, original)

    def test_a_constraint_inserts_one_clearly_labeled_section_before_the_closing_instructions(self):
        prompt = ov.render_prompt(
            self.QUESTION,
            self.STATES,
            self.BLOCKS,
            coverage_constraints=("The passages above do not establish the requested link.",),
        )
        self.assertIn(ov.COVERAGE_CONSTRAINTS_HEADER, prompt)
        self.assertIn("- The passages above do not establish the requested link.", prompt)
        # comes after the source passages, before the model is told to write
        self.assertLess(prompt.index("[U1] paper 1"), prompt.index(ov.COVERAGE_CONSTRAINTS_HEADER))
        self.assertLess(prompt.index(ov.COVERAGE_CONSTRAINTS_HEADER), prompt.index("Write a short overview"))

    def test_prompt_template_itself_is_never_touched(self):
        before = ov.PROMPT_TEMPLATE
        ov.render_prompt(self.QUESTION, self.STATES, self.BLOCKS, coverage_constraints=("anything",))
        self.assertEqual(ov.PROMPT_TEMPLATE, before)

    def test_select_for_prompt_with_no_constraints_matches_todays_behavior_exactly(self):
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        units, claims = oe.build_units(sealed)
        states = sealed["obligation_states"]
        sent_a, prompt_a = ov.select_for_prompt(units, claims, sealed["request_contract"]["original_question"], states)
        sent_b, prompt_b = ov.select_for_prompt(
            units, claims, sealed["request_contract"]["original_question"], states, coverage_constraints=()
        )
        self.assertEqual((sent_a, prompt_a), (sent_b, prompt_b))

    def test_a_constraint_is_never_added_as_a_citable_unit(self):
        """The constraint text must be structurally impossible to cite: it never becomes a `unit`, so it can never
        appear in the schema's closed `unit_ids` enum built from real, sent units."""
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(s={"overview": []})
        record, _ = ov.build_overview(
            sealed,
            "hash",
            supervisor=make_supervisor(client),
            entail=Entail(),
            coverage_constraints=("The passages above do not establish the requested link.",),
        )
        unit_texts = {u["passage"] for u in record["units"]}
        self.assertNotIn("The passages above do not establish the requested link.", unit_texts)
        schema = ov.schema_overview([u["unit_id"] for u in record["units"] if u["sent_to_model"]], ["c1"])
        allowed_ids = schema["properties"]["overview"]["items"]["properties"]["unit_ids"]["items"]["enum"]
        self.assertNotIn("constraint", [i.lower() for i in allowed_ids])  # only real Un ids are ever enumerable

    def test_build_overview_records_the_supplied_constraints_in_its_receipt(self):
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(s={"overview": []})
        default_record, _ = ov.build_overview(sealed, "hash", supervisor=make_supervisor(client), entail=Entail())
        self.assertEqual(default_record["coverage_constraints"], [])
        with_record, _ = ov.build_overview(
            sealed,
            "hash",
            supervisor=make_supervisor(client),
            entail=Entail(),
            coverage_constraints=("a limit of the admitted evidence",),
        )
        self.assertEqual(with_record["coverage_constraints"], ["a limit of the admitted evidence"])

    def test_the_prompt_cap_check_accounts_for_the_constraint_section_length(self):
        """A long constraint section must be counted toward MAX_PROMPT_CHARS during packing, not added after the
        cap check -- otherwise a packed prompt could silently exceed the cap once the section is inserted."""
        long_constraint = "x" * (ov.MAX_PROMPT_CHARS)  # alone, larger than the whole cap
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        units, claims = oe.build_units(sealed)
        states = sealed["obligation_states"]
        sent, prompt = ov.select_for_prompt(
            units,
            claims,
            sealed["request_contract"]["original_question"],
            states,
            coverage_constraints=(long_constraint,),
        )
        self.assertEqual(sent, [])  # every unit omitted; the constraint section alone already exceeds the cap
        for u in units:
            self.assertEqual(u["not_sent_reason"], "omitted_by_prompt_cap")


class CrashRecoveryHooksTests(unittest.TestCase):
    """`on_prompt_ready`/`on_raw_response` (2026-09-27, the Gate 2 incident fix): optional, additive hooks at the
    two boundaries a caller needs to persist data before any downstream failure can lose it. Omitting either
    must reproduce today's exact behavior."""

    def test_omitting_both_hooks_reproduces_todays_exact_record(self):
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(s={"overview": []})
        without_hooks, _ = ov.build_overview(sealed, "hash", supervisor=make_supervisor(client), entail=Entail())
        with_none, _ = ov.build_overview(
            sealed,
            "hash",
            supervisor=make_supervisor(client),
            entail=Entail(),
            on_prompt_ready=None,
            on_raw_response=None,
        )
        self.assertEqual(without_hooks, with_none)

    def test_on_prompt_ready_fires_before_any_call_with_the_prompt_and_a_manifest(self):
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(s={"overview": []})
        seen = []
        ov.build_overview(
            sealed,
            "hash",
            supervisor=make_supervisor(client),
            entail=Entail(),
            on_prompt_ready=lambda prompt, manifest: seen.append((prompt, manifest)),
        )
        self.assertEqual(len(seen), 1)
        prompt, manifest = seen[0]
        self.assertIn("Original request", prompt)
        self.assertEqual(manifest["sealed_ledger_hash"], "hash")
        self.assertIn(uid(sealed, GIVING), manifest["sent_unit_ids"])

    def test_on_prompt_ready_fires_even_when_nothing_is_eligible_to_send(self):
        """ "Before inference" must mean before inference is attempted at all, including when no call happens."""
        sealed = sealed_ledger([])  # no propositions at all -> no units -> nothing sent
        client = OverviewClient(s={"overview": []})
        seen = []
        record, _ = ov.build_overview(
            sealed,
            "hash",
            supervisor=make_supervisor(client),
            entail=Entail(),
            on_prompt_ready=lambda prompt, manifest: seen.append(manifest),
        )
        self.assertEqual(record["call"], None)  # no call was made
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["sent_unit_ids"], [])

    def test_on_raw_response_fires_exactly_once_with_the_real_stage_result(self):
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(s={"overview": []})
        seen = []
        ov.build_overview(
            sealed,
            "hash",
            supervisor=make_supervisor(client),
            entail=Entail(),
            on_raw_response=lambda result: seen.append(result),
        )
        self.assertEqual(len(seen), 1)
        result = seen[0]
        self.assertTrue(hasattr(result, "answer"))
        self.assertTrue(hasattr(result, "raw_text"))
        self.assertTrue(hasattr(result, "record"))

    def test_on_raw_response_fires_before_any_screening_or_parts_status(self):
        """Proves the ordering, not just that the hook is called: if the hook itself raises, NOTHING downstream
        of the model call (screening, parts_status) may have already run -- the exception must reach the caller
        unweakened, with `entail` never invoked."""
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(
            s={"overview": [{"text": "a grounded statement here", "unit_ids": [uid(sealed, GIVING)], "bears_on": []}]}
        )
        entail = Entail()

        def boom(result):
            raise RuntimeError("simulated crash exactly at the raw-response boundary")

        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            ov.build_overview(sealed, "hash", supervisor=make_supervisor(client), entail=entail, on_raw_response=boom)
        self.assertEqual(entail.calls, [])  # screening (and therefore its NLI call) never ran

    def test_on_raw_response_receives_the_answer_even_when_it_is_none(self):
        """A mechanical NO ANSWER is still real data worth capturing at this boundary -- not just a successful
        parse."""
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(s=None)  # every call caps -> result.answer is None
        seen = []
        record, _ = ov.build_overview(
            sealed,
            "hash",
            supervisor=make_supervisor(client),
            entail=Entail(),
            on_raw_response=lambda result: seen.append(result.answer),
        )
        self.assertEqual(record["state"], "model_no_answer")
        self.assertEqual(seen, [None])


if __name__ == "__main__":
    unittest.main()
