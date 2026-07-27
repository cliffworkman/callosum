"""Spawn a bundled (portable) Python interpreter against a staged callosum source tree, confirm
GET /health comes back 200, then kill it. No Tauri involved — this is the standalone proof that the
portable-Python bundling approach actually works, used both as a local dev check and as a required,
blocking step in the macOS CI build (where it is the only verification anyone gets before the .dmg
reaches a real Mac — see app/desktop-shell's increment notes for why that gap can't be closed here).

Usage: python smoke_test_backend.py --python <path to bundled python(.exe)> --source <staged callosum-src dir>
"""

from __future__ import annotations

import argparse
import collections
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

TIMEOUT_SECONDS = 150
LOG_TAIL_LINES = 40


def _health_check(url: str) -> bool:
    """curl rather than a Python HTTP client — no functional reason, just proven reliable here."""
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-o",
                "NUL" if sys.platform == "win32" else "/dev/null",
                "-w",
                "%{http_code}",
                "--max-time",
                "2",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() == "200"
    except (subprocess.TimeoutExpired, OSError):
        return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _drain(proc: subprocess.Popen, tail: collections.deque) -> None:
    """Continuously read the child's combined stdout/stderr into a bounded tail buffer.

    This is required, not cosmetic: `stdout=PIPE` has a small OS buffer (~64KB on Windows), and
    uvicorn's startup alone emits dozens of multi-line Alembic migration log lines. Left unread
    during the health-poll loop, that buffer fills and the child blocks on its own next write —
    it hangs mid-startup and /health never comes up, which looks exactly like "still starting"
    from the outside. (This was a real bug caught while building this script: the first version
    read stdout only after detecting the child had exited, and every run timed out at 150s because
    the child never got that far.) The real Rust launcher (`backend.rs::drain_output`) does the
    same continuous draining for the same reason — this mirrors it.
    """
    if proc.stdout is None:
        return
    for line in iter(proc.stdout.readline, ""):
        tail.append(line.rstrip("\n"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()

    python_exe = Path(args.python)
    source_root = Path(args.source)
    if not python_exe.exists():
        print(f"FAIL: interpreter not found: {python_exe}", file=sys.stderr)
        return 1
    if not (source_root / "app" / "backend" / "api" / "app.py").is_file():
        print(f"FAIL: staged source tree missing app/backend/api/app.py under {source_root}", file=sys.stderr)
        return 1

    port = _free_port()
    with tempfile.TemporaryDirectory() as tmp:
        db_url = f"sqlite:///{Path(tmp, 'smoke.sqlite').as_posix()}"
        library_dir = Path(tmp, "library")
        # Inherit the parent environment (TEMP/USERPROFILE/etc. — torch and friends need these) and
        # only override the two callosum-specific vars, matching what the real Tauri launcher does
        # (std::process::Command inherits by default; it never replaces the environment wholesale).
        env = dict(os.environ)
        env["CALLOSUM_DB_URL"] = db_url
        env["CALLOSUM_LIBRARY_DIR"] = str(library_dir)
        proc = subprocess.Popen(
            [
                str(python_exe),
                "-m",
                "uvicorn",
                "app.backend.api.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(source_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        tail: collections.deque = collections.deque(maxlen=LOG_TAIL_LINES)
        threading.Thread(target=_drain, args=(proc, tail), daemon=True).start()

        try:
            deadline = time.monotonic() + TIMEOUT_SECONDS
            url = f"http://127.0.0.1:{port}/health"
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    print(
                        f"FAIL: backend exited early (code {proc.returncode}):\n" + "\n".join(tail),
                        file=sys.stderr,
                    )
                    return 1
                if _health_check(url):
                    print(f"OK: {url} -> 200")
                    return 0
                time.sleep(0.4)
            print(
                f"FAIL: {url} never returned 200 within {TIMEOUT_SECONDS}s. Last output:\n" + "\n".join(tail),
                file=sys.stderr,
            )
            return 1
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
