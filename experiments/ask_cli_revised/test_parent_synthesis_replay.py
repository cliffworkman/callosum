"""Phase 27 offline replay over the REAL frozen Phase-23 final state (read-only): the production helper, a faithful fake
S2 client and the c12 adversarial fake. No model, no network, no execute(), no recovery. Skipped when the frozen run
artifacts are not present in this worktree (the same convention as the other artifact-backed tests)."""

from __future__ import annotations

import contextlib
import copy
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from experiments.ask_cli_revised import e2e
from experiments.ask_cli_revised import parent_synthesis_audit as psa
from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_render as psr
from experiments.ask_cli_revised import parent_synthesis_test_support as pst
from experiments.ask_cli_revised.trace import TraceWriter

RUN_DIR = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "phase23-live-recovery-targeted-u2-remap-validation-20261003T020939Z"
)
ARTIFACTS_PRESENT = (RUN_DIR / "phase23_result.json").exists() and (
    RUN_DIR / "run" / "11_verified_ledger.json"
).exists()


def _load():
    result = json.loads((RUN_DIR / "phase23_result.json").read_text(encoding="utf-8"))
    sealed = json.loads((RUN_DIR / "run" / "11_verified_ledger.json").read_text(encoding="utf-8"))
    return result["sufficiency_map_final"], sealed, result["recovery_targets_final"]


def _block(prompt: str, claim_id: str) -> str:
    return prompt.split(f"[{claim_id}]", 1)[1].split("\n\n", 1)[0]


def _c12_relational(claims: list[dict]) -> dict:
    """The one real relational claim owned by child c12 (the adversarial fixture). Selected by child id, never by
    position: the first relational claim in the ledger belongs to c1."""
    return next(c for c in claims if c["claim_kind"] == "relational" and "c12" in c["child_ids"])


def _restated_values(block: str) -> str:
    """The claim's own authorized values, verbatim, with the framing headers removed. Every value line the prompt shows
    (role-prefixed, bulleted, or a bare list item) is kept; only the category/instruction headers are dropped."""
    parts = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("Category:") or (line.endswith(":") and not line.startswith("-")):
            continue
        if line.startswith("- "):
            line = line[2:]
        if ": " in line:
            line = line.split(": ", 1)[1]
        parts.append(line)
    return "; ".join(parts)


def _faithful(prompt, schema):
    """Restates each claim's own authorized values, verbatim and in order, and nothing else. Capped at the schema's
    400-character bound. A bare fragment shorter than the schema's 15-character minimum is given a neutral sentence
    frame ("Reported: ...") so it is a schema-valid statement, as a sentence-writing model would produce; the frame adds
    no content, so the screens still judge exactly the authorized values."""
    items = []
    for cid in pst.prompt_claim_ids(prompt):
        text = _restated_values(_block(prompt, cid))[:400]
        if len(text) < 15:
            text = f"Reported: {text}"
        items.append({"claim_id": cid, "statement": text})
    return {"items": items}


def _c12_correction(prompt, schema):
    """The adversary: restates everything faithfully, except the c12 relational claim, whose target slot it rewrites
    to the scientifically correct alternate phrase found in the very same passage."""
    answer = _faithful(prompt, schema)
    for item in answer["items"]:
        if "target_manifestation" in _block(prompt, item["claim_id"]):
            item["statement"] = "The intervention targeted bias against people with anomalous faces."
    return answer


def _realize(answer, smf, sealed, targets):
    """Run the production helper once over the frozen state with a fake S2 client. Returns (output, client, stages)."""
    client = pst.FakeParentClient(answer=answer)
    stage_entries = []

    @contextlib.contextmanager
    def stage(name, role):
        stage_entries.append(name)
        yield {}

    with tempfile.TemporaryDirectory() as tmp:
        out = e2e._parent_synthesis_outputs(
            trace=TraceWriter(Path(tmp) / "run"),
            stage=stage,
            bound=SimpleNamespace(supervisors={"S": pst.make_s2_supervisor(client)}),
            sealed=sealed,
            sealed_hash="frozen-phase23",
            sufficiency_map_final=smf,
            recovery_targets_final=targets,
            question="frozen Phase-23 request",
            entail=pst.FakeEntail(),
        )
    return out, client, stage_entries


