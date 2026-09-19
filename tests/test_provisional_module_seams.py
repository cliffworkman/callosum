"""Guards for the provisional-capture module split (#61, rule #1).

`provisional.py` was split by responsibility into a core module plus `provisional_evidence` (pure PDF evidence),
`provisional_review` (manual review actions) and `provisional_recovery` (startup recovery + permanent delete). The
behavioral suites (`test_capture.py`, `test_import_queue.py`) prove behavior is unchanged; these tests pin the three
structural properties a split like this can silently lose:

* the late-bound seams stay late-bound -- review/recovery reach core functions THROUGH the module, so replacing one on
  `app.backend.capture.provisional` still takes effect (the way the failure-injection tests patch `attach_pdf_to_paper`);
* there are no import cycles, whichever module is imported first;
* names that moved are still importable from their old location and resolve to the defining module's objects.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "app" / "backend" / "capture"
CORE = "app.backend.capture.provisional"

MOVED_PUBLIC_API = {
    "best_candidate": "provisional_review",
    "confirm_identity": "provisional_review",
    "explain_evidence": "provisional_review",
    "preview_doi": "provisional_review",
    "retry_promotion": "provisional_review",
    "permanently_delete_provisional_artifact": "provisional_recovery",
    "recover_at_startup": "provisional_recovery",
}


def _tree(module: str) -> ast.Module:
    return ast.parse((CAPTURE_DIR / f"{module}.py").read_text(encoding="utf-8"))


def _core_names() -> set[str]:
    return {n.name for n in _tree("provisional").body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


@pytest.mark.parametrize("module", ["provisional_review", "provisional_recovery"])
def test_dependent_modules_reach_core_through_the_module_never_by_name(module: str) -> None:
    tree = _tree(module)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != CORE, (
                f"{module} must not `from {CORE} import ...` (it would bind core names at import time)"
            )
    # ...and every core function it uses is referenced as `provisional.<name>`, never as a bare name.
    core_names = _core_names()
    assigned_here = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    bare_uses = {
        n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in core_names and n.id not in assigned_here
    }
    assert bare_uses == set(), f"{module} uses core names as bare names: {sorted(bare_uses)}"
    qualified = {
        n.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "provisional"
    }
    assert qualified, f"{module} is expected to use the core module through `provisional.`"
    assert qualified <= core_names, sorted(qualified - core_names)


def test_the_core_module_never_imports_its_dependents() -> None:
    dependents = {"provisional_review", "provisional_recovery"}
    for node in ast.walk(_tree("provisional")):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.rsplit(".", 1)[-1] not in dependents, f"circular import of {node.module}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.rsplit(".", 1)[-1] not in dependents


def test_the_evidence_module_is_a_leaf() -> None:
    for node in ast.walk(_tree("provisional_evidence")):
        module = getattr(node, "module", None) or ""
        assert not module.startswith("app.backend.capture"), f"evidence must not depend on capture modules: {module}"


@pytest.mark.parametrize(
    "first_import",
    [
        "app.backend.capture.provisional_review",
        "app.backend.capture.provisional_recovery",
        "app.backend.capture.provisional_evidence",
        "app.backend.capture.provisional",
        "app.backend.api.capture_startup",
        "app.backend.api.routers.import_queue",
    ],
)
def test_no_import_cycle_whichever_module_is_imported_first(first_import: str) -> None:
    script = (
        "import importlib\n"
        f"importlib.import_module({first_import!r})\n"
        "for name in ('provisional', 'provisional_evidence', 'provisional_review', 'provisional_recovery'):\n"
        "    importlib.import_module('app.backend.capture.' + name)\n"
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_moved_public_names_are_still_importable_and_resolve_to_the_defining_module() -> None:
    import importlib

    core = importlib.import_module(CORE)
    for name, module in MOVED_PUBLIC_API.items():
        defining = importlib.import_module(f"app.backend.capture.{module}")
        assert getattr(core, name) is getattr(defining, name), name


def test_the_compat_table_covers_exactly_the_moved_public_api_and_rejects_unknown_names() -> None:
    import importlib

    core = importlib.import_module(CORE)
    assert set(core._MOVED_PUBLIC_API) == set(MOVED_PUBLIC_API)
    for name, module in MOVED_PUBLIC_API.items():
        assert core._MOVED_PUBLIC_API[name] == f"app.backend.capture.{module}"
    with pytest.raises(AttributeError):
        core.definitely_not_a_name  # noqa: B018
    assert not hasattr(core, "definitely_not_a_name")


def test_the_late_bound_attach_seam_stays_in_the_core_module() -> None:
    """The failure-injection tests patch `provisional.attach_pdf_to_paper`; the call that must see the patch lives there."""
    tree = _tree("provisional")
    holders = [
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and any(
            isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "attach_pdf_to_paper"
            for c in ast.walk(n)
        )
    ]
    assert holders, "attach_pdf_to_paper must be called from the core module (the patched seam)"
    for module in ("provisional_review", "provisional_recovery", "provisional_evidence"):
        assert "attach_pdf_to_paper" not in {n.id for n in ast.walk(_tree(module)) if isinstance(n, ast.Name)}
