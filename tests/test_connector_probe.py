"""The CI connector probe must prove "the host answered, in this state, and issued a token" WITHOUT ever emitting the token (#61).

The macOS workflow drives the bundled connector and its reply carries a short-lived `session_token`. A first run printed that reply
into the Actions log and an uploaded artifact (an ephemeral CI backend on a destroyed runner, but still a token in a log). The probe
now fails closed: allowlisted, vocabulary-validated fields plus `session_token_present`, and metadata only on every error path.

A fake host emits a known SENTINEL in the token (and elsewhere) and every output channel of the real CLI is checked for it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "app/desktop-shell/packaging/connector_probe.py"
IDENTITY = json.loads((ROOT / "app/desktop-shell/connector/identity.json").read_text(encoding="utf-8"))
SENTINEL = "SENTINEL-session-token-9f3c1a7e5b"

FAKE_HOST = """
import json, os, struct, sys

mode = os.environ["FAKE_MODE"]
sentinel = os.environ["FAKE_SENTINEL"]
header = sys.stdin.buffer.read(4)
request = json.loads(sys.stdin.buffer.read(struct.unpack("<I", header)[0]))


def frame(payload: bytes, declared: int | None = None) -> None:
    sys.stdout.buffer.write(struct.pack("<I", len(payload) if declared is None else declared) + payload)
    sys.stdout.buffer.flush()


def reply(**extra):
    base = {"protocol_version": request["protocol_version"], "connector_host_version": "0.0.0",
            "connector_identity": "org.callosum.connector.dev", "app_version": "0.0.0", "instance_role": "ui",
            "runtime_state": "available", "session_token": sentinel, "backend_base_url": "http://127.0.0.1:1"}
    base.update(extra)
    return json.dumps(base).encode()


if mode == "ok":
    frame(reply())
elif mode == "ok_with_extra_secretish_fields":
    frame(reply(refresh_token=sentinel, api_key=sentinel, note=sentinel))
elif mode == "ok_with_hostile_allowlisted_values":
    frame(reply(runtime_state=sentinel, app_version=sentinel + " with spaces", connector_identity={"x": sentinel}))
elif mode == "empty_token":
    frame(reply(session_token=""))
elif mode == "no_token":
    frame(json.dumps({"protocol_version": request["protocol_version"], "runtime_state": "callosum_closed"}).encode())
elif mode == "missing_runtime_state":
    frame(json.dumps({"protocol_version": request["protocol_version"], "session_token": sentinel}).encode())
elif mode == "malformed_json":
    frame(b'{"session_token": "' + sentinel.encode() + b'", ')
elif mode == "not_utf8":
    frame(b'\\xff\\xfe' + sentinel.encode())
elif mode == "truncated_frame":
    frame(reply(), declared=len(reply()) + 500)
elif mode == "not_an_object":
    frame(json.dumps([sentinel]).encode())
elif mode == "wrong_protocol_version":
    frame(reply(protocol_version=request["protocol_version"] + 41))
elif mode == "no_frame_but_noisy_stderr":
    sys.stderr.write("fatal: " + sentinel + "\\n")
elif mode == "crash_with_secret_in_message":
    raise RuntimeError("boom " + sentinel)