@unittest.skipUnless(ARTIFACTS_PRESENT, "the frozen Phase-23 run artifacts are not present in this worktree")
class ParentRealizationReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smf, cls.sealed, cls.targets = _load()
        cls.claims = psl.build_claim_ledger(cls.smf, cls.sealed)
        cls.gaps = psl.build_gap_report(cls.targets, sufficiency_map_final=cls.smf)

    def _run(self, answer):
        return _realize(answer, self.smf, self.sealed, self.targets)

    def test_the_real_state_yields_the_expected_claim_and_gap_counts(self):
        self.assertEqual(len(self.claims), 24)
        self.assertEqual(len(self.gaps), 33)

    def test_one_fake_realization_call_covers_every_claim_exactly_once(self):
        out, client, stages = self._run(_faithful)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(stages, ["S2"])
        ids = [s["claim_id"] for s in out["record"]["realized_segments"]]
        self.assertEqual(sorted(ids), sorted(c["claim_id"] for c in self.claims))
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_citation_resolves_and_is_the_claims_own(self):
        out, _client, _stages = self._run(_faithful)
        index = {row["proposition_id"] for row in self.sealed["verified_propositions"]}
        for claim in out["record"]["claim_ledger"]:
            self.assertTrue(set(claim["admissible_proposition_ids"]) <= index)

    def test_the_real_replay_audit_passes(self):
        out, _client, _stages = self._run(_faithful)
        self.assertTrue(out["audit"]["ok"], out["audit"])

    def test_c12_wrong_value_remains_the_realization_authority(self):
        """The faithful fake echoes the ledger's own value; the wrong target_manifestation text survives unchanged."""
        out, _client, _stages = self._run(_faithful)
        relational = _c12_relational(out["record"]["claim_ledger"])
        values = {v["role"]: v["exact_text"] for v in relational["values"]}
        self.assertEqual(values["target_manifestation"], pst.C12_WRONG_TARGET_MANIFESTATION_TEXT)
        segment = next(s for s in out["record"]["realized_segments"] if s["claim_id"] == relational["claim_id"])
        self.assertIn(pst.C12_WRONG_TARGET_MANIFESTATION_TEXT, segment["final_text"])

    def test_the_c12_adversarial_correction_is_withheld_on_the_real_claim(self):
        out, _client, _stages = self._run(_c12_correction)
        relational = _c12_relational(out["record"]["claim_ledger"])
        segment = next(s for s in out["record"]["realized_segments"] if s["claim_id"] == relational["claim_id"])
        self.assertEqual(segment["status"], "withheld")
        self.assertTrue(any("target_manifestation" in r for r in segment["claim_screen_reasons"]))
        self.assertIn(pst.C12_WRONG_TARGET_MANIFESTATION_TEXT, segment["final_text"])
        self.assertTrue(out["audit"]["ok"], out["audit"])

    def test_the_gap_report_is_the_full_33_entries(self):
        out, _client, _stages = self._run(_faithful)
        self.assertEqual(len(out["record"]["gap_report"]), 33)

    def test_the_c8_and_c11_structures_are_preserved(self):
        out, _client, _stages = self._run(_faithful)
        c8 = [c for c in out["record"]["claim_ledger"] if "c8" in c["child_ids"]]
        c11 = [c for c in out["record"]["claim_ledger"] if "c11" in c["child_ids"]]
        self.assertTrue(any(c["claim_kind"] == "category_list" for c in c8))
        self.assertTrue(any(c["claim_kind"] == "category_list" for c in c11))


def _rehashed(record: dict) -> dict:
    """Re-seal a tampered record so the hash check passes and only the targeted re-derivation can fail."""
    record["parent_synthesis_hash"] = psr.record_hash(record)
    return record


