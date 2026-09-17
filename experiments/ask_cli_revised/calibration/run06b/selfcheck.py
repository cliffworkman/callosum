"""Deterministic Run 0.6b self-checks (no Qwen, no DB, no network).

Asserts the spec's structural invariants that can be proven without inference. Runtime-only invariants
(NO/weak rows retained in artifacts, GPU/digest, smoke enforcement) are enforced by the orchestrator and
noted here rather than asserted.

    python -m experiments.ask_cli_revised.calibration.run06b.selfcheck
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.pdf_processing.extraction import canonical_text_contains  # noqa: E402
from app.backend.summarization.verification import VerificationConfig  # noqa: E402
from experiments.ask_cli_revised.calibration.run06b import dataset as ds  # noqa: E402
from experiments.ask_cli_revised.calibration.run06b import qwen_primitives as qp  # noqa: E402
from experiments.ask_cli_revised.calibration.run06b import review as rv  # noqa: E402
from experiments.ask_cli_revised.calibration.run06b.inputs import BASELINE_RUN_DIR  # noqa: E402

_RUN06B_DIR = Path(__file__).resolve().parent
_FORBIDDEN_IMPORT_FRAGMENTS = (
    "retrieval",
    "discovery",
    "context_growth",
    "decompos",
    "coverage",
    "recovery",
    "gemini",
    "run06a",
    "run07",
)


def _check(cond: bool, label: str) -> str:
    if not cond:
        raise AssertionError(f"SELF-CHECK FAILED: {label}")
    return f"  ok  {label}"


def _import_lines(src: str) -> list[str]:
    return [ln.strip() for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))]


def main() -> int:  # noqa: C901 - a flat sequence of independent assertions
    out: list[str] = []
    root = BASELINE_RUN_DIR

    # ---- dataset determinism + provenance ----
    payload_a = ds.build_dataset(root)
    payload_b = ds.build_dataset(root)
    units = payload_a["units"]
    out.append(
        _check(payload_a["dataset_hash"] == payload_b["dataset_hash"], "dataset build is deterministic (stable hash)")
    )
    out.append(_check(payload_a["dataset_hash"] == ds.dataset_hash(units), "dataset_hash matches its own units"))

    packets = ds._load_jsonl(root, "08_evidence_packets.jsonl")
    frozen_chunk_text = {int(c["chunk_id"]): c["text"] for pk in packets for c in pk["chunks"]}
    frozen_chunk_ids = set(frozen_chunk_text)

    for u in units:
        cid = u["containing_chunk_id"]
        if cid is None:
            _check(
                u["span_note"] == "FROZEN_EXTRACTION_MISMATCH", f"unmatched span flagged: {u['dataset_instance_id']}"
            )
            continue
        _check(cid in frozen_chunk_ids, f"span {u['dataset_instance_id']} chunk {cid} is a frozen packet chunk")
        if u["stratum"] == "select_evidence_span":
            _check(
                canonical_text_contains(needle=u["exact_span_text"], haystack=frozen_chunk_text[cid]),
                f"span {u['dataset_instance_id']} is a canonical substring of its frozen chunk",
            )
        else:
            _check(
                u["exact_span_text"] == frozen_chunk_text[cid],
                f"S2 unit {u['dataset_instance_id']} IS its frozen chunk text",
            )
        if u["context_available"]:
            _check(
                u["context_text"] == frozen_chunk_text[cid],
                f"context of {u['dataset_instance_id']} is the frozen chunk text",
            )
    out.append("  ok  every span/context is frozen prior-run material")

    # ---- strata kept distinct, unknown not excluded ----
    s1 = [u for u in units if u["stratum"] == "select_evidence_span"]
    s2 = [u for u in units if u["stratum"] == "pre_selection_chunk"]
    out.append(_check(len(s1) > 0 and len(s2) > 0, "both strata are populated and labeled distinctly"))
    unknown = [u for u in units if u["evidence_role"] in (None, "unknown")]
    out.append(_check(len(unknown) > 0, f"UNKNOWN/None evidence-role rows are included ({len(unknown)})"))

    # ---- old selection is not reduced to selected/not; the four fields exist on S1 ----
    for u in s1:
        for field in ("old_model_selected", "old_effective_selected", "old_fallback_used", "old_call_failure_reason"):
            if field not in u:
                raise AssertionError(f"SELF-CHECK FAILED: S1 unit {u['dataset_instance_id']} missing {field}")
    out.append("  ok  old selection recorded as model_selected / effective_selected / fallback_used / failure_reason")

    # ---- primitives never receive the user question / obligations ----
    question = json.loads((root / "00_question.json").read_text(encoding="utf-8"))
    q_text = question.get("question") or question.get("text") or ""
    decomposition = ds._load_json(root, "01_decomposition.json")
    subq_texts = [sq["text"] for sq in decomposition.get("subquestions", [])]
    obligation_notes = [ob["note"] for sq in decomposition.get("subquestions", []) for ob in sq.get("obligations", [])]
    sample = next(u for u in s1 if u["context_available"])
    for builder in (qp.build_p1_prompt, qp.build_p2_prompt):
        prompt = builder(
            span_text=sample["exact_span_text"], context_text=sample["context_text"], context_available=True
        )
        _check(q_text not in prompt, f"{builder.__name__} omits the user question")
        for t in subq_texts:
            _check(t not in prompt, f"{builder.__name__} omits subquestion text")
        for t in obligation_notes:
            _check(t not in prompt, f"{builder.__name__} omits obligation text")
        _check(
            "Requested information" not in prompt and "Question:" not in prompt,
            f"{builder.__name__} has no question section",
        )
        _check("responsive" not in prompt.lower(), f"{builder.__name__} does not ask about responsiveness")
    out.append("  ok  P1/P2 prompts contain no user-question / subquestion / obligation / responsiveness text")

    # ---- schema shape: P1 exactly YES/NO; neither primitive emits ids or an evidence quote ----
    out.append(
        _check(
            qp.P1_SCHEMA["properties"]["answer"]["enum"] == ["YES", "NO"], "P1 schema answer enum is exactly [YES, NO]"
        )
    )
    out.append(_check(set(qp.P1_SCHEMA["properties"]) == {"answer"}, "P1 schema emits only 'answer' (no ids)"))
    out.append(
        _check(
            set(qp.P2_SCHEMA_NULLABLE["properties"]) == {"claim"}, "P2 nullable schema emits only 'claim' (no id/quote)"
        )
    )
    out.append(_check("quote" not in qp.P2_SCHEMA_GATED["properties"], "P2 gated schema emits no evidence quote"))

    # ---- verifier thresholds unchanged ----
    cfg = VerificationConfig()
    out.append(
        _check(
            (cfg.retrieval_threshold, cfg.quote_threshold, cfg.support_threshold, cfg.contradiction_threshold)
            == (0.7, 1.0, 0.55, 0.55),
            "verifier thresholds are the frozen 0.7 / 1.0 / 0.55 / 0.55",
        )
    )

    # ---- DEV annotations are pre-registerable + deterministic; RTPJ e1 is the leakage probe ----
    frozen_ann = rv.freeze_dev_annotations(units)
    rv.assert_dev_annotations_unchanged(frozen_ann, units)
    rtpj_e1 = next((u for u in s1 if u["containing_chunk_id"] == 26831 and u["local_span_id"] == "e1"), None)
    out.append(_check(rtpj_e1 is not None, "RTPJ e1 heading specimen present"))
    out.append(
        _check(
            rv.dev_proposition_annotation(rtpj_e1)["label"] == rv.AMBIGUOUS,
            "RTPJ e1 pre-registered as AMBIGUOUS (leakage probe)",
        )
    )
    out.append(
        _check(
            "distinct patterns" in rtpj_e1["context_text"],
            "RTPJ e1 context contains substantive sibling science (leakage setup)",
        )
    )

    # ---- no forbidden imports anywhere in the run06b package ----
    for py in sorted(_RUN06B_DIR.glob("*.py")):
        for line in _import_lines(py.read_text(encoding="utf-8")):
            for frag in _FORBIDDEN_IMPORT_FRAGMENTS:
                if frag in line:
                    raise AssertionError(f"SELF-CHECK FAILED: forbidden import '{frag}' in {py.name}: {line}")
    out.append("  ok  no retrieval/decomposition/context-growth/coverage/recovery/gemini/run06a/run07 imports")

    print("\n".join(out))
    print(f"\nRun 0.6b self-checks PASSED ({len(units)} units: {len(s1)} S1 spans + {len(s2)} S2 chunks)")
    print("Runtime-only invariants (NO+weak rows retained in artifacts; GPU/digest; smoke enforcement; ")
    print("verifier code untouched; no prior-run artifact written) are enforced by run_run06b at run time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
