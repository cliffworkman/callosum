"""The browser-extension store package builder (#61 Phase 1 store-readiness).

`app/desktop-shell/packaging/build_extension_package.py` is the only sanctioned way to make the zip that goes to
the Chrome Web Store and Microsoft Edge Add-ons. These tests prove what that zip is: an allowlisted, keyless,
reproducible archive of the runtime files, and that the builder refuses (rather than quietly shipping) anything
a store would reject or that must never ship -- a manifest `key`, signing material, an unclassified file.
Nothing here talks to a store.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "app" / "desktop-shell" / "extension"
BUILDER_PATH = ROOT / "app" / "desktop-shell" / "packaging" / "build_extension_package.py"

EXPECTED_FILES = [
    "background.js",
    "icons/icon128.png",
    "icons/icon16.png",
    "icons/icon32.png",
    "icons/icon48.png",
    "manifest.json",
]


@functools.cache
def _builder():
    spec = importlib.util.spec_from_file_location("callosum_extension_packager", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A private copy of the real extension directory that a test may freely mutate."""
    copy = tmp_path / "extension"
    shutil.copytree(EXTENSION_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    return copy


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_manifest(source: Path, mutate) -> None:
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def test_the_real_extension_builds_a_keyless_package_of_exactly_the_runtime_files(tmp_path: Path) -> None:
    result = _builder().build_package(EXTENSION_DIR, tmp_path / "pkg.zip")

    with zipfile.ZipFile(result.path) as archive:
        names = archive.namelist()
        assert names == EXPECTED_FILES  # sorted, exactly the runtime set, manifest.json at the zip root
        manifest = json.loads(archive.read("manifest.json"))
        assert "key" not in manifest and "update_url" not in manifest
        assert manifest["manifest_version"] == 3
        for name in names:
            assert not name.startswith(("dev/", "tests/"))
            assert not name.endswith((".md", ".mjs", ".pem", ".key", ".crx", ".py"))
    assert result.files == tuple(EXPECTED_FILES)
    assert result.sha256 == _sha(result.path)


def test_package_entries_carry_normalized_metadata_and_are_stored_not_compressed(tmp_path: Path) -> None:
    result = _builder().build_package(EXTENSION_DIR, tmp_path / "pkg.zip")
    with zipfile.ZipFile(result.path) as archive:
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0), info.filename
            assert info.compress_type == zipfile.ZIP_STORED, info.filename  # DEFLATE bytes vary by zlib build
            assert info.create_system == 3, info.filename
            assert (info.external_attr >> 16) == 0o644, info.filename
        assert archive.testzip() is None


def test_package_contents_equal_the_source_bytes_with_lf_line_endings(tmp_path: Path) -> None:
    result = _builder().build_package(EXTENSION_DIR, tmp_path / "pkg.zip")
    with zipfile.ZipFile(result.path) as archive:
        for name in EXPECTED_FILES:
            expected = (EXTENSION_DIR / name).read_bytes()
            if name.endswith((".json", ".js")):
                expected = expected.replace(b"\r\n", b"\n")
            assert archive.read(name) == expected, name


def test_two_builds_of_the_same_input_are_byte_identical(tmp_path: Path, source: Path) -> None:
    builder = _builder()
    first = builder.build_package(source, tmp_path / "one" / "pkg.zip")
    # Change every source file's mtime (a fresh checkout / a later build) -- the package must not care.
    for path in source.rglob("*"):
        if path.is_file():
            os.utime(path, (1_000_000_000, 1_000_000_000))
    second = builder.build_package(source, tmp_path / "two" / "renamed.zip")

    assert first.sha256 == second.sha256
    assert first.path.read_bytes() == second.path.read_bytes()


def test_a_windows_checkout_with_crlf_line_endings_builds_the_same_package(tmp_path: Path, source: Path) -> None:
    builder = _builder()
    lf = builder.build_package(source, tmp_path / "lf.zip")
    for name in ("manifest.json", "background.js"):
        path = source / name
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    crlf = builder.build_package(source, tmp_path / "crlf.zip")
    assert lf.sha256 == crlf.sha256


