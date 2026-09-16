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

    print(f"dev extension staged at {DEST}")
    print(f"expected unpacked id: {identity['dev_extension_id']}")


if __name__ == "__main__":
    main()
