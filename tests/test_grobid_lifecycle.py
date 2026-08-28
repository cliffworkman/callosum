"""Hermetic tests for GROBID's Docker lifecycle management (backlog #58) — a fake `subprocess.run` stands in
for the real Docker CLI throughout (never touches a real Docker daemon), matching this codebase's established
injected-fake pattern for external processes/services."""

from __future__ import annotations

import subprocess

import pytest

from app.backend import grobid_lifecycle


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeDocker:
    """Dispatches on the docker subcommand (argv[1]) so a test can script exactly what each call returns,
    in order, per subcommand -- mirrors real Docker CLI usage without a real daemon."""

    def __init__(self, **responses) -> None:
        # responses: e.g. {"info": _FakeCompleted(0), "pull": [_FakeCompleted(1), _FakeCompleted(0)]}
        # A list is consumed in order (one entry per call); a bare value is returned every time.
        self._responses = responses
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        sub = argv[1] if len(argv) > 1 else argv[0]
        entry = self._responses.get(sub, _FakeCompleted(0))
        if isinstance(entry, list):
            return entry.pop(0)
        return entry


# --- docker_available --------------------------------------------------------------------------------------


def test_docker_available_not_installed(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle.shutil, "which", lambda name: None)
    assert grobid_lifecycle.docker_available() == (False, False)


