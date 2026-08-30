from __future__ import annotations

import json
import stat
import sys
import zipfile
from pathlib import Path

import pytest

from tools.endnote import legacy_bootstrap as probe


def _archive(path: Path, extras: list[zipfile.ZipInfo] | None = None) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name in sorted(probe.REQUIRED_MEMBERS):
            target.writestr(name, b"fixture")
        for info in extras or []:
            target.writestr(info, b"extra")
    return path


def test_archive_preflight_and_copy_are_bounded_and_source_immutable(tmp_path: Path) -> None:
    archive = _archive(tmp_path / "sample.enlx")
    before = probe.sha256_file(archive)

    receipt = probe.inspect_archive(archive)
    probe.extract_engine_tables(archive, tmp_path / "data")

    assert receipt.profile == probe.PROFILE
    assert receipt.sha256 == before == probe.sha256_file(archive)
    assert {path.name for path in (tmp_path / "data" / "rdb").iterdir()} == {
        name.split("/")[-1] for name in probe.REQUIRED_MEMBERS
    }


@pytest.mark.parametrize("size", [0, 7, 3 * 1024 * 1024])
def test_streaming_digest_is_deterministic_for_default_stack(tmp_path: Path, size: int) -> None:
    source = tmp_path / "runtime.bin"
    source.write_bytes(b"a" * size)

    expected = probe.sha256_file(source)

    assert probe.sha256_file(source) == expected


def test_private_archive_copy_rejects_preflight_mismatch(tmp_path: Path) -> None:
    archive = _archive(tmp_path / "sample.enlx")
    receipt = probe.inspect_archive(archive)
    archive.write_bytes(archive.read_bytes() + b"changed")

    with pytest.raises(probe.ProbeError, match="changed during the private copy"):
        probe.copy_archive(archive, tmp_path / "private.enlx", receipt)


@pytest.mark.parametrize(
    ("constant", "value", "message"),
    [
        ("MAX_ARCHIVE_BYTES", 1, "archive exceeds"),
        ("MAX_ENTRIES", 1, "too many entries"),
        ("MAX_EXPANDED_BYTES", 1, "expanded-size"),
        ("MAX_COMPRESSION_RATIO", 0, "compression-ratio"),
    ],
)
def test_archive_preflight_enforces_resource_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, constant: str, value: int, message: str
) -> None:
    archive = _archive(tmp_path / "bounded.enlx")
    monkeypatch.setattr(probe, constant, value)

    with pytest.raises(probe.ProbeError, match=message):
        probe.inspect_archive(archive)


def test_archive_preflight_rejects_unknown_table_profile(tmp_path: Path) -> None:
    archive = tmp_path / "unknown.enlx"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("rdb/db.opt", b"fixture")

    with pytest.raises(probe.ProbeError, match="supported legacy EndNote table profile"):
        probe.inspect_archive(archive)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/drive"])
def test_archive_rejects_escaping_or_ambiguous_names(tmp_path: Path, name: str) -> None:
    with zipfile.ZipFile(tmp_path / "bad.enlx", "w") as target:
        for required in probe.REQUIRED_MEMBERS:
            target.writestr(required, b"fixture")
        target.writestr(name, b"bad")

    with pytest.raises(probe.ProbeError):
        probe.inspect_archive(tmp_path / "bad.enlx")


def test_archive_member_rejects_backslash_name() -> None:
    member = zipfile.ZipInfo("safe")
    member.filename = "rdb\\backslash.frm"
    with pytest.raises(probe.ProbeError, match="invalid member name"):
        probe._safe_member_name(member)


def test_archive_rejects_case_collisions(tmp_path: Path) -> None:
    duplicate = zipfile.ZipInfo("RDB/REFS.FRM")
    archive = _archive(tmp_path / "collision.enlx", [duplicate])

    with pytest.raises(probe.ProbeError, match="case-colliding"):
        probe.inspect_archive(archive)


