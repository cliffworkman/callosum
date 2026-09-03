"""Identity and package the independently distributed desktop Python runtime.

The runtime ID covers every declared build input, not the Callosum application version. Packaging
produces a deterministic tar.gz, an exact resolved-package receipt, and a manifest that the release
workflow signs with the same Minisign key used by the Tauri updater.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import stat
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = Path(__file__).with_name("python-runtime-inputs.json")
TREE_DOMAIN = b"callosum-python-runtime-tree-v1\n"
DOWNLOAD_BASE = "https://github.com/cliffworkman/callosum/releases/download"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _identity_material(spec: dict, platform_key: str) -> dict:
    platform = spec["platforms"][platform_key]
    input_paths = [*spec["shared_inputs"], platform["build_script"]]
    input_hashes = {}
    for relative in sorted(set(input_paths)):
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"runtime identity input is missing: {relative}")
        input_hashes[relative] = _sha256_file(path)
    return {
        "schema_version": spec["schema_version"],
        "packaging_schema": spec["packaging_schema"],
        "platform": {key: value for key, value in platform.items() if key != "runtime_id"},
        "input_sha256": input_hashes,
    }


def runtime_id(spec: dict, platform_key: str) -> str:
    platform = spec["platforms"][platform_key]
    digest = hashlib.sha256(_canonical_json(_identity_material(spec, platform_key))).hexdigest()[:16]
    os_label = {"windows": "win", "macos": "macos", "linux": "linux"}[platform["os"]]
    return f"{os_label}-{platform['arch']}-py3.11-s{spec['schema_version']}-{digest}"


def _load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def verify_spec(spec: dict) -> None:
    for key, platform in spec["platforms"].items():
        expected = runtime_id(spec, key)
        if platform["runtime_id"] != expected:
            raise SystemExit(
                f"{key} runtime_id is stale: expected {expected}; run package_python_runtime.py update-ids"
            )


def update_ids() -> None:
    spec = _load_spec()
    for key, platform in spec["platforms"].items():
        platform["runtime_id"] = runtime_id(spec, key)
    SPEC_PATH.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")


def _safe_link_target(relative: PurePosixPath, target: str) -> None:
    target_path = PurePosixPath(target)
    if target_path.is_absolute() or "\\" in target:
        raise SystemExit(f"runtime symlink has an unsafe target: {relative} -> {target}")
    candidate = relative.parent.joinpath(target_path)
    depth = 0
    for part in candidate.parts:
        if part in ("", "."):
            continue
        if part == "..":
            depth -= 1
        else:
            depth += 1
        if depth < 0:
            raise SystemExit(f"runtime symlink escapes its root: {relative} -> {target}")


@dataclass(frozen=True)
class TreeEntry:
    relative: str
    kind: str
    size: int
    identity: str
    executable: bool

    def digest_line(self) -> bytes:
        return (f"{self.kind}\t{self.relative}\t{self.size}\t{self.identity}\t{1 if self.executable else 0}\n").encode()


def _tree_entries(root: Path) -> list[TreeEntry]:
    entries: list[TreeEntry] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            _safe_link_target(PurePosixPath(relative), target)
            entries.append(TreeEntry(relative, "link", 0, target, False))
            continue
        if not stat.S_ISREG(info.st_mode):
            raise SystemExit(f"unsupported runtime filesystem entry: {relative}")
        entries.append(
            TreeEntry(
                relative,
                "file",
                info.st_size,
                _sha256_file(path),
                bool(info.st_mode & 0o111),
            )
        )
    return entries


def _tree_digest(entries: list[TreeEntry]) -> str:
    digest = hashlib.sha256(TREE_DOMAIN)
    for entry in entries:
        digest.update(entry.digest_line())
    return digest.hexdigest()


def _tar_file(tar: tarfile.TarFile, root: Path, entry: TreeEntry) -> None:
    source = root / Path(entry.relative)
    name = f"python-runtime/{entry.relative}"
    info = tar.gettarinfo(str(source), arcname=name)
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    if entry.kind == "link":
        info.mode = 0o777
        tar.addfile(info)
        return
    info.mode = 0o755 if entry.executable else 0o644
    with source.open("rb") as stream:
        tar.addfile(info, stream)


def _write_archive(path: Path, root: Path, entries: list[TreeEntry]) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                root_info = tarfile.TarInfo("python-runtime")
                root_info.type = tarfile.DIRTYPE
                root_info.mode = 0o700
                root_info.mtime = 0
                tar.addfile(root_info)
                directories = sorted(
                    {
                        parent.as_posix()
                        for entry in entries
                        for parent in PurePosixPath(entry.relative).parents
                        if parent.as_posix() != "."
                    }
                )
                for directory in directories:
                    info = tarfile.TarInfo(f"python-runtime/{directory}")
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o700
                    info.mtime = 0
                    tar.addfile(info)
                for entry in entries:
                    _tar_file(tar, root, entry)


def _resolved_packages(runtime_root: Path, python_relative_path: str) -> tuple[list[str], str]:
    python = runtime_root / Path(python_relative_path)
    result = subprocess.run(
        [str(python), "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    packages = sorted(line.strip() for line in result.stdout.splitlines() if line.strip())
    digest = hashlib.sha256(("\n".join(packages) + "\n").encode()).hexdigest()
    return packages, digest


def package(platform_key: str, runtime_root: Path, output_dir: Path) -> None:
    spec = _load_spec()
    verify_spec(spec)
    platform = spec["platforms"][platform_key]
    expected_python = runtime_root / Path(platform["python_relative_path"])
    if not expected_python.is_file():
        raise SystemExit(f"runtime interpreter missing: {expected_python}")
    output_dir.mkdir(parents=True, exist_ok=True)
    identity = platform["runtime_id"]
    archive = output_dir / f"{identity}.tar.gz"
    entries = _tree_entries(runtime_root)
    _write_archive(archive, runtime_root, entries)
    packages, package_digest = _resolved_packages(runtime_root, platform["python_relative_path"])
    tag = f"python-runtime-{identity}"
    manifest = {
        "schema_version": spec["schema_version"],
        "packaging_schema": spec["packaging_schema"],
        "runtime_id": identity,
        "platform": platform["os"],
        "arch": platform["arch"],
        "python_version": platform["python_version"],
        "python_build": platform["python_build"],
        "python_relative_path": platform["python_relative_path"],
        "archive_url": f"{DOWNLOAD_BASE}/{tag}/{archive.name}",
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": _sha256_file(archive),
        "tree_sha256": _tree_digest(entries),
        "entry_count": len(entries),
        "unpacked_bytes": sum(entry.size for entry in entries),
        "resolved_packages_sha256": package_digest,
        "resolved_packages": packages,
        "input_identity": _identity_material(spec, platform_key),
        "glibc_min": platform.get("glibc_min"),
        "distribution_boundary": platform.get("distribution_boundary"),
    }
    (output_dir / "runtime-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(identity)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("update-ids")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--platform", choices=sorted(_load_spec()["platforms"]), required=False)
    identify = subparsers.add_parser("id")
    identify.add_argument("--platform", choices=sorted(_load_spec()["platforms"]), required=True)
    bundle = subparsers.add_parser("package")
    bundle.add_argument("--platform", choices=sorted(_load_spec()["platforms"]), required=True)
    bundle.add_argument("--runtime-root", type=Path, required=True)
    bundle.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "update-ids":
        update_ids()
    elif args.command == "verify":
        spec = _load_spec()
        verify_spec(spec)
        if args.platform:
            print(spec["platforms"][args.platform]["runtime_id"])
    elif args.command == "id":
        spec = _load_spec()
        verify_spec(spec)
        print(spec["platforms"][args.platform]["runtime_id"])
    else:
        package(args.platform, args.runtime_root.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
