from __future__ import annotations

import importlib
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

# Bind the startup module (where the auto-migration machinery lives) for direct calls/monkeypatch.
app_module = importlib.import_module("app.backend.api.startup")

HEAD = "0008_wanted_items"
BEHIND = "0001_persistence_core"


def _db_at(tmp_path: Path, name: str, revision: str) -> str:
    db_url = f"sqlite:///{(tmp_path / name).as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, revision)
    return db_url


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _capture_callosum() -> _ListHandler:
    """Attach a capturing handler directly to the 'callosum' logger.

    We don't use pytest's caplog here: Alembic's env.py runs fileConfig() on every migrate,
    which reconfigures the root logger and removes caplog's capture handler. A handler bound
    to the 'callosum' logger itself survives that (handlers aren't removed by
    disable_existing_loggers), and `_loud` re-enables the logger before each line.
    """
    handler = _ListHandler()
    logging.getLogger("callosum").addHandler(handler)
    return handler


def test_startup_logs_from_to_when_migrating(tmp_path: Path) -> None:
    db_url = _db_at(tmp_path, "behind.sqlite", BEHIND)
    handler = _capture_callosum()
    try:
        app_module._upgrade_database_to_head(db_url)
    finally:
        logging.getLogger("callosum").removeHandler(handler)

    migrated = [r for r in handler.records if "auto-migrated" in r.getMessage()]
    assert migrated, "expected a loud 'auto-migrated' log line"
    assert migrated[0].levelno == logging.WARNING
    assert BEHIND in migrated[0].getMessage() and HEAD in migrated[0].getMessage()  # from -> to named
    assert app_module._current_revision(db_url) == HEAD  # the DB actually advanced


def test_startup_logs_already_at_head(tmp_path: Path) -> None:
    db_url = _db_at(tmp_path, "head.sqlite", "head")
    handler = _capture_callosum()
    try:
        app_module._upgrade_database_to_head(db_url)
    finally:
        logging.getLogger("callosum").removeHandler(handler)

    text = "\n".join(r.getMessage() for r in handler.records)
    assert "already at head" in text
    assert "auto-migrated" not in text  # nothing was applied


def test_startup_migration_failure_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    db_url = _db_at(tmp_path, "behind.sqlite", BEHIND)  # built before patching upgrade

    def boom(*args, **kwargs):
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(app_module.command, "upgrade", boom)
    handler = _capture_callosum()
    try:
        app_module._upgrade_database_to_head(db_url)  # must NOT raise
    finally:
        logging.getLogger("callosum").removeHandler(handler)

    errors = [r for r in handler.records if r.levelno == logging.ERROR and "FAILED" in r.getMessage()]
    assert errors, "expected a loud ERROR log on migration failure"
    assert app_module._current_revision(db_url) == BEHIND  # unchanged — failure was non-fatal
