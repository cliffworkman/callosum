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
        "tokenizers==0.22.2",
    ):
        assert requirement in requirements
        assert f'"{requirement}"' in project
    assert "transformers==5.14.1" in requirements
    assert '"transformers==5.14.1;' in project
    smoke = (ROOT / "app/desktop-shell/packaging/smoke_test_backend.py").read_text(encoding="utf-8")
    assert "require_version(deps['tokenizers'])" in smoke
    assert "from sentence_transformers import CrossEncoder" in smoke


def test_linux_torch_prune_preserves_required_runtime_helper() -> None:
    script = (ROOT / "app/desktop-shell/packaging/build_python_linux.sh").read_text(encoding="utf-8")
    assert 'rm -rf "$TORCH_BIN"' not in script
    assert "-name 'test_*' -o -name '*Test'" in script
    assert 'test -x "$TORCH_BIN/torch_shm_manager"' in script


def test_macos_packaging_and_updates_cover_native_arm_and_intel() -> None:
    python_build = (ROOT / "app/desktop-shell/packaging/build_python_macos.sh").read_text(encoding="utf-8")
    macos_workflow = (ROOT / ".github/workflows/desktop-shell-macos.yml").read_text(encoding="utf-8")
    release_workflow = (ROOT / ".github/workflows/desktop-shell-release.yml").read_text(encoding="utf-8")

    assert 'PYTHON_ARCH="aarch64"' in python_build
    assert 'PYTHON_ARCH="x86_64"' in python_build
    assert '"torch==2.2.2"' in python_build
    assert '"numpy>=1.26,<2"' in python_build
    assert "macos-latest" in macos_workflow
    assert "macos-15-intel" in macos_workflow
    assert "callosum-macos-${{ matrix.arch }}" in macos_workflow
    assert "callosum-macos-arm64" in release_workflow
    assert "callosum-macos-x64" in release_workflow
    assert '"darwin-aarch64"' in release_workflow
    assert '"darwin-x86_64"' in release_workflow
    assert "Callosum-macos-arm64.dmg" in release_workflow
    assert "Callosum-macos-x64.dmg" in release_workflow


def test_intel_macos_local_ai_runtime_identity_is_pinned() -> None:
    source = (ROOT / "app/desktop-shell/src-tauri/src/managed_local_ai/install.rs").read_text(encoding="utf-8")
    assert "llama-b10516-bin-macos-x64.tar.gz" in source
    assert "b7adecf7bd2cde577ddabee8357a72409165d8104f43b4acee9f1b98cc9c447a" in source
    assert "f3136584b712d052374aa14765bea077721dc886af647228483ce79e2d838964" in source
    assert "9621e3a085f91d8c3091540c80684cde76dd637862fa0e07910744a8f63534f3" in source


def test_intel_macos_ml_stack_has_a_native_compatible_lane() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    intel_marker = "platform_machine == 'x86_64'"
    assert "\"torch==2.2.2; sys_platform == 'darwin' and platform_machine == 'x86_64'\"" in project
    assert "\"transformers==4.57.6; sys_platform == 'darwin' and platform_machine == 'x86_64'\"" in project
    assert intel_marker in project
    assert 'transformers==4.57.6 ; sys_platform == "darwin" and platform_machine == "x86_64"' in requirements
