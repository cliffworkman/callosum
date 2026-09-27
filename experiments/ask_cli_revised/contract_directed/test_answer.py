import hashlib
import json
import unittest

from experiments.ask_cli_revised.contract_directed import answer, freeze

RECEIPT = freeze.AB_ROOT / "child_evidence_diag" / "00_contracts_evidence_and_receipt.json"


@unittest.skipUnless(RECEIPT.is_file(), "frozen private run data not present on this machine")
class BaselineFidelityTests(unittest.TestCase):
    def test_the_eleven_recorded_prompts_reproduce_byte_for_byte(self):
        record = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(len(record["children"]), 11)
        for child in record["children"]:
            units = [
                {"unit_id": p["unit_id"], "paper_id": p["paper_id"], "passage": p["passage"]}
                for p in child["eligible_passages"]
            ]
            prompt = answer.render_baseline_prompt(child["approved_child_contract_as_shown_to_models"], units)
            self.assertEqual(prompt, child["prompt"], child["child_id"])
            self.assertEqual(
                hashlib.sha256(prompt.encode("utf-8")).hexdigest(), child["prompt_sha256"], child["child_id"]
            )

    def test_no_evidence_children_render_the_recorded_none_block(self):
        record = json.loads(RECEIPT.read_text(encoding="utf-8"))
        empty = [c for c in record["children"] if c["no_eligible_evidence"]]
        self.assertEqual({c["child_id"] for c in empty}, {"c9", "c10", "c11"})
        for child in empty:
            self.assertIn(answer.NO_EVIDENCE_BLOCK, child["prompt"])


class PacketRenderTests(unittest.TestCase):
    def packet(self, pid="k1", parts=None, attachment=None):
        return {
            "packet_id": pid,
            "paper_id": 67,
            "attachment": attachment or {"id": 67, "role": "primary", "is_primary": True},
            "parts": parts
            or [
                {
                    "text": "Participants expressed explicit biases.",
                    "section": "results",
                    "page_start": 7,
                    "page_end": 7,
                }
            ],
        }

    def test_instruction_text_is_the_baseline_template(self):
        prompt, _ = answer.render_packet_prompt("a question", [self.packet()])
        head, tail = answer.PROMPT_TEMPLATE.split("{passages}")
        self.assertTrue(prompt.startswith(head.format(contract="a question") if "{contract}" in head else head))
        self.assertTrue(prompt.endswith(tail))

    def test_single_span_packet_shows_source_metadata_not_claims(self):
        prompt, id_map = answer.render_packet_prompt("q", [self.packet()])
        self.assertIn(
            '[P1] paper 67 · attachment 67 (primary) · Results · p.7\nPassage: "Participants expressed explicit biases."',
            prompt,
        )
        self.assertEqual(id_map, {"P1": "k1"})

    def test_alternate_attachment_is_labelled(self):
        prompt, _ = answer.render_packet_prompt(
            "q", [self.packet(attachment={"id": 78, "role": None, "is_primary": False})]
        )
        self.assertIn("attachment 78 (alternate attachment, role unset)", prompt)

    def test_multi_part_packet_keeps_each_span_separate_with_its_link_note(self):
        parts = [
            {"text": "less generosity in the DG", "section": "discussion", "page_start": 13, "page_end": 13},
            {
                "text": "Dictator Game (DG)",
                "section": "methods",
                "page_start": 5,
                "page_end": 5,
                "note": 'linked by shared designator "DG"',
            },
        ]
        block = answer.packet_block(1, self.packet(parts=parts))
        self.assertIn('(a) Discussion · p.13 — "less generosity in the DG"', block)
        self.assertIn('(b) Methods · p.5 — linked by shared designator "DG" — "Dictator Game (DG)"', block)
        self.assertNotIn("less generosity in the DG Dictator", block)  # never merged into one quotation

    def test_empty_evidence_renders_the_none_block(self):
        prompt, id_map = answer.render_packet_prompt("q", [])
        self.assertIn(answer.NO_EVIDENCE_BLOCK, prompt)
        self.assertEqual(id_map, {})

    def test_context_selection_never_truncates_and_records_omissions(self):
        big = self.packet("big", parts=[{"text": "x" * 30000}])
        small = self.packet("small")
        kept, omitted = answer.select_within_context("q", [small, big, small | {"packet_id": "small2"}])
        self.assertEqual([p["packet_id"] for p in kept], ["small", "small2"])
        self.assertEqual(omitted, ["big"])
        self.assertTrue(all(p["parts"][0]["text"] in {"Participants expressed explicit biases."} for p in kept))


if __name__ == "__main__":
    unittest.main()
