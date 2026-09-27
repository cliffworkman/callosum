"""Embed an exact, key-pinned manual preview separately from the keyless store package."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from build_extension_package import _classify, _payload, validate_manifest
from connector_identity import load_identity, validate_identity

ROOT = Path(__file__).resolve().parents[3]
SHELL = ROOT / "app/desktop-shell"
OUT = SHELL / "connector/preview-package.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def package(shell: Path = SHELL) -> dict:
    identity = load_identity(shell / "connector/identity.json")
    require(not validate_identity(identity), "Invalid connector identity")
    extension = shell / "extension"
    files = _classify(extension)
    require(
        set(files) == {"manifest.json", "background.js", *(f"icons/icon{s}.png" for s in (16, 32, 48, 128))},
        "Unexpected preview inventory",
    )
    require(
        not extension.is_symlink() and not any(p.is_symlink() for p in extension.rglob("*")),
        "Preview sources contain a link",
    )
    manifest = json.loads(_payload(extension, "manifest.json"))
    require(not validate_manifest(manifest, files), "Invalid source manifest")
    manifest.update(
        name="Callosum Capture (early access)",
        version=identity["preview_extension_version"],
        key=identity["preview_extension_public_key_base64"],
        options_ui={"page": "options.html", "open_in_tab": True},
    )
    payload = {name: _payload(extension, name) for name in files}
    payload["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    options = shell / "preview-extension"
    require(
        not options.is_symlink() and {p.name for p in options.iterdir()} == {"options.html", "options.js"},
        "Unexpected Options inventory",
    )
    for p in options.iterdir():
        require(p.is_file() and not p.is_symlink(), "Options sources must be regular files")
        payload[p.name] = p.read_bytes().replace(b"\r\n", b"\n")
    entries = {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "base64": base64.b64encode(data).decode()}
        for name, data in sorted(payload.items())
    }
    digest = hashlib.sha256(
        json.dumps({k: v["sha256"] for k, v in entries.items()}, sort_keys=True).encode()
    ).hexdigest()
    return {
        "version": identity["preview_extension_version"],
        "extension_id": identity["preview_extension_id"],
        "sha256": digest,
        "files": entries,
    }


if __name__ == "__main__":
    import sys

    text = json.dumps(package(), indent=2) + "\n"
    if "--check" in sys.argv:
        require(OUT.read_text(encoding="utf-8") == text, "Regenerate the embedded preview package")
    else:
        OUT.write_text(text, encoding="utf-8")
