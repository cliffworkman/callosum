"""Build the store-upload package for the Callosum Capture browser extension (#61 Phase 1 store-readiness).

Produces ONE zip from `app/desktop-shell/extension/`, intended for BOTH the Chrome Web Store and Microsoft Edge
Add-ons (they are two submissions of one package, each assigned its own extension ID by its own store). This is
the only sanctioned way to make that zip; the dev staging script (`extension/dev/build_dev_manifest.py`) makes a
different, key-pinned, host-name-patched copy for local testing and must never be uploaded.

What the package is, by construction:

* an ALLOWLIST of runtime files (`manifest.json`, `background.js`, `icons/*.png`); every other file in the
  extension directory must be explicitly classified as excluded, so a new file can never ship by accident;
* KEYLESS: no `key` (neither store accepts one on a first upload, and a repository manifest must never carry a
  production key) and no `update_url`; no private-key/signing material can be included, ever;
* manifest checks that the stores' own rules would otherwise surface late: Manifest V3, a valid version, a
  description within the 132-character Chrome Web Store limit, no "Chrome" in the name/description (Microsoft
  Edge certification requires rebranding those), and every file the manifest references present;
* REPRODUCIBLE: sorted entries, fixed timestamps and attributes, LF-normalized text, and *stored* (uncompressed)
  entries. Compression is deliberately not used: DEFLATE output depends on the zlib implementation (some Python
  builds ship zlib-ng), so the same input could hash differently across machines. The package is ~60 KB;
  uncompressed is fine, and two builds from the same input are byte-identical on any platform.

Usage: python app/desktop-shell/packaging/build_extension_package.py [--extension-dir DIR] [--out ZIP]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXTENSION_DIR = PROJECT_ROOT / "app" / "desktop-shell" / "extension"
DEFAULT_OUT_DIR = PROJECT_ROOT / ".local" / "extension-package"

# The files a user's browser needs. Anything not matching one of these (or EXCLUDED) stops the build.
RUNTIME_FILES = ("manifest.json", "background.js")
RUNTIME_ICON_DIR = "icons"
# Known, deliberately-not-shipped entries (top-level names): documentation, tests, and the dev tooling.
EXCLUDED = ("README.md", "background.test.mjs", "dev")
# Never allowed in a package, wherever they appear (signing / private-key material).
FORBIDDEN_SUFFIXES = (".pem", ".key", ".crx", ".p12", ".pfx")
TEXT_SUFFIXES = (".json", ".js", ".mjs", ".html", ".css")

DESCRIPTION_MAX = 132  # Chrome Web Store manifest `description` limit
_VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}$")
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)  # the earliest timestamp a zip can carry


class PackageError(ValueError):
    """The extension directory cannot be turned into a store package; the message says why."""


@dataclass(frozen=True)
class PackageResult:
    path: Path
    sha256: str
    files: tuple[str, ...]


def _classify(extension_dir: Path) -> list[str]:
    """Relative posix paths of the files to ship; raises on anything unclassified or forbidden."""
    shipped: list[str] = []
    problems: list[str] = []
    for path in sorted(extension_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(extension_dir).as_posix()
        top = relative.split("/", 1)[0]
        if top in EXCLUDED:
            continue
        if relative.lower().endswith(FORBIDDEN_SUFFIXES):
            problems.append(f"{relative}: signing/private-key material can never be packaged")
        elif relative in RUNTIME_FILES:
            shipped.append(relative)
        elif top == RUNTIME_ICON_DIR and relative.count("/") == 1 and relative.lower().endswith(".png"):
            shipped.append(relative)
        else:
            problems.append(f"{relative}: not classified -- add it to RUNTIME_FILES or EXCLUDED deliberately")
    for required in RUNTIME_FILES:
        if required not in shipped:
            problems.append(f"{required}: required runtime file is missing")
    if problems:
        raise PackageError("; ".join(problems))
    return shipped


def _manifest_references(manifest: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    service_worker = (manifest.get("background") or {}).get("service_worker")
    if service_worker:
        refs.append(service_worker)
    refs.extend((manifest.get("icons") or {}).values())
    refs.extend(((manifest.get("action") or {}).get("default_icon") or {}).values())
    return refs


def validate_manifest(manifest: dict[str, Any], shipped: list[str]) -> list[str]:
    """Every problem with this manifest for a first store submission; empty means acceptable."""
    problems: list[str] = []
    if manifest.get("manifest_version") != 3:
        problems.append("manifest_version must be 3")
    if "key" in manifest:
        problems.append(
            "manifest must not contain 'key' (no production key belongs in the repository or a first upload)"
        )
    if "update_url" in manifest:
        problems.append("manifest must not contain 'update_url' (the stores host updates)")

    version = manifest.get("version")
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        problems.append(f"version {version!r} must be 1-4 dot-separated integers")
    elif any(int(part) > 65535 for part in version.split(".")):
        problems.append(f"version {version!r} has a component above 65535")

    name, description = manifest.get("name"), manifest.get("description")
    for label, value in (("name", name), ("description", description)):
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{label} is required")
        elif "chrome" in value.lower():
            problems.append(f"{label} must not contain 'Chrome' (Microsoft Edge certification requires rebranding it)")
    if isinstance(description, str) and len(description) > DESCRIPTION_MAX:
        problems.append(f"description is {len(description)} chars; the limit is {DESCRIPTION_MAX}")

    for reference in _manifest_references(manifest):
        if reference not in shipped:
            problems.append(f"manifest references {reference!r}, which is not in the package")
    if "128" not in (manifest.get("icons") or {}):
        problems.append("icons must include a 128 entry (both stores require a 128x128 icon)")
    return problems


def _payload(extension_dir: Path, relative: str) -> bytes:
    data = (extension_dir / relative).read_bytes()
    if relative.endswith(TEXT_SUFFIXES):
        data = data.replace(b"\r\n", b"\n")  # a Windows checkout must hash the same as a Linux one
    return data


def build_package(extension_dir: Path, out_path: Path) -> PackageResult:
    shipped = _classify(extension_dir)
    manifest_bytes = _payload(extension_dir, "manifest.json")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as exc:
        raise PackageError(f"manifest.json is not valid JSON: {exc}") from exc
    problems = validate_manifest(manifest, shipped)
    if problems:
        raise PackageError("; ".join(problems))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative in sorted(shipped):
            info = zipfile.ZipInfo(relative, date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3  # normalize: the default differs between Windows and POSIX Pythons
            info.external_attr = 0o644 << 16
            archive.writestr(info, manifest_bytes if relative == "manifest.json" else _payload(extension_dir, relative))
    os.replace(tmp_path, out_path)
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    return PackageResult(path=out_path, sha256=digest, files=tuple(sorted(shipped)))


def default_out_path(extension_dir: Path) -> Path:
    manifest = json.loads((extension_dir / "manifest.json").read_text(encoding="utf-8"))
    return DEFAULT_OUT_DIR / f"callosum-capture-{manifest['version']}.zip"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--extension-dir", type=Path, default=EXTENSION_DIR)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    out_path = args.out or default_out_path(args.extension_dir)
    try:
        result = build_package(args.extension_dir, out_path)
    except PackageError as exc:
        raise SystemExit(f"extension package refused: {exc}") from exc
    print(f"built {result.path} ({len(result.files)} files)")
    for name in result.files:
        print(f"  {name}")
    print(f"sha256 {result.sha256}")


if __name__ == "__main__":
    main()
