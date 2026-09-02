from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config


@pytest.fixture(autouse=True)
def _egress_consent_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    # BYOK (inc 146): isolate the local app-settings file per test so the suite never reads/writes the real
    # ~/.callosum/app-settings.json (and one test's writes can't leak into another).
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "app-settings.json"))
    # inc 152: secrets (provider keys, the sealed sync keyring) are read from the OS keychain BEFORE the file,
    # so on a dev machine with a real backend (e.g. Windows Credential Vault) the suite would otherwise read the
    # maintainer's REAL Gemini key / sync passphrase — making hermetic settings/sync/auth tests fail (a 409
    # "already set up" from a real sync keyring, a leaked stored key). Force `keyring` off so `_get_secret`/
    # `_set_secret` fall back to the isolated temp file above — same hermeticity spirit as `skip_under_pytest`.
    monkeypatch.setattr("app.backend.app_settings._keyring", lambda: None)
    # inc 160: isolate the library folder (the always-watched default + OA-acquire managed dir) to a per-test
    # temp dir, so the suite never scans/writes the real project `library/`. Non-existent by default → the
    # rescan skips it; a test that needs it real mkdirs + overrides this env var itself.
    monkeypatch.setenv("CALLOSUM_LIBRARY_DIR", str(tmp_path / "_library"))


@pytest.fixture(scope="session")
def _migrated_template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the real Alembic chain ONCE per session; every test copies the resulting file.

    Measured on this project: `command.upgrade(head)` costs ~2.29s (78 migrations) while copying the
    finished SQLite file costs ~0.04s -- a ~53x per-test saving across the ~1,139 tests that take
    ``temp_db_url``. The schema is byte-identical either way, because it IS the migrated database, just
    reused rather than rebuilt. Tests that specifically exercise migration behavior (tests/test_migrations.py)
    still drive Alembic directly and are unaffected by this fixture.

    Session-scoped and xdist-safe: pytest-xdist runs each worker in its own process with its own
    ``tmp_path_factory`` root, so each worker builds its own template once -- no cross-worker sharing,
    no lock, no shared mutable state.
    """
    template = tmp_path_factory.mktemp("callosum-db-template") / "template.sqlite"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{template.as_posix()}")
    command.upgrade(config, "head")
    return template


@pytest.fixture()
def temp_db_url(tmp_path: Path, _migrated_template_db: Path) -> str:
    db_path = tmp_path / "callosum-api.sqlite"
    shutil.copyfile(_migrated_template_db, db_path)
    return f"sqlite:///{db_path.as_posix()}"
