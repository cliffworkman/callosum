from __future__ import annotations

import ipaddress
import os
import subprocess
from pathlib import Path

import pytest
from cryptography import x509
from fastapi.testclient import TestClient

from app.backend import app_settings
from app.backend import word_https_lifecycle as lifecycle
from app.backend.api import create_app


@pytest.fixture
def client(temp_db_url: str) -> TestClient:
    return TestClient(create_app(db_url=temp_db_url))


def _paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    # Exercise the supported Windows lifecycle consistently even when the test suite runs on Linux CI.
    monkeypatch.setattr(lifecycle.sys, "platform", "win32")
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "app-settings.json"))
    monkeypatch.setenv(lifecycle.WORD_HTTPS_DIR_ENV, str(tmp_path / "word-https"))
    monkeypatch.setattr(lifecycle, "_restrict_windows_acl", lambda _path: None)
    return lifecycle.certificate_paths()


def test_generated_certificate_is_localhost_leaf_and_reused(monkeypatch, tmp_path) -> None:
    cert_path, key_path = _paths(monkeypatch, tmp_path)
    first = lifecycle.ensure_certificate()
    first_bytes = cert_path.read_bytes(), key_path.read_bytes()
    second = lifecycle.ensure_certificate()
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    basic = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    usage = cert.extensions.get_extension_for_class(x509.KeyUsage).value

    assert first == second == (cert_path, key_path)
    assert first_bytes == (cert_path.read_bytes(), key_path.read_bytes())
    assert basic.ca is False and usage.key_cert_sign is False
    assert san.get_values_for_type(x509.DNSName) == ["localhost"]
    assert san.get_values_for_type(x509.IPAddress) == [ipaddress.ip_address("127.0.0.1")]
    assert b"PRIVATE KEY" in key_path.read_bytes()


def test_invalid_pair_is_replaced_and_private_write_is_bounded(monkeypatch, tmp_path) -> None:
    cert_path, key_path = _paths(monkeypatch, tmp_path)
    cert_path.parent.mkdir(parents=True)
    cert_path.write_text("not a certificate", encoding="utf-8")
    key_path.write_text("not a key", encoding="utf-8")

    lifecycle.ensure_certificate()

    assert lifecycle._certificate_valid(cert_path, key_path)
    assert cert_path.stat().st_size < 10_000
    assert key_path.stat().st_size < 10_000


def test_windows_trust_uses_fixed_current_user_commands(monkeypatch, tmp_path) -> None:
    cert_path, _ = _paths(monkeypatch, tmp_path)
    lifecycle.ensure_certificate()
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_run(script: str, *args: str):
        calls.append((script, args))
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(lifecycle, "_run_powershell", fake_run)
    lifecycle.install_certificate_trust(cert_path)
    assert lifecycle.certificate_trusted(cert_path)
    lifecycle.remove_certificate_trust(cert_path)

    assert "Import-Certificate" in calls[0][0]
    assert "Cert:\\CurrentUser\\Root" in calls[0][0]
    assert calls[0][1] == (str(cert_path),)
    assert "Test-Path" in calls[1][0]
    assert calls[1][1] == (lifecycle.certificate_thumbprint(cert_path),)
    assert "Remove-Item" in calls[2][0]
    assert all(str(cert_path) not in script for script, _args in calls)


def test_windows_private_key_acl_uses_fixed_script_and_separate_path(monkeypatch, tmp_path) -> None:
    key_path = tmp_path / "path with ' punctuation" / "localhost.key"
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_run(script: str, *args: str):
        calls.append((script, args))
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(lifecycle, "_run_powershell", fake_run)
    lifecycle._restrict_windows_acl(key_path)

    assert calls[0][1] == (str(key_path),)
    assert str(key_path) not in calls[0][0]
    assert "$env:CALLOSUM_WORD_HTTPS_PS_ARG_0" in calls[0][0]
    assert "SetAccessRuleProtection($true,$false)" in calls[0][0]


def test_powershell_value_uses_child_environment_not_command_or_parent(monkeypatch) -> None:
    captured = {}
    variable = "CALLOSUM_WORD_HTTPS_PS_ARG_0"
    monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("WINDIR", r"C:\Windows")

    def fake_run(args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)
    lifecycle._run_powershell("fixed-command", "path with ' punctuation")

    assert captured["args"][-1] == "fixed-command"
    assert "path with ' punctuation" not in captured["args"]
    assert captured["kwargs"]["env"][variable] == "path with ' punctuation"
    assert captured["kwargs"]["env"]["PSModulePath"] == str(
        Path(r"C:\Windows") / "System32" / "WindowsPowerShell" / "v1.0" / "Modules"
    )
    assert variable not in os.environ


