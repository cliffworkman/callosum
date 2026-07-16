"""External API cache helper behavior."""

from __future__ import annotations

import sqlite3

from sqlalchemy.exc import OperationalError

from integrations.api_cache import put_cached


def test_put_cached_retries_transient_lock_then_writes():
    class _Result:
        def mappings(self):
            return self

        def first(self):
            return None

    class _Conn:
        def __init__(self) -> None:
            self.write_calls = 0

        def execute(self, statement):
            if statement.__class__.__name__ == "Select":
                return _Result()
            self.write_calls += 1
            if self.write_calls == 1:
                raise OperationalError("INSERT", (), sqlite3.OperationalError("database is locked"))
            return None

    conn = _Conn()

    put_cached(
        conn,
        "openalex",
        "work:W1",
        request_json={"work_id": "W1"},
        response_json={"id": "W1"},
        status_code=200,
    )

    assert conn.write_calls == 2


def test_put_cached_lock_is_nonfatal():
    class _Result:
        def mappings(self):
            return self

        def first(self):
            return None

    class _LockedConn:
        def execute(self, statement):
            if statement.__class__.__name__ == "Select":
                return _Result()
            raise OperationalError("INSERT", (), sqlite3.OperationalError("database is locked"))

    put_cached(
        _LockedConn(),
        "semantic-scholar",
        "references:10.1/x",
        request_json={"doi": "10.1/x"},
        response_json={"data": []},
        status_code=200,
    )


def test_put_cached_reraises_non_lock_operational_error():
    class _BrokenConn:
        def execute(self, statement):
            raise OperationalError("INSERT", (), sqlite3.OperationalError("no such table: external_api_cache"))

    try:
        put_cached(
            _BrokenConn(),
            "crossref",
            "10.1/x",
            request_json={"doi": "10.1/x"},
            response_json={"status": "ok"},
            status_code=200,
        )
    except OperationalError as exc:
        assert "no such table" in str(exc.orig)
    else:  # pragma: no cover - explicit failure reads better than pytest.raises for this tiny fake
        raise AssertionError("non-lock OperationalError was swallowed")


def test_put_cached_committing_self_commits(temp_db_url):
    """inc D: put_cached_committing writes in its OWN transaction — a fresh connection sees the entry with no
    caller transaction (so a fetch phase on a read connection can cache without holding the caller's write lock)."""
    from sqlalchemy import select

    from app.backend.persistence.database import make_engine
    from app.backend.persistence.schema import external_api_cache
    from integrations.api_cache import get_cached, put_cached_committing

    engine = make_engine(temp_db_url)
    put_cached_committing(  # no caller transaction
        engine,
        "openalex",
        "work:W1",
        request_json={"work_id": "W1"},
        response_json={"title": "X"},
        status_code=200,
    )
    with engine.connect() as conn:  # a fresh connection sees it → it was committed
        row = get_cached(conn, "openalex", "work:W1")
        assert row is not None and row["response_json"] == {"title": "X"}
        assert conn.execute(select(external_api_cache).where(external_api_cache.c.cache_key == "work:W1")).first()
    engine.dispose()