@unittest.skipUnless(ARTIFACTS_PRESENT, "the frozen Phase-23 run artifacts are not present in this worktree")
class TamperedRealizationAuditTests(unittest.TestCase):
    """The audit must FAIL a record whose realization was edited after the fact, and must name the failing check. Each
    tamper is re-sealed (rehashed) so that exactly one re-derivation is what catches it."""

    @classmethod
    def setUpClass(cls):
        cls.smf, cls.sealed, cls.targets = _load()
        out, _client, _stages = _realize(_faithful, cls.smf, cls.sealed, cls.targets)
        cls.base = out["record"]

    def _audit(self, record: dict) -> dict:
        return psa.audit_parent_synthesis(self.smf, self.sealed, self.targets, record)

    def test_the_untampered_record_passes_the_audit(self):
        self.assertTrue(self._audit(copy.deepcopy(self.base))["ok"])

    def test_an_unsealed_edit_is_caught_by_the_hash_binding(self):
        record = copy.deepcopy(self.base)
        record["realized_segments"][0]["final_text"] += " Edited after the fact."
        audit = self._audit(record)
        self.assertFalse(audit["ok"])
        self.assertFalse(audit["checks"]["parent_synthesis_hash_matches_content"])

    def test_a_grounded_segment_that_is_not_its_one_claim_fails_its_check(self):
        record = copy.deepcopy(self.base)
        segment = next(s for s in record["realized_segments"] if s["status"] == "grounded")
        segment["final_text"] = segment["proposed_text"] + " A second, unauthorized assertion."
        audit = self._audit(_rehashed(record))
        self.assertFalse(audit["ok"])
        self.assertFalse(audit["checks"]["grounded_segment_is_exactly_one_claim"])

    def test_a_citation_that_is_not_the_claims_admissible_id_fails_its_check(self):
        record = copy.deepcopy(self.base)
        segment = next(s for s in record["realized_segments"] if s["cited_proposition_ids"])
        segment["cited_proposition_ids"] = []
        audit = self._audit(_rehashed(record))
        self.assertFalse(audit["ok"])
        self.assertFalse(audit["checks"]["citations_are_exactly_the_claims_admissible_ids"])

    def test_a_dropped_segment_fails_the_coverage_check(self):
        record = copy.deepcopy(self.base)
        record["realized_segments"] = record["realized_segments"][1:]
        audit = self._audit(_rehashed(record))
        self.assertFalse(audit["ok"])
        self.assertFalse(audit["checks"]["realized_segments_cover_each_claim_exactly_once"])


def _unpadded(prompt, schema):
    """The raw restatement with NO sentence frame: a bare value can fall under the editorial floor, as a real model's
    fragment could. This is the input that collapsed the whole answer before Phase 27a."""
    return {
        "items": [
            {"claim_id": cid, "statement": _restated_values(_block(prompt, cid))[:400]}
            for cid in pst.prompt_claim_ids(prompt)
        ]
    }


def _with_one_short(prompt, schema):
    """The padded faithful restatement, except one role value is replaced by the bare word ``explicit``."""
    answer = _faithful(prompt, schema)
    for item in answer["items"]:
        block = _block(prompt, item["claim_id"])
        if block.startswith("\nCategory:") and block.rstrip().endswith("explicit"):
            item["statement"] = "explicit"
    return answer


