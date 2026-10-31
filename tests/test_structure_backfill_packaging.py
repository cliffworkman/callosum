"""Inc 613: the source-role structure derivation ships inside the packaged application.

The desktop installer stages only ``app/backend``, ``alembic`` and ``integrations`` (``stage_source.TOP_LEVEL_DIRS``),
so a derivation living in ``tools/`` could never run on a user's library. These tests pin that the derivation is
packaged, depends on nothing outside it, and that the developer CLI is a thin wrapper over the very same functions
(so the CLI and a future background job can never derive different output).
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from app.backend.pdf_processing import structure_backfill

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "app" / "backend" / "pdf_processing" / "structure_backfill.py"


def _load(path: Path, name: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_derivation_is_inside_a_staged_directory() -> None:
    stage = _load(ROOT / "app" / "desktop-shell" / "packaging" / "stage_source.py", "stage_source_under_test")
    rel = MODULE.relative_to(ROOT).as_posix()
    assert any(rel.startswith(top + "/") for top in stage.TOP_LEVEL_DIRS)


def test_derivation_imports_nothing_outside_the_package() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    modules |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    first_party = {m for m in modules if m.split(".")[0] in {"app", "tools", "tests", "experiments"}}
    assert first_party and all(m.startswith("app.backend.") for m in first_party), first_party


def test_cli_wraps_the_packaged_functions() -> None:
    cli = _load(ROOT / "tools" / "backfill_chunk_structure.py", "backfill_cli_under_test")
    assert cli.backfill is structure_backfill.backfill
    assert cli.coverage is structure_backfill.coverage
