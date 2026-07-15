from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy.exc import OperationalError

from app.backend.persistence.paper_lifecycle_repo import update_paper_metadata
from app.backend.persistence.sqlite_retry import retry_sqlite_locked


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
