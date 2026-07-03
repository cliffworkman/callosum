#!/usr/bin/env python3
"""Spin up callosum against a fresh, seeded, throwaway SQLite DB on a free port.

The fixture contract from `.claude/QA-POLICY.md`, made reusable so every QA route (and every Codex
run) stands the app up identically and NEVER touches the user's real library. Mirrors the server
fixture in `tests/e2e/test_smoke.py`.

Use as a context manager from a Playwright harness:

    from tools.qa._qa_serve import qa_server
    with qa_server() as base_url:        # e.g. http://127.0.0.1:54123
        ...  # drive base_url with Playwright; teardown is automatic

or as a CLI (prints the base URL, serves until you Ctrl-C / kill it):

    python tools/qa/_qa_serve.py            # egress stays OFF
    python tools/qa/_qa_serve.py --egress   # Tier-2 only: sets CALLOSUM_ALLOW_DATA_EGRESS=1

The DB lives in a temp dir and is deleted on exit. `CALLOSUM_ALLOW_DATA_EGRESS` is explicitly removed
from the child env unless --egress is passed, so a route can assert the gate honestly.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import httpx

from alembic import command
from alembic.config import Config

# repo root = two levels up from tools/qa/
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tests.api_helpers import _seed_library  # noqa: E402  (the canonical seed — pin it; see QA-POLICY)


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_health(base: str, proc: subprocess.Popen, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"uvicorn exited early (code {proc.returncode})")
        try:
            if httpx.get(base + "/health", timeout=1.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("uvicorn did not become healthy within 30s")


@contextlib.contextmanager
def qa_server(*, egress: bool = False) -> Iterator[str]:
    tmp = tempfile.TemporaryDirectory(prefix="callosum_qa_")
    db_path = Path(tmp.name) / "qa.sqlite"
    db_url = f"sqlite:///{db_path.as_posix()}"

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
    _seed_library(db_url)

    port = _free_port()
    env = {**os.environ, "CALLOSUM_DB_URL": db_url, "PYTHONPATH": str(REPO_ROOT)}
    # Isolate from the user's SHARED settings (~/.callosum/app-settings.json), not just their DB: point
    # CALLOSUM_SETTINGS_PATH at a throwaway file so no stored BYOK key / remote token / Remote-access toggle
    # leaks in, and force the remote-access gate OFF regardless. Without this, Remote access left enabled in
    # the real settings 401s every QA request — the disposable DB doesn't help (settings are a separate file) —
    # which stalled a whole run (backlog #46). A route that exercises Settings then mutates this temp file, not
    # the user's real one.
    env["CALLOSUM_SETTINGS_PATH"] = str(Path(tmp.name) / "qa-app-settings.json")
    env["CALLOSUM_DISABLE_REMOTE_ACCESS"] = "1"
    # Isolate the *library folder* too. The library folder is default-watched and auto-rescanned on launch
    # (inc 160); with CALLOSUM_LIBRARY_DIR unset, library_dir() falls back to PROJECT_ROOT/library, so the
    # disposable instance imports the user's real PDFs into the throwaway DB (documented 3 seeded papers ->
    # "50 shown") AND that background import starves the single WAL write slot, 500-ing foreground writes with
    # "database is locked" (QA runs 20260702/03, routes 15/23/30/65). Point it at an empty temp dir so the
    # launch rescan finds nothing to import and the fixture stays exactly the seeded library.
    empty_library = Path(tmp.name) / "empty-library"
    empty_library.mkdir(exist_ok=True)
    env["CALLOSUM_LIBRARY_DIR"] = str(empty_library)
    if egress:
        env["CALLOSUM_ALLOW_DATA_EGRESS"] = "1"
    else:
        env.pop("CALLOSUM_ALLOW_DATA_EGRESS", None)  # assert the gate honestly

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.backend.api.app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base, proc)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        tmp.cleanup()


def main() -> int:
    ap = argparse.ArgumentParser(description="serve a seeded throwaway callosum for QA")
    ap.add_argument("--egress", action="store_true", help="Tier-2 only: enable CALLOSUM_ALLOW_DATA_EGRESS")
    args = ap.parse_args()
    with qa_server(egress=args.egress) as base:
        print(base, flush=True)
        print("[qa-serve] serving; Ctrl-C to stop", file=sys.stderr)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
