import json
from dataclasses import replace

import pytest

from experiments.ask_070.adapters.runtimes import serialize
from experiments.ask_070.contracts import ContractError, ModelConfiguration, OutputBudgetPolicy


def model(route="ollama_openai"):
    return ModelConfiguration(
        "fake",
        "synthetic",
        "repo",
        "rev",
        "fake.gguf",
        "a" * 64,
        "SYNTHETIC",
        route,
        "fake-runtime",
        thinking="DISABLED",
    )


PREP = {"prompt": "neutral tokens", "schema": {"type": "object"}, "schema_name": "neutral"}


@pytest.mark.parametrize(
    "route,field", [("ollama_openai", "response_format"), ("llama_cpp", "json_schema"), ("ollama_native", "format")]
)
def test_distinct_deterministic_routes(route, field):
    a = serialize(model(route), PREP, context=12288, output_cap=4096)
    assert a == serialize(model(route), PREP, context=12288, output_cap=4096)
    body = json.loads(a.body_json)
    assert field in body
    assert len(set(body) & {"response_format", "json_schema", "format"}) == 1
    assert json.loads(a.prerequisites_json)["rendered_prompt_max_tokens"] == 8192


def test_thinking_and_weight_kv_are_separate():
    a = serialize(replace(model(), kv_k="q8_0", kv_v="q8_0"), PREP, context=12288, output_cap=4096)
    assert json.loads(a.body_json)["reasoning_effort"] == "none"
    req = json.loads(a.prerequisites_json)
    assert req["weight_quantization"] == "Q4_K_M" and req["kv_configuration"]["k"] == "q8_0"


def test_budget_unresolved_and_both_future_modes():
    with pytest.raises(ContractError):
        OutputBudgetPolicy().resolve("R_CONTROL")
    assert OutputBudgetPolicy("COMMON", 1024).resolve("R_CONTROL") == 1024
    assert OutputBudgetPolicy("PACKAGE_SPECIFIC", None, (("R_CONTROL", 2048),)).resolve("R_CONTROL") == 2048
    with pytest.raises(ContractError):
        serialize(model(), PREP, context=12288, output_cap=12288)
    with pytest.raises(ContractError):
        serialize(replace(model(), runtime="unknown"), PREP, context=12288, output_cap=4096)
