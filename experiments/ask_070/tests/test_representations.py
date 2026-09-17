import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from experiments.ask_070.adapters.r_0_6 import R06Unavailable
from experiments.ask_070.adapters.r_control import RControl
from experiments.ask_070.adapters.r_control import planner as production
from experiments.ask_070.contracts import ContractError, FrozenTask

QUESTION = "Give me an overview of neutral tokens in my library, alpha, beta, gamma, and delta."
TASK = FrozenTask("s1", "request_planning", "SYNTHETIC", QUESTION)
GOOD = json.dumps({"scope": "broad", "facets": [{"label": str(i), "query": f"token {i}"} for i in range(3)]})


@pytest.mark.parametrize(
    "raw",
    [
        GOOD,
        "prefix " + GOOD + " suffix",
        "```json\n" + GOOD + "\n```",
        "bad",
        '{"scope":"narrow","facets":[]}',
        '{"scope":"broad","facets":[]}',
        json.dumps(
            {
                "scope": " BROAD ",
                "facets": [
                    {"label": " x " * 50, "query": " q " * 100},
                    {"label": "b", "query": "different"},
                    {"label": "c", "query": "third"},
                    {"label": "d", "query": "third"},
                ],
            }
        ),
        json.dumps({"scope": "broad", "facets": [{"label": str(i), "query": f"t {i}"} for i in range(9)]}),
        '{"scope":"broad","facets":[null,{},1]}',
    ],
)
def test_effective_plan_exactly_production(raw):
    actual = RControl().interpret(TASK, raw)
    expected = production.plan_query(QUESTION, config=None, complete_fn=lambda *_: SimpleNamespace(text=raw))
    assert actual["effective_representation"] == asdict(expected)
    assert RControl().prepare(TASK)["prompt"] == production._planner_prompt(QUESTION)


def test_strict_failure_does_not_replace_tolerant_plan():
    output = RControl().interpret(TASK, "prefix " + GOOD)
    assert output["effective_representation"]["scope"] == "broad"
    assert not output["format"]["whole_response_json_valid"]
    assert not output["fallback"]


def test_error_and_breadth_gate_parity():
    result = RControl().interpret(TASK, GOOD, error="timeout")
    assert result["fallback"] and result["effective_representation"] == asdict(production.NARROW)
    short = FrozenTask("short", "request_planning", "SYNTHETIC", "token?")
    assert not RControl().prepare(short)["invoke"]
    assert RControl().interpret(short, GOOD)["effective_representation"] == asdict(production.NARROW)


def test_transforms_are_explicit_and_unavailable_never_replaced():
    raw = json.dumps({"scope": "broad", "facets": [{"label": " x ", "query": "q"}] * 4})
    result = RControl().interpret(TASK, raw)
    assert any(d["reason_code"] == "DUPLICATE_QUERY" for d in result["decisions"])
    assert result["fallback"]
    with pytest.raises(ContractError, match="REPRESENTATION_PACKAGE_NOT_AVAILABLE"):
        R06Unavailable().prepare(TASK)
