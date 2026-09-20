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
    assert all(len(platform["python_asset_sha256"]) == 64 for platform in spec["platforms"].values())


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


def test_connector_registration_guards_shortcut_and_registry_removal_on_update() -> None:
    """The finding that justified this whole increment: Tauri's own updater invokes the OLD
    version's uninstaller with /UPDATE (confirmed against the actual NSIS template bytes embedded
    in @tauri-apps/cli-win32-x64-msvc, not assumed) before laying down new files. Without the same
    guard the stock template uses for shortcuts, every auto-update would silently unregister the
    browser-capture connector."""
    hook = (ROOT / "app/desktop-shell/src-tauri/windows/installer-hooks.nsh").read_text(encoding="utf-8")
    assert "!macro NSIS_HOOK_PREUNINSTALL" in hook
    assert "${If} $UpdateMode <> 1" in hook
    # Ownership is exact-path equality, not "starts with $INSTDIR" (steering point 5).
    assert "${If} $8 == $9" in hook
    assert hook.count("${If} $8 == $9") == 2  # once per browser (Chrome, Edge)


def test_connector_registration_never_touches_a_third_party_manifest_by_construction() -> None:
    """The uninstall hook only ever DeleteRegKey's after confirming the stored value still points at
    THIS install's own manifest path -- a third-party NativeMessagingHosts sibling registered under
    a different name is never read, written, or matched by this comparison."""
    hook = (ROOT / "app/desktop-shell/src-tauri/windows/installer-hooks.nsh").read_text(encoding="utf-8")
    assert 'StrCpy $9 "$INSTDIR\\connector\\${CONNECTOR_NATIVE_HOST_NAME}.json"' in hook
    assert hook.count("DeleteRegKey HKCU") == 2


TAURI_DIR = ROOT / "app/desktop-shell/src-tauri"
COMMON_SOURCE_RESOURCE = {"../resources/callosum-src": "callosum-src"}
CONNECTOR_RESOURCE = {"../resources/connector": "connector"}
MACOS_CONNECTOR_SIDECAR = ["binaries/callosum-connector"]


def _merge_patch(target: object, patch: object) -> object:
    """RFC 7396 JSON Merge Patch -- how Tauri applies a platform config (`tauri.<os>.conf.json`) over the base config:
    objects merge key-by-key, arrays and scalars replace, null deletes."""
    if not isinstance(patch, dict):
        return patch
    result = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = _merge_patch(result.get(key), value)
    return result


def _effective_tauri_config(platform: str) -> dict:
    """The config Tauri actually builds with on `platform` (windows / macos / linux): base + that platform's override."""
    merged = json.loads((TAURI_DIR / "tauri.conf.json").read_text(encoding="utf-8"))
    override = TAURI_DIR / f"tauri.{platform}.conf.json"
    if override.is_file():
        merged = _merge_patch(merged, json.loads(override.read_text(encoding="utf-8")))
    assert isinstance(merged, dict)
    return merged


def test_shared_tauri_config_bundles_only_the_common_source_tree() -> None:
    """The connector is platform-owned. A connector declared in the SHARED config makes every platform's cargo build
    fail on `resource path ../resources/connector doesn't exist` unless that platform also stages it (found by the
    first GitHub run of PR #103: Linux and both macOS jobs failed exactly this way while main had passed)."""
    base = json.loads((TAURI_DIR / "tauri.conf.json").read_text(encoding="utf-8"))["bundle"]
    assert base["resources"] == COMMON_SOURCE_RESOURCE
    assert "externalBin" not in base


def test_connector_ownership_is_per_platform_in_the_effective_tauri_config() -> None:
    windows = _effective_tauri_config("windows")["bundle"]
    macos = _effective_tauri_config("macos")["bundle"]
    linux = _effective_tauri_config("linux")["bundle"]

    # Windows: the connector is a bundle RESOURCE (NSIS installs it under $INSTDIR\connector), source tree still common.
    assert windows["resources"] == {**COMMON_SOURCE_RESOURCE, **CONNECTOR_RESOURCE}
    assert "externalBin" not in windows

    # macOS: the connector is EXECUTABLE CODE -> an external-binary sidecar, never a Contents/Resources resource.
    assert macos["resources"] == COMMON_SOURCE_RESOURCE
    assert not any("connector" in source for source in macos["resources"])
    assert macos["externalBin"] == MACOS_CONNECTOR_SIDECAR

    # Linux: browser capture is unsupported for now; the shell must still build without any connector.
    assert linux["resources"] == COMMON_SOURCE_RESOURCE
    assert "externalBin" not in linux


def test_connector_resource_ships_in_its_own_subdirectory_not_the_install_root() -> None:
    """A resource named callosum-connector.exe placed directly under $INSTDIR would collide with
    cargo's own target/release/ output of the same name and churn fingerprints -- shipping it in a
    connector/ subdirectory avoids that regardless of naming. (Windows only: see the per-platform test above.)"""
    resources = _effective_tauri_config("windows")["bundle"]["resources"]
    assert resources["../resources/connector"] == "connector"