def test_the_excluded_dev_directory_never_ships_even_if_it_holds_key_material(tmp_path: Path, source: Path) -> None:
    (source / "dev" / "leftover.pem").write_text("-----BEGIN PRIVATE KEY-----", encoding="utf-8")
    result = _builder().build_package(source, tmp_path / "pkg.zip")
    assert list(result.files) == EXPECTED_FILES
    with zipfile.ZipFile(result.path) as archive:
        assert not any("pem" in name or name.startswith("dev/") for name in archive.namelist())


@pytest.mark.parametrize(
    "filename", ["private.pem", "signing.key", "extension.crx", "store.p12", "store.pfx", "icons/x.pem", "PRIVATE.PEM"]
)
def test_signing_material_can_never_be_packaged(tmp_path: Path, source: Path, filename: str) -> None:
    target = source / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("secret", encoding="utf-8")
    with pytest.raises(_builder().PackageError, match="signing/private-key material"):
        _builder().build_package(source, tmp_path / "pkg.zip")
    assert not (tmp_path / "pkg.zip").exists()


@pytest.mark.parametrize("filename", ["notes.txt", "extra.js", "icons/readme.txt", "icons/nested/icon.png", "LICENSE"])
def test_an_unclassified_file_stops_the_build_instead_of_shipping(tmp_path: Path, source: Path, filename: str) -> None:
    target = source / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x")
    with pytest.raises(_builder().PackageError, match="not classified"):
        _builder().build_package(source, tmp_path / "pkg.zip")


def test_a_missing_runtime_file_stops_the_build(tmp_path: Path, source: Path) -> None:
    (source / "background.js").unlink()
    with pytest.raises(_builder().PackageError, match="background.js"):
        _builder().build_package(source, tmp_path / "pkg.zip")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda m: m.update(key="MIIB-placeholder"), "must not contain 'key'"),
        (lambda m: m.update(update_url="https://example.com/u.xml"), "update_url"),
        (lambda m: m.update(manifest_version=2), "manifest_version must be 3"),
        (lambda m: m.update(version="1.2.3.4.5"), "version"),
        (lambda m: m.update(version="1.99999"), "above 65535"),
        (lambda m: m.update(version=None), "version"),
        (lambda m: m.update(description="x" * 133), "limit is 132"),
        (lambda m: m.update(description="Send it to Chrome"), "'Chrome'"),
        (lambda m: m.update(name="Callosum for CHROME"), "'Chrome'"),
        (lambda m: m.update(name=""), "name is required"),
        (lambda m: m["icons"].pop("128"), "128"),
        (lambda m: m["background"].update(service_worker="missing.js"), "missing.js"),
    ],
)
def test_manifest_problems_a_store_would_reject_are_refused_up_front(
    tmp_path: Path, source: Path, mutate, message
) -> None:
    _rewrite_manifest(source, mutate)
    with pytest.raises(_builder().PackageError, match=message):
        _builder().build_package(source, tmp_path / "pkg.zip")


def test_the_cli_writes_the_zip_and_reports_its_hash(tmp_path: Path) -> None:
    out = tmp_path / "cli.zip"
    completed = subprocess.run(
        [sys.executable, str(BUILDER_PATH), "--out", str(out)], capture_output=True, text=True, check=True
    )
    assert out.is_file()
    assert f"sha256 {_sha(out)}" in completed.stdout
    for name in EXPECTED_FILES:
        assert name in completed.stdout


def test_the_cli_refuses_with_a_readable_message(tmp_path: Path, source: Path) -> None:
    _rewrite_manifest(source, lambda m: m.update(key="MIIB-placeholder"))
    completed = subprocess.run(
        [sys.executable, str(BUILDER_PATH), "--extension-dir", str(source), "--out", str(tmp_path / "x.zip")],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "extension package refused" in completed.stderr
    assert not (tmp_path / "x.zip").exists()


def test_the_default_output_lives_under_the_gitignored_local_directory() -> None:
    default = _builder().default_out_path(EXTENSION_DIR)
    assert ".local" in default.parts
    manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert default.name == f"callosum-capture-{manifest['version']}.zip"
