"""Literal request referent for the experimental CLI; no semantic completeness claim.

Run06 units are navigation spans, not independent meanings. Their full original
context stays attached, including anaphora, operations and specialist spellings.
"""
from __future__ import annotations

import hashlib

from experiments.ask_cli_revised.calibration.run06.segment import segment_source_units_v2


_SENTENCE_TERMINATORS = ".!?"


def _sentence_spans(question: str) -> list[tuple[int, int]]:
    """Exact [start, end) spans of the request's sentences (each ends at its terminator)."""
    spans: list[tuple[int, int]] = []
    start = None
    for index, char in enumerate(question):
        if start is None and not char.isspace():
            start = index
        if char in _SENTENCE_TERMINATORS and start is not None:
            spans.append((start, index + 1))
            start = None
    if start is not None:
        spans.append((start, len(question.rstrip())))
    return spans


def _with_frames(question: str, units: list[dict]) -> list[dict]:
    """Attach the exact containing sentence to every unit that is only a fragment of it.

    Deterministic and derived from offsets alone, so it is independent of how the segmenter split the request.
    A unit that already starts and ends on sentence boundaries (a full sentence, or a whole '?' clause) is left
    exactly as it was; a fragment keeps its literal text and gains ``source_sentence`` / ``list_position`` /
    ``list_size`` so a bare list item ("amyloid", "coherence") does not lose the frame it was written in.
    """
    spans = _sentence_spans(question)
    enclosing = []
    for unit in units:
        touched = [s for s in spans if s[0] < unit["end"] and s[1] > unit["start"]]
        enclosing.append((min(s[0] for s in touched), max(s[1] for s in touched)) if touched else None)
    siblings: dict[tuple[int, int], list[int]] = {}
    for index, (unit, frame) in enumerate(zip(units, enclosing, strict=True)):
        if frame is not None and frame != (unit["start"], unit["end"]):
            siblings.setdefault(frame, []).append(index)
    out = [dict(unit) for unit in units]
    for frame, members in siblings.items():
        for position, index in enumerate(members, start=1):
            out[index].update(
                source_sentence=question[frame[0]:frame[1]], list_position=position, list_size=len(members)
            )
    return out


_FRAME_KEYS = ("source_sentence", "list_position", "list_size")


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
    units = _with_frames(question, units)
    return {"version": "literal-request-v1", "original_question": question,
            "question_hash": digest, "source_units": units,
            "semantic_completeness": "not_certified"}


def request_subquestions(contract: dict) -> list[dict]:
    """One exact focus plus full context per unit, with no generated requests.

    The query is a retrieval view, not a semantic rewrite. Its effectiveness and
    embedding truncation must be measured separately from literal retention.
    """
    if contract.get("version") == "hierarchical-request-v1":  # hierarchy_contract.HIER_VERSION; the flat path below is unchanged
        from experiments.ask_cli_revised import hierarchy_contract

        return hierarchy_contract.hierarchy_subquestions(contract)
    question = contract["original_question"]
    return [
        {"subquestion_id": f"s{i}", "source_unit_id": unit["source_unit_id"],
         "source_text": unit["text"], "source_start": unit["start"], "source_end": unit["end"],
         "question_hash": contract["question_hash"], "original_question": question,
         "text": f"Requested focus (literal):\n{unit['text']}\n\nOriginal request (context):\n{question}",
         "retrieval_view_kind": "literal_focus_with_original_context",
         "obligations": [{"field_id": f"s{i}-o1", "note": unit["text"],
                          "source_unit_id": unit["source_unit_id"], "coverage_basis": "literal_unit",
                          **{k: unit[k] for k in _FRAME_KEYS if k in unit}}]}
        for i, unit in enumerate(contract["source_units"], 1)
    ]


def obligation_display(obligation: dict) -> str:
    """The obligation as model-facing stages show it: the literal unit, plus its exact frame if it is a fragment.

    ``note`` stays the literal unit text (provenance, rendering, evaluation); this is what a model reads.
    """
    if "model_display" in obligation:  # a hierarchical child carries its exact model-facing item line
        return obligation["model_display"]
    note = obligation.get("note", "")
    sentence = obligation.get("source_sentence")
    return f'{note} [part of the request sentence: "{sentence}"]' if sentence else note


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
