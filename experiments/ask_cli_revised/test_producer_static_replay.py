"""Executable ownership boundaries and unchanged legacy characterization."""

import ast
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import producer_authorization as auth
from experiments.ask_cli_revised import producer_replay as issuer
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import test_i4_2a_replay as replay
from experiments.ask_cli_revised import test_i4_2b3_replay as v6
from experiments.ask_cli_revised.answer_plan import plan
from experiments.ask_cli_revised.test_layerc_projection import FIXTURE

BASE = Path(__file__).parent
NEW = {
    "_producer_schema",
    "_producer_inputs",
    "producer_authorization",
    "producer_authorization_store",
    "producer_replay",
}
PURE = {"_producer_schema", "_producer_inputs", "producer_authorization"}
IMPORTS = {
    "_producer_schema": {"hashlib", "json", "math", "re", "collections.abc", "dataclasses", "types"},
    "_producer_inputs": {"json", "sufficiency_engine", "sufficiency_model_scope", "_producer_schema"},
    "producer_authorization": {"sufficiency_identity", "_producer_inputs", "_producer_schema"},
    "producer_authorization_store": {"pathlib", "_producer_schema"},
    "producer_replay": {
        "copy",
        "platform",
        "dataclasses",
        "pathlib",
        "tempfile",
        "types",
        "ownership_context",
        "producer_authorization",
        "sufficiency_diagnostic",
        "sufficiency_freeze",
        "sufficiency_mapping",
        "sufficiency_model_scope",
        "sufficiency_recovery_targets",
        "_producer_inputs",
        "_producer_schema",
        "producer_authorization_store",
    },
}
FORBIDDEN = {
    "open",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "connect",
    "urlopen",
    "request",
    "execute",
    "eval",
    "exec",
    "compile",
    "getenv",
    "time",
    "random",
    "compute_diagnostic_sufficiency_map",
    "compute_direction_and_effectiveness",
    "build_context_index",
    "nominate_with_model",
    "compute_recovery_targets",
    "build_support_views",
    "select_completion_proofs",
    "select_i1_proofs",
    "witness_instance",
    "default_support_policy",
    "classify_category_observation",
    "classify_assertion_authority",
}


def tree(name):
    return ast.parse((BASE / (name + ".py")).read_text(encoding="utf-8"))


def imports(root):
    for node in ast.walk(root):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "experiments.ask_cli_revised":
                yield from (a.name for a in node.names)
            elif node.module and node.module.startswith("experiments.ask_cli_revised."):
                yield node.module.rsplit(".", 1)[-1]
            else:
                yield node.module


@pytest.mark.parametrize("name", sorted(NEW))
def test_narrow_import_allowlists(name):
    assert set(imports(tree(name))) <= IMPORTS[name]


@pytest.mark.parametrize("name", sorted(PURE))
def test_verifier_family_is_pure_and_does_not_execute_producer(name):
    for node in ast.walk(tree(name)):
        if isinstance(node, ast.Call):
            called = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            regex_compile = (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "re"
                and called == "compile"
            )
            assert regex_compile or called not in FORBIDDEN, (name, called)
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            # Writes only to newly created local objects, never input maps/bundles/receipts.
            base = node.value.id if isinstance(node.value, ast.Name) else ""
            assert base not in {"smap", "receipt", "producer_receipt", "bundle", "files", "contracts", "registry"}


def test_only_store_reads_trust_configuration_and_no_runtime_enrollment():
    for name in NEW:
        root = tree(name)
        for node in ast.walk(root):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in {"producer_authorization.registry.json", "producer_authorization_material"}:
                    assert name == "producer_authorization_store"
        if name != "producer_replay":
            assert not any(
                isinstance(n, ast.Call) and getattr(n.func, "attr", "") in {"write_text", "write_bytes", "mkdir"}
                for n in ast.walk(root)
            )


def test_no_existing_consumer_imports_or_calls_new_authority():
    for path in BASE.rglob("*.py"):
        if path.stem in NEW or path.name.startswith("test_") or path.name.startswith("producer_test_"):
            continue
        root = ast.parse(path.read_text(encoding="utf-8"))
        assert not (set(imports(root)) & NEW), path
        assert not any(
            isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "reproduce_accepted_v8" for n in ast.walk(root)
        ), path


def test_producer_has_closed_inputs_no_eval_or_global_scientific_patch():
    root = tree("producer_replay")
    public = next(n for n in root.body if isinstance(n, ast.FunctionDef) and n.name == "reproduce_accepted_v8")
    assert not public.args.args and not public.args.vararg and not public.args.kwarg
    assert [a.arg for a in public.args.kwonlyargs] == ["output_dir"]
    for node in ast.walk(root):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"exec", "eval", "compile", "getattr", "__import__"}
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            assert not (isinstance(node.value, ast.Name) and node.value.id in {"sm", "sd", "se", "rt", "oc", "scope"})
    stores = [n for n in ast.walk(root) if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store)]
    assert all(not (isinstance(n.value, ast.Attribute) and n.value.attr in {"body", "materials"}) for n in stores)


def test_exact_membership_guard_independent_of_profile():
    root = tree("producer_authorization")
    resolution = next(n for n in root.body if isinstance(n, ast.FunctionDef) and n.name == "resolve_authority")
    text = ast.unparse(resolution)
    assert "receipt_ref in registry.body['accepted_receipts']" in text
    assert "profile_ref in registry.body['profiles']" in text


@pytest.fixture(scope="module")
def legacy():
    with (
        patch.object(auth, "verify_producer_authorization", side_effect=AssertionError("legacy authority activation")),
        patch.object(issuer, "reproduce_accepted_v8", side_effect=AssertionError("legacy issuer activation")),
    ):
        context = v6.context()
        return {
            v: replay.remap("sufficiency-semantics-" + v, ownership_context_index=context) for v in FIXTURE["hashes"]
        }


@pytest.mark.parametrize("version", list(FIXTURE["hashes"]))
def test_M_and_exact_v4_to_v8_characterization(legacy, version):
    assert hashlib.sha256(v6.replay_bytes(legacy[version])).hexdigest() == FIXTURE["hashes"][version]
    assert se.SUFFICIENCY_SEMANTICS_VERSION == se.SUFFICIENCY_SEMANTICS_V7
    assert plan.PLAN_VERSION == "answer-plan-step2-v4"
