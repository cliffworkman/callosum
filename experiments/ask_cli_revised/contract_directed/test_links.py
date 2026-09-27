import sqlite3
import unittest

from experiments.ask_cli_revised.contract_directed import freeze, links

DB = freeze.SLICE_ROOT / "library.sqlite"


def piece(cid, text, section="methods", start=0):
    return {
        "chunk_id": cid,
        "start": start,
        "end": start + len(text),
        "text": text,
        "section": section,
        "page_start": 5,
    }


class DesignatorTests(unittest.TestCase):
    def test_definition_pairs_require_matching_initials(self):
        text = (
            "In the Dictator Game (DG), one player splits $5. Explicit Bias Questionnaire (EBQ). A random thing (XQZ)."
        )
        self.assertEqual(
            links.definition_pairs(text), [("DG", "Dictator Game"), ("EBQ", "Explicit Bias Questionnaire")]
        )

    def test_fmri_style_lowercase_initial_acronyms(self):
        self.assertEqual(
            links.definition_pairs("functional magnetic resonance imaging (fMRI) was used"),
            [("FMRI", "functional magnetic resonance imaging")],
        )

    def test_designator_extraction_is_bounded_and_specific(self):
        text = "Participants completed a Just World Beliefs Scale and the Dictator Game (DG); see Table 2 and Study 1. THE AND IAT EBQ SES CI"
        kinds = [d.kind for d in links.extract_designators(text)]
        self.assertLessEqual(len(kinds), links.MAX_DESIGNATORS)
        self.assertEqual(kinds[0], "instrument")
        surfaces = [d.surface for d in links.extract_designators("less generosity in the DG and IAT scores")]
        self.assertEqual(surfaces, ["DG", "IAT"])


class LinkTests(unittest.TestCase):
    def pieces(self):
        return [
            piece(
                1,
                "Prosociality. In the Dictator Game (DG), one player (the dictator) decides how to split an endowment ($5).",
            ),
            piece(2, "We recruited 40 participants from a university subject pool.", "methods"),
            piece(3, "Table 2. Regression results for prosociality.", "results"),
            piece(
                4,
                "Participants completed a Just World Beliefs Scale, which measures beliefs about fairness.",
                "methods",
            ),
            piece(5, "Smith et al. developed the Dictator Game (DG) earlier.", "references"),
        ]

    def test_acronym_used_in_a_finding_links_to_its_methods_definition(self):
        out = links.find_links(
            ["undesirable behaviors (less generosity in the DG)"],
            self.pieces(),
            exclude_chunk_ids={99},
            finding_key="f",
        )
        [link] = [lk for lk in out if lk["basis"]["designator"] == "DG"]
        self.assertTrue(link["verified"], link)
        self.assertEqual(link["basis"]["type"], "definition_acronym")
        self.assertEqual(link["linked"]["chunk_id"], 1)
        self.assertEqual(link["occurrences"], 1)  # the References-section mention never counts

    def test_named_measure_links_only_when_verbatim_in_both_spans(self):
        out = links.find_links(
            ["scores on the Just World Beliefs Scale were higher"], self.pieces(), exclude_chunk_ids=set()
        )
        [link] = [lk for lk in out if lk["basis"]["type"] == "shared_designator"]
        self.assertTrue(link["verified"])
        self.assertEqual(link["linked"]["chunk_id"], 4)

    def test_explicit_table_reference_links_to_its_caption(self):
        out = links.find_links(["(β = 1.2; see Table 2)"], self.pieces(), exclude_chunk_ids=set())
        [link] = [lk for lk in out if lk["basis"]["type"] == "explicit_reference"]
        self.assertTrue(link["verified"])
        self.assertEqual(link["linked"]["chunk_id"], 3)

    def test_topical_co_occurrence_is_not_a_link(self):
        pieces = [piece(1, "The amygdala responds to disgust. Participants were scanned.")]
        out = links.find_links(["the amygdala response correlated with empathy"], pieces, exclude_chunk_ids=set())
        self.assertEqual(out, [])

    def test_the_findings_own_neighborhood_and_references_are_never_targets(self):
        out = links.find_links(["less generosity in the DG"], self.pieces(), exclude_chunk_ids={1})
        self.assertEqual(out, [])

    def test_study_label_conflict_refuses_the_link(self):
        pieces = [piece(1, "Study 2. In the Dictator Game (DG), players split $5.")]
        out = links.find_links(["In Study 1 there was less generosity in the DG."], pieces, exclude_chunk_ids=set())
        [link] = out
        self.assertFalse(link["verified"])
        self.assertEqual(link["refusal_reason"], "study_label_conflict")

    def test_verify_link_needs_the_acronym_to_be_used_in_the_finding(self):
        ok, reason = links.verify_link(
            ["nothing relevant here"], "Dictator Game (DG)", {"type": "definition_acronym", "designator": "DG"}
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "acronym_not_used_or_not_defined")


@unittest.skipUnless(DB.is_file(), "disposable library copy not present")
class RealDictatorGameLinkTests(unittest.TestCase):
    """Discussion 'less generosity in the DG' <-> Methods 'Dictator Game (DG)' in the real paper 67 attachment."""

    @classmethod
    def setUpClass(cls):
        con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro&immutable=1", uri=True)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "select id, text, section, page_start from chunks where attachment_id=67 order by char_start, id"
            ).fetchall()
        finally:
            con.close()
        cls.chunks = [
            {"chunk_id": r["id"], "text": r["text"], "section": r["section"], "page_start": r["page_start"]}
            for r in rows
        ]

    def test_the_discussion_finding_links_to_the_methods_definition_by_verified_acronym(self):
        pieces = links.attachment_pieces(self.chunks)
        finding = "undesirable behaviors (less generosity in the DG)"
        out = links.find_links([finding], pieces, exclude_chunk_ids={35111}, finding_key="u6")
        [link] = [lk for lk in out if lk["basis"]["designator"] == "DG"]
        self.assertTrue(link["verified"], link)
        self.assertEqual(link["linked"]["chunk_id"], 35014)
        self.assertEqual(link["linked"]["section"], "methods")
        chunk_text = next(c["text"] for c in self.chunks if c["chunk_id"] == 35014)
        self.assertEqual(chunk_text[link["linked"]["start"] : link["linked"]["end"]], link["linked"]["text"])
        self.assertIn("Dictator Game (DG)", link["linked"]["text"])


if __name__ == "__main__":
    unittest.main()
