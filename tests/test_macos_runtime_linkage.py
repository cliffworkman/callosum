from __future__ import annotations

import importlib.util
import json
import subprocess
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "macos_linkage", ROOT / "app/desktop-shell/packaging/check_macos_runtime_linkage.py"
)
linkage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linkage)


@pytest.mark.parametrize("command", sorted(linkage.LOAD_COMMANDS))
@pytest.mark.parametrize(
    "path",
    [
        "/usr/local/opt/openssl@3/lib/libssl.3.dylib",
        "/opt/homebrew/lib/libcrypto.3.dylib",
        "/Users/runner/work/libssl.dylib",
        "/private/tmp/build/lib.dylib",
        "libssl.dylib",
    ],
)
def test_rejects_builder_local_dependency(command, path):
    entries = linkage.parse_load_commands(f"Load command 1\n cmd {command}\n cmdsize 80\n name {path} (offset 24)\n")
    assert linkage.invalid_dependencies(entries) == [path]


def test_distinguishes_library_identity_and_search_hints_from_dependencies():
    output = """extension.so (architecture x86_64):
Load command 0
          cmd LC_ID_DYLIB
         name /Users/runner/work/extension.so (offset 24)
Load command 1
          cmd LC_LOAD_DYLIB
         name /usr/lib/libSystem.B.dylib (offset 24)
Load command 2
          cmd LC_LOAD_DYLIB
         name @loader_path/../.dylibs/libbundled.dylib (offset 24)
Load command 3
          cmd LC_RPATH
         path /Users/runner/work/unused (offset 12)
extension.so (architecture arm64):
Load command 1
          cmd LC_LOAD_DYLIB
         name /System/Library/Frameworks/Security.framework/Versions/A/Security (offset 24)
"""
    entries = linkage.parse_load_commands(output)
    assert len(entries) == 5
    assert entries[0]["command"] == "LC_ID_DYLIB"
    assert entries[3]["command"] == "LC_RPATH"
    assert entries[-1]["architecture"] == "arm64"
    assert linkage.invalid_dependencies(entries) == []


def test_scanner_records_failure_without_loading_native_code(tmp_path, monkeypatch):
    (tmp_path / "rust.so").write_bytes(bytes.fromhex("cffaedfe") + b"fixture")
    (tmp_path / "module.py").write_text("pass")
    calls = []

    def otool(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(
            stdout="cmd LC_LOAD_DYLIB\nname /usr/local/opt/openssl@3/lib/libssl.3.dylib (offset 24)\n"
        )

    monkeypatch.setattr(linkage.subprocess, "run", otool)
    result = linkage.inspect_runtime(tmp_path)
    assert len(calls) == 1
    assert calls[0][:4] == ["otool", "-arch", "all", "-l"]
    assert result["violations"] == [{"file": "rust.so", "dependency": "/usr/local/opt/openssl@3/lib/libssl.3.dylib"}]
    assert len(result["binaries"][0]["sha256"]) == 64


def test_otool_failure_is_not_silently_accepted(tmp_path, monkeypatch):
    (tmp_path / "rust.so").write_bytes(bytes.fromhex("cffaedfe"))

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "otool")

    monkeypatch.setattr(linkage.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        linkage.inspect_runtime(tmp_path)


@pytest.mark.parametrize(
    "platform,machine,version",
    [
        ("darwin", "x86_64", "48.0.1"),
        ("darwin", "arm64", "50.0.0"),
        ("win32", "AMD64", "50.0.0"),
        ("linux", "x86_64", "50.0.0"),
    ],
)
def test_cryptography_constraint_only_changes_intel_macos(platform, machine, version):
    env = dict(default_environment(), sys_platform=platform, platform_machine=machine)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    fallback = [
        line.split(" #", 1)[0]
        for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line.startswith("cryptography")
    ]
    for requirements in [project["project"]["dependencies"], fallback]:
        applicable = [
            r
            for text in requirements
            if (r := Requirement(text)).name == "cryptography" and (not r.marker or r.marker.evaluate(env))
        ]
        assert len(applicable) == 1
        assert version in applicable[0].specifier
        if platform == "darwin" and machine == "x86_64":
            assert "50.0.0" not in applicable[0].specifier
    locked = tomllib.loads((ROOT / "uv.lock").read_text())
    variants = [p for p in locked["package"] if p["name"] == "cryptography" and p["version"] == version]
    assert len(variants) == 1
    if version == "48.0.1":
        assert any("cp311-abi3-macosx_10_9_universal2.whl" in w["url"] for w in variants[0]["wheels"])


def test_native_guard_and_report_are_part_of_runtime_identity():
    spec = json.loads((ROOT / "app/desktop-shell/packaging/python-runtime-inputs.json").read_text())
    assert "app/desktop-shell/packaging/check_macos_runtime_linkage.py" in spec["shared_inputs"]
    recipe = (ROOT / "app/desktop-shell/packaging/build_python_macos.sh").read_text()
    assert "--only-binary=cryptography" in recipe
    assert "check_macos_runtime_linkage.py" in recipe
    assert '"$PYTHON_BIN" -m pip check' in recipe
