"""Developer-only, one-shot legacy EndNote MyISAM bootstrap probe.

This module is intentionally outside production paths. It validates and copies a bounded
legacy ``.enlx`` archive, then runs a developer-supplied MariaDB executable in bootstrap
mode. It does not import papers, ingest PDFs, expose an API, or bundle/download a runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterable, Sequence

MAX_ARCHIVE_BYTES = 4 * 1024**3
MAX_ENTRIES = 65_535
MAX_ENTRY_BYTES = 512 * 1024**2
MAX_EXPANDED_BYTES = 6 * 1024**3
MAX_COMPRESSION_RATIO = 1_000
MAX_ENGINE_LOG_BYTES = 1024**2
MAX_RECEIPT_BYTES = 64 * 1024
MAX_RUNTIME_FILES = 512
MAX_RUNTIME_BYTES = 512 * 1024**2
MAX_BOOTSTRAP_SQL_BYTES = 64 * 1024
COPY_CHUNK_BYTES = 1024**2

PROFILE = "endnote-x1-x7-myisam-v1"
TABLES = ("refs", "refs_ext", "misc", "pdf_index")
TABLE_SUFFIXES = ("frm", "MYD", "MYI")
REQUIRED_MEMBERS = frozenset(
    {"rdb/db.opt"} | {f"rdb/{table}.{suffix}" for table in TABLES for suffix in TABLE_SUFFIXES}
)


class ProbeError(RuntimeError):
    """Safe developer diagnostic without scholarly content."""


@dataclass(frozen=True)
class ArchiveReceipt:
    sha256: str
    bytes: int
    entries: int
    expanded_bytes: int
    profile: str


@dataclass(frozen=True)
class RuntimeManifestEntry:
    relative_path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class RuntimeReceipt:
    family: str
    version: str
    launcher_sha256: str
    bundle_manifest_sha256: str
    manifest_entries: tuple[RuntimeManifestEntry, ...]
    manifest_scope: str


@dataclass(frozen=True)
class BootstrapReceipt:
    schema_version: int
    qualification_state: str
    archive: ArchiveReceipt
    runtime: RuntimeReceipt
    refs_rows: int
    refs_columns: int
    elapsed_ms: int
    source_unchanged: bool
    network_mode: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(COPY_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not name or "\x00" in name or "\\" in name:
        raise ProbeError("archive contains an invalid member name")
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ProbeError("archive member escapes the private extraction root")
    if pure.parts and re.fullmatch(r"[A-Za-z]:", pure.parts[0]):
        raise ProbeError("archive member uses an absolute drive path")
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    # ZIPs created on Windows commonly carry permission bits but no POSIX type bits.
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise ProbeError("archive contains a link or special file")
    if info.flag_bits & 0x1:
        raise ProbeError("encrypted archive members are unsupported")
    if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
        raise ProbeError("archive compression method is unsupported")
    return pure.as_posix().rstrip("/")


def inspect_archive(archive: Path) -> ArchiveReceipt:
    archive = archive.resolve(strict=True)
    archive_bytes = archive.stat().st_size
    if archive_bytes > MAX_ARCHIVE_BYTES:
        raise ProbeError("archive exceeds the developer probe size bound")
    digest = sha256_file(archive)
    try:
        with zipfile.ZipFile(archive) as source:
            infos = source.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ProbeError("archive contains too many entries")
            expanded = 0
            seen: set[str] = set()
            names: set[str] = set()
            for info in infos:
                name = _safe_member_name(info)
                folded = name.casefold()
                if folded in seen:
                    raise ProbeError("archive has duplicate or case-colliding members")
                seen.add(folded)
                if not info.is_dir():
                    if info.file_size > MAX_ENTRY_BYTES:
                        raise ProbeError("archive member exceeds the per-entry bound")
                    expanded += info.file_size
                    if expanded > MAX_EXPANDED_BYTES:
                        raise ProbeError("archive exceeds the expanded-size bound")
                    compressed = max(info.compress_size, 1)
                    if info.file_size / compressed > MAX_COMPRESSION_RATIO:
                        raise ProbeError("archive member exceeds the compression-ratio bound")
                    names.add(name)
    except zipfile.BadZipFile as error:
        raise ProbeError("archive is not a valid compressed EndNote library") from error
    if not REQUIRED_MEMBERS.issubset(names):
        raise ProbeError("archive does not match the supported legacy EndNote table profile")
    return ArchiveReceipt(digest, archive_bytes, len(infos), expanded, PROFILE)


def _copy_member(source: BinaryIO, destination: Path, expected: int) -> None:
    written = 0
    with destination.open("xb") as output:
        while True:
            chunk = source.read(COPY_CHUNK_BYTES)
            if not chunk:
                break
            written += len(chunk)
            if written > expected or written > MAX_ENTRY_BYTES:
                raise ProbeError("archive member expanded beyond its declared bound")
            output.write(chunk)
    if written != expected:
        raise ProbeError("archive member size changed during extraction")


def copy_archive(source: Path, destination: Path, receipt: ArchiveReceipt) -> None:
    """Create the private execution copy and prove it matches the preflighted bytes."""
    digest = hashlib.sha256()
    written = 0
    with source.resolve(strict=True).open("rb") as input_stream, destination.open("xb") as output_stream:
        for chunk in iter(lambda: input_stream.read(COPY_CHUNK_BYTES), b""):
            written += len(chunk)
            if written > receipt.bytes or written > MAX_ARCHIVE_BYTES:
                raise ProbeError("source archive changed during the private copy")
            digest.update(chunk)
            output_stream.write(chunk)
    if written != receipt.bytes or digest.hexdigest() != receipt.sha256:
        raise ProbeError("source archive changed during the private copy")


def extract_engine_tables(archive: Path, datadir: Path) -> None:
    datadir.mkdir(mode=0o700, parents=True, exist_ok=False)
    rdb = datadir / "rdb"
    rdb.mkdir(mode=0o700)
    with zipfile.ZipFile(archive) as source:
        by_name = {_safe_member_name(info): info for info in source.infolist() if not info.is_dir()}
        for name in sorted(REQUIRED_MEMBERS, key=str.casefold):
            info = by_name[name]
            destination = rdb / PurePosixPath(name).name
            with source.open(info) as member:
                _copy_member(member, destination, info.file_size)


def _is_link_like(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _runtime_tree_files(root: Path, basedir: Path) -> list[Path]:
    if _is_link_like(root):
        raise ProbeError("runtime manifest root cannot be a link or junction")

    def reject_walk_error(error: OSError) -> None:
        raise ProbeError("runtime manifest could not inspect the allowlisted tree") from error

    files: list[Path] = []
    for current, directories, names in os.walk(root, followlinks=False, onerror=reject_walk_error):
        current_path = Path(current)
        try:
            current_path.resolve(strict=True).relative_to(basedir)
        except ValueError as error:
            raise ProbeError("runtime manifest directory escapes the runtime root") from error
        for name in directories:
            child = current_path / name
            if _is_link_like(child):
                raise ProbeError("runtime manifest directory cannot contain links or junctions")
        for name in names:
            child = current_path / name
            if _is_link_like(child) or not child.is_file():
                raise ProbeError("runtime manifest contains a link or special file")
            files.append(child)
            if len(files) > MAX_RUNTIME_FILES:
                raise ProbeError("runtime manifest contains too many files")
    return files


def _manifest_candidates(executable: Path, basedir: Path) -> tuple[list[Path], str]:
    files = [executable]
    if executable.suffix.lower() == ".exe":
        server = executable.with_name("server.dll")
        if not server.is_file():
            raise ProbeError("Windows runtime is missing adjacent server.dll")
        files.append(server)
        for relative in (Path("share/english"), Path("share/charsets")):
            root = basedir / relative
            if not root.is_dir():
                raise ProbeError("Windows runtime is missing required message/charset data")
            files.extend(_runtime_tree_files(root, basedir))
        return files, "windows-bootstrap-files-v1"
    return files, "launcher-only-development-v1"


def runtime_manifest(executable: Path, *, version: str | None = None) -> RuntimeReceipt:
    if _is_link_like(executable):
        raise ProbeError("runtime executable cannot be a link or junction")
    executable = executable.resolve(strict=True)
    if not executable.is_file():
        raise ProbeError("runtime executable is not a regular file")
    basedir = executable.parent.parent if executable.parent.name.lower() in {"bin", "sbin"} else executable.parent
    files, scope = _manifest_candidates(executable, basedir)
    if len(files) > MAX_RUNTIME_FILES:
        raise ProbeError("runtime manifest contains too many files")
    entries: list[RuntimeManifestEntry] = []
    runtime_bytes = 0
    for path in sorted(files, key=lambda item: item.relative_to(basedir).as_posix().casefold()):
        if _is_link_like(path):
            raise ProbeError("runtime manifest contains a link or junction")
        resolved = path.resolve(strict=True)
        try:
            relative = resolved.relative_to(basedir).as_posix()
        except ValueError as error:
            raise ProbeError("runtime manifest entry escapes the runtime root") from error
        size = resolved.stat().st_size
        runtime_bytes += size
        if runtime_bytes > MAX_RUNTIME_BYTES:
            raise ProbeError("runtime manifest exceeds the byte bound")
        entries.append(RuntimeManifestEntry(relative, size, sha256_file(resolved)))
    canonical = json.dumps([asdict(entry) for entry in entries], sort_keys=True, separators=(",", ":"))
    manifest_digest = hashlib.sha256(canonical.encode()).hexdigest()
    resolved_version = version or _runtime_version(executable)
    return RuntimeReceipt(
        "mariadb",
        resolved_version,
        sha256_file(executable),
        manifest_digest,
        tuple(entries),
        scope,
    )


def _runtime_version(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "--no-defaults", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        stdin=subprocess.DEVNULL,
        env=_minimal_environment(),
    )
    if result.returncode != 0:
        raise ProbeError("runtime version probe failed")
    combined = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"Ver\s+([^\r\n]+)", combined)
    if not match:
        raise ProbeError("runtime version output was not recognized")
    return f"Ver {match.group(1).strip()}"


def _sql_literal(path: Path) -> str:
    value = path.resolve().as_posix()
    if "\x00" in value:
        raise ProbeError("output path is invalid")
    return "'" + value.replace("'", "''") + "'"


def bootstrap_sql(output_dir: Path) -> str:
    rows = _sql_literal(output_dir / "refs-count.tsv")
    columns = _sql_literal(output_dir / "refs-columns.hex")
    return "\n".join(
        (
            "ALTER TABLE rdb.refs FORCE;",
            f"SELECT COUNT(*) INTO OUTFILE {rows} FROM rdb.refs;",
            "SELECT HEX(GROUP_CONCAT(COLUMN_NAME ORDER BY ORDINAL_POSITION SEPARATOR ',')) "
            f"INTO OUTFILE {columns} FROM information_schema.columns "
            "WHERE table_schema='rdb' AND table_name='refs';",
            "",
        )
    )


def bootstrap_command(executable: Path, datadir: Path, output_dir: Path, log_path: Path) -> list[str]:
    executable = executable.resolve(strict=True)
    basedir = executable.parent.parent if executable.parent.name.lower() in {"bin", "sbin"} else executable.parent
    share = basedir / "share"
    plugin_dir = datadir.parent / "empty-plugins"
    plugin_dir.mkdir(mode=0o700, exist_ok=False)
    return [
        str(executable),
        "--no-defaults",
        "--bootstrap",
        "--skip-grant-tables",
        "--skip-networking",
        "--skip-log-bin",
        "--skip-innodb",
        "--skip-external-locking",
        "--skip-symbolic-links",
        "--local-infile=0",
        "--default-storage-engine=MyISAM",
        f"--basedir={basedir}",
        f"--datadir={datadir}",
        f"--lc-messages-dir={share}",
        f"--plugin-dir={plugin_dir}",
        f"--log-error={log_path}",
        f"--secure-file-priv={output_dir}",
    ]


def _bounded_file_bytes(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _bounded_output_bytes(paths: Sequence[Path]) -> int:
    return sum(_bounded_file_bytes(path) for path in paths)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            timeout=10,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def run_bounded_process(
    command: Sequence[str],
    stdin: bytes,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float,
    monitored_paths: Sequence[Path] = (),
) -> int:
    if timeout_seconds <= 0:
        raise ProbeError("engine timeout must be positive")
    if len(stdin) > MAX_BOOTSTRAP_SQL_BYTES:
        raise ProbeError("bootstrap SQL exceeds the fixed input bound")
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    output_paths = (stdout_path, stderr_path, *monitored_paths)
    with (
        tempfile.TemporaryFile() as input_stream,
        stdout_path.open("xb") as stdout,
        stderr_path.open("xb") as stderr,
    ):
        input_stream.write(stdin)
        input_stream.seek(0)
        process = subprocess.Popen(
            list(command),
            stdin=input_stream,
            stdout=stdout,
            stderr=stderr,
            env=_minimal_environment(),
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        try:
            deadline = time.monotonic() + timeout_seconds
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise ProbeError("engine exceeded the developer probe timeout")
                if _bounded_output_bytes(output_paths) > MAX_ENGINE_LOG_BYTES:
                    raise ProbeError("engine output exceeded the developer probe bound")
                time.sleep(0.05)
        except BaseException:
            _terminate_process_tree(process)
            raise
        exit_code = process.wait(timeout=10)
        if _bounded_output_bytes(output_paths) > MAX_ENGINE_LOG_BYTES:
            raise ProbeError("engine output exceeded the developer probe bound")
        return exit_code


def _minimal_environment() -> dict[str, str]:
    allowed = ("SystemRoot", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")
    return {name: os.environ[name] for name in allowed if name in os.environ}


def _read_small(path: Path) -> bytes:
    if not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ProbeError("engine receipt is missing or oversized")
    return path.read_bytes()


def _parse_receipts(output_dir: Path) -> tuple[int, int]:
    try:
        rows = int(_read_small(output_dir / "refs-count.tsv").strip())
        encoded = _read_small(output_dir / "refs-columns.hex").strip()
        names = bytes.fromhex(encoded.decode("ascii")).decode("utf-8").split(",")
    except (UnicodeError, ValueError) as error:
        raise ProbeError("engine receipt could not be parsed") from error
    if rows < 0 or rows > 1_000_000 or not names or len(names) > 512:
        raise ProbeError("engine receipt exceeds the schema/row bounds")
    if any(not re.fullmatch(r"[A-Za-z0-9_]+", name) for name in names):
        raise ProbeError("engine returned an invalid column identity")
    return rows, len(names)


def run_probe(archive: Path, executable: Path, timeout_seconds: float = 60) -> BootstrapReceipt:
    archive_receipt = inspect_archive(archive)
    runtime_receipt = runtime_manifest(executable)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="callosum-endnote-bootstrap-") as temporary:
        root = Path(temporary)
        if os.name != "nt":
            root.chmod(0o700)
        datadir = root / "data"
        output_dir = root / "output"
        output_dir.mkdir(mode=0o700)
        private_archive = root / "source.enlx"
        copy_archive(archive, private_archive, archive_receipt)
        extract_engine_tables(private_archive, datadir)
        log_path = root / "engine.log"
        stdout_path = root / "stdout.log"
        stderr_path = root / "stderr.log"
        command = bootstrap_command(executable, datadir, output_dir, log_path)
        exit_code = run_bounded_process(
            command,
            bootstrap_sql(output_dir).encode(),
            stdout_path,
            stderr_path,
            timeout_seconds,
            monitored_paths=(log_path,),
        )
        if exit_code != 0:
            raise ProbeError(f"engine bootstrap failed with exit code {exit_code}")
        if _bounded_file_bytes(log_path) > MAX_ENGINE_LOG_BYTES:
            raise ProbeError("engine operational log exceeded the developer probe bound")
        refs_rows, refs_columns = _parse_receipts(output_dir)
    unchanged = sha256_file(archive.resolve(strict=True)) == archive_receipt.sha256
    if not unchanged:
        raise ProbeError("source archive changed during the copy-only probe")
    return BootstrapReceipt(
        1,
        "DEVELOPER_TEST_ONLY",
        archive_receipt,
        runtime_receipt,
        refs_rows,
        refs_columns,
        round((time.monotonic() - started) * 1000),
        True,
        "disabled",
    )


def receipt_json(receipt: BootstrapReceipt) -> str:
    return json.dumps(asdict(receipt), sort_keys=True, indent=2)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        print(receipt_json(run_probe(args.archive, args.runtime, args.timeout)))
    except ProbeError as error:
        print(f"EndNote bootstrap probe failed: {error}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError, zipfile.BadZipFile):
        print("EndNote bootstrap probe failed: local archive/runtime operation failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
