"""Literal request referent for the experimental CLI; no semantic completeness claim.

Run06 units are navigation spans, not independent meanings. Their full original
context stays attached, including anaphora, operations and specialist spellings.
"""
from __future__ import annotations

import hashlib

from experiments.ask_cli_revised.calibration.run06.segment import segment_source_units_v2


def build_request_contract(question: str) -> dict:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("a nonempty original question is required")
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    units = []
    cursor = 0
    for unit in segment_source_units_v2(question):
        text = unit["text"]
        start = question.index(text, cursor)
        cursor = start + len(text)
        units.append({**unit, "start": start, "end": cursor, "question_hash": digest})
    return {"version": "literal-request-v1", "original_question": question,
            "question_hash": digest, "source_units": units,
            "semantic_completeness": "not_certified"}


def request_subquestions(contract: dict) -> list[dict]:
    """One exact focus plus full context per unit, with no generated requests.

    The query is a retrieval view, not a semantic rewrite. Its effectiveness and
    embedding truncation must be measured separately from literal retention.
    """
    question = contract["original_question"]
    return [
        {"subquestion_id": f"s{i}", "source_unit_id": unit["source_unit_id"],
         "source_text": unit["text"], "source_start": unit["start"], "source_end": unit["end"],
         "question_hash": contract["question_hash"], "original_question": question,
         "text": f"Requested focus (literal):\n{unit['text']}\n\nOriginal request (context):\n{question}",
         "retrieval_view_kind": "literal_focus_with_original_context",
         "obligations": [{"field_id": f"s{i}-o1", "note": unit["text"],
                          "source_unit_id": unit["source_unit_id"], "coverage_basis": "literal_unit"}]}
        for i, unit in enumerate(contract["source_units"], 1)
    ]


def audit_original_request(contract: dict, subquestions: list[dict], records: list[dict]) -> dict:
    """Report evidence associations, never infer completion from model mappings.

    Enumeration uses the original contract, so dropping a derived subquestion
    cannot remove its source unit from this denominator.
    """
    rows = []
    for unit in contract["source_units"]:
        matches = [sq for sq in subquestions if sq.get("source_unit_id") == unit["source_unit_id"]]
        fields = {o["field_id"] for sq in matches for o in sq.get("obligations", [])}
        mapped = [r for r in records if fields.intersection(r.get("obligation_ids", []))]
        verified = [r for r in mapped if r.get("verification", {}).get("status") == "verified"]
        rows.append({**unit, "represented": bool(matches), "mapped_records": len(mapped),
                     "verified_mapped_records": len(verified),
                     "state": "evidence_mapped_completeness_unassessed" if verified else "unresolved",
                     "completeness": "not_certified"})
    return {"question_hash": contract["question_hash"], "original_question": contract["original_question"],
            "source_units": rows, "unresolved_unit_ids": [r["source_unit_id"] for r in rows],
            "completeness": "not_certified",
            "basis": "literal original units; verification and model mapping do not establish completeness"}