def test_docker_available_installed_but_daemon_down(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", _FakeDocker(info=_FakeCompleted(1)))
    assert grobid_lifecycle.docker_available() == (True, False)


def test_docker_available_daemon_down_raises_oserror(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle.shutil, "which", lambda name: "/usr/bin/docker")

    def _boom(*a, **k):
        raise OSError("no such pipe")

    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", _boom)
    assert grobid_lifecycle.docker_available() == (True, False)


def test_docker_available_installed_and_running(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", _FakeDocker(info=_FakeCompleted(0)))
    assert grobid_lifecycle.docker_available() == (True, True)


# --- container_state ----------------------------------------------------------------------------------------


def test_container_state_absent_when_inspect_fails(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", _FakeDocker(inspect=_FakeCompleted(1)))
    assert grobid_lifecycle.container_state() == "absent"


def test_container_state_running(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", _FakeDocker(inspect=_FakeCompleted(0, stdout="running\n")))
    assert grobid_lifecycle.container_state() == "running"


def test_container_state_stopped(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", _FakeDocker(inspect=_FakeCompleted(0, stdout="exited\n")))
    assert grobid_lifecycle.container_state() == "stopped"


# --- install_and_start ---------------------------------------------------------------------------------------


def _patch_ready(monkeypatch, sequence):
    """sequence: a list of bools consumed in order by successive _ping_isalive calls."""
    it = iter(sequence)

    def _fake_ping(url, timeout=5.0):
        try:
            return next(it)
        except StopIteration:
            return False

    monkeypatch.setattr(grobid_lifecycle, "_ping_isalive", _fake_ping)
    monkeypatch.setattr(grobid_lifecycle, "_READY_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(grobid_lifecycle, "_READY_TIMEOUT", 0.05)


def test_install_and_start_refuses_when_docker_not_installed(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (False, False))
    with pytest.raises(grobid_lifecycle.GrobidInstallError, match="not installed"):
        grobid_lifecycle.install_and_start()


def test_install_and_start_refuses_when_daemon_not_running(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, False))
    with pytest.raises(grobid_lifecycle.GrobidInstallError, match="not running"):
        grobid_lifecycle.install_and_start()


def test_install_and_start_success(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "absent")
    fake = _FakeDocker(pull=_FakeCompleted(0), run=_FakeCompleted(0))
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", fake)
    _patch_ready(monkeypatch, [True])

    stages: list[str] = []
    url = grobid_lifecycle.install_and_start(on_progress=stages.append)

    assert url == f"http://127.0.0.1:{grobid_lifecycle.GROBID_DEFAULT_PORT}"
    assert any("Downloading" in s for s in stages) and any("ready" in s for s in stages)
    pull_call = next(c for c in fake.calls if c[1] == "pull")
    assert pull_call == ["docker", "pull", grobid_lifecycle.GROBID_IMAGE]


def test_install_and_start_removes_stale_container_first(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "stopped")
    fake = _FakeDocker(pull=_FakeCompleted(0), run=_FakeCompleted(0))
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", fake)
    _patch_ready(monkeypatch, [True])

    grobid_lifecycle.install_and_start()

    rm_call = next(c for c in fake.calls if c[1] == "rm")
    assert rm_call == ["docker", "rm", "-f", grobid_lifecycle.GROBID_CONTAINER_NAME]
    # the stale-cleanup rm must happen BEFORE the pull
    assert fake.calls.index(rm_call) < next(i for i, c in enumerate(fake.calls) if c[1] == "pull")


def test_install_and_start_pull_failure_surfaces_stderr(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "absent")
    monkeypatch.setattr(
        grobid_lifecycle.subprocess, "run", _FakeDocker(pull=_FakeCompleted(1, stderr="no matching manifest"))
    )
    with pytest.raises(grobid_lifecycle.GrobidInstallError, match="no matching manifest"):
        grobid_lifecycle.install_and_start()


def test_install_and_start_falls_back_to_free_port_on_conflict(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "absent")
    monkeypatch.setattr(grobid_lifecycle, "_free_port", lambda: 54321)
    fake = _FakeDocker(
        pull=_FakeCompleted(0),
        run=[_FakeCompleted(1, stderr="Bind for 0.0.0.0:8070 failed: port is already allocated"), _FakeCompleted(0)],
    )
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", fake)
    _patch_ready(monkeypatch, [True])

    url = grobid_lifecycle.install_and_start()

    assert url == "http://127.0.0.1:54321"
    run_calls = [c for c in fake.calls if c[1] == "run"]
    assert len(run_calls) == 2
    assert "8070:8070" in run_calls[0] and "54321:8070" in run_calls[1]


def test_install_and_start_run_failure_for_other_reason_does_not_retry(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "absent")
    fake = _FakeDocker(pull=_FakeCompleted(0), run=_FakeCompleted(1, stderr="Error: no such image"))
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", fake)
    with pytest.raises(grobid_lifecycle.GrobidInstallError, match="no such image"):
        grobid_lifecycle.install_and_start()
    assert len([c for c in fake.calls if c[1] == "run"]) == 1


def test_install_and_start_never_becomes_ready(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "absent")
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", _FakeDocker(pull=_FakeCompleted(0), run=_FakeCompleted(0)))
    _patch_ready(monkeypatch, [])  # _ping_isalive always returns False
    with pytest.raises(grobid_lifecycle.GrobidInstallError, match="never became ready"):
        grobid_lifecycle.install_and_start()


def test_install_and_start_pull_timeout(monkeypatch):
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "absent")

    def _timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", _timeout)
    with pytest.raises(grobid_lifecycle.GrobidInstallError, match="timed out"):
        grobid_lifecycle.install_and_start()


# --- stop_and_remove ------------------------------------------------------------------------------------------


def test_stop_and_remove_only_ever_targets_the_fixed_container_name(monkeypatch):
    fake = _FakeDocker(rm=_FakeCompleted(0))
    monkeypatch.setattr(grobid_lifecycle.subprocess, "run", fake)
    grobid_lifecycle.stop_and_remove()
    assert fake.calls == [["docker", "rm", "-f", "callosum-grobid"]]


def test_stop_and_remove_is_a_noop_when_absent(monkeypatch):
    monkeypatch.setattr(
        grobid_lifecycle.subprocess, "run", _FakeDocker(rm=_FakeCompleted(1, stderr="No such container"))
    )
    grobid_lifecycle.stop_and_remove()  # must not raise
