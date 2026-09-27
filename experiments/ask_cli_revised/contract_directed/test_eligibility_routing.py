"""Task D's pure helpers: fair ordering (never exclusion), and the Tier-3 distinctness test. The actual scheduling
loop (`pipeline.schedule_and_judge`) is exercised end to end by test_pipeline_integration.py's real-environment
tests; this module tests the ordering/priority/distinctness logic in isolation."""

import unittest

from experiments.ask_cli_revised.contract_directed import eligibility_routing as routing
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract, Unit


def child(child_id="c5", contract_text="brain areas relate to behaviors, in the context of the anomalous is bad bias"):
    return ChildContract(
        child_id=child_id, parent="c4", contract_text=contract_text, contract_sha256="x", wording=contract_text,
        wording_sha256="y", scope_carrier_wording=None,
        units=(Unit("M5", "relationship", "brain areas relate to behaviors", False),), primary_unit_id="M5",
        pair_requirement_ids=(), machine_side_constraints=(),
    )  # fmt: skip


def pk(pid, text, *, found_under, paper_id=1, nbhd_score=0.0, chunk_id=100):
    return {
        "packet_id": pid, "paper_id": paper_id, "found_under": found_under, "nbhd_score": nbhd_score,
        "parts": [{"role": "establishing", "text": text, "pieces": [{"chunk_id": chunk_id}]}],
    }  # fmt: skip


class SalientTermsTests(unittest.TestCase):
    def test_short_and_stop_words_are_excluded(self):
        terms = routing.salient_terms("The amygdala responded to anomalous faces and it was not a large effect")
        self.assertIn("amygdala", terms)
        self.assertIn("responded", terms)
        self.assertIn("anomalous", terms)
        self.assertNotIn("the", terms)
        self.assertNotIn("and", terms)
        self.assertNotIn("was", terms)


class CrossChildPriorityHintTests(unittest.TestCase):
    def test_shared_vocabulary_scores_higher_than_none(self):
        c = child()
        on_topic = pk("a", "The amygdala's response relates to anomalous facial behaviors.", found_under=["c9"])
        off_topic = pk("b", "The dmPFC tracked social scene viewing time in daily life.", found_under=["c9"])
        self.assertGreater(
            routing.cross_child_priority_hint(on_topic, c), routing.cross_child_priority_hint(off_topic, c)
        )

    def test_zero_shared_vocabulary_is_a_valid_score_never_an_exception(self):
        """Cliff's correction: missing vocabulary is not proof of irrelevance — the hint is a float, not a
        boolean, and a score of 0.0 is a perfectly legitimate (if low-priority) outcome, never an exclusion."""
        c = child()
        off_topic = pk("b", "Completely unrelated vocabulary entirely.", found_under=["c9"])
        self.assertEqual(routing.cross_child_priority_hint(off_topic, c), 0.0)


class RouteQueueTests(unittest.TestCase):
    def test_own_route_only_includes_packets_found_under_this_child(self):
        c = child("c5")
        packets = [pk("a", "x", found_under=["c5"]), pk("b", "y", found_under=["c9"])]
        own = routing.own_route_packets(c, packets)
        self.assertEqual([p["packet_id"] for p in own], ["a"])

    def test_own_route_orders_by_neighborhood_score_descending(self):
        c = child("c5")
        packets = [
            pk("low", "x", found_under=["c5"], nbhd_score=0.2),
            pk("high", "y", found_under=["c5"], nbhd_score=0.9),
        ]
        self.assertEqual([p["packet_id"] for p in routing.own_route_packets(c, packets)], ["high", "low"])

    def test_cross_route_includes_every_packet_not_found_under_this_child_regardless_of_hint(self):
        """No hard exclusion exists — every cross-child candidate is returned, only ordered."""
        c = child("c5")
        packets = [
            pk("a", "unrelated text entirely", found_under=["c9"]),
            pk("b", "amygdala anomalous behavior", found_under=["c9"]),
        ]
        cross = routing.cross_route_packets(c, packets)
        self.assertEqual({p["packet_id"] for p in cross}, {"a", "b"})
        self.assertEqual(cross[0]["packet_id"], "b")  # higher lexical overlap ordered first, never excluded


class DistinctnessTests(unittest.TestCase):
    def test_a_different_paper_is_always_distinct(self):
        closing = [pk("a", "x", found_under=["c5"], paper_id=61, chunk_id=100)]
        candidate = pk("b", "y", found_under=["c5"], paper_id=68, chunk_id=100)
        self.assertTrue(routing.is_distinct_from(candidate, closing))

    def test_a_non_overlapping_chunk_range_of_the_same_paper_is_distinct(self):
        closing = [pk("a", "x", found_under=["c5"], paper_id=61, chunk_id=100)]
        candidate = pk("b", "y", found_under=["c5"], paper_id=61, chunk_id=999)
        self.assertTrue(routing.is_distinct_from(candidate, closing))

    def test_an_overlapping_chunk_range_of_the_same_paper_is_not_distinct(self):
        closing = [pk("a", "x", found_under=["c5"], paper_id=61, chunk_id=100)]
        candidate = pk("b", "y", found_under=["c5"], paper_id=61, chunk_id=100)
        self.assertFalse(routing.is_distinct_from(candidate, closing))

    def test_no_closing_packets_means_everything_is_distinct(self):
        candidate = pk("b", "y", found_under=["c5"], paper_id=61, chunk_id=100)
        self.assertTrue(routing.is_distinct_from(candidate, []))


if __name__ == "__main__":
    unittest.main()
