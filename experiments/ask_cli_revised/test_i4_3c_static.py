"""I4-3C file/function isolation and pure selector guards."""

import ast
import builtins
import hashlib
import json
import socket
from pathlib import Path

from experiments.ask_cli_revised import compatible_witness as cw
from experiments.ask_cli_revised import test_i4_3c_witness as h

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "experiments/ask_cli_revised"
FROZEN = json.loads((BASE / "witness_i4_3c_isolation.json").read_text(encoding="utf-8"))


def test_frozen_layer_c_identity_policy_grounding_and_classifier_code():
    for name, expected in FROZEN["files"].items():
        text = (ROOT / name).read_text(encoding="utf-8")
        assert hashlib.sha256(text.encode()).hexdigest() == expected, name
    for key, expected in FROZEN["functions"].items():
        name, function = key.split("::")
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
        assert hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest() == expected, key


def test_selector_calls_and_candidate_reads_stay_at_named_seams():
    allowed_calls = {
        "sufficiency_engine.py": {"recompute_instance": {"initialize_instance"}},
        "relation_witness.py": {"_witness_instance_v8": {"finalize_instance", "WitnessIntegrityError"}},
        "sufficiency_mapping.py": {
            "attach_aligned_observations": {"validate_witness_bundle", "canonical", "WitnessIntegrityError"},
            "_aligned_sentence_spans": {"WitnessIntegrityError"},
            "_aligned_scopes": {"source_identity", "text_hash", "digest", "WitnessIntegrityError"},
            "_merge_aligned_observation": {"text_hash", "reference"},
        },
    }
    helpers = {
        "build_support_views",
        "select_completion_proofs",
        "select_i1_proofs",
        "build_observation_bases",
        "initialize_instance",
        "finalize_instance",
    }
    found = set()
    for path in BASE.rglob("*.py"):
        if path.name.startswith("test") or path.name == "compatible_witness.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        selector_aliases = {
            a.asname or a.name
            for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom)
            for a in n.names
            if a.name == "compatible_witness"
        }
        for function in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            for call in (n for n in ast.walk(function) if isinstance(n, ast.Call)):
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id in selector_aliases
                ):
                    name = call.func.attr
                    assert name in allowed_calls.get(path.name, {}).get(function.name, set()), (
                        path,
                        function.name,
                        name,
                    )
                    if name in helpers:
                        found.add((path.name, function.name, name))
            if path.name in ("sufficiency_diagnostic.py", "direction_target.py") or "answer_plan" in path.parts:
                assert not any(
                    isinstance(n, ast.Constant) and n.value == "candidate_supports" for n in ast.walk(function)
                )
    assert found == {
        ("sufficiency_engine.py", "recompute_instance", "initialize_instance"),
        ("relation_witness.py", "_witness_instance_v8", "finalize_instance"),
    }


def test_selector_dependency_calls_are_closed():
    tree = ast.parse(Path(cw.__file__).read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    engine_calls = {
        n.func.attr
        for n in calls
        if isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "se"
    }
    assert engine_calls == {"validate_evaluated_candidate_support"}
    forbidden = {"open", "exec", "eval", "__import__", "getattr", "setattr"}
    assert not any(isinstance(n.func, ast.Name) and n.func.id in forbidden for n in calls)
    # New selection code never assigns to input bindings or candidate payloads.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript):
                    root = target
                    while isinstance(root, ast.Subscript):
                        root = root.value
                    assert not isinstance(root, ast.Name) or root.id not in {
                        "bindings",
                        "binding",
                        "role_bindings",
                        "candidate",
                        "props",
                        "instance",
                        "requirement",
                    }


def test_selector_runtime_no_io(monkeypatch):
    props = {"P2": h.prop("P2")}
    bindings = {"a": h.binding("a", [h.candidate("P2", props["P2"]["quote"])]), "b": h.legacy("b")}

    def denied(*args, **kwargs):
        raise AssertionError("pure witness path attempted I/O")

    with monkeypatch.context() as guarded:
        guarded.setattr(builtins, "open", denied)
        guarded.setattr(socket, "create_connection", denied)
        guarded.setattr(socket.socket, "connect", denied)
        _, instance = h.run(bindings, props)
    assert instance["relation_witnessed"]
