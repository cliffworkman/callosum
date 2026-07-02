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


def _ensure_sqlite_parent_dir(db_url: str) -> None:
    """Create the parent directory of a SQLite file URL if it's missing.

    A no-config launch defaults to a *relative* SQLite path; if that path's parent directory
    doesn't exist, SQLite raises "unable to open database file" on the very first connect —
    every DB-backed request then 500s while the server otherwise looks healthy (``/`` still
    serves the static shell). Creating the parent lets the startup migration create + stamp a
    fresh database, so a bare ``uvicorn ...`` boots a working (empty) library instead of a
    console full of tracebacks. No-op for in-memory or non-SQLite URLs. Best-effort: a mkdir
    failure (e.g. permissions) is left for the connect below to report actionably.

    Relative paths resolve against the current working directory — the same base SQLAlchemy
    uses for a ``sqlite:///relative/path`` URL — so the directory created matches the file
    that will be opened.
    """
    prefix = "sqlite:///"
    if not db_url.startswith(prefix):
        return  # non-sqlite, or the in-memory 'sqlite://' form (no file to back)
    path_part = db_url[len(prefix) :].split("?", 1)[0]  # drop any ?query params
    if not path_part or path_part.lstrip("/").startswith(":memory:") or "mode=memory" in db_url:
        return
    parent = Path(path_part).parent
    if parent.exists():
        return
    try:
        parent.mkdir(parents=True, exist_ok=True)
        _loud(logging.INFO, "created missing database directory: %s", parent)
    except OSError as exc:
        _loud(logging.WARNING, "could not create database directory %s (%s)", parent, exc)


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
        _ensure_sqlite_parent_dir(db_url)  # a no-config launch → create the dir so a fresh DB can be made
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
        # One actionable line, not a traceback flood: name the DB and the fix. The most common
        # cause is a missing/unwritable path, so point at CALLOSUM_DB_URL. The full trace stays
        # at DEBUG for deep debugging (hidden at the default INFO level).
        detail = str(exc).splitlines()[0] if str(exc).strip() else exc.__class__.__name__
        _loud(
            logging.ERROR,
            "startup DB auto-migration FAILED: db=%s (%s). "
            "If the path is missing or unwritable, set CALLOSUM_DB_URL to a valid SQLite path "
            "(see CLAUDE.md); the server keeps serving but DB operations will fail until resolved.",
            db_url,
            detail,
        )
        logger.debug("startup DB auto-migration traceback", exc_info=True)


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
