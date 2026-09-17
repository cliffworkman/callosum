import socket
import subprocess
from pathlib import Path

import pytest

from experiments.ask_070.hashing import read_json
from experiments.ask_070.preflight import assess, trials


def test_guards_block_network_and_processes():
    with pytest.raises(RuntimeError, match="OFFLINE_GUARD"):
        socket.getaddrinfo("example.invalid", 80)
    with socket.socket() as s:
        with pytest.raises(RuntimeError, match="OFFLINE_GUARD"):
            s.connect(("127.0.0.1", 1))
    with pytest.raises(RuntimeError, match="OFFLINE_GUARD"):
        subprocess.Popen(["must-not-launch"])
    with pytest.raises(RuntimeError, match="OFFLINE_GUARD"):
        __import__("torch")


@pytest.mark.parametrize("role,latency", [("worker", 4), ("orchestrator", 16), ("worker", 599)])
def test_product_budget_is_not_stage1_cull(role, latency):
    observation = {
        "loadable": True,
        "context_allocated": True,
        "complete_schema_valid": True,
        "runtime_template_contract": True,
        "cleanup_ok": True,
        "crashed": False,
        "thermal_state": "warm",
        "latency_seconds": latency,
    }
    result = assess(observation, role=role)
    assert result["decision"] == "MECHANICALLY_ADMITTED" and result["exceeds_preferred_product_budget"]
    observation["latency_seconds"] = 601
    assert assess(observation, role=role)["decision"] == "MECHANICALLY_FAILED"


def test_neutral_trials_have_stable_distinct_identity_and_no_scholarly_content():
    tasks = trials()
    assert len({t.hash for t in tasks}) == 3
    assert [t.trial_id for t in tasks] == ["compact-cold", "compact-warm", "padded"]
    forbidden = (
        "q_aib",
        "q_builtenv",
        "q_depr",
        "serotonin",
        "parkinson",
        "research",
        "relationship",
        "obligation",
        "source fidelity",
    )
    assert all(not any(f in t.text.lower() for f in forbidden) for t in tasks)
    spec = read_json(Path(__file__).parents[1] / "specifications/neutral_preflight_v0.json")
    assert spec["not_executed"] and spec["trials_are_distinct_not_retries"]


def test_incomplete_preflight_cannot_pass():
    assert assess({}, role="worker")["decision"] == "INCOMPLETE"


def test_padding_algorithm_only_calls_fake_tokenizer():
    from experiments.ask_070.preflight import build_padded_prompt

    calls = []

    def fake(text):
        calls.append(text)
        return text, tuple(range(len(text)))

    prepared = build_padded_prompt(fake)
    assert 8000 <= len(prepared["token_ids"]) <= 8128
    assert len(calls) <= 17 and prepared["model_inference_calls"] == 0
