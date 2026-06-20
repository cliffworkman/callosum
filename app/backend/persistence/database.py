"""Database helpers for the persistence core."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event


def make_engine(url: str, *, echo: bool = False) -> Engine:
    """Create a SQLite engine with foreign-key enforcement enabled."""
    engine = create_engine(url, echo=echo, future=True)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine
