"""Reject builder-local dylib dependencies and record Mach-O linkage before signing a runtime.

LC_ID_DYLIB is a library's identity, not a dependency. Record it separately. Unused LC_RPATH
entries occur in upstream wheels; record those too, without confusing them with required loads.
This gate detects absolute non-system dependencies (#106), not every dyld resolution failure
or a supported macOS floor. The real backend smoke and clean-Mac acceptance remain necessary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

MACHO_MAGIC = {
    bytes.fromhex(value)
    for value in ("feedface", "cefaedfe", "feedfacf", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca")
}
LOAD_COMMANDS = {
    "LC_LOAD_DYLIB",
    "LC_LOAD_WEAK_DYLIB",
    "LC_REEXPORT_DYLIB",
    "LC_LAZY_LOAD_DYLIB",
    "LC_LOAD_UPWARD_DYLIB",
}


def parse_load_commands(output: str) -> list[dict[str, str]]:
    entries = []
    command = ""
    architecture = "native"
    for line in output.splitlines():
        arch = re.search(r"\(architecture ([^)]+)\):$", line)
        if arch:
            architecture = arch.group(1)
        stripped = line.strip()
        if stripped.startswith("cmd "):
            command = stripped[4:]
        field = "path" if command == "LC_RPATH" else "name"
        if command in LOAD_COMMANDS | {"LC_ID_DYLIB", "LC_RPATH"} and stripped.startswith(field + " "):
            value = stripped[len(field) + 1 :].rsplit(" (offset ", 1)[0]
            entries.append({"architecture": architecture, "command": command, "path": value})
    return entries


def non_system_absolute(path: str) -> bool:
    return path.startswith("/") and not path.startswith(("/usr/lib/", "/System/Library/"))


def invalid_dependencies(entries: list[dict[str, str]]) -> list[str]:
    invalid = []
    for entry in entries:
        if entry["command"] not in LOAD_COMMANDS:
            continue
        path = entry["path"]
        if non_system_absolute(path) or not path.startswith(("/", "@rpath/", "@loader_path/", "@executable_path/")):
            invalid.append(path)
    return invalid


def inspect_runtime(root: Path) -> dict:
    records = []
    violations = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) not in MACHO_MAGIC:
                continue
        output = subprocess.run(
            ["otool", "-arch", "all", "-l", str(path)], check=True, capture_output=True, text=True
        ).stdout
        entries = parse_load_commands(output)
        relative = path.relative_to(root).as_posix()
        records.append(
            {"file": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "load_commands": entries}
        )
        violations.extend({"file": relative, "dependency": dep} for dep in invalid_dependencies(entries))
    if not records:
        raise ValueError("no Mach-O binaries found in runtime")
    return {"schema_version": 1, "binaries": records, "violations": violations}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime_root", type=Path)
    args = parser.parse_args()
    root = args.runtime_root.resolve(strict=True)
    report = inspect_runtime(root)
    # Included in the archive/tree hash and therefore covered by the signed runtime manifest.
    (root / "native-dependencies.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for violation in report["violations"]:
        print(f"FAIL: {violation['file']} requires non-portable {violation['dependency']}")
    if report["violations"]:
        return 1
    print(f"OK: {len(report['binaries'])} Mach-O files; no absolute non-system dylib dependencies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
