"""GROBID Docker lifecycle endpoints (backlog #58) — hermetic: every real Docker CLI call is monkeypatched at
the `grobid_lifecycle` layer, never a real subprocess/daemon (mirrors `test_grobid_lifecycle.py`'s own posture,
one layer up)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.backend import grobid_lifecycle
from app.backend.api import create_app


def _await_install_job(client: TestClient, job_id: str) -> dict:
    for _ in range(200):
        body = client.get(f"/grobid/docker/install/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.02)
    raise AssertionError("install job never finished")


def test_docker_status_reports_not_installed(monkeypatch, temp_db_url: str) -> None:
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (False, False))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "absent")
    c = TestClient(create_app(db_url=temp_db_url))
    body = c.get("/grobid/docker/status").json()
    assert body == {
        "docker_installed": False,
        "docker_daemon_running": False,
        "container_state": "absent",
        "managed_url": None,
    }


def test_docker_status_reports_running_with_managed_url(monkeypatch, temp_db_url: str) -> None:
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "running")
    c = TestClient(create_app(db_url=temp_db_url))
    c.post("/grobid/settings", json={"url": "http://127.0.0.1:8070"})
    body = c.get("/grobid/docker/status").json()
    assert body["container_state"] == "running"
    assert body["managed_url"] == "http://127.0.0.1:8070"


def test_install_refused_when_docker_not_installed(monkeypatch, temp_db_url: str) -> None:
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (False, False))
    c = TestClient(create_app(db_url=temp_db_url))
    r = c.post("/grobid/docker/install")
    assert r.status_code == 409 and "not installed" in r.json()["detail"]


def test_install_refused_when_daemon_not_running(monkeypatch, temp_db_url: str) -> None:
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, False))
    c = TestClient(create_app(db_url=temp_db_url))
    r = c.post("/grobid/docker/install")
    assert r.status_code == 409 and "not running" in r.json()["detail"]


def test_install_success_saves_grobid_url(monkeypatch, temp_db_url: str) -> None:
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    monkeypatch.setattr(grobid_lifecycle, "install_and_start", lambda **kw: "http://127.0.0.1:8070")
    c = TestClient(create_app(db_url=temp_db_url))
    r = c.post("/grobid/docker/install")
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    result = _await_install_job(c, job_id)
    assert result["status"] == "done" and result["url"] == "http://127.0.0.1:8070"
    assert c.get("/grobid/status").json() == {"configured": True, "url": "http://127.0.0.1:8070"}


def test_install_failure_reported_as_job_error_not_a_crash(monkeypatch, temp_db_url: str) -> None:
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))

    def _boom(**kw):
        raise grobid_lifecycle.GrobidInstallError("could not download GROBID: network unreachable")

    monkeypatch.setattr(grobid_lifecycle, "install_and_start", _boom)
    c = TestClient(create_app(db_url=temp_db_url))
    job_id = c.post("/grobid/docker/install").json()["job_id"]
    result = _await_install_job(c, job_id)
    assert result["status"] == "error" and "network unreachable" in result["detail"]
    # a failed install must never silently save a bogus grobid_url
    assert c.get("/grobid/status").json() == {"configured": False, "url": None}


def test_install_refuses_a_second_concurrent_attempt(monkeypatch, temp_db_url: str) -> None:
    """`TestClient` runs FastAPI BackgroundTasks synchronously within the request/response cycle, so a real
    two-request race can't be driven through it -- instead seed the job store with an already-"running" job
    directly (the exact precondition `start_install`'s guard checks), then assert a second install is refused."""
    monkeypatch.setattr(grobid_lifecycle, "docker_available", lambda: (True, True))
    app = create_app(db_url=temp_db_url)
    app.state.grobid_lifecycle_jobs.mark_running(app.state.grobid_lifecycle_jobs.create())
    c = TestClient(app)
    r = c.post("/grobid/docker/install")
    assert r.status_code == 409 and "already in progress" in r.json()["detail"]


def test_stop_only_ever_targets_the_fixed_container(monkeypatch, temp_db_url: str) -> None:
    calls: list[str] = []
    monkeypatch.setattr(grobid_lifecycle, "stop_and_remove", lambda: calls.append("stopped"))
    monkeypatch.setattr(grobid_lifecycle, "container_state", lambda name=None: "absent")
    c = TestClient(create_app(db_url=temp_db_url))
    r = c.post("/grobid/docker/stop")
    assert r.status_code == 200 and r.json() == {"container_state": "absent"}
    assert calls == ["stopped"]
