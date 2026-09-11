"""Run callosum's dev server(s) — plain HTTP always, plus HTTPS (for the Word add-in) if the trusted dev cert
is installed — as two supervised subprocesses of ONE parent command (inc 514).

Fixes a real, repeatedly-hit failure mode from running `uvicorn ... --port 8888` and `python tools/run_https.py`
as two SEPARATELY-started processes: they can silently drift apart — different `CALLOSUM_DB_URL` (each process
only ever sees its own launching shell's environment), different code versions (one left running from a much
earlier session while the other got restarted, confirmed live via mismatched `app_version` in `/health`), or
one simply not running at all with nothing to notice until Word's task pane throws "ADD-IN ERROR." This
launcher starts both from ONE command, in ONE parent's environment, and tears both down together if either dies.

    python tools/run_dev.py                # http on :8888 (+ https on :8443 if the dev cert is installed)
    python tools/run_dev.py --port 8080     # a different HTTP port (CALLOSUM_HTTP_PORT env also works)

Word add-in support (see adapters/word/README.md) still needs `npx office-addin-dev-certs install` once; if
that hasn't been run, HTTP starts normally and HTTPS is skipped with a one-line note — never an error, since
most callosum use doesn't touch Word at all.

Scope: this is the DEV-WORKFLOW launcher only. The packaged desktop-shell app (`app/desktop-shell/`) has its
own, separate backend-spawning path (`src-tauri/src/backend.rs`) that picks a random port per launch and
serves plain HTTP only — Word has never been wired into that path. See `INCREMENT-BACKLOG.md` #33/#34's
"packaged desktop app" entry for that separate, harder problem (no `office-addin-dev-certs`-style tooling is
available to an end user's installed copy, and a single cert baked into every install would defeat TLS trust).
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

# Same sys.path fix inc 508 gave run_https.py -- script mode puts this file's own directory on sys.path, not
# the project root, so a sibling `tools.*`/`app.*` import needs the root added explicitly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_https import _dev_cert_paths  # noqa: E402

POLL_INTERVAL = 0.5  # seconds


def _spawn(argv: list[str], env: dict[str, str]) -> subprocess.Popen:
    # On POSIX, give each child its own session/process group so teardown can signal the WHOLE tree
    # (the grandchild llama-server is spawned by run_local_ai.py, a child of a child -- backlog #83).
    # A plain terminate() only ever reaches the direct child, orphaning the grandchild. On Windows the
    # tree is reaped by `taskkill /T` instead (see _terminate_tree), which needs no spawn-time flag.
    kwargs: dict[str, object] = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    return subprocess.Popen(argv, cwd=str(ROOT), env=env, **kwargs)  # noqa: S603 (fixed argv, no request-derived input)


def _clear_local_ai_descriptor(dev_dir: Path) -> None:
    """Defense in depth: a descriptor outliving its llama-server would make the backend report Local AI as
    available and then fail on every request. run_local_ai.py cleans up after itself, but if it was hard-killed
    its `finally` never ran -- so the supervisor clears the pair too, on the way in and on the way out."""
    managed = dev_dir / "managed-local-ai"
    for name in ("target.json", "auth-token"):
        try:
            (managed / name).unlink(missing_ok=True)
        except OSError:
            pass


def _port_in_use(port: int) -> bool:
    """True if 127.0.0.1:<port> is already bound. A plain bind (no SO_REUSEADDR) matches uvicorn's own
    failure mode, so if this says taken, uvicorn's bind would 'Errno 10048 / address already in use' too.
    Without this preflight run_dev announced 'serving on :8888', then died on the bind -- while /health
    answered 200 the whole time because ANOTHER server already held the port, so the tooling looked
    healthy while serving someone else's instance (backlog #83)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def _terminate_tree(proc: subprocess.Popen) -> None:
    """Signal a child AND its descendants. The direct child is a supervisor (uvicorn, or run_local_ai.py
    which itself spawns llama-server); a plain terminate() reaches only the direct child and orphans the
    grandchild (backlog #83). Windows: `taskkill /T` walks the live PID tree and force-kills it. POSIX:
    the child leads its own group (see _spawn), so SIGTERM to the group reaches the grandchild too."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603 - fixed argv apart from our own child's pid
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False
        )
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        proc.terminate()  # group already gone, or we couldn't address it -- fall back to the direct child


def _force_kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        proc.kill()  # taskkill /F already forced the tree; this is a belt-and-suspenders backstop
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()


def _stop_all(procs: dict[str, subprocess.Popen]) -> None:
    for proc in procs.values():
        _terminate_tree(proc)
    for proc in procs.values():
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _force_kill_tree(proc)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass  # nothing more we can do from here; reported below by the caller's descriptor cleanup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=None, help="HTTP port (default: CALLOSUM_HTTP_PORT env, else 8888)")
    parser.add_argument(
        "--local-ai",
        action="store_true",
        help="also start managed Local AI for this dev session (backlog #72; no packaged desktop app needed)",
    )
    args = parser.parse_args()

    http_port = args.port if args.port is not None else int(os.environ.get("CALLOSUM_HTTP_PORT", "8888"))
    if _port_in_use(http_port):
        print(
            f"[run_dev] ERROR: port {http_port} is already in use -- another server (a stray uvicorn, or an "
            f"earlier run_dev?) is holding it. Stop that, or pass --port. Refusing to start, rather than "
            f"announce 'serving' and die on the bind while /health answers someone else's instance (backlog #83)."
        )
        return 1
    env = os.environ.copy()  # both children inherit the SAME environment -- including CALLOSUM_DB_URL

    procs: dict[str, subprocess.Popen] = {}
    dev_dir = ROOT / ".local" / "dev-app-data"
    if args.local_ai:
        # Start Local AI FIRST and set CALLOSUM_APP_DATA_DIR before the servers spawn: the env var is
        # process-local and read at request time, so a server started without it can never see the descriptor.
        _clear_local_ai_descriptor(dev_dir)  # never inherit a descriptor from a previously hard-killed run
        env["CALLOSUM_APP_DATA_DIR"] = str(dev_dir)
        procs["local-ai"] = _spawn([sys.executable, str(ROOT / "tools" / "run_local_ai.py")], env)
        print(f"[run_dev] local-ai: starting (descriptor under {dev_dir}); first run loads ~1 GiB, be patient")
    procs["http"] = _spawn(
        [sys.executable, "-m", "uvicorn", "app.backend.api.app:app", "--host", "127.0.0.1", "--port", str(http_port)],
        env,
    )
    print(f"[run_dev] http:  serving on http://127.0.0.1:{http_port}")

    crt, _key = _dev_cert_paths()
    if crt is not None:
        https_port = int(os.environ.get("CALLOSUM_HTTPS_PORT", "8443"))
        if _port_in_use(https_port):
            print(
                f"[run_dev] https: skipped -- port {https_port} is already in use (an earlier run_https may be "
                f"orphaned). Free it to enable the Word add-in this session."
            )
        else:
            procs["https"] = _spawn([sys.executable, str(ROOT / "tools" / "run_https.py")], env)
            print(f"[run_dev] https: serving on https://localhost:{https_port} -- for the Word add-in")
    else:
        print("[run_dev] https: skipped -- run `npx office-addin-dev-certs install` once to also enable Word")

    print("[run_dev] Ctrl-C to stop both.")
    try:
        while True:
            time.sleep(POLL_INTERVAL)
            for name, proc in procs.items():
                code = proc.poll()
                if code is not None:
                    print(f"[run_dev] {name} exited (code {code}) -- stopping the rest.")
                    _stop_all(procs)
                    _clear_local_ai_descriptor(dev_dir)
                    return 1
    except KeyboardInterrupt:
        print("\n[run_dev] stopping...")
        _stop_all(procs)
        _clear_local_ai_descriptor(dev_dir)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
