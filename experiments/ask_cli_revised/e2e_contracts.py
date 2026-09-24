"""The Wave-1 E2E questions and their frozen, common model-facing contract representation.

Every topology arm must read the *same* valid contract. This module records, for each question, the units, exact frames,
model-facing display lines and a hash over everything a model is shown about the request, and refuses to run on drift.
Evaluation-only unit-role labels are deliberately not part of this record and never enter a model input.

    python -m experiments.ask_cli_revised.e2e_contracts freeze   # (re)write e2e_contracts.frozen.json
    python -m experiments.ask_cli_revised.e2e_contracts verify   # exit 1 on any drift
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from experiments.ask_cli_revised.calibration.run06.dataset06 import BUILT_ENV_QUESTION, DEPRESSION_QUESTION
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.request_contract import (
    build_request_contract,
    obligation_display,
    request_subquestions,
)

# LLD = late-life depression (`q_depr`), confirmed by Cliff.
E2E_QUESTIONS = {"aib": BENCHMARK_QUESTION, "lld": DEPRESSION_QUESTION, "builtenv": BUILT_ENV_QUESTION}
FROZEN_PATH = Path(__file__).with_name("e2e_contracts.frozen.json")
_VERSION = 1


class ContractDriftError(RuntimeError):
    """The model-facing contract no longer matches the frozen record; comparative arms would not share a contract."""


def _sha256(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def frozen_record(question: str) -> dict:
    contract = build_request_contract(question)
    subquestions = request_subquestions(contract)
    obligations = []
    for unit, subquestion in zip(contract["source_units"], subquestions, strict=True):
        obligation = subquestion["obligations"][0]
        row = {
            "field_id": obligation["field_id"],
            "source_unit_id": unit["source_unit_id"],
            "start": unit["start"],
            "end": unit["end"],
            "note": obligation["note"],
            "display": obligation_display(obligation),
        }
        row.update({k: obligation[k] for k in ("source_sentence", "list_position", "list_size") if k in obligation})
        obligations.append(row)
    model_facing = {
        "original_question": question,
        "subquestions": [
            {"subquestion_id": sq["subquestion_id"], "retrieval_text": sq["text"], "display": row["display"]}
            for sq, row in zip(subquestions, obligations, strict=True)
        ],
    }
    return {
        "question_hash": contract["question_hash"],
        "n_units": len(obligations),
        "obligations": obligations,
        "model_facing_sha256": _sha256(model_facing),
    }


def build_frozen() -> dict:
    return {"version": _VERSION, "questions": {key: frozen_record(text) for key, text in E2E_QUESTIONS.items()}}


def verify_frozen(frozen: dict | None = None) -> None:
    """Raise ContractDriftError unless the current representation equals the frozen record for every question."""
    if frozen is None:
        frozen = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    recorded = frozen.get("questions", {})
    if sorted(recorded) != sorted(E2E_QUESTIONS):
        raise ContractDriftError(f"frozen questions {sorted(recorded)} != {sorted(E2E_QUESTIONS)}")
    for key, text in E2E_QUESTIONS.items():
        current = frozen_record(text)
        for field in ("question_hash", "n_units", "obligations", "model_facing_sha256"):
            if current[field] != recorded[key].get(field):
                raise ContractDriftError(f"{key}: frozen {field} no longer matches the current contract")


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "verify"
    if command == "freeze":
        FROZEN_PATH.write_text(json.dumps(build_frozen(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"froze {len(E2E_QUESTIONS)} contracts -> {FROZEN_PATH.name}")
        return 0
    if command == "verify":
        try:
            verify_frozen()
        except ContractDriftError as exc:
            print(f"CONTRACT DRIFT: {exc}")
            return 1
        print("contracts frozen and intact")
        return 0
    print("usage: freeze | verify")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
