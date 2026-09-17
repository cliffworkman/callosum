"""Deterministic self-check for the revised ask_cli harness - no DB, Qwen, or network calls."""

from __future__ import annotations

from experiments.ask_cli_revised import coverage as cov
from experiments.ask_cli_revised import synthesis
from experiments.ask_cli_revised.propositions import _split_exact_spans
from experiments.ask_cli_revised.qwen import (
    _extract_json,
    _validate_claim,
    _validate_gate,
    _validate_id_list,
    _validate_query,
    _validate_requested_items,
    _validate_subquestion_texts,
)


def _check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"FAILED: {name}")
    print(f"  ok: {name}")


def main() -> int:
    _check("json object", _extract_json('prefix {"a":1} suffix') == {"a": 1})
    _check("json array", _extract_json('```json\n[{"x":2}]\n```') == [{"x": 2}])
    _check("json none", _extract_json("no json here") is None)

    texts, ok = _validate_subquestion_texts({"question": "Which brain regions are implicated?"})
    _check("single object tolerated", ok and texts == ["Which brain regions are implicated?"])
    texts, ok = _validate_subquestion_texts([{"question": "q1"}, {"text": "q2"}])
    _check("subquestion list", ok and texts == ["q1", "q2"])

    requested, ok = _validate_requested_items(
        [{"requested": "specific brain regions"}, {"requested": "relation to behavior"}]
    )
    _check("natural obligations", ok and len(requested) == 2)

    gate, ok = _validate_gate({"action": "after"})
    _check("gate strict valid", ok and gate == {"action": "after"})
    _check("gate rejects old loose schema", _validate_gate({"proposition_bearing": 1})[1] is False)

    selected, ok = _validate_id_list(
        {"span_ids": ["e2", "made-up", "e1", "e2"]},
        key="span_ids",
        allowed={"e1", "e2"},
        limit=4,
    )
    _check("id filtering", ok and selected == ["e2", "e1"])

    claim, ok = _validate_claim({"claim": "Amygdala response correlated with less prosociality."})
    _check("claim valid", ok and claim is not None)
    claim, ok = _validate_claim({"claim": None})
    _check("claim null valid", ok and claim is None)

    query, ok = _validate_query({"query": "Hadza anomalous is bad bias"})
    _check("recovery query", ok and query == "Hadza anomalous is bad bias")

    spans = _split_exact_spans("First result was null. Second result was positive.\n\nThird conclusion.")
    _check("exact span split", spans == ["First result was null.", "Second result was positive.", "Third conclusion."])

    subquestions = [
        {
            "subquestion_id": "s1",
            "text": "q",
            "obligations": [
                {"field_id": "s1-o1", "note": "specific brain region"},
                {"field_id": "s1-o2", "note": "measurement instrument"},
                {"field_id": "s1-o3", "note": "intervention evidence"},
            ],
        }
    ]
    records = [
        {"obligation_ids": ["s1-o1"], "verification": {"status": "verified"}},
        {"obligation_ids": ["s1-o2"], "verification": {"status": "weak"}},
    ]
    audit = cov.audit_coverage(subquestions, records)
    states = {item["field_id"]: item["state"] for item in audit["obligations"]}
    _check("coverage answered", states["s1-o1"] == "answered")
    _check("coverage unresolved", states["s1-o2"] == "unresolved")
    _check("coverage unanswered", states["s1-o3"] == "unanswered")
    _check("coverage partial", audit["subquestions"][0]["state"] == "partial")

    ledger_record = {
        "proposition_id": "p1",
        "proposition_text": "The amygdala responded to anomalous faces.",
        "verification": {"status": "verified"},
    }
    prompt = synthesis.build_prompt(
        {
            "subquestions": subquestions,
            "verified_propositions": [ledger_record],
            "coverage": audit,
        }
    )
    _check("synthesis ancestry", "Every factual sentence" in prompt and "[p3]" in prompt)

    print("ALL SELF-CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
