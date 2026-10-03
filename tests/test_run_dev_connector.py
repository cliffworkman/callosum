"""The dev native-host registration is cross-platform (#61): Windows keeps its registry path, macOS writes per-user
manifests. These tests pin the macOS side and the shared manifest shape without touching the real registry or home."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools import run_dev

IDENTITY = json.loads((run_dev.ROOT / "app/desktop-shell/connector/identity.json").read_text(encoding="utf-8"))
DEV_HOST = IDENTITY["dev_native_host_name"]


def test_the_dev_manifest_allows_only_the_dev_extension_under_the_dev_host_name() -> None:
    manifest = run_dev._dev_host_manifest(IDENTITY, Path("/x/dev_connector_launcher"))
    assert manifest["name"] == DEV_HOST != IDENTITY["native_host_name"]
    assert manifest["allowed_origins"] == [f"chrome-extension://{IDENTITY['dev_extension_id']}/"]
    assert manifest["type"] == "stdio"
    assert manifest["path"] == str(Path("/x/dev_connector_launcher"))


def test_binary_names_follow_the_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert run_dev._exe_suffix() == ".exe"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert run_dev._exe_suffix() == ""


def test_macos_manifest_dirs_always_include_chrome_and_edge_only_when_present(tmp_path: Path) -> None:
    chrome = tmp_path / "Library/Application Support/Google/Chrome/NativeMessagingHosts"
    assert run_dev._macos_manifest_dirs(tmp_path) == [chrome]
    (tmp_path / "Library/Application Support/Microsoft Edge").mkdir(parents=True)
    assert run_dev._macos_manifest_dirs(tmp_path) == [
        chrome,
        tmp_path / "Library/Application Support/Microsoft Edge/NativeMessagingHosts",
    ]


def test_macos_dev_registration_writes_and_clears_only_the_dev_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "callosum_connector"
    launcher = tmp_path / "dev_connector_launcher"
    binary.write_bytes(b"")
    launcher.write_bytes(b"")
    profile_dir = tmp_path / "throwaway-profile" / "NativeMessagingHosts"
    profile_dir.mkdir(parents=True)
    neighbour = profile_dir / "com.example.other.json"
    neighbour.write_text('{"name": "com.example.other"}', encoding="utf-8")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(run_dev, "DEV_CONNECTOR_DIR", tmp_path / "dev-connector")
    monkeypatch.setattr(run_dev, "_dev_connector_binary", lambda: binary)
    monkeypatch.setattr(run_dev, "_dev_connector_launcher_binary", lambda: launcher)

    run_dev._register_dev_connector(manifest_dirs=[profile_dir])
    written = json.loads((profile_dir / f"{DEV_HOST}.json").read_text(encoding="utf-8"))
    assert written["name"] == DEV_HOST
    assert written["path"] == str(launcher) and Path(written["path"]).is_absolute()
    assert written["allowed_origins"] == [f"chrome-extension://{IDENTITY['dev_extension_id']}/"]
    assert (tmp_path / "dev-connector" / f"{DEV_HOST}.json").is_file()
    assert not (profile_dir / f"{IDENTITY['native_host_name']}.json").exists()  # never the production host name

    run_dev._clear_dev_connector(manifest_dirs=[profile_dir])
    assert not (profile_dir / f"{DEV_HOST}.json").exists()
    assert neighbour.read_text(encoding="utf-8") == '{"name": "com.example.other"}'  # third-party manifest untouched


def test_dev_registration_is_skipped_on_linux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(run_dev, "DEV_CONNECTOR_DIR", tmp_path / "dev-connector")
    run_dev._register_dev_connector(manifest_dirs=[tmp_path])
    assert list(tmp_path.iterdir()) == []