"""


@pytest.fixture(scope="module")
def probe_module():
    spec = importlib.util.spec_from_file_location("callosum_connector_probe", PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_host(tmp_path: Path) -> Path:
    path = tmp_path / "fake_host.py"
    path.write_text(FAKE_HOST, encoding="utf-8")
    return path


def _run_cli(fake_host: Path, mode: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    """The REAL CLI, exactly as the workflow invokes it, against a fake host in the given mode."""
    env = {**os.environ, "FAKE_MODE": mode, "FAKE_SENTINEL": SENTINEL}
    result = subprocess.run(
        [sys.executable, str(PROBE_PATH), sys.executable, str(fake_host)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert result.stdout.strip(), f"the probe must always print a diagnostic ({mode}): stderr={result.stderr!r}"
    return result, json.loads(result.stdout)


def _assert_sentinel_nowhere(result: subprocess.CompletedProcess[str]) -> None:
    assert SENTINEL not in result.stdout, "the raw token reached stdout (the log / tee'd file / uploaded artifact)"
    assert SENTINEL not in result.stderr, "the raw token reached stderr"


# ── the CLI proves token presence without emitting the token ─────────────────────────────────────────────────────


def test_a_normal_reply_proves_a_nonempty_token_without_printing_it(fake_host: Path) -> None:
    result, out = _run_cli(fake_host, "ok")
    assert result.returncode == 0
    _assert_sentinel_nowhere(result)
    assert out["runtime_state"] == "available"
    assert out["session_token_present"] is True
    assert out["parse"] == "ok"
    assert "session_token" not in out


def test_an_empty_or_absent_token_is_reported_as_not_present(fake_host: Path) -> None:
    for mode in ("empty_token", "no_token"):
        result, out = _run_cli(fake_host, mode)
        assert result.returncode == 0, mode
        assert out["session_token_present"] is False, mode


def test_unknown_fields_are_dropped_and_counted_never_echoed(fake_host: Path) -> None:
    """Fail closed: a future or unexpected field that happens to hold a secret is not echoed."""
    result, out = _run_cli(fake_host, "ok_with_extra_secretish_fields")
    _assert_sentinel_nowhere(result)
    assert out["dropped_field_count"] == 3
    assert not {"refresh_token", "api_key", "note"} & set(out)


def test_an_unexpected_value_in_an_allowlisted_field_is_reported_as_unrecognized_never_echoed(fake_host: Path) -> None:
    """The SENTINEL is identifier-shaped, so a SHAPE check alone would echo it; each field is validated against its known
    vocabulary instead (runtime states, instance roles, the connector's own host names, version shapes)."""
    result, out = _run_cli(fake_host, "ok_with_hostile_allowlisted_values")
    _assert_sentinel_nowhere(result)
    assert out["runtime_state"] == "<unrecognized>"
    assert out["app_version"] == "<unrecognized>"
    assert out["connector_identity"] == "<unrecognized>"
    assert out["instance_role"] == "ui"  # a genuinely known value is still reported


def test_a_missing_runtime_state_is_reported_as_missing_not_guessed(fake_host: Path) -> None:
    result, out = _run_cli(fake_host, "missing_runtime_state")
    _assert_sentinel_nowhere(result)
    assert out["runtime_state"] is None
    assert out["session_token_present"] is True


# ── every error path is metadata only ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "status"),
    [
        ("malformed_json", "not_json"),
        ("not_utf8", "not_json"),
        ("truncated_frame", "truncated_frame"),
        ("not_an_object", "not_an_object"),
        ("no_frame_but_noisy_stderr", "no_frame"),
        ("crash_with_secret_in_message", "no_frame"),
    ],
)
def test_framing_and_parse_errors_never_echo_the_reply_or_the_hosts_stderr(
    fake_host: Path, mode: str, status: str
) -> None:
    result, out = _run_cli(fake_host, mode)
    assert result.returncode == 2, mode
    _assert_sentinel_nowhere(result)
    assert out["error"] == f"connector reply unusable: {status}"
    assert out["parse"] == "failed"
    assert out["session_token_present"] is False
    assert set(out) <= {"error", "parse", "returncode", "stdout_length", "stderr_length", "session_token_present"}


def test_an_unexpected_protocol_version_is_an_error_that_still_hides_the_token(fake_host: Path) -> None:
    result, out = _run_cli(fake_host, "wrong_protocol_version")
    assert result.returncode == 2
    _assert_sentinel_nowhere(result)
    assert out["error"] == "unexpected protocol version"
    assert out["expected_protocol_version"] == IDENTITY["protocol_version"]


def test_a_connector_that_cannot_be_run_reports_only_the_exception_type() -> None:
    result = subprocess.run(
        [sys.executable, str(PROBE_PATH), str(ROOT / "no" / f"such-host-{SENTINEL}")],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = json.loads(result.stdout)
    assert result.returncode == 2
    assert out["error"] == "connector could not be run"
    assert SENTINEL not in result.stdout and SENTINEL not in result.stderr, "not even the requested path is echoed"


def test_the_last_line_of_defence_reports_only_an_exception_type(probe_module, monkeypatch, capsys) -> None:
    def explode(*_args, **_kwargs):
        raise RuntimeError("secret " + SENTINEL)

    monkeypatch.setattr(probe_module, "probe", explode)
    assert probe_module.main(["whatever"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"error": "probe failed unexpectedly", "exception_type": "RuntimeError"}
    assert SENTINEL not in captured.out + captured.err


# ── the pure functions ───────────────────────────────────────────────────────────────────────────────────────────


def test_redact_reply_is_an_allowlist_and_reports_only_presence_of_the_token(probe_module) -> None:
    out = probe_module.redact_reply(
        {
            "protocol_version": 1,
            "runtime_state": "available",
            "session_token": SENTINEL,
            "backend_base_url": "http://127.0.0.1:9",
            "surprise": SENTINEL,
        }
    )
    assert SENTINEL not in json.dumps(out)
    assert out["session_token_present"] is True and out["backend_base_url_present"] is True
    assert out["dropped_field_count"] == 1


def test_a_boolean_or_non_string_token_does_not_count_as_a_token(probe_module) -> None:
    for token in (True, 1, ["x"], {"a": 1}, None, ""):
        assert probe_module.redact_reply({"session_token": token})["session_token_present"] is False, token


def test_parse_frame_uses_a_fixed_status_vocabulary(probe_module) -> None:
    assert probe_module.parse_frame(b"")[1] == "no_frame"
    assert probe_module.parse_frame(b"\x05\x00\x00\x00abc")[1] == "truncated_frame"
    assert probe_module.parse_frame(b"\x03\x00\x00\x00abc")[1] == "not_json"
    assert probe_module.parse_frame(b"\x02\x00\x00\x00[]")[1] == "not_an_object"
    assert probe_module.parse_frame(b"\x02\x00\x00\x00{}") == ({}, "ok")
