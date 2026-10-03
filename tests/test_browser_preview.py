"""Preview package/release policy and opt-out contracts; no claim of real-browser acceptance."""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "app/desktop-shell"
sys.path.insert(0, str(SHELL / "packaging"))
builder = importlib.import_module("build_preview_package")
release = importlib.import_module("check_capture_release")


def identity():
    return json.loads((SHELL / "connector/identity.json").read_text(encoding="utf-8"))


def test_preview_is_separate_exact_reproducible_package():
    bundle = builder.package()
    assert bundle == json.loads(builder.OUT.read_text(encoding="utf-8"))
    assert bundle == builder.package()
    assert set(bundle["files"]) == {
        "manifest.json",
        "background.js",
        "options.html",
        "options.js",
        *(f"icons/icon{s}.png" for s in [16, 32, 48, 128]),
    }
    for entry in bundle["files"].values():
        assert hashlib.sha256(base64.b64decode(entry["base64"])).hexdigest() == entry["sha256"]
    manifest = json.loads(base64.b64decode(bundle["files"]["manifest.json"]["base64"]))
    assert manifest["version"] == bundle["version"]
    assert "early access" in manifest["name"]
    assert "update_url" not in manifest
    assert "key" not in json.loads((SHELL / "extension/manifest.json").read_text())
    key = base64.b64decode(manifest["key"])
    from cryptography.hazmat.primitives.serialization import load_der_public_key

    assert load_der_public_key(key).key_size == 2048
    derived = "".join(chr(97 + int(c, 16)) for c in hashlib.sha256(key).hexdigest()[:32])
    assert derived == bundle["extension_id"] != identity()["dev_extension_id"]
    assert derived not in identity()["production_extension_ids"]
    assert set(manifest["permissions"]) == {"activeTab", "nativeMessaging", "scripting"}


@pytest.mark.parametrize(
    "name", ["extension/unexpected.exe", "preview-extension/private.pem", "extension/icons/private.key"]
)
def test_unexpected_files_refuse_packaging(tmp_path, name):
    for folder in ["extension", "preview-extension", "connector"]:
        shutil.copytree(SHELL / folder, tmp_path / folder)
    (tmp_path / name).write_text("never package this")
    with pytest.raises(ValueError):
        builder.package(tmp_path)


def test_store_policy_and_tag_ratchet_are_not_bypassed_by_preview():
    preview = identity()
    assert release.validate_release(preview) == []
    store = {
        **preview,
        "released": True,
        "release_channel": "store",
        "production_extension_ids": ["c" * 32, "e" * 32],
        "store_extension_ids": {"chrome": "c" * 32, "edge": "e" * 32},
    }
    assert release.validate_release(store) == []
    assert release.validate_release({**store, "store_extension_ids": {"chrome": "c" * 32}})
    assert release.validate_release({**preview, "released": True})
    assert release.validate_release(preview, [store])
    assert release.validate_release({**store, "production_extension_ids": ["c" * 32]}, [store])
    assert release.validate_release(store, [store]) == []
    inputs = {"platforms": {"macos-x86_64": {"runtime_id": next(iter(release.BROKEN_INTEL_RUNTIMES))}}}
    assert release.validate_runtime(inputs)


def test_opt_out_revokes_existing_preview_token_without_revoking_store_token(tmp_path, monkeypatch):
    from app.backend.capture import pairing

    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pairing, "read_pairing_secret", lambda: "local-test-secret")
    pairing.clear_sessions()
    root = tmp_path / "browser-capture-preview"
    root.mkdir()
    state = root / "enabled.json"

    def write(enabled, generation):
        state.write_text(json.dumps({"enabled": enabled, "generation": generation}))

    try:
        assert pairing.issue_session("local-test-secret", preview_generation="a" * 64) is None
        write(True, "a" * 64)
        token = pairing.issue_session("local-test-secret", preview_generation="a" * 64)
        regular = pairing.issue_session("local-test-secret")
        assert token and pairing.session_is_valid(token)
        write(False, "b" * 64)
        assert not pairing.session_is_valid(token)
        assert pairing.session_is_valid(regular)
        write(True, "c" * 64)
        assert not pairing.session_is_valid(token)
        assert pairing.issue_session("local-test-secret", preview_generation="a" * 64) is None
        assert pairing.issue_session("local-test-secret", preview_generation="c" * 64)
        for malformed in ["[]", "null", '{"enabled":true,"generation":5}', "bad json"]:
            state.write_text(malformed)
            assert pairing._preview_generation() is None
    finally:
        pairing.clear_sessions()
