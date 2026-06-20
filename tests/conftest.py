from __future__ import annotations

from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config


@pytest.fixture(autouse=True)
def _egress_consent_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model data-egress consent as GIVEN by default for the suite.

    Generation now runs through the egress gate at the DI seam (inc 58), so an injected fake provider
    is blocked when egress is disabled — exactly the hole we closed. Happy-path tests that inject a
    fake to exercise generation therefore need consent on; setting it here keeps them green without
    per-test edits. Tests asserting egress-OFF behavior withdraw consent explicitly with
    ``monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS")`` (which composes: this runs first in setup). The
    help assistant's INDEPENDENT toggle is likewise on by default; the gate-independence test withdraws the
    library egress flag while keeping the help flag, and the help-off test withdraws the help flag.
    """
    monkeypatch.setenv("CALLOSUM_ALLOW_DATA_EGRESS", "1")
    monkeypatch.setenv("CALLOSUM_HELP_ASSISTANT_ENABLED", "1")


@pytest.fixture()
def temp_db_url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{(tmp_path / 'callosum-api.sqlite').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
    return db_url