def test_macos_trust_is_login_keychain_scoped_without_admin_domain(monkeypatch, tmp_path) -> None:
    cert_path, _ = _paths(monkeypatch, tmp_path)
    lifecycle.ensure_certificate()
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(lifecycle.sys, "platform", "darwin")
    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)
    lifecycle.install_certificate_trust(cert_path)
    lifecycle.remove_certificate_trust(cert_path)

    assert calls[0][:3] == [lifecycle._MAC_SECURITY, "add-trusted-cert", "-r"]
    assert "-d" not in calls[0]
    assert str(lifecycle._mac_keychain()) in calls[0]
    assert calls[1] == [lifecycle._MAC_SECURITY, "remove-trusted-cert", str(cert_path)]


def test_enable_persists_only_after_verified_trust(monkeypatch, tmp_path) -> None:
    _paths(monkeypatch, tmp_path)
    monkeypatch.setattr(lifecycle, "install_certificate_trust", lambda _path: None)
    monkeypatch.setattr(lifecycle, "certificate_trusted", lambda _path: True)

    result = lifecycle.enable()

    assert result.enabled and result.certificate_ready and result.trusted
    assert app_settings.load_settings()["word_https_enabled"] is True


def test_enable_failure_does_not_publish_opt_in(monkeypatch, tmp_path) -> None:
    _paths(monkeypatch, tmp_path)

    def fail(_path: Path) -> None:
        raise lifecycle.WordHttpsError("trust failed")

    monkeypatch.setattr(lifecycle, "install_certificate_trust", fail)
    with pytest.raises(lifecycle.WordHttpsError, match="trust failed"):
        lifecycle.enable()
    assert app_settings.load_settings().get("word_https_enabled") is not True


def test_disable_fails_closed_when_trust_remains(monkeypatch, tmp_path) -> None:
    cert_path, key_path = _paths(monkeypatch, tmp_path)
    lifecycle.ensure_certificate()
    app_settings.save_settings({"word_https_enabled": True})
    monkeypatch.setattr(lifecycle, "certificate_trusted", lambda _path: True)
    monkeypatch.setattr(lifecycle, "remove_certificate_trust", lambda _path: None)

    with pytest.raises(lifecycle.WordHttpsError, match="still trusted"):
        lifecycle.disable()

    assert app_settings.load_settings()["word_https_enabled"] is True
    assert cert_path.exists() and key_path.exists()


def test_disable_removes_trust_files_and_opt_in(monkeypatch, tmp_path) -> None:
    cert_path, key_path = _paths(monkeypatch, tmp_path)
    lifecycle.ensure_certificate()
    app_settings.save_settings({"word_https_enabled": True})
    trusted = True

    def is_trusted(_path: Path) -> bool:
        return trusted

    def remove_trust(_path: Path) -> None:
        nonlocal trusted
        trusted = False

    monkeypatch.setattr(lifecycle, "certificate_trusted", is_trusted)
    monkeypatch.setattr(lifecycle, "remove_certificate_trust", remove_trust)

    result = lifecycle.disable()

    assert result.enabled is False
    assert not cert_path.exists() and not key_path.exists()
    assert app_settings.load_settings()["word_https_enabled"] is False


def test_status_and_api_never_expose_paths_or_private_material(client, monkeypatch) -> None:
    safe = lifecycle.WordHttpsStatus(True, True, True, True, "win32", "Word support is enabled.")
    monkeypatch.setattr(lifecycle, "status", lambda: safe)
    response = client.get("/word-https/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert "path" not in str(payload).lower()
    assert "private" not in str(payload).lower()


def test_trust_lifecycle_routes_are_local_only(client) -> None:
    response = client.get("/word-https/status", headers={"x-forwarded-for": "203.0.113.4"})
    assert response.status_code == 403
    assert response.json()["detail"] == "This system action is available only on this machine."


def test_trust_mutation_requires_settings_csrf_header(client) -> None:
    response = client.post("/word-https/enable")
    assert response.status_code == 403
    assert response.json()["detail"] == "Confirm this system action from Callosum Settings."


def test_cross_origin_preflight_cannot_authorize_trust_mutation(client) -> None:
    response = client.options(
        "/word-https/enable",
        headers={
            "origin": "https://attacker.example",
            "access-control-request-method": "POST",
            "access-control-request-headers": "x-callosum-local-action",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_api_reports_lifecycle_errors_without_secret_detail(client, monkeypatch) -> None:
    def fail():
        raise lifecycle.WordHttpsError("The operating system did not trust the certificate.")

    monkeypatch.setattr(lifecycle, "enable", fail)
    response = client.post("/word-https/enable", headers={"x-callosum-local-action": "settings-ui-v1"})
    assert response.status_code == 422
    assert response.json()["detail"] == "The operating system did not trust the certificate."
