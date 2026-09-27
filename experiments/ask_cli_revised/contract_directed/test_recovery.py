import re
import unittest
from types import SimpleNamespace

from experiments.ask_cli_revised.contract_directed import coverage, freeze, recovery
from experiments.ask_cli_revised.contract_directed.fakes import fake_chunk


class FakeRetriever:
    """Scores chunks by token overlap with the query: deterministic and dependency-free."""

    def __init__(self, texts):
        self.texts = texts  # chunk_id -> text

    def search(self, query, *, chunk_ids=None, top_k=10, demote=True):
        q = set(re.findall(r"[a-z]+", query.lower()))
        scored = []
        for cid in chunk_ids if chunk_ids is not None else self.texts:
            overlap = len(q & set(re.findall(r"[a-z]+", self.texts[cid].lower())))
            if overlap:
                scored.append(SimpleNamespace(chunk_id=cid, score=overlap / 10, evidence_role=None))
        return sorted(scored, key=lambda h: (-h.score, h.chunk_id))[:top_k]


class FakeLibrary:
    def __init__(self):
        self.att = {
            10: [
                fake_chunk(
                    1,
                    "Results: people were rated as less trustworthy overall here.",
                    attachment_id=10,
                    section="results",
                    paper_id=1,
                ),
                fake_chunk(
                    2,
                    "Methods: participants completed scales that measure empathy.",
                    attachment_id=10,
                    section="methods",
                    paper_id=1,
                ),
                fake_chunk(
                    3, "Discussion of the results and limitations.", attachment_id=10, section="discussion", paper_id=1
                ),
            ],
            11: [
                fake_chunk(
                    4,
                    "Manuscript version: participants completed the scales measuring empathy carefully.",
                    attachment_id=11,
                    section="methods",
                    paper_id=1,
                )
            ],
            20: [
                fake_chunk(
                    5,
                    "Methods: scales measuring disgust sensitivity were used.",
                    attachment_id=20,
                    section="methods",
                    paper_id=2,
                ),
                fake_chunk(6, "Results: disgust scores were higher.", attachment_id=20, section="results", paper_id=2),
            ],
        }
        for chunks in self.att.values():
            for c in chunks:
                c["char_start"] = c["chunk_id"] * 1000
        self.owner = {10: 1, 11: 1, 20: 2}

    def article_attachments(self, paper_id):
        ids = sorted(a for a, p in self.owner.items() if p == paper_id)
        return [
            {
                "id": a,
                "role": "primary" if i == 0 else None,
                "checksum": f"c{a}",
                "is_primary": i == 0,
                "n_chunks": len(self.att[a]),
            }
            for i, a in enumerate(ids)
        ]

    def attachment_chunks(self, attachment_id):
        return self.att[attachment_id]

    def paper(self, paper_id):
        return {"id": paper_id, "abstract": None, "title": f"P{paper_id}"}

    def attachment(self, attachment_id):
        ids = [a for a, p in self.owner.items() if p == self.owner[attachment_id]]
        return {
            "id": attachment_id,
            "paper_id": self.owner[attachment_id],
            "role": "primary" if attachment_id == min(ids) else None,
            "checksum": f"c{attachment_id}",
            "is_primary": attachment_id == min(ids),
        }


def child():
    units = (
        freeze.Unit("M10", "operation", "using which scales?", False),
        freeze.Unit("W21", "requested_item", "scales", False),
    )
    return freeze.ChildContract(
        "c9", "c8", "which scales measure traits", "h", "which scales measure traits", "w", None, units, "M10", (), ()
    )


def row(unit_id, state, partial=(), missing=None):
    return {
        "child_id": "c9",
        "unit_id": unit_id,
        "row_type": "content",
        "state": state,
        "closing_packet_ids": [],
        "partial_packet_ids": list(partial),
        "missing_by_partial_packet": missing or {},
    }


