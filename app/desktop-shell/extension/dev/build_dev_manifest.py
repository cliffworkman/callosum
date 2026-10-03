"""Build a locally-loadable dev copy of the extension with the dev signing key pinned.

Chrome/Edge derive an UNPACKED extension's ID from its absolute filesystem path when manifest.json
has no `key` field -- which differs per checkout and per CI runner. Pinning
connector/identity.json's `dev_extension_public_key_base64` makes "Load unpacked" produce the SAME
32-character ID everywhere: the id `tools/run_dev.py` registers under
`org.callosum.connector.dev`'s `allowed_origins` (never the production manifest's).

Usage:
    python app/desktop-shell/extension/dev/build_dev_manifest.py
    Then in chrome://extensions or edge://extensions: Developer mode -> Load unpacked -> the
    printed directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC = PROJECT_ROOT / "app" / "desktop-shell" / "extension"
IDENTITY_PATH = PROJECT_ROOT / "app" / "desktop-shell" / "connector" / "identity.json"
DEST = PROJECT_ROOT / ".local" / "dev-extension"


def main() -> None:
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))

    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(SRC, DEST, ignore=shutil.ignore_patterns("dev", "README.md"))

    manifest_path = DEST / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["key"] = identity["dev_extension_public_key_base64"]
    manifest["name"] = f"{manifest['name']} (dev)"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # background.js hardcodes the PRODUCTION native host name -- correctly so, since that constant
    # ships as-is to real users. But that means an unpatched dev copy calls
    # chrome.runtime.sendNativeMessage("org.callosum.connector", ...), which nothing is ever
    # registered under in a dev/test environment (_register_dev_connector only registers
    # dev_native_host_name) -- a real Edge click-through run found this makes the dev extension
    # ALWAYS report "host_unavailable", with no native-messaging attempt ever reaching the
    # connector host at all. Rewrite the constant in this STAGED COPY ONLY.
    background_path = DEST / "background.js"
    background = background_path.read_text(encoding="utf-8")
    production_host_line = f'const NATIVE_HOST_NAME = "{identity["native_host_name"]}";'
    if production_host_line not in background:
        raise SystemExit(
            f"expected to find {production_host_line!r} in background.js -- constant changed or "
            "already patched; update this script"
        )
    background = background.replace(
        production_host_line,
        f'const NATIVE_HOST_NAME = "{identity["dev_native_host_name"]}";',
    )
    background_path.write_text(background, encoding="utf-8")

    print(f"dev extension staged at {DEST}")
    print(f"expected unpacked id: {identity['dev_extension_id']}")
    print(f"native host name patched to: {identity['dev_native_host_name']}")


if __name__ == "__main__":
    main()
