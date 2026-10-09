"""Exact-file policy consumer and purity boundaries; synthetic unauthorized modules must fail."""

import ast
from pathlib import Path

import pytest

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import support_policy as sp

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_CONSUMER = "experiments/ask_cli_revised/sufficiency_mapping.py"
MODULE = "experiments/ask_cli_revised/support_policy.py"
FORBIDDEN = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "input",
    "getattr",
    "globals",
    "locals",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "support_label",
    "authority_veto",
    "is_caption",
    "guard_exclusions",
    "attachment_ambiguous",
    "mapping_strategy",
    "category_description",
    "proposition_id",
    "exact_text",
    "question",
    "role",
    "q_aib",
    "amygdala",
    "dehumanization",
    "attractiveness",
    "p40",
    "p41",
}
API = {"default_support_policy", "evaluate_authored_support_policy"}


def check_purity(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(n.name in {"hashlib", "json"} for n in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module == "experiments.ask_cli_revised"
            assert [(n.name, n.asname) for n in node.names] == [("sufficiency_engine", "se")]
        if isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN
        if isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN
            assert isinstance(node.value, ast.Name) and node.value.id in {"se", "failures"}
            if node.value.id == "se":
                assert node.attr in {
                    "SUPPORT_ASSERTION_RELATIONS",
                    "SUPPORT_AGGREGATIONS",
                    "SUPPORT_ASSERTION_KINDS",
                    "support_policy_identity",
                    "default_support_policy_snapshot",
                    "canonical_support_policy",
                }
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in FORBIDDEN
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in API:
        fn = functions[name]
        assert [a.arg for a in fn.args.kwonlyargs] == ["assertion_relation", "aggregation", "assertion_kind"]
        assert [a.arg for a in fn.args.args] == (["policy"] if name.startswith("evaluate") else [])
        assert fn.args.vararg is fn.args.kwarg is None


def check_consumers(paths):
    for name, source in paths.items():
        if name in (ALLOWED_CONSUMER, MODULE) or Path(name).name.startswith("test_"):
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(n.name.endswith("support_policy") for n in node.names), name
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").endswith("support_policy"), name
                assert not any(n.name == "support_policy" or n.name in API for n in node.names), name
            if isinstance(node, (ast.Name, ast.Attribute)):
                assert (node.id if isinstance(node, ast.Name) else node.attr) not in API, name
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in API and not node.value.endswith(".support_policy"), name


def test_production_purity():
    check_purity(Path(sp.__file__).read_text(encoding="utf-8"))
    assert "import support_policy" not in Path(se.__file__).read_text(encoding="utf-8")


def test_exact_consumer_boundary():
    paths = {}
    for directory in ("experiments", "app", "integrations", "tools"):
        for p in (ROOT / directory).rglob("*.py"):
            if p.name.startswith("test_") or "__pycache__" in p.parts:
                continue
            paths[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8-sig")
    check_consumers(paths)


@pytest.mark.parametrize(
    "source",
    [
        "import socket",
        "import sqlite3",
        "from experiments.ask_cli_revised import assertion_authority",
        "from experiments.ask_cli_revised import ownership_context",
        "open('x')",
        "support_label",
        "x['authority_veto']",
        "x['is_caption']",
        "x['attachment_ambiguous']",
        "x['guard_exclusions']",
        "x['question']",
        "x['amygdala']",
    ],
)
def test_purity_rejects_prohibited_inputs_and_effects(source):
    with pytest.raises(AssertionError):
        check_purity(source)


@pytest.mark.parametrize(
    "source",
    [
        "from experiments.ask_cli_revised import support_policy as p",
        "import experiments.ask_cli_revised.support_policy as p",
        "from experiments.ask_cli_revised.support_policy import default_support_policy",
        "x.default_support_policy()",
        "__import__('experiments.ask_cli_revised.support_policy')",
    ],
)
def test_unauthorized_consumer_rejected(source):
    check_consumers({ALLOWED_CONSUMER: source})
    with pytest.raises(AssertionError):
        check_consumers({"app/sufficiency_mapping.py": source})
