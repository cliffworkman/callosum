"""Startup machinery for the Callosum API: logging + Alembic auto-migration.

Kept separate from the app factory so the (loud, self-healing) migration story is easy to
review in isolation. `create_app`'s lifespan calls `_upgrade_database_to_head` before serving.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.backend.persistence.database import make_engine

PROJECT_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger("callosum")
# The user launches via `uvicorn`/`python -m uvicorn` and watches the console, but uvicorn
# does not configure arbitrary loggers — without a handler only WARNING+ would surface and
# the startup migration story (esp. the INFO "at head" line) would be invisible. Attach a
# stdout handler once; keep propagate=True so pytest's caplog still captures these records.
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s:callosum: %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)
# Don't propagate to root: Alembic's env.py reconfigures the root logger (for its own
# console output), and we already have our own stdout handler — propagating would double-log.
logger.propagate = False


def _loud(level: int, msg: str, *args, **kwargs) -> None:
    """Emit a migration log line that survives Alembic's logging reconfiguration.

    Alembic's `env.py` runs `logging.config.fileConfig(disable_existing_loggers=True)` on
    every migrate, which would otherwise silence this logger mid-startup (so the crucial
    post-upgrade "auto-migrated X -> Y" line would never appear). Re-enable before logging.
    """
    logger.disabled = False
    logger.log(level, msg, *args, **kwargs)


def _alembic_config(db_url: str | None = None) -> Config:
    """Alembic Config with an ABSOLUTE script_location (cwd-independent).

    The DB URL is only needed for running migrations; reading the head revision does not
    require it.
    """
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    if db_url is not None:
        cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _head_revision() -> str | None:
    """The latest Alembic revision id on disk (the migration target), or None."""
    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


def _current_revision(db_url: str) -> str | None:
    """The revision the given database is currently stamped at, or None."""
    engine = make_engine(db_url)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def _upgrade_database_to_head(db_url: str) -> None:
    """Bring the configured database up to the latest Alembic revision — LOUDLY.

    Run at startup so the app self-heals any DB it opens — this is what prevents the
    "table annotations has no column named ..." class of error on a database created
    before a migration landed. It announces itself clearly (which DB, from which revision,
    to which) because silently mutating the user's schema on startup is exactly the kind of
    state change that must be surfaced. Idempotent (no-op + a quiet confirmation when already
    at head). Failures are logged at ERROR but are non-fatal: the server still serves reads
    and /health reports the true state.
    """
    try:
        cfg = _alembic_config(db_url)
        head = _head_revision()
        current = _current_revision(db_url)
        _loud(logging.INFO, "startup migration check: db=%s current=%s head=%s", db_url, current, head)
        if current == head:
            _loud(logging.INFO, "database already at head (%s); no migration needed", head)
            return
        command.upgrade(cfg, "head")
        _loud(logging.WARNING, "database auto-migrated (startup safety net): db=%s  %s -> %s", db_url, current, head)
    except Exception as exc:  # defensive: a migration hiccup must never crash startup
        _loud(
            logging.ERROR,
            "startup DB auto-migration FAILED: db=%s (%s); server continues, writes may fail until migrated",
            db_url,
            exc,
            exc_info=True,
        )


def _parse_dotenv(text: str) -> dict[str, str]:
    """Parse a minimal .env: `KEY=VALUE` per line; blank lines + `#` comments ignored; the first `=`
    splits (values may contain `=`); surrounding single/double quotes are stripped."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def load_local_env(
    env_path: Path | None = None, *, environ: dict | None = None, skip_under_pytest: bool = True
) -> None:
    """Populate the environment from a gitignored local ``.env`` for any key NOT already set.

    Local-first convenience so secrets (e.g. ``GOOGLE_API_KEY``) live in ``.env`` rather than being
    exported by hand. An explicitly-set shell variable always wins (only unset keys are filled) — which
    is what lets you swap a BYO test key by exporting it. **Skipped under pytest** so the suite stays
    hermetic and never picks up real keys from a developer's ``.env``. No new dependency (stdlib parser).
    """
    if skip_under_pytest and "pytest" in sys.modules:
        return
    path = env_path or (PROJECT_ROOT / ".env")
    if not path.is_file():
        return
    env = os.environ if environ is None else environ
    for key, val in _parse_dotenv(path.read_text(encoding="utf-8")).items():
        if key not in env:
            env[key] = val
