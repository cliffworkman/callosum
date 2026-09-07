"""Deterministic self-check for the ask_cli harness — no DB, no Qwen, no network.

Run: python -m experiments.ask_cli.selfcheck
Exercises the pure logic the pipeline depends on (tolerant JSON, Qwen output validation incl. the closed
obligation taxonomy + verbatim/chunk/obligation filtering, coverage states, synthesis prompt). This is NOT
the experiment; it only proves the deterministic guards behave before a frozen run.
"""

from __future__ import annotations

from experiments.ask_cli import coverage as cov
from experiments.ask_cli import synthesis
from experiments.ask_cli.qwen import (
    _extract_json,
    _validate_gate,
    _validate_propositions,
    _validate_subquestions,
)


def _check(name: str, cond: bool) -> None:
    if not cond:
        raise AssertionError(f"FAILED: {name}")
    print(f"  ok: {name}")


def main() -> int:
    # tolerant JSON: object, array, prose-wrapped, code-fenced
    _check("json object", _extract_json('prefix {"a":1} suffix') == {"a": 1})
    _check("json array", _extract_json('```json\n[{"x":2}]\n```') == [{"x": 2}])
    _check("json none", _extract_json("no json here") is None)

    # subquestion validation drops out-of-taxonomy kinds, keeps valid ones
    subqs, ok = _validate_subquestions(
        [
            {
                "subquestion_id": "s1",
                "text": "brain regions?",
                "obligations": [
                    {"field_id": "s1-o1", "kind": "brain_region", "note": "x"},
                    {"field_id": "s1-o2", "kind": "made_up_kind", "note": "y"},
                ],
            }
        ]
    )
    _check("subq valid", ok and len(subqs) == 1)
    _check(
        "subq drops bad kind",
        len(subqs[0]["obligations"]) == 1 and subqs[0]["obligations"][0]["kind"] == "brain_region",
    )
    _check("subq empty invalid", _validate_subquestions([]) == ([], False))

    # gate validation clamps grow + coerces types
    g, ok = _validate_gate({"proposition_bearing": 1, "grow": "sideways", "dead_end": 0})
    _check("gate valid", ok and g["grow"] == "none" and g["proposition_bearing"] is True and g["dead_end"] is False)

    # proposition validation: verbatim chunk-id + obligation filtering; drops unknown chunk / keeps allowed obligation
    props, ok = _validate_propositions(
        [
            {
                "subject": "amygdala",
                "relation": "associated with",
                "object": "bias",
                "direction": "+",
                "obligation_ids": ["s1-o1", "not-real"],
                "evidence_anchor_chunk_id": 101,
                "quote": "the amygdala was implicated",
            },
            {"subject": "x", "evidence_anchor_chunk_id": 999, "quote": "off-packet"},  # chunk not allowed -> dropped
            {"subject": "y", "evidence_anchor_chunk_id": 101, "quote": ""},  # empty quote -> dropped
        ],
        allowed_chunk_ids={101},
        allowed_obligations={"s1-o1"},
    )
    _check("prop valid", ok and len(props) == 1)
    _check("prop obligation filtered", props[0]["obligation_ids"] == ["s1-o1"])
    _check("prop direction kept", props[0]["direction"] == "+")

    # coverage states
    subquestions = [
        {
            "subquestion_id": "s1",
            "text": "q",
            "obligations": [
                {"field_id": "s1-o1", "kind": "brain_region", "note": ""},
                {"field_id": "s1-o2", "kind": "instrument", "note": ""},
                {"field_id": "s1-o3", "kind": "intervention", "note": ""},
            ],
        }
    ]
    records = [
        {"obligation_ids": ["s1-o1"], "verification": {"status": "verified"}},  # answered
        {"obligation_ids": ["s1-o2"], "verification": {"status": "weak"}},  # mapped, not verified -> unresolved
        # s1-o3: nothing -> unanswered
    ]
    audit = cov.audit_coverage(subquestions, records)
    states = {o["field_id"]: o["state"] for o in audit["obligations"]}
    _check("coverage answered", states["s1-o1"] == "answered")
    _check("coverage unresolved", states["s1-o2"] == "unresolved")
    _check("coverage unanswered", states["s1-o3"] == "unanswered")
    _check("coverage subq partial", audit["subquestions"][0]["state"] == "partial")
    _check("coverage gaps", {g["field_id"] for g in audit["gaps"]} == {"s1-o2", "s1-o3"})

    # synthesis prompt contains only ledger material + honesty instruction, no DB handle
    prompt = synthesis.build_prompt(
        {"subquestions": subquestions, "verified_propositions": records[:1], "coverage": audit}
    )
    _check("synthesis prompt honest", "Do NOT add any fact" in prompt and "gaps" in prompt.lower())

    print("ALL SELF-CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
