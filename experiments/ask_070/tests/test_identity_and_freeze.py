from dataclasses import replace

import pytest

from experiments.ask_070.contracts import ContractError
from experiments.ask_070.hashing import canonical, digest
from experiments.ask_070.runner import ordered_cells
from experiments.ask_070.tests.test_runner_and_receipts import cell


def test_stable_identity_sensitive_to_frozen_dimensions():
    c = cell()
    assert c.cell_id == cell().cell_id and len(c.cell_id) == 64
    assert canonical({"a": 1, "b": 2}) == canonical({"b": 2, "a": 1})
    for altered in [
        replace(c, model=replace(c.model, weight_quantization="Q5_K_M")),
        replace(c, model=replace(c.model, kv_k="q8_0")),
        replace(c, model=replace(c.model, artifact_revision="changed")),
        replace(c, task=replace(c.task, text=c.task.text + " ")),
        replace(c, task=replace(c.task, trial_id="compact-warm")),
        replace(c, hardware=replace(c.hardware, configuration_hash="changed")),
    ]:
        assert altered.cell_id != c.cell_id
    with pytest.raises(ContractError):
        _ = replace(c, context=4096).cell_id


def test_order_and_duplicate_detection():
    a = cell()
    b = replace(a, task=replace(a.task, task_id="s2"))
    args = dict(model_order=["fake"], package_order=["R_CONTROL"], task_order=["s1", "s2"])
    assert ordered_cells([b, a], **args) == [a, b]
    with pytest.raises(ContractError):
        ordered_cells([a, a], **args)


def test_manifest_when_present():
    from experiments.ask_070.freeze import MANIFEST, verify

    if not MANIFEST.exists():
        pytest.skip("manifest generated after initial source tests; required final check reruns this")
    assert verify()["execution_authorized"] is False


def test_no_nonfinite_hashes():
    with pytest.raises(ValueError):
        digest({"x": float("nan")})


def test_internal_freeze_links_cannot_lie():
    from experiments.ask_070.freeze import validate_links

    with pytest.raises(ContractError):
        validate_links({"path": "experiments/ask_070/runner.py", "sha256": "0" * 64})
