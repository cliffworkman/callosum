"""Regression/negative-control tests for `nli_repair_prototypes.py` (`NLI_REPAIR_DESIGN.md`, 2026-09-28).

Every test here is deterministic and offline: stubbed scores, saved receipts, and the REAL saved diagnostic
JSON files are the only inputs. Zero model/NLI/network calls (enforced by wrapping the whole module in
`endpoint_guard.refuse_all()`, matching the two prior diagnostics' own convention). These tests describe what a
FUTURE, separately-authorized implementation must satisfy -- they do not themselves change any production
behavior, since nothing in `nli_repair_prototypes.py` is imported anywhere else yet.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.ask_cli_revised import overview_guards as guards
from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_repair_prototypes as proto

RUNS_DIR = Path(r"C:\Users\cliff\callosum-data\contract-directed-slice\runs")


def _load_record(run_id: str) -> dict:
    with open(RUNS_DIR / run_id / "04_final_record.json", encoding="utf-8") as f:
        return json.load(f)["record"]


class CitationBoundaryTests(unittest.TestCase):
    """Section 2: citation-metadata contamination of the NLI hypothesis."""

    def test_acceptance_fixture_b_strips_to_exactly_a_zero_inference(self):
        """The saved c9 minimal pair, used as-is -- NOT re-scored, per the authorization."""
        with endpoint_guard.refuse_all():
            live = _load_record("gate-integration-live-002")
            diag = _load_record("gate2-diagnostic-002")
        b = next(p for p in live["proposals"] if p["unit_ids"] == ["U1"])
        a = next(p for p in diag["proposals"] if p["unit_ids"] == ["U1"])
        result = proto.strip_redundant_unit_markers(b["text"], b["unit_ids"])
        self.assertEqual(result.nli_hypothesis_text, a["text"], "stripped B must equal A byte-for-byte")
        self.assertEqual(result.raw_text, b["text"], "raw text must be the untouched original")
        self.assertEqual(result.marker_outcome, proto.MARKER_STRIPPED)
        self.assertIsNotNone(result.stripped_marker)

    def test_c11_marker_also_strips_correctly(self):
        with endpoint_guard.refuse_all():
            live = _load_record("gate-integration-live-002")
        d = next(p for p in live["proposals"] if p["unit_ids"] == ["U2", "U3"])
        result = proto.strip_redundant_unit_markers(d["text"], d["unit_ids"])
        self.assertTrue(result.nli_hypothesis_text.endswith("less moral."))
        self.assertNotIn("(U2, U3)", result.nli_hypothesis_text)
        self.assertEqual(result.marker_outcome, proto.MARKER_STRIPPED)

    def test_generic_non_citation_parenthetical_is_never_touched(self):
        """nli-boundary-diagnostic-001's generic_trailing_parenthetical control: support went UP (0.91 vs
        A's 0.81) when a non-citation parenthetical was appended -- confirming it must never be stripped."""
        text = "Participants completed a scale that measures fairness beliefs (see above)."
        result = proto.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(result.nli_hypothesis_text, text)
        self.assertEqual(result.marker_outcome, proto.MARKER_NONE)

    def test_marker_referencing_a_unit_not_in_unit_ids_is_left_untouched(self):
        text = "Participants completed a scale that measures fairness beliefs (U1, U2)."
        result = proto.strip_redundant_unit_markers(text, ["U1"])  # only U1 cited structurally
        self.assertEqual(result.nli_hypothesis_text, text, "must not strip a superset marker")
        self.assertEqual(result.marker_outcome, proto.MARKER_AMBIGUOUS)

    def test_marker_missing_a_structurally_cited_unit_is_left_untouched(self):
        text = "The finding held across both conditions (U2)."
        result = proto.strip_redundant_unit_markers(text, ["U2", "U3"])  # marker is a strict subset
        self.assertEqual(result.nli_hypothesis_text, text, "must not strip a subset marker")
        self.assertEqual(result.marker_outcome, proto.MARKER_AMBIGUOUS)

    def test_marker_embedded_mid_sentence_is_left_untouched(self):
        text = "As shown (U1), the scale measures fairness beliefs in participants."
        result = proto.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(result.nli_hypothesis_text, text, "only a TRAILING marker is ever stripped")
        self.assertEqual(result.marker_outcome, proto.MARKER_NONE)

    def test_marker_mixed_with_prose_is_left_untouched(self):
        """ "(U1, p. 4)" doesn't even match the citation-marker shape (the regex requires every comma-separated
        token to be a bare "U<digits>"), so this correctly falls to MARKER_NONE rather than MARKER_AMBIGUOUS --
        both labels leave the text untouched; the distinction is "never looked citation-shaped" vs. "looked
        citation-shaped but disagreed with unit_ids", not a difference in outcome."""
        text = "The scale measures fairness beliefs (U1, p. 4)."
        result = proto.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(result.nli_hypothesis_text, text)
        self.assertEqual(result.marker_outcome, proto.MARKER_NONE)

    def test_no_marker_present_is_a_no_op(self):
        text = "The scale measures fairness beliefs."
        result = proto.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(result.nli_hypothesis_text, text)
        self.assertEqual(result.stripped_marker, None)
        self.assertEqual(result.marker_outcome, proto.MARKER_NONE)


