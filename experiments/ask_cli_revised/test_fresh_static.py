"""Fresh entry stays independent of qualification artifacts and scientific selection."""

import ast
import re
from pathlib import Path

BASE = Path(__file__).parent
FRESH = (
    "reporting_contract",
    "reviewed_ask_inputs",
    "reviewed_ask",
    "fresh_invocation",
    "fresh_layerc",
    "layerc_pipeline",
)


def test_no_fresh_fixture_identity_or_qualification_imports():
    prohibited = re.compile(r"q_aib|qaib|aib_hier|phase.?28|phase.?30|C0[1-9]|C1[0-7]|V0[1-9]|V[12][0-9]|V3[0-2]", re.I)
    for name in FRESH:
        root = ast.parse((BASE / (name + ".py")).read_text())
        for n in ast.walk(root):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                assert not prohibited.search(n.value), (name, n.value)
            if isinstance(n, ast.ImportFrom):
                targets = [n.module or "", *[a.name for a in n.names]]
                assert not any("producer_" in t or "profile_b" in t or "sufficiency_freeze" in t for t in targets)
            if isinstance(n, ast.Call):
                call = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
                assert call not in {
                    "reproduce_accepted_v8",
                    "load_overlay",
                    "load_verified",
                    "compute_diagnostic_sufficiency_map",
                }


def test_only_actual_execution_issues_fresh_provenance():
    sites = []
    for p in BASE.rglob("*.py"):
        if p.name.startswith("test_"):
            continue
        root = ast.parse(p.read_text(encoding="utf-8-sig"))
        for n in ast.walk(root):
            if isinstance(n, ast.Call):
                call = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
                if call == "_begin_execution":
                    sites.append(p.name)
                if call == "_Execution":
                    assert p.name == "fresh_invocation.py"
    assert sites == ["e2e.py"]
    root = ast.parse((BASE / "e2e.py").read_text())
    execute = next(n for n in root.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    text = ast.unparse(execute)
    assert (
        text.index("_begin_execution")
        < text.index("compute_diagnostic_sufficiency_map")
        < text.index("fresh_execution.finish")
    )
    assert "result_out['selected_answer'] = text" in text
    assert "se.SUFFICIENCY_SEMANTICS_V8" in text


def test_fresh_scientific_consumers_do_not_select_or_repair_science():
    forbidden = {
        "build_support_views",
        "select_completion_proofs",
        "select_i1_proofs",
        "recompute_requirement",
        "default_support_policy",
        "classify_assertion_authority",
        "compute_direction_and_effectiveness",
    }
    for name in ("fresh_layerc", "layerc_pipeline"):
        root = ast.parse((BASE / (name + ".py")).read_text())
        for n in ast.walk(root):
            if isinstance(n, ast.Call):
                call = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
                assert call not in forbidden
