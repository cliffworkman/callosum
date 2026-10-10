"""No activation, no classifier/selector and no mutable output boundary."""

import ast
import builtins
import socket
from pathlib import Path

from experiments.ask_cli_revised import test_layerc_integrity as h
from experiments.ask_cli_revised import test_layerc_projection as f

BASE = Path(__file__).parent
MODULES = [
    "layerc_projection.py",
    "_layerc_common.py",
    "_layerc_validation.py",
    "_layerc_observations.py",
    "_layerc_values.py",
]
ALLOWED_IMPORTS = {
    "json",
    "hashlib",
    "collections.abc",
    "types",
    "dataclasses",
    "app.backend.pdf_processing.extraction",
    "experiments.ask_cli_revised._layerc_common",
    "experiments.ask_cli_revised._layerc_validation",
    "experiments.ask_cli_revised._layerc_observations",
    "experiments.ask_cli_revised._layerc_values",
    "experiments.ask_cli_revised.contract_directed.links",
    "experiments.ask_cli_revised.sufficiency_engine",
}
FORBIDDEN = {
    "build_support_views",
    "common_assignments",
    "select_completion_proofs",
    "select_i1_proofs",
    "finalize_instance",
    "witness_instance",
    "validate_witness_bundle",
    "build_observation_bases",
    "default_support_policy",
    "evaluate_authored_support_policy",
    "classify_category_observation",
    "find_direction_observations",
    "find_effectiveness_observations",
    "remap",
    "recompute_requirement",
    "open",
    "eval",
    "exec",
    "__import__",
    "getattr",
    "setattr",
    "product",
}


def test_closed_import_call_allowlist_and_no_input_assignment():
    for name in MODULES:
        tree = ast.parse((BASE / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name in ALLOWED_IMPORTS for a in node.names), (name, node)
            if isinstance(node, ast.ImportFrom):
                assert node.module in ALLOWED_IMPORTS, (name, node.module)
                if node.module == "experiments.ask_cli_revised.sufficiency_engine":
                    assert [alias.name for alias in node.names] == ["validate_evaluated_candidate_support"]
            if isinstance(node, ast.Call):
                called = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else None
                )
                assert called not in FORBIDDEN, (name, called)
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    if isinstance(target, ast.Subscript):
                        root = target
                        while isinstance(root, ast.Subscript):
                            root = root.value
                        assert not isinstance(root, ast.Name) or root.id not in {
                            "smap",
                            "sealed",
                            "authored_contract",
                            "profile",
                            "candidate",
                            "binding",
                            "bindings",
                            "instance",
                            "requirement",
                            "props",
                            "bundle",
                            "obs",
                            "proof",
                        }, (name, ast.dump(target))


def test_no_production_consumers():
    names = {p[:-3] for p in MODULES}
    for path in BASE.rglob("*.py"):
        if path.name in MODULES or path.name.startswith("test"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name.split(".")[-1] not in names for a in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[-1] not in names, path
                assert all(a.name not in names for a in node.names), path


def test_runtime_no_io_or_scientific_calls(monkeypatch):
    args = h.fixture()

    def denied(*args, **kwargs):
        raise AssertionError("substrate attempted I/O/selection")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", denied)
        guard.setattr(socket, "create_connection", denied)
        guard.setattr(socket.socket, "connect", denied)
        for name in (
            "build_support_views",
            "common_assignments",
            "select_completion_proofs",
            "select_i1_proofs",
            "finalize_instance",
            "validate_witness_bundle",
        ):
            guard.setattr(h.h.cw, name, denied)
        guard.setattr(h.h.rw, "witness_instance", denied)
        guard.setattr(h.sm.cp, "classify_category_observation", denied)
        guard.setattr(h.h.sp, "default_support_policy", denied)
        projection = f.project(args)
    assert projection.schema_version == "layerc-validated-projection-v1"
