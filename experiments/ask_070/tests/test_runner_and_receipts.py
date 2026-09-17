from dataclasses import asdict, replace

import pytest

from experiments.ask_070.adapters.r_control import RControl
from experiments.ask_070.contracts import (
    CellSpec,
    ContractError,
    HardwareConfiguration,
    OutputBudgetPolicy,
    RepresentationPackageIdentity,
    RuntimeObservation,
)
from experiments.ask_070.hashing import digest
from experiments.ask_070.receipts import ObservationStore, performance_only
from experiments.ask_070.runner import FakeRuntimeAdapter, run_synthetic_cell
from experiments.ask_070.tests.test_representations import GOOD, TASK
from experiments.ask_070.tests.test_runtime_serialization import model


def cell():
    return CellSpec(
        model(),
        RepresentationPackageIdentity("R_CONTROL", digest(RControl().identity_manifest())),
        HardwareConfiguration("FAKE", "b" * 64),
        TASK,
        output_budget=OutputBudgetPolicy("COMMON", 4096),
    )


def observation(c, **kwargs):
    return replace(
        RuntimeObservation(
            GOOD,
            GOOD.encode(),
            "stop",
            False,
            None,
            digest(asdict(c.model)),
            c.context,
            b'{"measurement_status":"SYNTHETIC"}',
        ),
        **kwargs,
    )


def test_success_failed_missing_and_no_retry(tmp_path):
    c = cell()
    adapter = FakeRuntimeAdapter(observation(c))
    assert ObservationStore(tmp_path).inspect(c.cell_id)["status"] == "MISSING"
    assert run_synthetic_cell(c, adapter, tmp_path)["status"] == "SUCCESS"
    assert ObservationStore(tmp_path).inspect(c.cell_id)["success"]
    with pytest.raises(ContractError, match="NO_RETRY"):
        run_synthetic_cell(c, adapter, tmp_path)
    assert adapter.calls == 1


@pytest.mark.parametrize(
    "change,reason",
    [
        (dict(actual_context=4096), "ALLOCATED_CONTEXT_MISMATCH"),
        (dict(actual_model_configuration_hash="x"), "MODEL_ARTIFACT_RUNTIME_CONFIGURATION_MISMATCH"),
        (dict(truncated=True), "COMPLETION_NOT_ESTABLISHED"),
        (dict(raw_text="bad"), "MECHANICAL_FORMAT_OR_PARSER_FAILURE"),
    ],
)
def test_no_rescue_on_failure(tmp_path, change, reason):
    c = cell()
    adapter = FakeRuntimeAdapter(observation(c, **change))
    result = run_synthetic_cell(c, adapter, tmp_path)
    assert result["status"] == "FAILED" and result["decisions"][0]["reason_code"] == reason and adapter.calls == 1
    assert not ObservationStore(tmp_path).inspect(c.cell_id)["success"]


def test_unavailable_and_network_adapter_rejected(tmp_path):
    c = replace(cell(), package=RepresentationPackageIdentity("R_0_6", "NOT_YET_AVAILABLE"))
    adapter = FakeRuntimeAdapter(RuntimeError())
    result = run_synthetic_cell(c, adapter, tmp_path)
    assert adapter.calls == 0 and result["decisions"][0]["reason_code"] == "REPRESENTATION_PACKAGE_NOT_AVAILABLE"
    with pytest.raises(ContractError, match="LIVE_INFERENCE_NOT_IMPLEMENTED"):
        run_synthetic_cell(cell(), object(), tmp_path)


def test_journal_survives_interrupted_observation_and_tamper(tmp_path):
    c = cell()
    store = ObservationStore(tmp_path)
    store.claim(c.cell_id, c.identity)
    store.event(c.cell_id, "SUBMITTED", {"attempt": 1})
    assert store.inspect(c.cell_id)["status"] == "INDETERMINATE_NO_RETRY"
    with pytest.raises(ContractError):
        store.claim(c.cell_id, c.identity)
    p = tmp_path / c.cell_id / "journal.jsonl"
    p.write_bytes(p.read_bytes().replace(b"SUBMITTED", b"REPLACED"))
    assert store.inspect(c.cell_id)["status"] == "CORRUPT_OR_INCOMPLETE"


def test_missing_artifact_not_success(tmp_path):
    c = cell()
    run_synthetic_cell(c, FakeRuntimeAdapter(observation(c)), tmp_path)
    (tmp_path / c.cell_id / "provider-response.bin").unlink()
    assert not ObservationStore(tmp_path).inspect(c.cell_id)["success"]


def test_privacy_and_missing_metrics():
    assert performance_only({})["peak_vram_bytes"] is None
    for bad in ({"prompt": "private"}, {"thermal_state": "private prompt"}, {"peak_rss_bytes": "C:/private"}):
        with pytest.raises(ContractError):
            performance_only(bad)


def test_failed_observation_cannot_retry_but_predeclared_trial_is_distinct(tmp_path):
    first = replace(cell(), task=replace(cell().task, trial_id="compact-cold"))
    second = replace(first, task=replace(first.task, trial_id="compact-warm"))
    adapter = FakeRuntimeAdapter(TimeoutError("synthetic failure"))
    failed = run_synthetic_cell(first, adapter, tmp_path)
    assert failed["status"] == "FAILED" and failed["attempts"] == 1
    with pytest.raises(ContractError, match="NO_RETRY"):
        run_synthetic_cell(first, adapter, tmp_path)
    adapter.observation = observation(second)
    succeeded = run_synthetic_cell(second, adapter, tmp_path)
    assert succeeded["status"] == "SUCCESS" and succeeded["attempts"] == 1
    assert adapter.calls == 2 and first.cell_id != second.cell_id


def test_strict_failure_receipt_preserves_tolerant_effective_representation(tmp_path):
    from experiments.ask_070.hashing import read_json

    c = cell()
    result = run_synthetic_cell(c, FakeRuntimeAdapter(observation(c, raw_text="prefix " + GOOD)), tmp_path)
    assert result["status"] == "FAILED"
    interpretation = read_json(tmp_path / c.cell_id / "interpretation.json")
    assert interpretation["effective_representation"]["scope"] == "broad"
    assert interpretation["format"]["whole_response_json_valid"] is False


def test_frozen_input_references_retained_outside_model_prompt(tmp_path):
    from experiments.ask_070.hashing import read_json

    c = replace(cell(), task=replace(cell().task, input_refs=(("input-packet", "c" * 64),)))
    run_synthetic_cell(c, FakeRuntimeAdapter(observation(c)), tmp_path)
    task = read_json(tmp_path / c.cell_id / "frozen-task.json")
    assert task["input_refs"] == [["input-packet", "c" * 64]] and task["text"] == c.task.text
    package_input = read_json(tmp_path / c.cell_id / "package-input.json")
    assert "input-packet" not in package_input["prompt"]
    (tmp_path / c.cell_id / "identity.json").write_text("{}")
    assert not ObservationStore(tmp_path).inspect(c.cell_id)["success"]
