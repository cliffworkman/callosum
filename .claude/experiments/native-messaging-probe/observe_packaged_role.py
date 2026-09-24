"""Observe the packaged UI backend's instance_role under a DISPOSABLE app-data directory.

EXPERIMENTAL HARNESS for issue #61's prerequisite verification. Not product code.

Isolation contract (the whole point of this script):

  1. refuse to run if installed Callosum is still running;
  2. rename the REAL %APPDATA%\\com.callosum.desktop out of the way;
  3. let the test build create a fresh, disposable app-data directory;
  4. observe;
  5. delete the disposable directory;
  6. restore the real directory unchanged.

The real library database is never opened, never copied, and never written to. If any step of the
isolation cannot be completed, this STOPS rather than falling back to the real library — losing an
observation is acceptable; touching a real 67 MB library is not.

The managed Python runtime lives under LOCAL app data, not Roaming, so renaming Roaming isolates the
library while leaving the runtime resolvable.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

APP_DATA = Path(os.environ["APPDATA"]) / "com.callosum.desktop"
EXE = Path(
    r"C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum\.claude\worktrees"
    r"\browser-capture-research\app\desktop-shell\src-tauri\target\release\callosum-shell.exe"
)
HEALTH_TIMEOUT = 180  # the shell allows 120s for eager ML imports; leave headroom


def fail(message: str) -> None:
    print(f"STOP: {message}", file=sys.stderr)
    raise SystemExit(1)


def callosum_running() -> bool:
    out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=60).stdout.lower()
    return "callosum-shell.exe" in out


def health(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None


def main() -> int:
    if not EXE.is_file():
        fail(f"built binary not found: {EXE}")
    if callosum_running():
        fail("installed Callosum is still running; close it before isolating the app-data directory")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    parked = APP_DATA.with_name(f"com.callosum.desktop.real-{stamp}")
    had_real_dir = APP_DATA.exists()

    if had_real_dir:
        try:
            APP_DATA.rename(parked)
        except OSError as exc:
            fail(f"could not rename the real app-data directory ({exc}); refusing to run against it")
        print(f"[isolate] real app-data parked at {parked.name}")
    else:
        print("[isolate] no existing app-data directory; the test build gets a fresh one anyway")

    observations: dict = {"disposable_app_data": str(APP_DATA)}
    proc = None
    try:
        proc = subprocess.Popen([str(EXE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[run] packaged binary started against the disposable directory")

        port_file = APP_DATA / "last-port.txt"
        deadline = time.monotonic() + HEALTH_TIMEOUT
        body = None
        port = None
        while time.monotonic() < deadline:
            if port_file.is_file():
                try:
                    port = int(port_file.read_text(encoding="utf-8").strip())
                except (OSError, ValueError):
                    port = None
                if port:
                    body = health(port)
                    if body:
                        break
            time.sleep(1.0)

        observations["last_port_txt"] = port
        observations["health"] = body
        if body:
            # The exit question, exercised end to end: can the native host identify the canonical UI
            # backend from packaged state alone, with no port probing? Drive the REAL probe host over
            # its stdio framing, exactly as the browser launches it.
            import struct

            request = json.dumps({"id": "resolve-1", "protocol_version": 1}).encode("utf-8")
            host = subprocess.run(
                ["cmd", "/c", str(Path(__file__).with_name("host.bat")), "chrome-extension://observed/"],
                input=struct.pack("<I", len(request)) + request,
                capture_output=True,
                timeout=60,
            )
            if len(host.stdout) >= 4:
                (size,) = struct.unpack("<I", host.stdout[:4])
                observations["connector_host_resolution"] = json.loads(host.stdout[4 : 4 + size].decode("utf-8"))[
                    "instance"
                ]
            else:
                observations["connector_host_resolution"] = {"error": host.stderr.decode(errors="replace")[:300]}

            observations["instance_role"] = body.get("instance_role")
            observations["app_version"] = body.get("app_version")
            print(json.dumps(observations, indent=2))
            print(f"\nRESULT instance_role={body.get('instance_role')!r} app_version={body.get('app_version')!r}")
        else:
            print(f"UNOBSERVED: no healthy backend within {HEALTH_TIMEOUT}s (port={port})", file=sys.stderr)
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
        subprocess.run(["taskkill", "/F", "/IM", "callosum-shell.exe"], capture_output=True)
        time.sleep(2)

        # 5. delete the disposable directory, 6. restore the real one unchanged.
        if had_real_dir:
            if APP_DATA.exists():
                shutil.rmtree(APP_DATA, ignore_errors=True)
            if APP_DATA.exists():
                print(
                    f"WARNING: could not delete the disposable directory; the real one is still at {parked}",
                    file=sys.stderr,
                )
            else:
                parked.rename(APP_DATA)
                print("[restore] real app-data directory restored unchanged")

    out = Path(__file__).with_name("packaged-role-observation.json")
    out.write_text(json.dumps(observations, indent=2), encoding="utf-8")
    print(f"[saved] {out}")
    return 0 if observations.get("health") else 1


if __name__ == "__main__":
    raise SystemExit(main())
