from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.backend.persistence.database import make_engine
from app.backend.persistence.paper_lifecycle_repo import update_paper_metadata
from app.backend.persistence.sqlite_retry import retry_sqlite_locked, run_write


def _locked() -> OperationalError:
    return OperationalError("WRITE", (), sqlite3.OperationalError("database is locked"))


def test_retry_sqlite_locked_retries_then_succeeds():
    calls = 0

    def op():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _locked()
        return "ok"

    assert retry_sqlite_locked(op, delay_seconds=0, sleeper=lambda _: None) == "ok"
    assert calls == 3


def test_retry_sqlite_locked_does_not_hide_non_lock_errors():
    calls = 0

    def op():
        nonlocal calls
        calls += 1
        raise OperationalError("WRITE", (), sqlite3.OperationalError("constraint failed"))

    with pytest.raises(OperationalError):
        retry_sqlite_locked(op, delay_seconds=0, sleeper=lambda _: None)
    assert calls == 1


def test_update_paper_metadata_retries_transient_locked_write():
    class _Conn:
        def __init__(self) -> None:
            self.calls = 0

        def execute(self, statement):
            self.calls += 1
            if self.calls == 1:
                raise _locked()
            return None

    conn = _Conn()

    update_paper_metadata(conn, 42, doi="10.1/x")

    assert conn.calls == 2


# ── run_write: transaction-level retry (this increment) ───────────────────────────────────────────────


def test_run_write_returns_result_and_commits(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))

    def op(conn):
        conn.execute(text("INSERT INTO t (v) VALUES ('x')"))
        return "done"

    assert run_write(engine, op, sleeper=lambda _s: None) == "done"
    with engine.connect() as conn:  # a separate connection sees the committed row
        assert conn.execute(text("SELECT COUNT(*) FROM t")).scalar() == 1
    engine.dispose()


def test_run_write_retries_then_succeeds(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
    calls = {"n": 0}

    def flaky(conn):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _locked()
        conn.execute(text("INSERT INTO t (v) VALUES ('ok')"))
        return calls["n"]

    slept: list[float] = []
    assert run_write(engine, flaky, attempts=5, delay_seconds=0.01, sleeper=slept.append) == 3
    assert slept == [0.01, 0.01]  # two backoffs before the succeeding third attempt
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM t")).scalar() == 1  # only the successful attempt committed
    engine.dispose()


def test_run_write_reraises_non_lock_immediately(temp_db_url):
    engine = make_engine(temp_db_url)
    calls = {"n": 0}

    def boom(conn):
        calls["n"] += 1
        raise OperationalError("WRITE", (), sqlite3.OperationalError("no such table: nope"))

    with pytest.raises(OperationalError):
        run_write(engine, boom, attempts=5, sleeper=lambda _s: None)
    assert calls["n"] == 1
    engine.dispose()


def test_run_write_exhausts_attempts_then_reraises(temp_db_url):
    engine = make_engine(temp_db_url)
    calls = {"n": 0}

    def always_locked(conn):
        calls["n"] += 1
        raise _locked()

    with pytest.raises(OperationalError):
        run_write(engine, always_locked, attempts=3, delay_seconds=0.0, sleeper=lambda _s: None)
    assert calls["n"] == 3
    engine.dispose()


def test_run_write_propagates_non_operationalerror_without_retry(temp_db_url):
    """A 404/validation raised inside the closure (e.g. HTTPException) must NOT be retried or swallowed."""
    engine = make_engine(temp_db_url)
    calls = {"n": 0}

    class Sentinel(Exception):
        pass

    def raises_sentinel(conn):
        calls["n"] += 1
        raise Sentinel()

    with pytest.raises(Sentinel):
        run_write(engine, raises_sentinel, sleeper=lambda _s: None)
    assert calls["n"] == 1
    engine.dispose()


def test_run_write_opens_a_fresh_connection_each_attempt(temp_db_url):
    """Each retry uses a NEW connection (fresh snapshot) — the whole point vs. retrying one execute in place."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
    seen: list[int] = []
    calls = {"n": 0}

    def op(conn):
        seen.append(id(conn))
        calls["n"] += 1
        if calls["n"] < 2:
            raise _locked()
        return None

    run_write(engine, op, delay_seconds=0.0, sleeper=lambda _s: None)
    assert len(seen) == 2 and seen[0] != seen[1]  # two distinct connection objects
    engine.dispose()
