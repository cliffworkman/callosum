"""Fixed loader, issuance gating and snapshot controls."""

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import producer_authorization as auth
from experiments.ask_cli_revised import producer_authorization_store as store
from experiments.ask_cli_revised import producer_replay as issuer
from experiments.ask_cli_revised import test_producer_authorization as shared
from experiments.ask_cli_revised._producer_schema import canonical, plain, safe_path
from experiments.ask_cli_revised.test_producer_authorization import EXPECTED, verify
from experiments.ask_cli_revised.test_producer_tamper import trusted_test_registry

real = shared.real


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/escape", "a/../b", "a\\b", "a//b"])
def test_path_traversal_rejected(path):
    with pytest.raises(auth.ProducerAuthorizationError, match="path"):
        safe_path(path)


def test_fixed_loader_has_no_caller_parameters_or_cwd_env_override(tmp_path, monkeypatch):
    assert not inspect.signature(store.load_trusted_producer_registry).parameters
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PRODUCER_REGISTRY", str(tmp_path / "forged.json"))
    (tmp_path / "producer_authorization.registry.json").write_text("{}")
    assert store.load_trusted_producer_registry().registry_ref == EXPECTED["registry"]


def test_missing_material_fails_no_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_STORE", tmp_path)
    with pytest.raises(ValueError, match="missing"):
        store.load_trusted_producer_registry()


def test_registry_duplicate_field_fails(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    path.write_bytes(b'{"schema":"x","schema":"y"}')
    monkeypatch.setattr(store, "_REGISTRY", path)
    with pytest.raises(auth.ProducerAuthorizationError, match="duplicate"):
        store.load_trusted_producer_registry()


def test_registry_path_reference_cannot_escape(tmp_path, monkeypatch):
    body = plain(store.load_trusted_producer_registry().body)
    body["profiles"]["../x:sha256:" + "0" * 64] = body["profiles"].pop(EXPECTED["profile"])
    path = tmp_path / "registry.json"
    path.write_bytes(canonical(body))
    monkeypatch.setattr(store, "_REGISTRY", path)
    with pytest.raises(auth.ProducerAuthorizationError):
        store.load_trusted_producer_registry()


def test_closed_issuer_interface():
    params = inspect.signature(issuer.reproduce_accepted_v8).parameters
    assert set(params) == {"output_dir"}
    with pytest.raises(TypeError):
        issuer.reproduce_accepted_v8(smap={})
    with pytest.raises(TypeError):
        issuer.reproduce_accepted_v8(nomination_provider=lambda: [])


def test_runtime_mismatch_fails_before_production(monkeypatch):
    monkeypatch.setattr(issuer.platform, "python_version", lambda: "3.12.8")
    with patch.object(issuer, "_produce", side_effect=AssertionError("must not produce")):
        with pytest.raises(auth.ProducerAuthorizationError, match="runtime"):
            issuer.reproduce_accepted_v8()


def test_source_drift_fails_before_production(monkeypatch):
    original = Path.read_bytes
    target = "sufficiency_mapping.py"

    def changed(path):
        data = original(path)
        return data + b"\n" if path.name == target else data

    monkeypatch.setattr(Path, "read_bytes", changed)
    with patch.object(issuer, "_produce", side_effect=AssertionError("must not produce")):
        with pytest.raises(auth.ProducerAuthorizationError, match="source drift"):
            issuer.reproduce_accepted_v8()


@pytest.mark.parametrize("state", ["retired", "revoked"])
def test_issuer_lifecycle_fails_before_code_reads(state, monkeypatch):
    registry = trusted_test_registry(lifecycle=state)
    monkeypatch.setattr(issuer, "load_trusted_producer_registry", lambda: registry)
    with patch.object(issuer, "_verify_installed_producer", side_effect=AssertionError("no source read")):
        with pytest.raises(auth.ProducerAuthorizationError):
            issuer.reproduce_accepted_v8()


def test_consumption_does_not_require_installed_old_producer(real):
    registry = store.load_trusted_producer_registry()
    with patch.object(issuer, "_verify_installed_producer", side_effect=AssertionError("issuance-only check")):
        assert verify(real, trusted_registry=registry).identities["receipt_ref"] == EXPECTED["receipt"]


def test_input_snapshot_is_detached_from_later_path_changes(real, tmp_path, monkeypatch):
    alias = "preserved-run/11_verified_ledger.json"
    path = tmp_path / "sealed.json"
    path.write_bytes(real.input_bundle.files[alias])
    from experiments.ask_cli_revised._producer_schema import byte_hash

    monkeypatch.setattr(issuer, "_ROOT", tmp_path)
    monkeypatch.setattr(issuer, "_input_path", lambda name: path)
    snapshot = issuer._snapshot_inputs({"files": {alias: byte_hash(path.read_bytes())}})
    path.write_bytes(b"changed after snapshot")
    assert snapshot[alias] == real.input_bundle.files[alias]


def test_authoring_loader_reads_private_snapshot_only(real, monkeypatch):
    original = Path.read_bytes

    def forbid_original(path):
        assert path.name not in (
            "sufficiency_contract.aib_hier_v9.frozen.json",
            "sufficiency_contract.aib_hier_v9.review.json",
        )
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", forbid_original)
    contracts = issuer._load_authoring_snapshot(real.input_bundle.files)
    assert issuer.requirements(contracts) == real.authored_contract["requirements"]


def test_nomination_source_is_fixed_and_fresh_attempt_fails():
    with pytest.raises(auth.ProducerAuthorizationError, match="fresh"):
        issuer._no_fresh_nomination()


def test_isolated_mapper_globals_and_output_protection(real, tmp_path):
    original = issuer.sm._bind_role_candidates
    isolated = issuer._isolated_functions(issuer.sm)
    isolated["_bind_role_candidates"] = issuer._no_fresh_nomination
    assert issuer.sm._bind_role_candidates is original
    assert isolated["map_any_requirement"].__code__ is issuer.sm.map_any_requirement.__code__
    assert isolated["map_any_requirement"].__globals__ is isolated
    assert inspect.signature(isolated["map_any_requirement"]) == inspect.signature(issuer.sm.map_any_requirement)
    with pytest.raises(auth.ProducerAuthorizationError):
        issuer._write_output(issuer._PRESERVED / "new-output", real)
    with pytest.raises(auth.ProducerAuthorizationError):
        issuer._write_output(tmp_path, real)


def test_actual_byte_snapshots_not_claimed_hashes(real):
    files = dict(real.input_bundle.files)
    key = "preserved-run/11_verified_ledger.json"
    files[key] = "a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d"
    from dataclasses import replace

    with pytest.raises(auth.ProducerAuthorizationError, match="byte"):
        verify(real, input_bundle=replace(real.input_bundle, files=files))


def test_scientific_production_consumes_verified_snapshots_without_file_reread(monkeypatch):
    original = issuer._produce

    def from_snapshots(*args):
        with (
            patch.object(Path, "read_bytes", side_effect=AssertionError("mutable path reread")),
            patch.object(Path, "read_text", side_effect=AssertionError("mutable path reread")),
            patch("builtins.open", side_effect=AssertionError("mutable path reread")),
        ):
            return original(*args)

    monkeypatch.setattr(issuer, "_produce", from_snapshots)
    result = issuer.reproduce_accepted_v8()
    assert result.verified_authorization.identities["receipt_ref"] == EXPECTED["receipt"]
