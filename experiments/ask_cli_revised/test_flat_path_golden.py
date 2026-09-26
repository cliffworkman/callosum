"""The flat request path is byte-identical to what it was before the hierarchy adapter existed.

The hashes below were captured from the unmodified flat code (Task 0, before any production edit). They cover the
literal request contracts and their subquestions, the model-facing item display, the frozen R/C/P prompt fills, the
deterministic and model coverage rows, the sealed ledger, and the responsiveness-aware rendered answer. Any change
that alters flat output, even by one byte, fails here.
"""

import hashlib
import json
import unittest

from experiments.ask_cli_revised import e2e_contracts, stages
from experiments.ask_cli_revised import execution_policy as policy
from experiments.ask_cli_revised import supervisor_prompts as sp
from experiments.ask_cli_revised.calibration.run06.dataset06 import BUILT_ENV_QUESTION, DEPRESSION_QUESTION
from experiments.ask_cli_revised.ledger_renderer import audit_final, render_answer
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.request_contract import (
    build_request_contract,
    obligation_display,
    request_subquestions,
)

QUESTIONS = {"aib": BENCHMARK_QUESTION, "lld": DEPRESSION_QUESTION, "builtenv": BUILT_ENV_QUESTION}


def _h(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _rec(sid, claim, *, chunk, mapping_state="mapped", obligation_ids=(), paper_id=7):
    return {
        "subquestion_id": sid,
        "proposition_text": claim,
        "quote": f"QUOTE {chunk}",
        "paper_id": paper_id,
        "evidence_anchor_chunk_id": chunk,
        "evidence_span_id": "e1",
        "obligation_ids": list(obligation_ids),
        "mapping_state": mapping_state,
        "verification": {"status": "verified"},
        "provenance": {"origin": "initial"},
    }


class _FakeSupervisor:
    def call(self, stage, prompt, schema, *, input_text=""):
        ids = schema["properties"]["coverage"]["required"]
        coverage = {
            ob: {
                "status": "responsive_support" if ob == ids[0] else "unresolved",
                "supporting_proposition_ids": ["p1"] if ob == ids[0] else [],
            }
            for ob in ids
        }
        return policy.StageResult(answer={"rationale": "r", "coverage": coverage}, record={"outcome": None})


def compute() -> dict:
    out = {}
    for key, text in QUESTIONS.items():
        contract = build_request_contract(text)
        subquestions = request_subquestions(contract)
        out[f"contract:{key}"] = _h(contract)
        out[f"subquestions:{key}"] = _h(subquestions)
        out[f"display:{key}"] = _h([obligation_display(sq["obligations"][0]) for sq in subquestions])
    contract = build_request_contract(BENCHMARK_QUESTION)
    subquestions = request_subquestions(contract)
    obligations = [sq["obligations"][0] for sq in subquestions]
    records = [
        _rec("s1", "Claim one about brain.", chunk=11, obligation_ids=["s1-o1"]),
        _rec("s2", "Claim two about behavior.", chunk=12, obligation_ids=["s2-o1", "s3-o1"]),
        _rec("s3", "Mapped to nothing.", chunk=13),
        _rec("s4", "Responsiveness not assessed.", chunk=14, mapping_state="no_answer"),
    ]
    packets = [
        {
            "paper_id": r["paper_id"],
            "candidate_spans": [{"chunk_id": r["evidence_anchor_chunk_id"], "span_id": "e1", "text": r["quote"]}],
        }
        for r in records
    ]
    out["prompts:aib"] = _h(
        [
            sp.render_responsiveness(BENCHMARK_QUESTION, "Claim one about brain.", obligations),
            sp.render_coverage(
                BENCHMARK_QUESTION,
                obligations,
                stages._proposition_rows(records, subquestions, with_quote=True),
            ),
        ]
    )
    det = stages.det_coverage(subquestions, records, authority={"kind": "det", "role": "R"})
    out["det_coverage:aib"] = _h(det)
    out["seal:det:aib"] = _h(stages.seal(contract, subquestions, records, packets, det))
    model = stages.run_coverage_audit(
        _FakeSupervisor(),
        question=BENCHMARK_QUESTION,
        obligations=obligations,
        subquestions=subquestions,
        records=records,
        authority={"kind": "model", "role": "C", "model": "fake"},
    )
    out["model_coverage:aib"] = _h(model)
    sealed = stages.seal(contract, subquestions, records, packets, model)
    text, manifest = render_answer(sealed)
    out["seal:model:aib"] = _h(sealed)
    out["render:aib"] = _h([text, manifest])
    out["audit_final:aib"] = _h(audit_final(sealed, text))
    text_det, manifest_det = render_answer(stages.seal(contract, subquestions, records, packets, det))
    out["render:det:aib"] = _h([text_det, manifest_det])
    # Parsed JSON, not raw bytes: this file is stored LF and written to disk per the checkout's EOL rules, so its bytes differ between
    # checkouts while its content cannot. verify_frozen() (asserted separately below) is unchanged.
    out["frozen_contracts_parsed"] = _h(json.loads(e2e_contracts.FROZEN_PATH.read_text(encoding="utf-8")))
    return out


GOLDEN = {
    "audit_final:aib": "b4e0d69d71781a128338b4be292c8daabc09204877e1ceb1b28eda81faf3dc88",
    "contract:aib": "2f9042a356787b9892f85176145c82a54edc162d04a8630f6a665bc179103b5c",
    "contract:builtenv": "7d976556e5c1fe33d6b0621c62decf73f1560c4e3ca322394602df09cb6a1f30",
    "contract:lld": "395e1ffb03081891c46b81c1520a1b615736c620a44a9c8016944f5a89ed45e4",
    "det_coverage:aib": "e440431205c4c06434792d46ef11cd03fa324fcf4045fbc1d26e019d98f29ecd",
    "display:aib": "66c7867a44304e42146acd9552df4e7de106239fd4980acb14724f7f99780db7",
    "display:builtenv": "a2025c74443d23e240d1bf9d38433fb893cd70eec230c807e88b7c01138d7876",
    "display:lld": "193cedd2166050f5f2ec79e567be3848672aaef5e9391416ce5d9a79a77ece0a",
    "frozen_contracts_parsed": "7730fd70538a066e22831ffab52ce95b5ff652e18b031ac9b79debf80e89eeea",
    "model_coverage:aib": "6e83fb86b2977123d701c70dc664a374c582310b402288b5481f58700568284d",
    "prompts:aib": "b6e279b567abd859588376ba8c1c36b6ac2e95fb23dbb69bd09ed9d6b35353d0",
    "render:aib": "9bb2fabf6f4091134a9cfa6696b8140f7f77fbe9da629ee6a4e42d2d13f533ef",
    "render:det:aib": "086b52233833f615d07d3b22626e4f6d5f44239ef8fabd1ce1ca6b551b854d64",
    "seal:det:aib": "7e43675047c31f0d50c31abefbc9a9eef7eb3b1e96daaf1e8615886f6a650637",
    "seal:model:aib": "524a98c03c763e999641d6132c4959b10821843fc6a36338b98ff9a25128c475",
    "subquestions:aib": "61e4266ed19bfc97bcb19fd069432c665be1d78bb1640fbdaf4fc20bed8265d7",
    "subquestions:builtenv": "120b68eafbd69b0ce8cbc23a7187324bd1306b4f928b932321f97fd1e8dba2bf",
    "subquestions:lld": "9d979e49c3191dbd999ac41fbd14ebe397acce5ffa4f8fdb922b7f7dbe7075e4",
}


class FlatPathGoldenTests(unittest.TestCase):
    def test_frozen_contracts_still_verify(self):
        e2e_contracts.verify_frozen()

    def test_every_flat_output_is_byte_identical_to_the_pre_adapter_capture(self):
        current = compute()
        self.assertEqual(sorted(current), sorted(GOLDEN))
        for key in sorted(GOLDEN):
            with self.subTest(output=key):
                self.assertEqual(current[key], GOLDEN[key])


if __name__ == "__main__":
    print(json.dumps(compute(), indent=1, sort_keys=True))
