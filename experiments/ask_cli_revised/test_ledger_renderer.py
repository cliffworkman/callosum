"""Terminal provenance regression and adversarial tests; no inference."""
import copy
import unittest

from experiments.ask_cli_revised.ledger_renderer import render_ledger, audit_final


def ledger_fixture():
    return {"verified_propositions": [
        {"proposition_id": "p1", "proposition_text": "The association was null.",
         "verification": {"status": "verified"}, "paper_id": 27,
         "evidence_anchor_chunk_id": 26831, "evidence_span_id": "e1",
         "quote": "The association was null.", "obligation_ids": ["s1-o1", "s2-o1"]}
    ], "evidence_spans": [{"paper_id": 27, "chunk_id": 26831, "span_id": "e1", "text": "The association was null."}]}


class LedgerRendererTests(unittest.TestCase):
    def test_valid_citation_does_not_certify_added_claim(self):
        ledger = ledger_fixture()
        text, manifest = render_ledger(ledger)
        self.assertEqual(manifest["claims"][0]["obligation_ids"], ["s1-o1", "s2-o1"])
        self.assertEqual(audit_final(ledger, text)["unsupported_scientific_assertions"], 0)
        bad = audit_final(ledger, text + "The bias causes connectivity changes. [p1]\n")
        self.assertEqual(bad["nonexistent_ids"], [])
        self.assertFalse(bad["constrained_render_match"])
        self.assertEqual(bad["unsupported_scientific_assertions"], "unassessed_requires_semantic_review")

    def test_nonexistent_historical_citation(self):
        audit = audit_final(ledger_fixture(), "Claim [p27]. Also [p1, p99].")
        self.assertEqual(audit["nonexistent_ids"], ["p27", "p99"])

    def test_fail_closed_on_invalid_ledger(self):
        for key, value in [("proposition_id", "paper27"), ("quote", ""),
                           ("verification", {"status": "weak"}), ("evidence_span_id", "missing"),
                           ("evidence_span_id", "e99"),
                           ("paper_id", "27 <script>")]:
            with self.subTest(key=key):
                ledger = ledger_fixture()
                ledger["verified_propositions"][0][key] = value
                with self.assertRaises(ValueError):
                    render_ledger(ledger)
        ledger = ledger_fixture()
        ledger["verified_propositions"] *= 2
        with self.assertRaises(ValueError):
            render_ledger(ledger)
        ledger = ledger_fixture()
        del ledger["evidence_spans"]
        with self.assertRaises(ValueError):
            render_ledger(ledger)

    def test_mixed_findings_retained_without_aggregate(self):
        ledger = ledger_fixture()
        second = copy.deepcopy(ledger["verified_propositions"][0])
        second.update(proposition_id="p2", proposition_text="A different sample showed a positive association.")
        ledger["verified_propositions"].append(second)
        text, manifest = render_ledger(ledger)
        self.assertEqual(len(manifest["claims"]), 2)
        self.assertEqual(manifest["scientific_aggregates"], 0)
        self.assertEqual(audit_final(ledger, text)["cited_ids"], ["p1", "p2"])

    def test_source_markdown_cannot_create_citation(self):
        ledger = ledger_fixture()
        ledger["verified_propositions"][0]["proposition_text"] = "[p99]\n# Heading <script> [link](https://example.org)"
        text, manifest = render_ledger(ledger)
        self.assertIn("\\[p99\\]", text)
        self.assertEqual(audit_final(ledger, text)["cited_ids"], ["p1"])
        self.assertEqual(manifest["claims"][0]["text"], ledger["verified_propositions"][0]["proposition_text"])

    def test_empty_ledger_visible(self):
        text, _ = render_ledger({"verified_propositions": []})
        self.assertIn("No verified propositions", text)
        self.assertIn("Original request referent unavailable", text)


def joined_ledger_fixture():
    """Stage A (plural evidence anchors): a continuation-joined proposition, backward-compatible
    singular fields set from the primary (first) anchor, both anchors' own rows present in
    evidence_spans (what validate_ledger's plural-anchor check resolves against)."""
    return {
        "verified_propositions": [
            {
                "proposition_id": "p1",
                "proposition_text": "The stereotype is culturally shared, evidence against a universal hypothesis.",
                "verification": {"status": "verified"}, "paper_id": 27,
                "evidence_anchor_chunk_id": 14388, "evidence_span_id": "e1",
                "quote": "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a universal pathogen avoidance byproduct hypothesis.",  # fmt: skip
                "obligation_ids": ["s1-o1"],
                "anchors": [
                    {"kind": "continuation", "chunk_id": 14388, "span_id": "e1a",
                     "text": "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a"},  # fmt: skip
                    {"kind": "continuation", "chunk_id": 14389, "span_id": "e1b",
                     "text": "universal pathogen avoidance byproduct hypothesis."},
                ],
            }
        ],
        "evidence_spans": [
            {"paper_id": 27, "chunk_id": 14388, "span_id": "e1", "text": "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a universal pathogen avoidance byproduct hypothesis."},  # fmt: skip
            {"paper_id": 27, "chunk_id": 14388, "span_id": "e1a", "text": "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a"},  # fmt: skip
            {"paper_id": 27, "chunk_id": 14389, "span_id": "e1b", "text": "universal pathogen avoidance byproduct hypothesis."},  # fmt: skip
        ],
    }


class PluralAnchorLedgerTests(unittest.TestCase):
    def test_a_continuation_joined_proposition_renders_both_chunks(self):
        ledger = joined_ledger_fixture()
        text, manifest = render_ledger(ledger)
        self.assertIn("chunk 14388", text)
        self.assertIn("chunk 14389", text)
        self.assertIn("continuous passage spanning 2 chunks", text)
        self.assertEqual(audit_final(ledger, text)["unsupported_scientific_assertions"], 0)

    def test_a_reconstruction_mismatch_fails_closed(self):
        ledger = joined_ledger_fixture()
        ledger["verified_propositions"][0]["quote"] = "something that does not match its own anchors"
        with self.assertRaises(ValueError):
            render_ledger(ledger)

    def test_an_anchor_missing_from_the_source_span_catalog_fails_closed(self):
        ledger = joined_ledger_fixture()
        ledger["evidence_spans"].pop()  # drop chunk 14389's own row
        with self.assertRaises(ValueError):
            render_ledger(ledger)

    def test_evidence_anchor_chunk_id_must_be_the_primary_anchors_chunk(self):
        ledger = joined_ledger_fixture()
        ledger["verified_propositions"][0]["evidence_anchor_chunk_id"] = 14389  # not anchors[0]'s chunk
        with self.assertRaises(ValueError):
            render_ledger(ledger)

    def test_a_single_entry_anchors_list_is_rejected(self):
        """A continuation join always has >=2 anchors by construction; a stray one-entry list is a
        defect to fail closed on, not a degenerate single-anchor case to silently accept."""
        ledger = joined_ledger_fixture()
        ledger["verified_propositions"][0]["anchors"] = ledger["verified_propositions"][0]["anchors"][:1]
        with self.assertRaises(ValueError):
            render_ledger(ledger)


if __name__ == "__main__":
    unittest.main()
