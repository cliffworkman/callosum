"""connector/identity.json is the single source of truth for browser-capture identity (#61 Phase 2,
steering point 1) -- these tests guard the things that would otherwise silently drift: the dev
extension id against the key it's derived from, the extension's hardcoded host-name constant
against identity.json, the NSIS generator's output against identity.json, and the extension's
permission set against creep. Nothing here talks to a browser or a real store.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_PATH = ROOT / "app" / "desktop-shell" / "connector" / "identity.json"
EXTENSION_DIR = ROOT / "app" / "desktop-shell" / "extension"
GENERATOR_PATH = ROOT / "app" / "desktop-shell" / "packaging" / "generate_connector_nsh.py"

_EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")


def _identity() -> dict:
    return json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))


def _chrome_extension_id(public_key_der_b64: str) -> str:
    der = base64.b64decode(public_key_der_b64)
    digest = hashlib.sha256(der).digest()[:16]
    return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0x0F)) for b in digest)


def test_identity_json_has_the_required_shape() -> None:
    identity = _identity()
    assert identity["protocol_version"] == 1
    assert isinstance(identity["native_host_name"], str) and identity["native_host_name"]
    assert isinstance(identity["dev_native_host_name"], str) and identity["dev_native_host_name"]
    assert identity["native_host_name"] != identity["dev_native_host_name"]
    assert isinstance(identity["production_extension_ids"], list)
    for ext_id in identity["production_extension_ids"]:
        assert _EXTENSION_ID_RE.match(ext_id), f"{ext_id!r} is not a valid 32-char Chrome/Edge extension id"


def test_production_extension_ids_are_deliberately_unpublished() -> None:
    """Guards against silently promoting a placeholder into the wire/install contract.

    If this ever legitimately changes (the extension gets published), that's a real, deliberate
    change to make by hand -- not something a refactor should flip by accident. See identity.json's
    own `_production_extension_ids_comment` for the full reasoning.
    """
    identity = _identity()
    assert identity["production_extension_ids"] == []


def test_dev_extension_id_matches_its_own_public_key() -> None:
    """The id isn't just a random-looking string -- it's REQUIRED to be exactly what Chrome/Edge
    derive from dev_extension_public_key_base64, since that's what makes 'Load unpacked' with this
    key produce this id in the first place."""
    identity = _identity()
    assert _chrome_extension_id(identity["dev_extension_public_key_base64"]) == identity["dev_extension_id"]
    assert identity["dev_extension_id"] not in identity["production_extension_ids"]


def test_extension_manifest_matches_the_minimal_permission_set() -> None:
    """Guards against permission creep: exactly this set, nothing broader, ever (README.md's table)."""
    manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["permissions"]) == {"nativeMessaging", "activeTab", "scripting"}
    assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
    assert "key" not in manifest, "no real production extension id exists yet -- see identity.json"
    for forbidden in ("cookies", "webRequest", "<all_urls>", "tabs"):
        assert forbidden not in manifest.get("permissions", []) + manifest.get("host_permissions", [])


def test_background_js_native_host_name_matches_identity_json() -> None:
    identity = _identity()
    background = (EXTENSION_DIR / "background.js").read_text(encoding="utf-8")
    assert f'const NATIVE_HOST_NAME = "{identity["native_host_name"]}";' in background


def test_generator_output_matches_identity_json(tmp_path: Path) -> None:
    """Runs the real generator against a copy of identity.json and checks its emitted .nsh."""
    fake_root = tmp_path / "root"
    (fake_root / "app" / "desktop-shell" / "connector").mkdir(parents=True)
    (fake_root / "app" / "desktop-shell" / "src-tauri" / "windows").mkdir(parents=True)
    identity = _identity()
    identity["native_host_name"] = "org.example.testhost"
    identity["production_extension_ids"] = ["a" * 32, "b" * 32]
    (fake_root / "app" / "desktop-shell" / "connector" / "identity.json").write_text(
        json.dumps(identity), encoding="utf-8"
    )

    script = GENERATOR_PATH.read_text(encoding="utf-8").replace(
        "PROJECT_ROOT = Path(__file__).resolve().parents[3]", f"PROJECT_ROOT = Path(r'{fake_root}')"
    )
    patched = tmp_path / "generate_connector_nsh.py"
    patched.write_text(script, encoding="utf-8")
    subprocess.run([sys.executable, str(patched)], check=True, cwd=tmp_path)

    generated = (
        fake_root / "app" / "desktop-shell" / "src-tauri" / "windows" / "connector-identity.generated.nsh"
    ).read_text(encoding="utf-8")
    assert "!define CONNECTOR_NATIVE_HOST_NAME org.example.testhost" in generated
    assert '"chrome-extension://' + "a" * 32 + '/"' in generated
    assert '"chrome-extension://' + "b" * 32 + '/"' in generated


def test_generator_rejects_a_malformed_extension_id(tmp_path: Path) -> None:
    fake_root = tmp_path / "root"
    (fake_root / "app" / "desktop-shell" / "connector").mkdir(parents=True)
    identity = _identity()
    identity["production_extension_ids"] = ["not-a-valid-id"]
    (fake_root / "app" / "desktop-shell" / "connector" / "identity.json").write_text(
        json.dumps(identity), encoding="utf-8"
    )

    script = GENERATOR_PATH.read_text(encoding="utf-8").replace(
        "PROJECT_ROOT = Path(__file__).resolve().parents[3]", f"PROJECT_ROOT = Path(r'{fake_root}')"
    )
    patched = tmp_path / "generate_connector_nsh.py"
    patched.write_text(script, encoding="utf-8")
    result = subprocess.run([sys.executable, str(patched)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "not a valid 32-char" in result.stderr
