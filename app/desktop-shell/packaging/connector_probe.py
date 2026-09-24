"""Drive the bundled connector host exactly as a browser does and print a REDACTED, fail-closed diagnostic (#61).

Usage: ``python connector_probe.py <connector-executable> [extra args...]`` -- the probe appends the caller origin as the
final argument (argv[1] on the real host), sends ONE length-prefixed JSON message on stdin, and reads ONE framed reply.

Why this exists. The connector's reply carries a short-lived ``session_token``. A CI log or an uploaded artifact must be able to
prove "the host answered, in this state, and issued a non-empty token" without ever containing the token. So the raw reply is
never printed, never written to a file, and never interpolated into an exception or diagnostic:

* Fail closed by allowlist. Only ``_TEXT_FIELDS`` (each validated against its known vocabulary) and the integer protocol
  version are echoed. Every other field -- including any future one -- is dropped and only COUNTED, and an unexpected value in an
  allowlisted field is reported as ``<unrecognized>``. The token is reduced to ``session_token_present``.
* Every error path reports metadata only (a fixed status word, lengths, the runtime state, ``session_token_present``): malformed
  JSON, framing errors, an unexpected protocol version, a missing ``runtime_state`` and an unexpected exception alike. The
  connector's stderr is never forwarded.

To surface a new reply field in diagnostics, add it to the allowlist deliberately.

Uses the existing DEV mechanism (``CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD=1`` + the dev extension origin): production_extension_ids
is still empty, so a production host correctly rejects every caller. Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

IDENTITY_PATH = Path(__file__).resolve().parents[1] / "connector" / "identity.json"
TIMEOUT_SECONDS = 60

# The ONLY reply text fields a diagnostic may echo, and each only when its value is in the field's KNOWN vocabulary -- an exact
# set (runtime states, instance roles, the connector's own host names) or a version shape. An unexpected value, including an
# identifier-shaped secret, is reported as "<unrecognized>" rather than echoed. The vocabularies mirror connector-host/src/main.rs
# (`RuntimeState`, the backend's `instance_role`); a genuinely new value needs adding here deliberately.
_RUNTIME_STATES = frozenset(
    {
        "available",
        "callosum_closed",
        "callosum_starting",
        "version_incompatible",
        "not_eligible_instance",
        "pairing_unavailable",
    }
)
_INSTANCE_ROLES = frozenset({"ui", "word-https", "tunnel-target"})
_VERSION = re.compile(r"(?:\d{1,4}\.\d{1,4}\.\d{1,4}(?:[-+.][0-9A-Za-z.]{1,24})?|dev-[0-9a-f]{4,12})")
_TEXT_FIELDS = ("connector_host_version", "connector_identity", "app_version", "instance_role", "runtime_state")
_KNOWN_FIELDS = {*_TEXT_FIELDS, "protocol_version", "session_token", "backend_base_url"}
_UNRECOGNIZED = "<unrecognized>"


def probe_message(identity: dict[str, Any]) -> bytes:
    body = json.dumps({"id": "ci-probe", "protocol_version": identity["protocol_version"]}).encode()
    return struct.pack("<I", len(body)) + body


def parse_frame(stdout: bytes) -> tuple[dict[str, Any] | None, str]:
    """``(reply, status)``. ``status`` is one of a FIXED vocabulary and never contains reply bytes."""
    if len(stdout) < 4:
        return None, "no_frame"
    length = struct.unpack("<I", stdout[:4])[0]
    body = stdout[4 : 4 + length]
    if len(body) < length:
        return None, "truncated_frame"
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, "not_json"
    if not isinstance(value, dict):
        return None, "not_an_object"
    return value, "ok"


def _recognized(key: str, value: Any, connector_identities: frozenset[str]) -> bool:
    if not isinstance(value, str):
        return False
    if key == "runtime_state":
        return value in _RUNTIME_STATES
    if key == "instance_role":
        return value in _INSTANCE_ROLES
    if key == "connector_identity":
        return value in connector_identities
    return _VERSION.fullmatch(value) is not None  # connector_host_version, app_version


def redact_reply(reply: dict[str, Any], connector_identities: frozenset[str] = frozenset()) -> dict[str, Any]:
    """The diagnostic view of a reply: allowlisted, vocabulary-validated fields plus presence flags. Never the token."""
    version = reply.get("protocol_version")
    out: dict[str, Any] = {
        "protocol_version": version if isinstance(version, int) and not isinstance(version, bool) else None
    }
    for key in _TEXT_FIELDS:
        value = reply.get(key)
        if value is None:
            out[key] = None
        else:
            out[key] = value if _recognized(key, value, connector_identities) else _UNRECOGNIZED
    token = reply.get("session_token")
    out["session_token_present"] = isinstance(token, str) and token != ""
    out["backend_base_url_present"] = bool(reply.get("backend_base_url"))
    out["dropped_field_count"] = len(set(reply) - _KNOWN_FIELDS)
    return out


def probe(command: Sequence[str], identity: dict[str, Any], *, run: Any = subprocess.run) -> tuple[dict[str, Any], int]:
    """Run the host once. Returns ``(diagnostic, exit_code)``; the diagnostic never contains the raw reply."""
    origin = f"chrome-extension://{identity['dev_extension_id']}/"
    try:
        result = run(
            [*command, origin],
            input=probe_message(identity),
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            env={**os.environ, "CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD": "1"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"error": "connector could not be run", "exception_type": type(exc).__name__}, 2

    reply, status = parse_frame(result.stdout)
    if reply is None:
        return {
            "error": f"connector reply unusable: {status}",
            "parse": "failed",
            "returncode": result.returncode,
            "stdout_length": len(result.stdout),
            "stderr_length": len(result.stderr),
            "session_token_present": False,
        }, 2

    diagnostic = redact_reply(reply, frozenset({identity["native_host_name"], identity["dev_native_host_name"]}))
    diagnostic["parse"] = "ok"
    diagnostic["reply_length"] = len(result.stdout) - 4
    if reply.get("protocol_version") != identity["protocol_version"]:
        diagnostic["error"] = "unexpected protocol version"
        diagnostic["expected_protocol_version"] = identity["protocol_version"]
        return diagnostic, 2
    return diagnostic, 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(json.dumps({"error": "usage: connector_probe.py <connector-executable> [extra args...]"}))
        return 2
    try:
        identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
        diagnostic, code = probe(args, identity)
    except Exception as exc:  # noqa: BLE001 -- the last line of defence: report the TYPE only, never a message
        diagnostic, code = {"error": "probe failed unexpectedly", "exception_type": type(exc).__name__}, 2
    print(json.dumps(diagnostic, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
