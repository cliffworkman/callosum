"""EXPERIMENTAL HARNESS proving browser-runtime feasibility. NOT the production connector host.

Answers one bounded question for the browser-capture research (#61): is native messaging viable as
the canonical packaged discovery/control boundary on Windows?

It deliberately does NOT resolve a real Callosum backend, authenticate anything, or ship. The eventual
connector host must be re-derived against the packaged contract.

Native messaging framing: each message is a 4-byte little-endian uint32 length followed by that many
bytes of UTF-8 JSON, on stdin/stdout. stdout is binary-mode; any stray print() corrupts the stream.
"""

from __future__ import annotations

import json
import os
import struct
import sys
import time
import urllib.request
from pathlib import Path

LOG = Path(__file__).with_name("probe-log.jsonl")
PROTOCOL_VERSION = 1
HOST_VERSION = "0.0.1-probe"


def log(event: str, **fields: object) -> None:
    record = {"ts": time.time(), "event": event, **fields}
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def read_message() -> dict | None:
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) < 4:
        return None
    (length,) = struct.unpack("<I", raw_len)
    payload = sys.stdin.buffer.read(length)
    return json.loads(payload.decode("utf-8"))


def write_message(message: dict) -> None:
    data = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def packaged_state() -> dict:
    """Resolve the canonical UI backend from packaged state alone — NO port probing.

    The whole resolution, in order:

      1. read the authoritative port from ``last-port.txt`` (a per-user file an extension cannot read
         but a local process can — the asymmetry that argues for a native host in the first place);
      2. ask THAT port, and only that port, for ``/health``;
      3. require ``instance_role == "ui"``.

    Step 3 is what closes the gap this increment exists for: before it, a sibling on some other port —
    including the Word HTTPS child whose Remote Access gate is deliberately disabled — was
    indistinguishable from the real UI backend. A missing or unrecognized role reports ``null``, which
    fails this check, so an undeclared process can never pass for the canonical instance.

    Note what is NOT decided here: whether the build is a packaged release or a dev checkout.
    ``app_version`` is returned alongside so the CONSUMER can compose its own eligibility policy — a
    production connector would additionally require an approved packaged identity, while a development
    connector may accept a ``dev-`` one.
    """
    port_file = Path(os.environ.get("APPDATA", "")) / "com.callosum.desktop" / "last-port.txt"
    try:
        port = int(port_file.read_text(encoding="utf-8").strip())
    except Exception as exc:  # noqa: BLE001 — the probe records the failure mode rather than raising
        return {"resolved": False, "reason": "no-port-file", "error": f"{type(exc).__name__}: {exc}"}

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"resolved": False, "reason": "no-backend-on-recorded-port", "port": port, "error": str(exc)}

    role = body.get("instance_role")
    return {
        "resolved": role == "ui",
        "reason": "ok" if role == "ui" else f"role-is-{role!r}-not-ui",
        "port": port,
        "port_file": str(port_file),
        "instance_role": role,
        "app_version": body.get("app_version"),  # the separate axis a consumer composes with
        "ports_probed": 0,  # the port came from packaged state, never from a scan
    }


def main() -> None:
    # Chrome passes the calling extension's origin as argv[1] — the identity check a real host would use.
    caller_origin = sys.argv[1] if len(sys.argv) > 1 else None
    log("host_launched", argv=sys.argv[1:], caller_origin=caller_origin)
    while True:
        try:
            message = read_message()
        except Exception as exc:  # noqa: BLE001
            log("read_error", error=f"{type(exc).__name__}: {exc}")
            return
        if message is None:
            log("stdin_closed")
            return
        log("received", message=message)
        reply = {
            "protocol_version": PROTOCOL_VERSION,
            "connector_host_version": HOST_VERSION,
            "caller_origin": caller_origin,
            "instance": packaged_state(),
            # A real host reports the canonical UI instance's role so an extension can never bind to
            # the Word-HTTPS child (auth gate disabled) or the tunnel target.
            "role": "probe-not-a-real-instance",
            "runtime_state": "probe",
            "echo_of": message.get("id"),
        }
        write_message(reply)
        log("replied", reply=reply)


if __name__ == "__main__":
    main()
