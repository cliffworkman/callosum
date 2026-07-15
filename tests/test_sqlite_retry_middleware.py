"""Tests for the backstop SqliteWriteRetryMiddleware (Layer 2 of the 'database is locked' hardening).

A tiny FastAPI app whose routes raise a transient lock error a fixed number of times, so we can assert the
middleware replays a replay-safe mutating request, and does NOT replay GETs, denylisted paths, non-lock errors,
or beyond the attempt cap.
"""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.backend.api.sqlite_retry_middleware import SqliteWriteRetryMiddleware, is_replay_safe


def _locked() -> OperationalError:
    return OperationalError("WRITE", (), sqlite3.OperationalError("database is locked"))


def _app(fail_times: dict[str, int], *, attempts: int = 4):
    """A FastAPI app whose routes raise a lock error `fail_times[name]` times, decrementing per call."""
    app = FastAPI()
    app.add_middleware(SqliteWriteRetryMiddleware, attempts=attempts, delay_seconds=0)
    calls: dict[str, int] = {}

    def _maybe_fail(name: str):
        calls[name] = calls.get(name, 0) + 1
        if calls[name] <= fail_times.get(name, 0):
            raise _locked()

    @app.post("/papers/1/read")
    def read_ok(payload: dict | None = None):
        _maybe_fail("read")
        return {"ok": True, "calls": calls["read"]}

    @app.get("/papers")
    def get_papers():
        _maybe_fail("get")
        return {"ok": True}

    @app.post("/library/scan")
    def scan():
        _maybe_fail("scan")
        return {"ok": True}

    @app.post("/papers/1/boom")
    def boom():
        calls["boom"] = calls.get("boom", 0) + 1
        raise OperationalError("WRITE", (), sqlite3.OperationalError("constraint failed"))

    return app, calls


def test_replay_safe_denylist():
    assert is_replay_safe("/papers/1/read") is True
    assert is_replay_safe("/tags/5/color") is True
    assert is_replay_safe("/reading-queue") is True
    assert is_replay_safe("/library/scan") is False  # job + FS
    assert is_replay_safe("/settings") is False  # secret write
    assert is_replay_safe("/axes/3/score") is False  # scoring job (substring)
    assert is_replay_safe("/papers/1/reprocess-pdf") is False  # substring
    assert is_replay_safe("/summaries") is False


def test_mutating_request_is_replayed_until_success():
    app, calls = _app({"read": 2})  # fail twice, succeed on the 3rd
    client = TestClient(app)
    r = client.post("/papers/1/read", json={})
    assert r.status_code == 200
    assert r.json()["calls"] == 3  # the handler ran three times (2 lock retries + success)


def test_get_is_not_retried():
    app, calls = _app({"get": 1})
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/papers")
    assert r.status_code == 500  # a GET is never replayed; the single failure surfaces
    assert calls["get"] == 1


def test_denylisted_path_is_not_retried():
    app, calls = _app({"scan": 1})
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/library/scan")
    assert r.status_code == 500  # replay-unsafe → not retried
    assert calls["scan"] == 1


def test_non_lock_error_is_not_retried():
    app, calls = _app({})
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/papers/1/boom")
    assert r.status_code == 500
    assert calls["boom"] == 1  # a non-lock OperationalError propagates immediately


def test_attempts_are_capped():
    app, calls = _app({"read": 99}, attempts=3)  # always locked
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/papers/1/read", json={})
    assert r.status_code == 500
    assert calls["read"] == 3  # exactly `attempts` tries, then gives up


def test_request_body_is_replayed_on_each_attempt():
    """The buffered body must reach the handler on every retry, not just the first."""
    app = FastAPI()
    app.add_middleware(SqliteWriteRetryMiddleware, attempts=4, delay_seconds=0)
    seen: list[dict] = []
    state = {"n": 0}

    @app.post("/papers/1/read")
    def read_body(payload: dict):
        state["n"] += 1
        seen.append(payload)
        if state["n"] < 2:
            raise _locked()
        return {"got": payload}

    client = TestClient(app)
    r = client.post("/papers/1/read", json={"hello": "world"})
    assert r.status_code == 200
    assert r.json() == {"got": {"hello": "world"}}
    assert seen == [{"hello": "world"}, {"hello": "world"}]  # same body both attempts
