from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _runtime_packager():
    path = ROOT / "app/desktop-shell/packaging/package_python_runtime.py"
    spec = importlib.util.spec_from_file_location("callosum_runtime_packager", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_python_runtime_ids_are_current_deterministic_and_platform_specific() -> None:
    packager = _runtime_packager()
    spec = packager._load_spec()
    packager.verify_spec(spec)
    ids = {key: packager.runtime_id(spec, key) for key in spec["platforms"]}
    assert len(set(ids.values())) == len(ids)
    assert ids["windows-x86_64"].startswith("win-x86_64-py3.11-s1-")
    assert ids["macos-aarch64"].startswith("macos-aarch64-py3.11-s1-")
    assert ids["macos-x86_64"].startswith("macos-x86_64-py3.11-s1-")
    assert ids["linux-x86_64"].startswith("linux-x86_64-py3.11-s1-")
    assert "0.5.4" not in json.dumps(packager._identity_material(spec, "windows-x86_64"))
    linux = spec["platforms"]["linux-x86_64"]
    assert linux["glibc_min"] == "2.35"
    assert linux["distribution_boundary"] == "ubuntu-22.04-or-newer-and-debian-12-or-newer"
    assert all(
        len(platform["python_asset_sha256"]) == 64
        for platform in spec["platforms"].values()
    )


def test_python_runtime_identity_ignores_checkout_line_endings(tmp_path: Path) -> None:
    packager = _runtime_packager()
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"one\ntwo\n")
    crlf.write_bytes(b"one\r\ntwo\r\n")
    assert packager._sha256_text_input(lf) == packager._sha256_text_input(crlf)


def test_python_runtime_archive_and_tree_digest_are_deterministic(tmp_path: Path) -> None:
    packager = _runtime_packager()
    runtime = tmp_path / "runtime"
    (runtime / "bin").mkdir(parents=True)
    executable = runtime / "bin" / "python3"
    executable.write_bytes(b"python")
    executable.chmod(0o755)
    (runtime / "empty").write_bytes(b"")
    (runtime / "data.txt").write_bytes(b"dependency bytes")

    entries = packager._tree_entries(runtime)
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    packager._write_archive(first, runtime, entries)
    os.utime(runtime / "data.txt", (2_000_000_000, 2_000_000_000))
    packager._write_archive(second, runtime, packager._tree_entries(runtime))

    assert first.read_bytes() == second.read_bytes()
    assert packager._tree_digest(entries) == packager._tree_digest(packager._tree_entries(runtime))


def test_python_runtime_symlink_escape_is_rejected(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("creating symlinks is not available to ordinary Windows test processes")
    packager = _runtime_packager()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "escape").symlink_to("../../outside")
    with pytest.raises(SystemExit, match="escapes its root"):
        packager._tree_entries(runtime)


def test_windows_update_replaces_source_but_preserves_legacy_runtime_for_migration() -> None:
    config = json.loads((ROOT / "app/desktop-shell/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert config["bundle"]["windows"]["nsis"]["installerHooks"] == "./windows/installer-hooks.nsh"
    hook = (ROOT / "app/desktop-shell/src-tauri/windows/installer-hooks.nsh").read_text(encoding="utf-8")
    assert "!macro NSIS_HOOK_PREINSTALL" in hook
    assert 'RMDir /r "$INSTDIR\\python-runtime"' not in hook
    assert 'RMDir /r "$INSTDIR\\callosum-src"' in hook
    assert "$APPDATA" not in hook and "$LOCALAPPDATA" not in hook


def test_python_runtime_is_not_a_tauri_bundle_resource() -> None:
    config = json.loads(
        (ROOT / "app/desktop-shell/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    )
    resources = config["bundle"]["resources"]
    assert "../resources/callosum-src" in resources
    assert all("python-runtime" not in source for source in resources)


def test_desktop_app_workflows_reuse_published_runtime_artifacts() -> None:
    for platform in ("windows", "macos", "linux"):
        workflow = (
            ROOT / f".github/workflows/desktop-shell-{platform}.yml"
        ).read_text(encoding="utf-8")
        assert "Verify referenced immutable Python runtime is published" in workflow
        assert "package_python_runtime.py id --platform" in workflow
        assert "runtime-manifest.json.sig" in workflow
        assert "Build portable Python runtime" not in workflow
        assert "Build native portable Python runtime" not in workflow


def test_runtime_artifact_workflow_covers_every_shipped_platform() -> None:
    workflow = (ROOT / ".github/workflows/desktop-python-runtime.yml").read_text(
        encoding="utf-8"
    )
    for platform in (
        "windows-x86_64",
        "macos-aarch64",
        "macos-x86_64",
        "linux-x86_64",
    ):
        assert f"platform: {platform}" in workflow
    assert "ubuntu-22.04" in workflow
    assert "runtime-manifest.json.sig" in workflow
    assert 'gh release create "python-runtime-$ID"' in workflow


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


def test_owned_transformer_loads_require_safetensors() -> None:
    sources = [
        ROOT / "app/backend/embeddings/models.py",
        ROOT / "app/backend/model_runtime.py",
        ROOT / "app/backend/summarization/verification.py",
        ROOT / "app/backend/summarization/stance.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    assert combined.count('model_kwargs={"use_safetensors": True}') == 5