def nbhd(nid, paper, att, chunk_ids, anchor, families=("methods",), unit_scores=None):
    return {
        "nbhd_id": nid, "paper_id": paper, "attachment_id": att, "chunk_ids": chunk_ids, "anchor_chunk_ids": [anchor],
        "attachment": {"id": att, "role": "primary", "checksum": f"c{att}", "is_primary": True},
        "anchors": [{"chunk_id": anchor, "routes": ["unit_probe:M10"], "family": f} for f in families],
        "routes": ["unit_probe:M10"], "unit_scores": unit_scores or {}, "best_score": 0.5,
    }  # fmt: skip


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.lib = FakeLibrary()
        self.retr = FakeRetriever({c["chunk_id"]: c["text"] for chunks in self.lib.att.values() for c in chunks})
        self.child = child()

    def plan(self, rows, read, capped=(), inspected=(1,), deferred=(), packets=None, cap=6):
        return recovery.plan_recovery(
            self.child,
            rows,
            read=list(read),
            capped=list(capped),
            inspected=list(inspected),
            deferred=list(deferred),
            packets_by_id=packets or {},
            library=self.lib,
            retriever=self.retr,
            cap=cap,
        )

    def test_nothing_unresolved_means_no_recovery(self):
        attached = [dict(row("M10", coverage.ATTACHED)), dict(row("W21", coverage.ATTACHED))]
        self.assertEqual(self.plan(attached, [nbhd("a", 1, 10, [1], 1, ("results",))]), [])

    def test_a_budget_capped_neighborhood_is_revisited_first_and_records_why(self):
        read = [nbhd("a", 1, 10, [1], 1, ("results",))]
        capped = [
            nbhd("b", 1, 10, [2], 2, unit_scores={"M10": 0.4}),
            nbhd("c", 1, 10, [3], 3, unit_scores={"M10": 0.2}),
        ]
        actions = self.plan([row("M10", coverage.UNRESOLVED_BUDGET), row("W21", coverage.ATTACHED)], read, capped)
        first = actions[0]
        self.assertEqual(
            (first["action"], first["trigger_reason"]), ("read_budget_capped_neighborhood", "budget_capped")
        )
        self.assertEqual(first["recovers"]["nbhd_id"], "b")  # the better-scoring capped neighborhood first
        self.assertEqual(first["unit_id"], "M10")
        self.assertIn("deferred by the neighborhood budget", first["recovers"]["why"])

    def test_a_partial_packet_gets_a_wider_neighborhood_and_the_original_is_untouched(self):
        origin = nbhd("a", 1, 10, [2], 2)
        packets = {
            "pk": {
                "packet_id": "pk",
                "nbhd_id": "a",
                "paper_id": 1,
                "evidence_form": "verbatim",
                "unresolved_notes": ["the scale named DG is defined elsewhere"],
            }
        }
        r = row(
            "M10",
            coverage.PARTIAL_ONLY,
            partial=["pk"],
            missing={"pk": {"missing": ["paired_with_construct"], "reasons": []}},
        )
        actions = [a for a in self.plan([r], [origin], packets=packets) if a["action"] == "widen_neighborhood"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["trigger_reason"], "unresolved_referent")
        self.assertEqual(actions[0]["recovers"]["packet_id"], "pk")
        self.assertGreater(len(actions[0]["nbhd"]["chunk_ids"]), len(origin["chunk_ids"]))
        self.assertEqual(origin["chunk_ids"], [2])  # append-only: the failed route is preserved as it was

    def test_an_unresolved_seam_is_named_as_the_trigger(self):
        origin = nbhd("a", 1, 10, [2], 2)
        packets = {
            "pk": {
                "packet_id": "pk",
                "nbhd_id": "a",
                "paper_id": 1,
                "evidence_form": "fragments_unresolved_seam",
                "unresolved_notes": [],
            }
        }
        r = row("M10", coverage.PARTIAL_ONLY, partial=["pk"])
        [widen] = [a for a in self.plan([r], [origin], packets=packets) if a["action"] == "widen_neighborhood"]
        self.assertEqual(widen["trigger_reason"], "seam_unresolved")

    def test_another_section_family_of_an_inspected_paper_is_probed_when_none_was_read(self):
        read = [nbhd("a", 1, 10, [1], 1, families=("results",))]  # methods never read for paper 1
        actions = [
            a
            for a in self.plan([row("M10", coverage.UNRESOLVED_SEARCHED)], read)
            if a["action"] == "other_section_family"
        ]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["recovers"]["families_read"], ["results"])
        self.assertIn(2, actions[0]["nbhd"]["chunk_ids"])  # the methods chunk mentioning the scale
        self.assertEqual(actions[0]["trigger_reason"], "no_closing_packet")

    def test_a_different_attachment_of_an_inspected_paper_is_revisited_and_labelled(self):
        read = [nbhd("a", 1, 10, [1, 2, 3], 2)]
        [alt] = [
            a for a in self.plan([row("M10", coverage.UNRESOLVED_SEARCHED)], read) if a["action"] == "other_attachment"
        ]
        self.assertEqual(alt["recovers"]["alternate_attachment"], 11)
        self.assertFalse(alt["nbhd"]["attachment"]["is_primary"])
        self.assertIn("never counted as corroboration", alt["recovers"]["note"])

    def test_the_pass_is_capped_and_never_repeats_a_neighborhood(self):
        read = [nbhd("a", 1, 10, [1], 1, ("results",))]
        capped = [nbhd("b", 1, 10, [2], 2, unit_scores={"M10": 0.4})]
        actions = self.plan(
            [row("M10", coverage.UNRESOLVED_BUDGET), row("W21", coverage.UNRESOLVED_BUDGET)],
            read,
            capped,
            inspected=(1,),
            cap=2,
        )
        self.assertEqual(len(actions), 2)
        ids = [a["nbhd"]["nbhd_id"] for a in actions]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_action_records_its_trigger_and_action_kind(self):
        read = [nbhd("a", 1, 10, [1], 1, ("results",))]
        for action in self.plan([row("M10", coverage.UNRESOLVED_SEARCHED)], read):
            self.assertIn(
                action["action"],
                {
                    "read_budget_capped_neighborhood",
                    "widen_neighborhood",
                    "other_section_family",
                    "other_attachment",
                    "deferred_paper",
                },
            )
            self.assertTrue(action["trigger_reason"])
            self.assertTrue(action["recovers"])
            self.assertTrue(action["nbhd"].get("recovery"))


if __name__ == "__main__":
    unittest.main()
