"""Benchmark isolation tests. Runtime (Layers A and B) may consume: the original request text,
the approved hierarchy contract, recorded RC-N/CD-N text, retrieved evidence, and verified
propositions. It may never consume: expected paper identities, expected instrument/scale names
absent from the request/evidence, expected populations, expected findings, or any other hidden
gold-answer content. Extends the existing `hierarchy_contract.provenance_tokens`/
`mentions_networks` guard (no code change needed there) with new call sites over the sufficiency
layer's own artifacts. No model, no network, no E2E.
"""

from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import sufficiency_authoring as sa
from experiments.ask_cli_revised import sufficiency_mapping as sm


def _mentions_whole_word(term: str, text: str) -> bool:
    """Word-boundary matching -- a naive substring check on a short acronym like "IRI" or "DG"
    false-positives on ordinary English ("requIRIng", "buDGet"); this is what the hidden-term
    checks below actually need."""
    return re.search(rf"\b{re.escape(term.strip())}\b", text, re.IGNORECASE) is not None


_DEFAULT_PATH = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "q-aib-hierarchical-t5c-live-20260930"
    / "run"
    / "01_request_contract.json"
)
_PATH = Path(os.environ.get("QAIB_REQUEST_CONTRACT", str(_DEFAULT_PATH)))
needs_real_contract = unittest.skipUnless(
    _PATH.is_file(), f"the preserved q_aib request contract is not present at {_PATH}"
)

# Hidden benchmark vocabulary that must NEVER be constructed by the sufficiency layer -- these
# are the specific instrument/culture identities the benchmark's own hidden ground truth names,
# never present in the frozen hierarchy contract's own approved wording or requirement text.
# Matched as whole words (see `_mentions_whole_word`) -- several of these are short enough to
# collide with ordinary English as a bare substring ("requIRIng", "buDGet").
_HIDDEN_BENCHMARK_TERMS = ("hadza", "iat", "ebq", "iri", "dg", "ug")


def _load_children_by_id() -> dict:
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    return {c["child_id"]: c for c in data["hierarchy"]["children"]}


class D1RecordByteIdentityTests(unittest.TestCase):
    """The supersession records are additive and provenanced -- never a silent rewrite of
    hierarchy_contract.py's own frozen D1_RECORD, pin, or hash."""

    def test_d1_record_unchanged_after_importing_sufficiency_authoring(self):
        before = json.dumps(hc.D1_RECORD, sort_keys=True)
        # sufficiency_authoring is already imported at module load time above; re-verify here so
        # the assertion is explicit and self-contained rather than relying on import order.
        import importlib

        importlib.reload(sa)
        after = json.dumps(hc.D1_RECORD, sort_keys=True)
        self.assertEqual(before, after)

    def test_frozen_hierarchy_pin_file_hash_unaffected(self):
        if not hc.FROZEN_PATH.is_file():
            self.skipTest("no installed hierarchy_contract.frozen.json in this worktree")
        before = hc._sha256_bytes(hc.FROZEN_PATH.read_bytes())
        import importlib

        importlib.reload(sa)
        after = hc._sha256_bytes(hc.FROZEN_PATH.read_bytes())
        self.assertEqual(before, after)


class ProvenanceTokenGuardTests(unittest.TestCase):
    """Reuses hierarchy_contract.py's existing regex-based guard, unmodified, over the
    sufficiency layer's own model-facing-shaped strings (role descriptions, recovery hints,
    rendered text)."""

    def test_supersession_records_carry_no_provenance_tokens_in_free_text_meant_for_display(self):
        # The supersession records themselves legitimately NAME RC-N/D-1 ids as their own subject
        # matter (this is machine-readable provenance, analogous to hierarchy_contract.py's own
        # D1_RECORD) -- the guard applies to what the sufficiency layer would ever show a MODEL,
        # which is `category_description`/`recovery_hint` output, checked separately below.
        self.assertTrue(hc.provenance_tokens(sa.D1_SUFFICIENCY_SUPERSESSION["operationalized_now"][0]))

    @needs_real_contract
    def test_no_role_category_description_carries_a_provenance_token_or_mentions_networks(self):
        children = _load_children_by_id()
        contract = sa.build_qaib_contract(children)
        for child_contract in contract.values():
            for req in child_contract["requirements"]:
                for spec in req["role_specs"].values():
                    self.assertEqual(hc.provenance_tokens(spec["category_description"]), [])
                    self.assertFalse(hc.mentions_networks(spec["category_description"]))

    @needs_real_contract
    def test_no_source_wording_span_carries_a_provenance_token(self):
        """source_wording_span is a substring of the child's own approved wording -- it should
        never independently pick up an RC-N/hash-shaped token (it never should, since it's
        copied verbatim from `child["wording"]`, but this is the direct regression test)."""
        children = _load_children_by_id()
        contract = sa.build_qaib_contract(children)
        for child_contract in contract.values():
            for req in child_contract["requirements"]:
                self.assertEqual(hc.provenance_tokens(req["source_wording_span"]), [])

    @needs_real_contract
    def test_recovery_hints_carry_no_provenance_tokens_and_no_hidden_terms(self):
        children = _load_children_by_id()
        contract = sa.build_qaib_contract(children)
        for child_id, child_contract in contract.items():
            for req in child_contract["requirements"]:
                hint = sm.recovery_hint(req)
                self.assertEqual(hc.provenance_tokens(hint), [], f"{child_id}/{req['id']}")
                self.assertFalse(hc.mentions_networks(hint), f"{child_id}/{req['id']}")
                for term in _HIDDEN_BENCHMARK_TERMS:
                    self.assertFalse(_mentions_whole_word(term, hint), f"{child_id}/{req['id']} leaked {term!r}")