def test_macos_connector_staging_follows_tauris_target_triple_sidecar_convention() -> None:
    spec = importlib.util.spec_from_file_location(
        "callosum_stage_connector", ROOT / "app/desktop-shell/packaging/stage_connector.py"
    )
    assert spec is not None and spec.loader is not None
    stage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage)

    arm = stage.staged_target("darwin", "aarch64-apple-darwin")
    intel = stage.staged_target("darwin", "x86_64-apple-darwin")
    assert arm == TAURI_DIR / "binaries" / "callosum-connector-aarch64-apple-darwin"
    assert intel == TAURI_DIR / "binaries" / "callosum-connector-x86_64-apple-darwin"
    # ...and it is NOT staged into the resource tree Tauri copies verbatim into Contents/Resources.
    assert "resources" not in arm.parts
    assert stage.staged_target("win32", None) == ROOT / "app/desktop-shell/resources/connector/callosum-connector.exe"
    with pytest.raises(ValueError):
        stage.staged_target("darwin", None)  # Tauri requires the triple suffix
    with pytest.raises(ValueError):
        stage.staged_target("linux", "x86_64-unknown-linux-gnu")  # Linux stages no connector


def test_preinstall_hook_clears_the_stale_connector_resource_like_callosum_src() -> None:
    hook = (ROOT / "app/desktop-shell/src-tauri/windows/installer-hooks.nsh").read_text(encoding="utf-8")
    assert 'RMDir /r "$INSTDIR\\connector"' in hook


def test_windows_ci_verifies_connector_registration_and_uninstall_ownership() -> None:
    """Steering points 4/5: beyond 'the registry key exists', CI asserts the manifest is exact and
    parses, exercises the REAL /UPDATE argv Tauri's own bundler constructs (not a guess), and proves
    a pre-seeded third-party NativeMessagingHosts sibling survives both uninstall paths untouched."""
    workflow = (ROOT / ".github/workflows/desktop-shell-windows.yml").read_text(encoding="utf-8")
    assert "generate_connector_nsh.py" in workflow
    assert "stage_connector.py" in workflow
    assert "NativeMessagingHosts\\org.callosum.connector" in workflow
    assert '"/S", "/UPDATE", "_?=$installDir"' in workflow
    assert '"/S", "_?=$installDir"' in workflow
    assert "com.example.thirdparty" in workflow
    assert "allowed_origins" in workflow


def test_macos_ci_packages_registers_and_probes_the_connector_as_nested_code() -> None:
    """Browser capture reaches macOS (#61: the first concrete user is on a Mac), so the macOS workflow must prove the
    connector is packaged as executable nested code and that the registration + host protocol work against the INSTALLED
    app -- on both architectures, before any browser click-through on real hardware."""
    workflow = (ROOT / ".github/workflows/desktop-shell-macos.yml").read_text(encoding="utf-8")
    # Staged natively per architecture BEFORE any cargo step that makes Tauri validate the sidecar path.
    stage = workflow.index("stage_connector.py")
    assert stage < workflow.index("cargo test live_pinned_preview_installs_and_runs_three_generation_contracts")
    assert stage < workflow.index("npx tauri build")
    assert "lipo -archs" in workflow
    assert "cargo test --release --manifest-path app/desktop-shell/connector-host/Cargo.toml" in workflow
    assert "cargo test --lib connector_registration" in workflow
    # Nested code, not a resource: located by observation, never under Contents/Resources, and codesign-verified.
    assert "find \"$INSTALLED\" -name 'callosum-connector*'" in workflow
    assert "must NOT be under Contents/Resources" in workflow
    assert 'codesign --verify --deep --strict --verbose=2 "$INSTALLED"' in workflow
    assert 'codesign --verify --strict --verbose=2 "$CONNECTOR"' in workflow
    # Registration evidence: exact manifest from identity.json, absolute installed path, no translocated/DMG path.
    assert "NativeMessagingHosts/org.callosum.connector.json" in workflow
    assert 'manifest["allowed_origins"] == expected_origins' in workflow
    assert "AppTranslocation" in workflow and "/Volumes/" in workflow
    # Direct-host probes use the explicit DEV mechanism (production_extension_ids is still empty) with explicit expectations.
    assert "CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD" in workflow
    assert '"callosum_closed"' in workflow and '"available"' in workflow


def test_the_connector_ci_job_declares_only_read_only_contents_permission() -> None:
    """CodeQL (`actions/missing-workflow-permissions`) found the new job without an explicit token scope. It only checks
    out the repository and runs tests, so the narrowest grant -- `contents: read`, no write scope -- is the whole fix."""
    import re

    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    job = re.search(r"^  connector-and-extension:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", text, re.S | re.M)
    assert job is not None
    block = job.group(1)
    assert re.search(r"^    permissions:\n      contents: read\n", block, re.M)
    assert not re.search(r":\s*write", block), "a permission value of write would exceed the narrowest grant"


def test_linux_workflow_stages_no_connector_but_must_still_build() -> None:
    workflow = (ROOT / ".github/workflows/desktop-shell-linux.yml").read_text(encoding="utf-8")
    assert "stage_connector" not in workflow
    assert "resources/connector" not in workflow


def test_python_runtime_is_not_a_tauri_bundle_resource() -> None:
    config = json.loads((ROOT / "app/desktop-shell/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    resources = config["bundle"]["resources"]
    assert "../resources/callosum-src" in resources
    assert all("python-runtime" not in source for source in resources)


def test_desktop_app_workflows_reuse_published_runtime_artifacts() -> None:
    for platform in ("windows", "macos", "linux"):
        workflow = (ROOT / f".github/workflows/desktop-shell-{platform}.yml").read_text(encoding="utf-8")
        assert "Verify referenced immutable Python runtime is published" in workflow
        assert "package_python_runtime.py id --platform" in workflow
        assert "runtime-manifest.json.sig" in workflow
        assert "Build portable Python runtime" not in workflow
        assert "Build native portable Python runtime" not in workflow


def test_runtime_artifact_workflow_covers_every_shipped_platform() -> None:
    workflow = (ROOT / ".github/workflows/desktop-python-runtime.yml").read_text(encoding="utf-8")
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
