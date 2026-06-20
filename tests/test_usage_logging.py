"""Tests for the token-usage logger (``app/backend/llm/usage.py``, inc 61).

It is deliberately failure-proof — a missing or malformed ``usage_metadata`` must never raise — and
emits one INFO line per call so real token spend can be measured. These pin both properties.

The ``callosum`` logger does not propagate to root in every configuration, so we capture by attaching
a handler to the actual ``callosum.llm.usage`` logger rather than relying on pytest's ``caplog``
(which listens on root).
"""

from __future__ import annotations

import contextlib
import logging

from app.backend.llm.usage import log_usage
from app.backend.llm.usage import logger as usage_logger


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@contextlib.contextmanager
def _capture():
    # Alembic's env.py runs fileConfig(disable_existing_loggers=True) on every migration, which sets
    # callosum.llm.usage.disabled = True as a side effect once that logger exists — so after any test
    # that migrates a DB, this logger is disabled. Force it back on so we test log_usage's own logic.
    handler = _ListHandler()
    prev_level = usage_logger.level
    prev_disabled = usage_logger.disabled
    usage_logger.addHandler(handler)
    usage_logger.setLevel(logging.INFO)
    usage_logger.disabled = False
    try:
        yield handler
    finally:
        usage_logger.removeHandler(handler)
        usage_logger.setLevel(prev_level)
        usage_logger.disabled = prev_disabled


class _Meta:
    prompt_token_count = 11
    candidates_token_count = 22
    total_token_count = 33


class _RespWithMeta:
    usage_metadata = _Meta()


def _usage_messages(handler: _ListHandler) -> list[str]:
    return [m for m in handler.messages if "llm-usage" in m]


def test_logs_token_counts():
    with _capture() as cap:
        log_usage("summary", "gemini-2.5-flash-lite", _RespWithMeta())
    messages = _usage_messages(cap)
    assert len(messages) == 1
    msg = messages[0]
    assert "site=summary" in msg
    assert "model=gemini-2.5-flash-lite" in msg
    assert "prompt=11" in msg and "candidates=22" in msg and "total=33" in msg


def test_no_usage_metadata_attr_is_silent():
    class _Bare:
        pass

    with _capture() as cap:
        log_usage("summary", "m", _Bare())
    assert _usage_messages(cap) == []


def test_none_usage_metadata_is_silent():
    class _RespNone:
        usage_metadata = None

    with _capture() as cap:
        log_usage("summary", "m", _RespNone())
    assert _usage_messages(cap) == []


def test_logger_survives_alembic_migration(tmp_path):
    """A migration must not leave the usage logger disabled.

    Regression test for the env.py fix (disable_existing_loggers=False): before the fix, the startup
    auto-migration's fileConfig disabled callosum.llm.usage, silently killing usage logging until the
    next restart. The logger must stay enabled across a migration.
    """
    from alembic import command
    from alembic.config import Config

    usage_logger.disabled = False  # prove the migration does not RE-disable it
    db_url = f"sqlite:///{(tmp_path / 'migrate.sqlite').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    assert usage_logger.disabled is False


def test_missing_count_fields_does_not_crash():
    class _EmptyMeta:
        pass

    class _RespEmptyMeta:
        usage_metadata = _EmptyMeta()

    with _capture() as cap:
        log_usage("axis-label", "m", _RespEmptyMeta())  # must not raise
    messages = _usage_messages(cap)
    assert len(messages) == 1
    assert "prompt=None" in messages[0]  # absent fields render as None placeholders
