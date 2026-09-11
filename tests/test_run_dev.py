"""Regression tests for the dev launcher's teardown + port preflight (backlog #83).

The load-bearing property: `_stop_all` must reap the WHOLE process tree, not just the direct child.
`run_dev` spawns `run_local_ai.py`, which itself spawns `llama-server` -- a grandchild that a plain
`terminate()` orphans (on Windows `TerminateProcess` is an immediate hard kill that never lets
run_local_ai's own cleanup run). This spawns a real two-level tree and asserts the grandchild dies.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

from tools import run_dev

# A parent that spawns a long-lived grandchild, records the grandchild's PID to argv[1], then sleeps.
_PARENT = (
    "import sys, subprocess, time, pathlib\n"
    "gc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "pathlib.Path(sys.argv[1]).write_text(str(gc.pid))\n"
    "time.sleep(120)\n"
)


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _force_kill(pid: int) -> None:
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        else:
            os.kill(pid, 9)
    except (OSError, ProcessLookupError):
        pass


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()


def test_port_in_use_false_for_a_free_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # socket closed -> port is free again
    assert run_dev._port_in_use(port) is False


def test_port_in_use_true_when_bound() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        port = held.getsockname()[1]
        assert run_dev._port_in_use(port) is True


def test_stop_all_reaps_the_grandchild(tmp_path) -> None:
    pidfile = tmp_path / "grandchild.pid"
    proc = run_dev._spawn([sys.executable, "-c", _PARENT, str(pidfile)], os.environ.copy())
    grandchild: int | None = None
    try:
        assert _wait_until(pidfile.exists, timeout=20), "parent never recorded the grandchild PID"
        grandchild = int(pidfile.read_text().strip())
        assert _pid_alive(grandchild), "grandchild should be running before teardown"

        run_dev._stop_all({"parent": proc})

        assert _wait_until(lambda: not _pid_alive(grandchild), timeout=15), (
            "grandchild orphaned after _stop_all -- backlog #83 regression"
        )
        assert proc.poll() is not None, "the direct child should also be gone"
    finally:
        run_dev._stop_all({"parent": proc})
        if grandchild is not None and _pid_alive(grandchild):
            _force_kill(grandchild)