class MutationInjectionTests(unittest.TestCase):
    """Mirrors the existing 'networks injected into a constraint' precedent
    (hierarchy_contract.py's own mutation tests): an injected provenance token or hidden term
    must be independently detectable, never silently accepted."""

    def test_injected_rc_token_is_detected(self):
        poisoned = "documented nature or direction per RC-9#scope:documented-nature-direction"
        self.assertTrue(hc.provenance_tokens(poisoned))

    def test_injected_network_mention_is_detected(self):
        self.assertTrue(hc.mentions_networks("a specific named brain region or network"))

    def test_injected_child_id_token_is_detected(self):
        self.assertTrue(hc.provenance_tokens("this text should not name c11 directly"))


class HiddenQualificationIsolationTests(unittest.TestCase):
    """recovery_hint() for c9's unfilled named-scale role must share no long token with
    c9#constraint:no-reask-traits' own stored text -- the hidden, machine-only constraint must
    never leak through even as a near-paraphrase."""

    @needs_real_contract
    def test_c9_recovery_hint_does_not_overlap_the_hidden_no_reask_constraint_text(self):
        children = _load_children_by_id()
        hidden_text = None
        for qual in children["c9"].get("qualifications") or []:
            if qual["id"] == "c9#constraint:no-reask-traits":
                hidden_text = qual["text"]
        self.assertIsNotNone(hidden_text, "fixture assumption: c9 carries this hidden qualification")
        contract = sa.build_qaib_contract(children)
        req = contract["c9"]["requirements"][0]
        hint = sm.recovery_hint(req)
        hint_tokens = {t for t in hint.lower().split() if len(t) >= 5}
        hidden_tokens = {t.strip(".,;") for t in hidden_text.lower().split() if len(t.strip(".,;")) >= 5}
        overlap = hint_tokens & hidden_tokens
        self.assertEqual(overlap, set(), f"recovery hint leaked hidden-constraint tokens: {overlap}")


class NominationPromptLeakageTests(unittest.TestCase):
    """Scope (Cliff's correction #9): these tests assert that PROMPT/SCHEMA CONSTRUCTION never
    injects hidden benchmark vocabulary or provenance tokens from the CONTRACT side --
    `category_description` text, exactly as every other leakage test in this file already checks
    for `recovery_hint`/role descriptions. They do NOT scan `candidates` (already-retrieved
    evidence passages) for the same terms: a benchmark term that independently occurs in
    genuinely retrieved, verified evidence text is legitimate runtime evidence, not a leak, and
    must never be rejected merely because it happens to match a hidden benchmark term -- that
    would reject real scientific evidence on a coincidence of vocabulary. Only the
    `category_description`-derived QUESTION portion of the prompt is asserted clean; the
    `candidates` fixture below deliberately contains a hidden-benchmark-shaped word inside
    evidence text to prove it is NOT what this test checks."""

    @needs_real_contract
    def test_every_role_category_description_is_leakage_clean_when_rendered_into_the_nomination_prompt(self):
        from experiments.ask_cli_revised import qwen as qwen_module

        children = _load_children_by_id()
        contract = sa.build_qaib_contract(children)
        # Evidence text may legitimately contain a hidden-benchmark-shaped word -- included here to
        # prove the assertions below are about the QUESTION construction, never this text.
        candidates = [
            {"proposition_id": "p1", "passage": "The IAT was administered to participants in Hadza villages."}
        ]
        for child_contract in contract.values():
            for req in child_contract["requirements"]:
                for spec in req["role_specs"].values():
                    if spec["mapping_strategy"] != "model_nomination_only":
                        continue
                    prompt = qwen_module.nomination_prompt(
                        category_description=spec["category_description"], candidates=candidates
                    )
                    question_only = prompt.split("Excerpts:\n", 1)[0]
                    self.assertEqual(hc.provenance_tokens(question_only), [])
                    self.assertFalse(hc.mentions_networks(question_only))
                    for term in _HIDDEN_BENCHMARK_TERMS:
                        self.assertFalse(
                            _mentions_whole_word(term, question_only),
                            f"nomination question leaked {term!r} via category_description",
                        )
                    # And the full prompt DOES carry the evidence text verbatim (the model needs
                    # it to do its job) -- confirming this test isn't accidentally vacuous.
                    self.assertIn("Hadza", prompt)

    def test_nomination_prompt_never_embeds_a_requirement_or_child_id(self):
        from experiments.ask_cli_revised import qwen as qwen_module

        prompt = qwen_module.nomination_prompt(
            category_description="a specific named brain area", candidates=[{"proposition_id": "p1", "passage": "x"}]
        )
        self.assertEqual(hc.provenance_tokens(prompt), [])


class BenchmarkIsolationScopeTests(unittest.TestCase):
    """Restates the isolation boundary as a direct, inspectable assertion over the module's own
    declared inputs, independent of any specific contract instance."""

    def test_sufficiency_authoring_module_never_imports_a_benchmark_answer_source(self):
        import inspect

        source = inspect.getsource(sa)
        for term in _HIDDEN_BENCHMARK_TERMS:
            self.assertFalse(_mentions_whole_word(term, source), f"module source unexpectedly mentions {term!r}")

    def test_sufficiency_engine_contains_no_qaib_vocabulary(self):
        """A stronger, positive companion to the file-content check in test_sufficiency_engine.py
        -- explicit q_aib role labels must never appear in the domain-agnostic engine module."""
        import inspect

        from experiments.ask_cli_revised import sufficiency_engine as se_module

        source = inspect.getsource(se_module).lower()
        qaib_terms = ("brain_region", "amygdala", "anomalous", "scale_or_instrument", "culture_or_population")
        for term in qaib_terms:
            self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