def test_archive_rejects_symlinks(tmp_path: Path) -> None:
    link = zipfile.ZipInfo("rdb/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    archive = _archive(tmp_path / "link.enlx", [link])

    with pytest.raises(probe.ProbeError, match="link or special"):
        probe.inspect_archive(archive)


def _windows_runtime(root: Path, dll: bytes = b"backend-a") -> Path:
    executable = root / "bin" / "mariadbd.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"launcher")
    executable.with_name("server.dll").write_bytes(dll)
    for relative in ("share/english/errmsg.sys", "share/charsets/Index.xml"):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(relative.encode())
    return executable


def test_runtime_bundle_manifest_is_deterministic_and_backend_sensitive(tmp_path: Path) -> None:
    first = probe.runtime_manifest(_windows_runtime(tmp_path / "a"), version="Ver test")
    repeated = probe.runtime_manifest(tmp_path / "a/bin/mariadbd.exe", version="Ver test")
    relocated = probe.runtime_manifest(_windows_runtime(tmp_path / "relocated"), version="Ver test")
    second = probe.runtime_manifest(_windows_runtime(tmp_path / "b", b"backend-b"), version="Ver test")

    assert first.bundle_manifest_sha256 == repeated.bundle_manifest_sha256
    assert first.bundle_manifest_sha256 == relocated.bundle_manifest_sha256
    assert first.bundle_manifest_sha256 != second.bundle_manifest_sha256
    assert all(not Path(entry.relative_path).is_absolute() for entry in first.manifest_entries)


def test_runtime_bundle_rejects_escape_link(tmp_path: Path) -> None:
    runtime = _windows_runtime(tmp_path / "runtime")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "runtime/share/charsets/escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("creating a directory symlink is unavailable")

    with pytest.raises(probe.ProbeError, match="links or junctions"):
        probe.runtime_manifest(runtime, version="Ver test")


def test_runtime_bundle_rejects_launcher_link(tmp_path: Path) -> None:
    runtime = _windows_runtime(tmp_path / "runtime")
    link = tmp_path / "mariadbd.exe"
    try:
        link.symlink_to(runtime)
    except OSError:
        pytest.skip("creating a file symlink is unavailable")

    with pytest.raises(probe.ProbeError, match="link or junction"):
        probe.runtime_manifest(link, version="Ver test")


def test_bootstrap_sql_is_fixed_encoded_and_escapes_generated_path(tmp_path: Path) -> None:
    output = tmp_path / "quote's output"
    sql = probe.bootstrap_sql(output)

    assert "ALTER TABLE rdb.refs FORCE" in sql
    assert "HEX(GROUP_CONCAT(COLUMN_NAME" in sql
    assert "quote''s output" in sql
    assert "SELECT *" not in sql


def test_command_forces_one_shot_no_network_semantics(tmp_path: Path) -> None:
    runtime = _windows_runtime(tmp_path / "runtime")
    datadir = tmp_path / "job" / "data"
    output = tmp_path / "job" / "output"
    datadir.mkdir(parents=True)
    output.mkdir()

    command = probe.bootstrap_command(runtime, datadir, output, tmp_path / "job/engine.log")

    assert "--no-defaults" in command
    assert "--bootstrap" in command
    assert "--skip-networking" in command
    assert "--skip-grant-tables" in command
    assert "--skip-log-bin" in command
    assert "--skip-innodb" in command
    assert "--skip-external-locking" in command
    assert "--skip-symbolic-links" in command
    assert "--local-infile=0" in command
    assert any(item.startswith("--secure-file-priv=") for item in command)
    assert not any("archive" in item for item in command)


def test_bounded_process_runner_accepts_success(tmp_path: Path) -> None:
    result = probe.run_bounded_process(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(); print('ok')"],
        b"input",
        tmp_path / "stdout",
        tmp_path / "stderr",
        5,
    )

    assert result == 0
    assert (tmp_path / "stdout").read_text().strip() == "ok"


def test_bounded_process_runner_kills_timeout(tmp_path: Path) -> None:
    with pytest.raises(probe.ProbeError, match="timeout"):
        probe.run_bounded_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            b"",
            tmp_path / "stdout",
            tmp_path / "stderr",
            0.1,
        )


def test_bounded_process_runner_caps_operational_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe, "MAX_ENGINE_LOG_BYTES", 64)
    operational_log = tmp_path / "engine.log"
    command = [
        sys.executable,
        "-c",
        "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_bytes(b'x'*65); time.sleep(30)",
        str(operational_log),
    ]

    with pytest.raises(probe.ProbeError, match="output exceeded"):
        probe.run_bounded_process(
            command,
            b"",
            tmp_path / "stdout",
            tmp_path / "stderr",
            5,
            monitored_paths=(operational_log,),
        )


def test_bounded_process_runner_rejects_oversized_sql(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe, "MAX_BOOTSTRAP_SQL_BYTES", 1)

    with pytest.raises(probe.ProbeError, match="SQL exceeds"):
        probe.run_bounded_process(
            [sys.executable, "-c", "pass"],
            b"xx",
            tmp_path / "stdout",
            tmp_path / "stderr",
            5,
        )


def test_receipt_parser_accepts_bounded_hex_schema(tmp_path: Path) -> None:
    (tmp_path / "refs-count.tsv").write_text("59\n")
    (tmp_path / "refs-columns.hex").write_text("id,title,author".encode().hex())

    assert probe._parse_receipts(tmp_path) == (59, 3)


def test_receipt_parser_rejects_invalid_or_oversized_schema(tmp_path: Path) -> None:
    (tmp_path / "refs-count.tsv").write_text("1000001\n")
    (tmp_path / "refs-columns.hex").write_text("id".encode().hex())

    with pytest.raises(probe.ProbeError, match="schema/row bounds"):
        probe._parse_receipts(tmp_path)


def test_receipt_json_contains_no_paths_or_scholarly_content() -> None:
    archive = probe.ArchiveReceipt("a" * 64, 10, 2, 20, probe.PROFILE)
    runtime = probe.RuntimeReceipt("mariadb", "Ver test", "b" * 64, "c" * 64, (), "test")
    receipt = probe.BootstrapReceipt(1, "DEVELOPER_TEST_ONLY", archive, runtime, 59, 54, 3, True, "disabled")

    encoded = probe.receipt_json(receipt)
    parsed = json.loads(encoded)

    assert parsed["qualification_state"] == "DEVELOPER_TEST_ONLY"
    assert "C:\\" not in encoded
    assert "/Users/" not in encoded
    assert "title" not in encoded.lower()


def test_minimal_environment_does_not_forward_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MENDELEY_SECRET", "do-not-forward")
    monkeypatch.setenv("GEMINI_API_KEY", "do-not-forward")

    environment = probe._minimal_environment()

    assert "MENDELEY_SECRET" not in environment
    assert "GEMINI_API_KEY" not in environment
    assert set(environment) <= {
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "PATH",
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
    }


def test_cli_io_failure_does_not_echo_private_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    private_path = tmp_path / "private-library.enlx"

    assert probe.main(["--archive", str(private_path), "--runtime", str(tmp_path / "missing")]) == 1

    assert str(private_path) not in capsys.readouterr().err
