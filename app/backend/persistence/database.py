"""Database helpers for the persistence core."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event


def make_engine(url: str, *, echo: bool = False) -> Engine:
    """Create a SQLite engine with foreign-key enforcement + a lock-wait timeout enabled."""
    engine = create_engine(url, echo=echo, future=True)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # uvicorn serves sync endpoints from a threadpool → concurrent connections to the one
            # SQLite file. With the default rollback journal a reader's SHARED lock blocks a writer
            # from upgrading to EXCLUSIVE, so a write racing the list-refresh GET it triggers fails
            # with "database is locked" (busy_timeout alone can't break that upgrade contention).
            # WAL lets the single writer proceed alongside readers; busy_timeout makes any residual
            # write-write collision wait instead of erroring. The standard local-SQLite-under-a-
            # web-server pairing. (WAL is a persistent DB-level pragma; re-setting per-connect is a
            # harmless no-op.)
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine
