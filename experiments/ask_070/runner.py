"""One-observation runner, exercised only by explicitly marked synthetic transports."""

import json
from dataclasses import asdict

from .adapters.representations import get_package
from .adapters.runtimes import serialize
from .contracts import ContractError, RuntimeObservation
from .hashing import canonical, digest
from .receipts import ObservationStore, performance_only


class FakeRuntimeAdapter:
    """No network behavior; output supplied by a synthetic fixture, not a model."""

    def __init__(self, observation: RuntimeObservation | Exception):
        self.observation = observation
        self.calls = 0

    def observe(self, request):
        self.calls += 1
        if isinstance(self.observation, Exception):
            raise self.observation
        return self.observation


def ordered_cells(cells, *, model_order, package_order, task_order):
    result = sorted(
        cells,
        key=lambda c: (
            model_order.index(c.model.candidate_id),
            digest(asdict(c.model)),
            package_order.index(c.package.package_id),
            task_order.index(c.task.task_id),
            c.task.trial_id,
            c.hardware.hardware_id,
            c.cell_id,
        ),
    )
    if len({c.cell_id for c in result}) != len(result):
        raise ContractError("DUPLICATE_PLANNED_CELL")
    return result


def run_synthetic_cell(cell, adapter, root):
    if type(adapter) is not FakeRuntimeAdapter or cell.task.split != "SYNTHETIC":
        raise ContractError("LIVE_INFERENCE_NOT_IMPLEMENTED")
    store = ObservationStore(root)
    calls_before = adapter.calls
    cell_id = cell.cell_id
    store.claim(cell_id, cell.identity)
    refs = []
    decisions = []
    status = "FAILED"
    interpretation = None
    performance = performance_only({"measurement_status": "NOT_RUN"})
    try:
        refs.append(store.artifact(cell_id, "frozen-task.json", canonical(asdict(cell.task))))
        package = get_package(cell.package.package_id)
        prepared = package.prepare(cell.task)  # R_0_6 fails explicitly before any dispatch
        if digest(package.identity_manifest()) != cell.package.package_hash:
            raise ContractError("PACKAGE_IDENTITY_MISMATCH")
        refs.append(store.artifact(cell_id, "package-input.json", canonical(prepared)))
        if not prepared["invoke"]:
            interpretation = package.interpret(cell.task, "")
            status = "SUCCESS"
        else:
            request = serialize(
                cell.model,
                prepared,
                context=cell.context,
                output_cap=cell.output_budget.resolve(cell.package.package_id),
            )
            refs.append(store.artifact(cell_id, "wire-request.json", request.body_json))
            refs.append(store.artifact(cell_id, "runtime-prerequisites.json", request.prerequisites_json))
            store.event(cell_id, "SUBMITTED", {"request_sha256": refs[-2]["sha256"], "attempt": 1})
            observed = adapter.observe(request)
            refs.append(store.artifact(cell_id, "provider-response.bin", observed.raw_provider_bytes))
            refs.append(store.artifact(cell_id, "provider-text.txt", observed.raw_text.encode("utf-8")))
            refs.append(
                store.artifact(
                    cell_id,
                    "provider-metadata.json",
                    canonical(
                        {
                            "finish_reason": observed.finish_reason,
                            "truncated": observed.truncated,
                            "error_code": observed.error_code,
                            "actual_context": observed.actual_context,
                            "actual_model_configuration_hash": observed.actual_model_configuration_hash,
                        }
                    ),
                )
            )
            interpretation = package.interpret(cell.task, observed.raw_text, error=observed.error_code)
            performance = performance_only(json.loads(observed.performance_json))
            if observed.actual_model_configuration_hash != digest(asdict(cell.model)):
                raise ContractError("MODEL_ARTIFACT_RUNTIME_CONFIGURATION_MISMATCH")
            if observed.actual_context != cell.context:
                raise ContractError("ALLOCATED_CONTEXT_MISMATCH")
            if observed.error_code:
                raise ContractError("RUNTIME_ERROR")
            if observed.truncated is not False or observed.finish_reason not in ("stop", "eos"):
                raise ContractError("COMPLETION_NOT_ESTABLISHED")
            if interpretation["fallback"] or not interpretation["format"]["schema_valid"]:
                raise ContractError("MECHANICAL_FORMAT_OR_PARSER_FAILURE")
            status = "SUCCESS"
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ContractError) else "RUNTIME_EXCEPTION_" + type(exc).__name__
        decisions.append({"decision": "FAIL", "reason_code": reason, "inputs": {"cell_id": cell_id}, "kept": False})
        store.event(cell_id, "FAILED", decisions[-1])
    if interpretation is not None:
        refs.append(store.artifact(cell_id, "interpretation.json", canonical(interpretation)))
        decisions.extend(interpretation["decisions"])
    refs.append(store.artifact(cell_id, "performance.json", canonical(performance)))
    receipt = {
        "schema_version": 1,
        "cell_id": cell_id,
        "identity": cell.identity,
        "status": status,
        "synthetic": True,
        "artifacts": refs,
        "decisions": decisions,
        "attempts": adapter.calls - calls_before,
        "semantic_scoring": "NOT_PERFORMED",
        "fallback": interpretation["fallback"] if interpretation else None,
    }
    store.finish(cell_id, receipt)
    return receipt