@unittest.skipUnless(ARTIFACTS_PRESENT, "the frozen Phase-23 run artifacts are not present in this worktree")
class PerItemRealReplayTests(unittest.TestCase):
    """Phase 27a on the real frozen state. Before this phase, one bare item collapsed all 24 claims to a whole-answer
    NO ANSWER (0/24). The counts below are the after-state, measured with the same fakes."""

    @classmethod
    def setUpClass(cls):
        cls.smf, cls.sealed, cls.targets = _load()
        cls.claims = psl.build_claim_ledger(cls.smf, cls.sealed)

    def test_one_too_short_item_among_the_real_twenty_four_costs_exactly_one_fallback(self):
        padded, _c, _s = _realize(_faithful, self.smf, self.sealed, self.targets)
        short, client, _s = _realize(_with_one_short, self.smf, self.sealed, self.targets)
        self.assertEqual(short["record"]["whole_call_status"], "ok")
        self.assertEqual(short["record"]["grounded_count"], padded["record"]["grounded_count"] - 1)
        self.assertEqual(short["record"]["fallback_count"], padded["record"]["fallback_count"] + 1)
        self.assertEqual(Counter(s["status"] for s in short["record"]["realized_segments"])["invalid_item"], 1)
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(short["audit"]["ok"], short["audit"])

    def test_an_unpadded_real_answer_recovers_per_item_instead_of_collapsing(self):
        out, client, _s = _realize(_unpadded, self.smf, self.sealed, self.targets)
        record = out["record"]
        self.assertEqual(record["whole_call_status"], "ok")
        self.assertEqual(Counter(s["status"] for s in record["realized_segments"])["invalid_item"], 3)
        self.assertEqual(record["grounded_count"], 19)
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(out["audit"]["ok"], out["audit"])

    def test_hadza_displays_once_while_both_supports_and_both_values_remain(self):
        c10 = next(c for c in self.claims if c["claim_kind"] == "category_list" and "c10" in c["child_ids"])
        self.assertEqual(psr.literal_statement(c10), "a named culture or population: Hadza.")
        self.assertEqual([v["exact_text"] for v in c10["values"]], ["Hadza", "Hadza"])
        self.assertEqual(len(set(c10["admissible_proposition_ids"])), 2)
        citation = psr.format_citations(c10)
        for proposition_id in c10["admissible_proposition_ids"]:
            self.assertIn(proposition_id, citation)

    def test_rendering_and_realization_never_mutate_the_real_ledger(self):
        before = copy.deepcopy(self.claims)
        out, _c, _s = _realize(_faithful, self.smf, self.sealed, self.targets)
        self.assertEqual(out["record"]["claim_ledger"], before)
        self.assertEqual(self.claims, before)


@unittest.skipUnless(ARTIFACTS_PRESENT, "the frozen Phase-23 run artifacts are not present in this worktree")
class PerItemAuditTamperTests(unittest.TestCase):
    """The Phase-27a audit checks must catch a tampered per-item record. Each tamper is re-sealed so exactly one
    re-derivation is what fails."""

    @classmethod
    def setUpClass(cls):
        cls.smf, cls.sealed, cls.targets = _load()
        out, _c, _s = _realize(_with_one_short, cls.smf, cls.sealed, cls.targets)
        cls.base = out["record"]

    def _audit(self, record: dict) -> dict:
        return psa.audit_parent_synthesis(self.smf, self.sealed, self.targets, record)

    def test_a_rendered_invalid_item_fails_its_check(self):
        record = copy.deepcopy(self.base)
        segment = next(s for s in record["realized_segments"] if s["status"] == "invalid_item")
        segment["proposed_text"] = "A rendered statement that the editorial bounds rejected."
        audit = self._audit(_rehashed(record))
        self.assertFalse(audit["checks"]["invalid_items_are_recorded_not_rendered"])

    def test_an_editorially_invalid_grounded_text_fails_its_check(self):
        record = copy.deepcopy(self.base)
        segment = next(s for s in record["realized_segments"] if s["status"] == "grounded")
        segment["proposed_text"] = segment["final_text"] = "ok"
        audit = self._audit(_rehashed(record))
        self.assertFalse(audit["checks"]["model_text_passes_the_editorial_bounds"])

    def test_diagnostics_that_disagree_with_the_segments_fail_their_check(self):
        record = copy.deepcopy(self.base)
        record["item_diagnostics"]["missing_claim_ids"] = ["role_value::0000"]
        audit = self._audit(_rehashed(record))
        self.assertFalse(audit["checks"]["item_diagnostics_match_segments"])


if __name__ == "__main__":
    unittest.main()
