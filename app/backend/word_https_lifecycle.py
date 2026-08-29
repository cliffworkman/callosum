"""Opt-in per-user TLS certificate lifecycle for the packaged desktop Word companion.

The certificate is a localhost-only *leaf*, never a CA: trusting it authorizes this exact key for
``localhost``/``127.0.0.1`` but cannot turn a leaked private key into an arbitrary-host signing key. Trust
mutation is explicit and current-user scoped. Tauri owns the HTTPS process; this module owns only its files and
the user's enable/trust decision.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import os
import stat

# Fixed OS trust/ACL executables only; every invocation is direct argv with no shell.
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.backend import app_settings

CERT_FILENAME = "localhost.crt"
KEY_FILENAME = "localhost.key"
WORD_HTTPS_DIR_ENV = "CALLOSUM_WORD_HTTPS_DIR"
_VALID_DAYS = 365
_POWERSHELL_TIMEOUT = 30
_MAC_SECURITY = "/usr/bin/security"


class WordHttpsError(RuntimeError):
    """A user-actionable certificate lifecycle failure."""


@dataclass(frozen=True)
class WordHttpsStatus:
    supported: bool
    enabled: bool
    certificate_ready: bool
    trusted: bool
    platform: str
    detail: str


def word_https_dir() -> Path:
    override = os.getenv(WORD_HTTPS_DIR_ENV)
    if override:
        return Path(override)
    return app_settings.settings_path().parent / "word-https"


def certificate_paths() -> tuple[Path, Path]:
    root = word_https_dir()
    return root / CERT_FILENAME, root / KEY_FILENAME


def _supported_platform() -> bool:
    return sys.platform.startswith("win") or sys.platform == "darwin"


def _enabled() -> bool:
    return bool(app_settings.load_settings().get("word_https_enabled", False))


def _set_enabled(enabled: bool) -> None:
    data = app_settings.load_settings()
    data["word_https_enabled"] = bool(enabled)
    app_settings.save_settings(data)


def _write_private(path: Path, payload: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(payload)
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    if sys.platform.startswith("win"):
        _restrict_windows_acl(path)


def _write_public(path: Path, payload: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(payload)
    os.replace(tmp, path)


def _run_powershell(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    # A packaged app may itself be launched from PowerShell 7, whose PSModulePath is incompatible with the
    # inbox Windows PowerShell 5 process used here. Pin the inbox module root needed by the fixed PKI/ACL calls.
    windows_root = Path(child_env.get("WINDIR", r"C:\Windows"))
    child_env["PSModulePath"] = str(windows_root / "System32" / "WindowsPowerShell" / "v1.0" / "Modules")
    powershell_exe = windows_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    for index, value in enumerate(args):
        child_env[f"CALLOSUM_WORD_HTTPS_PS_ARG_{index}"] = value
    # Fixed executable/command; dynamic values exist only in this child's environment.
    return subprocess.run(  # nosec B603
        [str(powershell_exe), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=_POWERSHELL_TIMEOUT,
        check=False,
        env=child_env,
    )


def _restrict_windows_acl(path: Path) -> None:
    # The command text is fixed; the generated app-owned path is a child-only env value, never interpolated.
    script = (
        "$p=$env:CALLOSUM_WORD_HTTPS_PS_ARG_0; $ErrorActionPreference='Stop'; $acl=Get-Acl -LiteralPath $p; "
        "$acl.SetAccessRuleProtection($true,$false); "
        "$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User; "
        "$rule=New-Object System.Security.AccessControl.FileSystemAccessRule($sid,'FullControl','Allow'); "
        "$acl.SetAccessRule($rule); Set-Acl -LiteralPath $p -AclObject $acl; "
        "$after=Get-Acl -LiteralPath $p; $rules=@($after.Access); "
        "$name=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name; "
        "if ($after.AreAccessRulesProtected -ne $true -or $rules.Count -ne 1 "
        "-or $rules[0].IdentityReference.Value -ne $name) { exit 2 }"
    )
    result = _run_powershell(script, str(path))
    if result.returncode != 0:
        raise WordHttpsError("Callosum could not restrict the local Word certificate key to your account.")


def _certificate_valid(cert_path: Path, key_path: Path) -> bool:
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        basic = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        now = dt.datetime.now(dt.UTC)
        return bool(
            cert.not_valid_before_utc <= now < cert.not_valid_after_utc
            and cert.not_valid_after_utc - now > dt.timedelta(days=1)
            and basic.ca is False
            and san.get_values_for_type(x509.DNSName) == ["localhost"]
            and san.get_values_for_type(x509.IPAddress) == [ipaddress.ip_address("127.0.0.1")]
            and key.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            == cert.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
    except (OSError, ValueError, TypeError, x509.ExtensionNotFound):
        return False


def ensure_certificate() -> tuple[Path, Path]:
    """Return a valid localhost leaf/key pair, generating it atomically when absent or invalid."""
    if not _supported_platform():
        raise WordHttpsError("Managed Word support is currently available on Windows and macOS only.")
    cert_path, key_path = certificate_paths()
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    if cert_path.is_file() and key_path.is_file() and _certificate_valid(cert_path, key_path):
        if sys.platform.startswith("win"):
            _restrict_windows_acl(key_path)
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Callosum localhost")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=_VALID_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    _write_private(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ),
    )
    _write_public(cert_path, cert.public_bytes(serialization.Encoding.PEM))
    if not _certificate_valid(cert_path, key_path):
        raise WordHttpsError("Callosum generated an invalid local Word certificate and refused to enable it.")
    return cert_path, key_path


def certificate_thumbprint(cert_path: Path) -> str:
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    # Windows certificate stores use the SHA-1 thumbprint as a lookup identity, not as a trust primitive.
    return cert.fingerprint(hashes.SHA1()).hex().upper()  # nosec B303


def _windows_trusted(cert_path: Path) -> bool:
    script = (
        "$thumbprint=$env:CALLOSUM_WORD_HTTPS_PS_ARG_0; "
        "if (Test-Path -LiteralPath ('Cert:\\CurrentUser\\Root\\'+$thumbprint)) { exit 0 } else { exit 3 }"
    )
    return _run_powershell(script, certificate_thumbprint(cert_path)).returncode == 0


def _mac_keychain() -> Path:
    return Path.home() / "Library" / "Keychains" / "login.keychain-db"


def certificate_trusted(cert_path: Path) -> bool:
    if not cert_path.is_file():
        return False
    if sys.platform.startswith("win"):
        return _windows_trusted(cert_path)
    if sys.platform == "darwin":
        # Fixed OS executable and direct argv.
        result = subprocess.run(  # nosec B603
            [_MAC_SECURITY, "verify-cert", "-c", str(cert_path), "-p", "ssl", "-n", "localhost"],
            capture_output=True,
            text=True,
            timeout=_POWERSHELL_TIMEOUT,
            check=False,
        )
        return result.returncode == 0
    return False


def install_certificate_trust(cert_path: Path) -> None:
    if sys.platform.startswith("win"):
        script = (
            "$p=$env:CALLOSUM_WORD_HTTPS_PS_ARG_0; "
            "$cert=Import-Certificate -FilePath $p -CertStoreLocation 'Cert:\\CurrentUser\\Root'; "
            "if ($null -eq $cert) { exit 1 }"
        )
        result = _run_powershell(script, str(cert_path))
    elif sys.platform == "darwin":
        # Fixed OS executable and direct argv.
        result = subprocess.run(  # nosec B603
            [
                _MAC_SECURITY,
                "add-trusted-cert",
                "-r",
                "trustRoot",
                "-k",
                str(_mac_keychain()),
                str(cert_path),
            ],
            capture_output=True,
            text=True,
            timeout=_POWERSHELL_TIMEOUT,
            check=False,
        )
    else:
        raise WordHttpsError("Managed Word support is currently available on Windows and macOS only.")
    if result.returncode != 0:
        raise WordHttpsError("The operating system did not trust Callosum's local Word certificate.")


def remove_certificate_trust(cert_path: Path) -> None:
    if not cert_path.is_file():
        return
    if sys.platform.startswith("win"):
        script = (
            "$thumbprint=$env:CALLOSUM_WORD_HTTPS_PS_ARG_0; $p='Cert:\\CurrentUser\\Root\\'+$thumbprint; "
            "if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force -ErrorAction Stop }"
        )
        result = _run_powershell(script, certificate_thumbprint(cert_path))
    elif sys.platform == "darwin":
        # Fixed OS executable and direct argv.
        result = subprocess.run(  # nosec B603
            [_MAC_SECURITY, "remove-trusted-cert", str(cert_path)],
            capture_output=True,
            text=True,
            timeout=_POWERSHELL_TIMEOUT,
            check=False,
        )
    else:
        raise WordHttpsError("Managed Word support is currently available on Windows and macOS only.")
    if result.returncode != 0:
        raise WordHttpsError("Callosum could not remove its local Word certificate from your trust store.")


def enable() -> WordHttpsStatus:
    cert_path, _ = ensure_certificate()
    install_certificate_trust(cert_path)
    if not certificate_trusted(cert_path):
        raise WordHttpsError("Certificate installation completed, but Callosum could not verify current-user trust.")
    _set_enabled(True)
    return status()


def disable() -> WordHttpsStatus:
    cert_path, key_path = certificate_paths()
    if cert_path.is_file() and certificate_trusted(cert_path):
        remove_certificate_trust(cert_path)
        if certificate_trusted(cert_path):
            raise WordHttpsError("The local Word certificate is still trusted; Callosum left its files for retry.")
    for path in (key_path, cert_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise WordHttpsError(
                "Word support was disabled, but a local certificate file could not be removed."
            ) from exc
    _set_enabled(False)
    return status()


def status() -> WordHttpsStatus:
    cert_path, key_path = certificate_paths()
    supported = _supported_platform()
    ready = cert_path.is_file() and key_path.is_file() and _certificate_valid(cert_path, key_path)
    trusted = supported and ready and certificate_trusted(cert_path)
    enabled = _enabled()
    if not supported:
        detail = "Managed Word support is currently available on Windows and macOS only."
    elif enabled and ready and trusted:
        detail = "Word support is enabled. Restart Callosum if the HTTPS companion is not already running."
    elif enabled:
        detail = "Word support is enabled but its certificate is incomplete or untrusted; disable and enable it again."
    else:
        detail = "Word support is off. Enabling it trusts a localhost-only certificate for your account."
    return WordHttpsStatus(supported, enabled, ready, trusted, sys.platform, detail)
