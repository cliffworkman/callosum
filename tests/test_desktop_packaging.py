from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_update_replaces_immutable_python_and_source_bundles() -> None:
    config = json.loads((ROOT / "app/desktop-shell/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert config["bundle"]["windows"]["nsis"]["installerHooks"] == "./windows/installer-hooks.nsh"
    hook = (ROOT / "app/desktop-shell/src-tauri/windows/installer-hooks.nsh").read_text(encoding="utf-8")
    assert "!macro NSIS_HOOK_PREINSTALL" in hook
    assert 'RMDir /r "$INSTDIR\\python-runtime"' in hook
    assert 'RMDir /r "$INSTDIR\\callosum-src"' in hook
    assert "$APPDATA" not in hook and "$LOCALAPPDATA" not in hook


def test_packaged_ml_dependency_trio_is_exact_and_smoke_checked() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for requirement in (
        "sentence-transformers==5.6.1",
        "transformers==5.14.1",
        "tokenizers==0.22.2",
    ):
        assert requirement in requirements
        assert f'"{requirement}"' in project
    smoke = (ROOT / "app/desktop-shell/packaging/smoke_test_backend.py").read_text(encoding="utf-8")
    assert "require_version(deps['tokenizers'])" in smoke
    assert "from sentence_transformers import CrossEncoder" in smoke


def test_linux_torch_prune_preserves_required_runtime_helper() -> None:
    script = (ROOT / "app/desktop-shell/packaging/build_python_linux.sh").read_text(encoding="utf-8")
    assert 'rm -rf "$TORCH_BIN"' not in script
    assert "-name 'test_*' -o -name '*Test'" in script
    assert 'test -x "$TORCH_BIN/torch_shm_manager"' in script