class ReliabilityDispositionTests(unittest.TestCase):
    """Section 3: the premise-reliability disposition and its required negative controls."""

    RELIABLE = proto.ReliabilityProbe(self_support=0.99, self_contradiction=0.0)
    UNRELIABLE = proto.ReliabilityProbe(self_support=0.0070, self_contradiction=0.9809)  # the real c11 number

    def test_low_score_alone_does_not_trigger_indeterminate(self):
        """Required negative control: a genuinely low candidate score against a RELIABLE premise must stay
        WITHHELD, never become INDETERMINATE merely because the score is low."""
        status, reasons = proto.disposition(
            candidate_support=0.10,
            candidate_contradiction=0.05,
            probe=self.RELIABLE,
            support_threshold=0.55,
            contradiction_threshold=0.55,
        )
        self.assertEqual(status, proto.WITHHELD)
        self.assertEqual(reasons, ["nli_low_support:0.10"])

    def test_failed_reliability_check_never_permits_display_even_with_a_high_candidate_score(self):
        """Required negative control: an UNRELIABLE premise must yield INDETERMINATE even for a hypothetically
        high candidate score -- a failed reliability check is never overridden by a good-looking number."""
        status, reasons = proto.disposition(
            candidate_support=0.99,
            candidate_contradiction=0.0,
            probe=self.UNRELIABLE,
            support_threshold=0.55,
            contradiction_threshold=0.55,
        )
        self.assertEqual(status, proto.INDETERMINATE)
        self.assertNotEqual(status, proto.GROUNDED)

    def test_high_contradiction_on_an_unreliable_premise_is_not_asserted_as_a_real_contradiction(self):
        """The c11 case itself: contradiction=0.98 against an unreliable premise must be labeled INDETERMINATE,
        never `nli_contradicted` -- a high contradiction score is not trustworthy when the premise already
        failed its own sanity check."""
        status, reasons = proto.disposition(
            candidate_support=0.0070,
            candidate_contradiction=0.9809,
            probe=self.UNRELIABLE,
            support_threshold=0.55,
            contradiction_threshold=0.55,
        )
        self.assertEqual(status, proto.INDETERMINATE)
        self.assertFalse(any("nli_contradicted" in r for r in reasons))

    def test_reliable_premise_with_a_real_contradiction_is_still_labeled_contradicted(self):
        """The reliability gate must not suppress a genuine contradiction on a TRUSTWORTHY premise."""
        status, reasons = proto.disposition(
            candidate_support=0.10,
            candidate_contradiction=0.80,
            probe=self.RELIABLE,
            support_threshold=0.55,
            contradiction_threshold=0.55,
        )
        self.assertEqual(status, proto.WITHHELD)
        self.assertEqual(reasons, ["nli_contradicted:0.80"])

    def test_backward_compatible_status_strings(self):
        """Wiring this in must only ADD a third value -- never rename what grounded/withheld already mean."""
        self.assertEqual(proto.GROUNDED, "grounded")
        self.assertEqual(proto.WITHHELD, "withheld")

    def test_reproduces_overview_guards_nli_reasons_exactly_for_every_historical_pair_when_reliable(self):
        """Compatibility regression: for every one of the four historical (support, contradiction) pairs from
        nli-boundary-diagnostic-001, assuming a RELIABLE premise, this prototype's decision must exactly
        reproduce `overview_guards.nli_reasons`'s real, current output -- proving the new logic changes nothing
        for the case that already works today."""
        historical = [
            (0.8108597993850708, 0.12746837735176086),  # A -- grounded today
            (0.23521043360233307, 0.231438547372818),  # B -- withheld today (marker contamination, separate fix)
            (0.2671320140361786, 0.1451309770345688),  # C -- withheld today
            (0.013148654252290726, 0.3011533319950104),  # D -- withheld today
        ]
        for support, contradiction in historical:
            with self.subTest(support=support, contradiction=contradiction):
                expected_reasons = guards.nli_reasons(support, contradiction)
                expected_status = proto.WITHHELD if expected_reasons else proto.GROUNDED
                status, reasons = proto.disposition(
                    candidate_support=support,
                    candidate_contradiction=contradiction,
                    probe=self.RELIABLE,
                    support_threshold=0.55,  # VerificationConfig defaults, matching overview_guards.nli_reasons
                    contradiction_threshold=0.55,
                )
                self.assertEqual(status, expected_status)
                self.assertEqual(reasons, expected_reasons)


class ExistingRendererGapTests(unittest.TestCase):
    """UPDATED 2026-09-28 (implementation pass): the gap this class originally documented -- `classify_row`
    silently dropping a proposal status it doesn't recognize -- is now FIXED (`UnknownProposalStatus`,
    `partial_answer_renderer.py`). This test now asserts the fixed behavior, per NLI_REPAIR_DESIGN.md Section
    3.5's own instruction that adding a real third status still requires teaching `classify_row` about it
    explicitly. The dedicated, more complete regression coverage for this now lives in
    `test_partial_answer_renderer.py::ClassifyRowTests` (the module this fix actually lives in); this test is
    kept as the direct before/after proof of the specific gap this design pass found."""

    def test_an_unrecognized_proposal_status_now_raises_explicitly_instead_of_silently_disappearing(self):
        from experiments.ask_cli_revised.contract_directed import partial_answer_renderer as renderer

        row = {
            "child_id": "c11",
            "unit_id": "M12",
            "kind": "population",
            "status": "source_supported",
            "accepted_spans": [],
            "packet_id": "pkt",
            "provenance": None,
        }
        hypothetically_indeterminate_proposal = {
            "index": 0,
            "text": "some candidate text",
            "unit_ids": ["U1"],
            "status": "indeterminate",  # not "grounded", not "withheld" -- still not a real production status
            "reasons": ["nli_unreliable_premise:self_support=0.01"],
        }
        with self.assertRaises(renderer.UnknownProposalStatus):
            renderer.classify_row(row, matched_units=["U1"], proposals=[hypothetically_indeterminate_proposal])


if __name__ == "__main__":
    unittest.main()
