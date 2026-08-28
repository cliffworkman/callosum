"""GROBID Docker lifecycle management (backlog #58).

GROBID (``integrations/grobid/``) is a self-hosted document-structure-parsing service that today requires the
user to already know Docker: pull the right image, run it with the right flags, and paste a URL into Settings.
This module lets callosum drive Docker on the user's behalf instead — detect it, pull a fixed lightweight image,
run/stop it, and poll for readiness — so no Docker knowledge is required. GROBID itself is still **not bundled**
into callosum's installer; Docker Desktop remains a one-time external prerequisite the user installs themselves
(same posture as LibreOffice for the citation adapter, or ``cloudflared`` for the Google Docs bridge) — this
module only detects Docker's presence and orchestrates it, never installs Docker itself.

Every subprocess argv element below is a fixed module-level constant, never built from request/user input —
the image tag, container name, and internal port are hardcoded; the only value derived at runtime is the local
bind port, which is either the fixed default or a locally-picked free port (never user-supplied). This keeps
the command surface structurally free of injection risk (rule #3's spirit, applied to shell commands rather
than SQL). See ``.claude/security-audits/2026-08-28_grobid-docker-lifecycle.md``.

No byte-level download progress: no precedent for it exists anywhere in this codebase's other "download a
public artifact" jobs (Retraction Watch / TOP Factor / AJOL mirrors all go straight running -> done with no
byte progress either) -- an indeterminate progress bar during ``docker pull`` is honest and consistent, not a
missing feature. Real byte-progress (parsing Docker's own pull-progress JSON stream) is a defensible future
refinement, not required here.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
from collections.abc import Callable
from typing import Literal

import httpx

GROBID_IMAGE = "grobid/grobid:0.9.1-crf"  # lightweight, CPU-only, ~500MB -- the right default for "just make it work"
# (the ~8GB GPU-optional -full tag is deliberately not offered in v1 -- no UI for it, simplest honest scope)
GROBID_CONTAINER_NAME = "callosum-grobid"  # fixed name: both the run target AND the "is this ours" detection key
GROBID_DEFAULT_PORT = 8070  # matches what a user would type manually today
GROBID_INTERNAL_PORT = 8070  # the port GROBID listens on inside the container (fixed by the image)

_DOCKER_CMD_TIMEOUT = 10.0  # a plain docker CLI query (info/inspect) should never hang
_PULL_TIMEOUT = 20 * 60.0  # ~500MB should complete comfortably within 20 minutes on any real connection
_RUN_TIMEOUT = 15.0  # `docker run -d` itself just starts the container, doesn't wait for readiness
_READY_TIMEOUT = 120.0  # GROBID's JVM startup + model load, bounded
_READY_POLL_INTERVAL = 2.0
_STOP_TIMEOUT = 20.0

ContainerState = Literal["absent", "running", "stopped"]


class GrobidInstallError(Exception):
    """Raised when the install/start sequence fails at any stage. The message is always the real underlying
    detail (Docker's own stderr, or a plain timeout/readiness explanation) -- never hidden (invariant #4)."""


def docker_available() -> tuple[bool, bool]:
    """(docker_installed, daemon_running). Never raises -- every failure mode is a normal (False, False) or
    (True, False) result, not an exception, since "Docker isn't set up yet" is an expected UI state."""
    if shutil.which("docker") is None:
        return False, False
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=_DOCKER_CMD_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return True, False
    return True, result.returncode == 0


def container_state(name: str = GROBID_CONTAINER_NAME) -> ContainerState:
    """Read-only Docker inspect -- the container's own existence/name is the sole source of truth for
    "does callosum have a managed instance," never a separately persisted flag that could drift from reality."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", name],
            capture_output=True,
            timeout=_DOCKER_CMD_TIMEOUT,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "absent"
    if result.returncode != 0:
        return "absent"
    return "running" if result.stdout.strip().lower() == "running" else "stopped"


def _free_port() -> int:
    """Bind ephemeral, read back the OS-assigned port, release -- the same TOCTOU-tolerant pattern used
    elsewhere in this codebase for local port allocation (a genuine race is vanishingly unlikely for a
    same-machine, moments-later `docker run`, and `docker run` itself would fail cleanly if lost)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ping_isalive(url: str, timeout: float = 5.0) -> bool:
    """The exact GROBID readiness check `grobid.py::test_connection` already uses -- reused, not duplicated."""
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{url.rstrip('/')}/api/isalive")
    except httpx.HTTPError:
        return False
    return 200 <= resp.status_code < 300


def install_and_start(*, on_progress: Callable[[str], None] | None = None) -> str:
    """Pull GROBID_IMAGE, run it as GROBID_CONTAINER_NAME, wait for readiness. Returns the reachable
    ``http://127.0.0.1:<port>`` URL. Raises GrobidInstallError with a human-readable detail on any failure.
    ``on_progress`` is an optional coarse stage-label callback (see the module docstring on why there's no
    byte-level progress)."""
    installed, running = docker_available()
    if not installed:
        raise GrobidInstallError("Docker is not installed. Install Docker Desktop, then try again.")
    if not running:
        raise GrobidInstallError("Docker is installed but not running. Start Docker Desktop, then try again.")

    # A leftover container from a prior failed attempt (stopped, or "created" but never started) would make
    # `docker run --name callosum-grobid` fail with a "name is already in use" error unrelated to ports --
    # clear it first so every install attempt starts from a clean slate. Fixed name only; never touches any
    # other container.
    if container_state() != "absent":
        _remove(GROBID_CONTAINER_NAME)

    if on_progress:
        on_progress(f"Downloading GROBID ({GROBID_IMAGE})…")
    try:
        pull = subprocess.run(["docker", "pull", GROBID_IMAGE], capture_output=True, timeout=_PULL_TIMEOUT, text=True)
    except subprocess.TimeoutExpired as exc:
        raise GrobidInstallError(
            f"Downloading {GROBID_IMAGE} timed out after {int(_PULL_TIMEOUT / 60)} minutes."
        ) from exc
    if pull.returncode != 0:
        raise GrobidInstallError(f"Could not download GROBID: {(pull.stderr or pull.stdout).strip()}")

    if on_progress:
        on_progress("Starting GROBID…")
    port = GROBID_DEFAULT_PORT
    run = _docker_run(port)
    if run.returncode != 0 and "port is already allocated" in (run.stderr or "").lower():
        port = _free_port()
        run = _docker_run(port)
    if run.returncode != 0:
        raise GrobidInstallError(f"Could not start GROBID: {(run.stderr or run.stdout).strip()}")

    url = f"http://127.0.0.1:{port}"
    if on_progress:
        on_progress("Waiting for GROBID to become ready…")
    deadline = time.monotonic() + _READY_TIMEOUT
    while time.monotonic() < deadline:
        if _ping_isalive(url):
            return url
        time.sleep(_READY_POLL_INTERVAL)
    raise GrobidInstallError(
        "GROBID started but never became ready in time. It may still be starting -- check again shortly, or "
        "run `docker logs callosum-grobid` for detail."
    )


def _docker_run(port: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                GROBID_CONTAINER_NAME,
                "-p",
                f"{port}:{GROBID_INTERNAL_PORT}",
                GROBID_IMAGE,
            ],
            capture_output=True,
            timeout=_RUN_TIMEOUT,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise GrobidInstallError("Starting the GROBID container timed out.") from exc


def _remove(name: str) -> None:
    try:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=_STOP_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        pass  # best-effort cleanup; a subsequent container_state() check reflects the true state either way


def stop_and_remove() -> None:
    """Stop + remove ONLY the fixed callosum-grobid container. A no-op if it doesn't exist. The target name
    is always the module constant, never a parameter -- structurally incapable of touching a user's own
    manually-run GROBID container (or anything else Docker-managed on their machine)."""
    _remove(GROBID_CONTAINER_NAME)
